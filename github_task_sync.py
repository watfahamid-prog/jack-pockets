#!/usr/bin/env python3
"""Run verified, task-scoped Git sync from a clean worktree.

Only explicitly selected changed paths can be committed. The helper runs the
required check before creating a unique task branch, rejects unrelated edits,
requires explicit risk approval for deletions/sensitive paths, uses ordinary
pushes, and verifies the remote SHA.
"""
from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
import uuid
from pathlib import Path


def repository_root() -> Path:
    """Resolve the Git root, including when invoked from a clean worktree."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=Path(__file__).resolve().parent,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode:
        raise RuntimeError("helper must run inside a Git worktree: " + result.stderr.strip())
    return Path(result.stdout.strip()).resolve()


ROOT = repository_root()


def git(*args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    if check and result.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed ({result.returncode}):\n{result.stdout}")
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch-slug", required=True)
    parser.add_argument("--check", required=True, help="Required passing check command")
    parser.add_argument("--message", help="Commit subject")
    parser.add_argument("--approve-risky", action="store_true",
                        help="explicitly approve reviewed deletions and sensitive paths")
    parser.add_argument("paths", nargs="+", help="Exact paths changed by this task")
    args = parser.parse_args()

    slug = args.branch_slug.lower().strip().replace(" ", "-")
    if not slug or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for c in slug):
        parser.error("--branch-slug may contain only lowercase letters, digits, hyphens and underscores")

    paths: list[str] = []
    for value in args.paths:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts or not value or "\x00" in value:
            parser.error(f"path must be repository-relative and contain no '..': {value}")
        normalized = path.as_posix()
        if normalized in paths:
            parser.error(f"duplicate selected path: {value}")
        paths.append(normalized)

    base = git("status", "--porcelain", "--untracked-files=all")
    if base:
        raise RuntimeError("Refusing to sync: baseline worktree is dirty. Preserve/review first.\n" + base)

    print(f"Running verification: {args.check}", flush=True)
    check_result = subprocess.run(args.check, cwd=ROOT, shell=True)
    if check_result.returncode:
        raise RuntimeError(f"Verification failed ({check_result.returncode}); no branch or commit created.")

    status_lines = git("status", "--porcelain", "--untracked-files=all").splitlines()
    changed = {line[3:].replace("\\", "/") for line in status_lines if len(line) >= 4}
    selected = set(paths)
    unrelated = changed - selected
    if unrelated:
        raise RuntimeError("Refusing unrelated changed paths:\n" + "\n".join(sorted(unrelated)))
    missing_changes = selected - changed
    if missing_changes:
        raise RuntimeError("Selected paths are not changed by this task:\n" + "\n".join(sorted(missing_changes)))

    sensitive_names = {".env", ".github", "secrets", "credentials", "private", "certs", "keys"}
    risky = [p for p in paths if any(part.lower() in sensitive_names for part in Path(p).parts)]
    deleted = [p for p in paths if git("ls-files", "--error-unmatch", "--", p, check=False)
               and not (ROOT / p).exists()]
    if (risky or deleted) and not args.approve_risky:
        raise RuntimeError("Explicit review required for sensitive paths/deletions; review diff and rerun "
                           "with --approve-risky.\n" + "\n".join(risky + deleted))

    branch = f"codex/{slug}-{dt.datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
    if git("show-ref", "--verify", "--quiet", f"refs/heads/{branch}", check=False):
        raise RuntimeError(f"Branch already exists; refusing to reuse it: {branch}")
    git("switch", "-c", branch)
    git("add", "--", *paths)
    staged = git("diff", "--cached", "--name-only")
    staged_paths = {line.replace("\\", "/") for line in staged.splitlines()}
    if not staged or staged_paths != selected:
        raise RuntimeError("Refusing to commit: staged paths differ from explicit selection.\n"
                           f"staged={sorted(staged_paths)!r} selected={sorted(selected)!r}")
    print("Staged files:\n" + staged)
    print("Self-review of staged patch before commit/push:\n" + git("diff", "--cached", "--"))

    git("commit", "-m", args.message or slug.replace("-", " ").replace("_", " ").capitalize())
    git("push", "--set-upstream", "origin", branch)
    commit = git("rev-parse", "HEAD")
    remote = git("ls-remote", "--heads", "origin", f"refs/heads/{branch}")
    if not remote or remote.split()[0] != commit:
        raise RuntimeError("Push verification failed: remote branch SHA does not match local commit.")
    print(f"Verified push: {branch} at {commit}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
