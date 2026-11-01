#!/usr/bin/env python3
"""Safely commit and push only explicitly selected changes from a clean task baseline.

Run after a successful check, with only files changed in the current task listed:
  python tools/github_task_sync.py --branch-slug fix-example --check "npm run typecheck" src/file.py

This helper refuses a dirty starting worktree, stages only named paths, never force-pushes,
and never merges into the default branch. Staged changes are reviewed before commit/push.
"""
from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(*args: str, check: bool = True) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, text=True,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if check and result.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed ({result.returncode}):\n{result.stdout}")
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch-slug", required=True, help="Short descriptive task slug")
    parser.add_argument("--check", required=True, help="Successful verification command to run")
    parser.add_argument("--message", help="Commit subject (defaults to task slug)")
    parser.add_argument("paths", nargs="+", help="Exact task file paths to review, stage and commit")
    args = parser.parse_args()

    slug = args.branch_slug.lower().strip().replace(" ", "-")
    if not slug or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for c in slug):
        parser.error("--branch-slug may contain only lowercase letters, digits, hyphens and underscores")

    status = git("status", "--porcelain", "--untracked-files=all")
    if status:
        raise RuntimeError("Refusing to sync: worktree is already dirty. Preserve and review existing changes first.\n" + status)
    for value in args.paths:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts or not (ROOT / path).exists():
            parser.error(f"path must exist inside repository and contain no '..': {value}")

    print(f"Running verification: {args.check}", flush=True)
    check_result = subprocess.run(args.check, cwd=ROOT, shell=True)
    if check_result.returncode:
        raise RuntimeError(f"Verification failed ({check_result.returncode}); no branch or commit created.")

    branch = f"codex/{slug}-{dt.datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
    if git("show-ref", "--verify", "--quiet", f"refs/heads/{branch}", check=False):
        raise RuntimeError(f"Branch already exists; refusing to reuse it: {branch}")
    git("switch", "-c", branch)
    git("add", "--", *args.paths)
    staged = git("diff", "--cached", "--name-only")
    if not staged:
        raise RuntimeError("No selected changes were staged; stopping without a commit.")
    print("Staged files:\n" + staged)
    print("Self-review of staged patch before commit:\n" + git("diff", "--cached", "--"))

    git("commit", "-m", args.message or slug.replace("-", " ").replace("_", " ").capitalize())
    # Ordinary push only. A rejection is a safety stop; there is no force-push fallback.
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
