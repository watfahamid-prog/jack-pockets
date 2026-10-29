import json
import tempfile
import unittest
from pathlib import Path

from harness2.record_run import render_memory, summarize, update_ledger


def create_valid_evidence(root: Path, warnings=None) -> tuple[Path, Path, str]:
    run_dir = root / "run"
    run_dir.mkdir()
    mp4 = root / "out" / "test.mp4"
    mp4.parent.mkdir()
    mp4.write_bytes(b"verified test mp4 bytes")
    stat = mp4.stat()
    (run_dir / "manifest.json").write_text("{}", encoding="utf-8")
    report = {
        "file": str(mp4.resolve()),
        "file_size_bytes": stat.st_size,
        "file_mtime_ns": stat.st_mtime_ns,
        "duration_seconds": 600,
        "width": 1920,
        "height": 1080,
        "fps": 30,
        "has_audio": True,
        "warnings": warnings or [],
    }
    (run_dir / "video-qc.json").write_text(json.dumps(report), encoding="utf-8")
    log = f"FINAL QC PASSED: {mp4.resolve()} | 600s | 1920x1080 | 30fps | audio=yes"
    return mp4, run_dir / "manifest.json", log


class Harness2RunFeedbackTests(unittest.TestCase):
    def test_detects_quality_gate_failure(self):
        text = chr(10).join(["QUALITY GATE FAILED:", "footage gate: only 2 distinct real video clips selected; need at least 6", "static-image gate: photos fill 20% of shots; maximum is 15%"]) + chr(10)
        result = summarize(text, None)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(result["observations"]), 2)

    def test_log_line_alone_does_not_verify_render(self):
        result = summarize("FINAL QC PASSED: out/test.mp4", None)
        self.assertEqual(result["status"], "incomplete")
        self.assertTrue(result["render_claimed_by_log"])
        self.assertFalse(result["render_verified_by_log"])
        self.assertTrue(any("not present" in item for item in result["observations"]))

    def test_verifies_artifact_against_current_qc_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, manifest_path, log = create_valid_evidence(Path(tmp))
            result = summarize(log, manifest_path)
        self.assertEqual(result["status"], "passed")
        self.assertTrue(result["render_verified_by_log"])
        self.assertTrue(result["render_verification"]["checks"]["qc_report_matches_current_file_size"])

    def test_stale_report_does_not_verify_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, manifest_path, log = create_valid_evidence(Path(tmp))
            report_path = manifest_path.parent / "video-qc.json"
            report = json.loads(report_path.read_text())
            report["file_size_bytes"] += 1
            report_path.write_text(json.dumps(report), encoding="utf-8")
            result = summarize(log, manifest_path)
        self.assertEqual(result["status"], "incomplete")
        self.assertFalse(result["render_verified_by_log"])
        self.assertTrue(any("stale" in item for item in result["observations"]))

    def test_qc_warnings_are_retained_without_being_called_a_clean_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, manifest_path, log = create_valid_evidence(Path(tmp), ["PySceneDetect is not installed; scene-change analysis was skipped"])
            result = summarize(log, manifest_path)
        self.assertEqual(result["status"], "passed_with_warnings")
        self.assertEqual(len(result["video_qc_warnings"]), 1)
        self.assertTrue(any("video QC warning" in item for item in result["observations"]))

    def test_bad_technical_properties_prevent_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, manifest_path, log = create_valid_evidence(Path(tmp))
            report_path = manifest_path.parent / "video-qc.json"
            report = json.loads(report_path.read_text())
            report["has_audio"] = False
            report_path.write_text(json.dumps(report), encoding="utf-8")
            result = summarize(log, manifest_path)
        self.assertEqual(result["status"], "incomplete")
        self.assertFalse(result["render_verified_by_log"])
        self.assertTrue(any("audio_stream_present" in item for item in result["observations"]))

    def test_ledger_persists_runs_and_surfaces_repeated_observations(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.json"
            update_ledger(path, {"run_id": "1", "observations": ["no relevant moving video"]})
            ledger = update_ledger(path, {"run_id": "2", "observations": ["no relevant moving video"]})
            self.assertEqual(len(ledger["runs"]), 2)
            self.assertEqual(ledger["runs"][-1]["recurring_observations"]["no relevant moving video"], 2)
            self.assertIn("Observed 2 times", render_memory(ledger))


if __name__ == "__main__":
    unittest.main()
