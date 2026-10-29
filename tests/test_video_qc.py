import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
import video_qc

class VideoQCTests(unittest.TestCase):
    def test_reports_metadata_audio_and_black_segments(self):
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / "test.mp4"
            video.write_bytes(b"video")
            stat = video.stat()
            probe = {"streams": [{"codec_type": "video", "width": 1920, "height": 1080, "r_frame_rate": "30/1"}, {"codec_type": "audio"}], "format": {"duration": "12.5"}}
            completed = Mock(stderr="black_start:1.0 black_end:2.0 black_duration:1.0", stdout="", returncode=0)
            with patch.object(video_qc.shutil, "which", return_value="/usr/bin/tool"), patch.object(video_qc, "_run", return_value=json.dumps(probe)), patch.object(video_qc.subprocess, "run", return_value=completed):
                report = video_qc.inspect_video(str(video), use_scene_detect=False)
        self.assertEqual(report["duration_seconds"], 12.5)
        self.assertTrue(report["has_audio"])
        self.assertEqual(len(report["black_segments_over_0_5s"]), 1)
        self.assertEqual(report["file_size_bytes"], stat.st_size)
        self.assertEqual(report["file_mtime_ns"], stat.st_mtime_ns)
        self.assertEqual(report["file"], str(video.resolve()))

    def test_failed_black_scan_is_reported_as_a_warning(self):
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / "test.mp4"
            video.write_bytes(b"video")
            probe = {
                "streams": [
                    {"codec_type": "video", "width": 1920, "height": 1080, "r_frame_rate": "30/1"},
                    {"codec_type": "audio"},
                ],
                "format": {"duration": "600"},
            }
            failed_scan = Mock(stderr="decoder failed", stdout="", returncode=1)
            with patch.object(video_qc.shutil, "which", return_value="/usr/bin/tool"), patch.object(
                video_qc, "_run", return_value=json.dumps(probe)
            ), patch.object(video_qc.subprocess, "run", return_value=failed_scan):
                report = video_qc.inspect_video(str(video), use_scene_detect=False)
        self.assertTrue(report["black_detection"].startswith("error:"))
        self.assertTrue(any("Black-frame detection failed" in item for item in report["warnings"]))

    def test_scene_analysis_exception_is_reported_as_a_warning(self):
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / "test.mp4"
            video.write_bytes(b"video")
            probe = {
                "streams": [
                    {"codec_type": "video", "width": 1920, "height": 1080, "r_frame_rate": "30/1"},
                    {"codec_type": "audio"},
                ],
                "format": {"duration": "600"},
            }
            successful_scan = Mock(stderr="", stdout="", returncode=0)
            with patch.object(video_qc.shutil, "which", return_value="/usr/bin/tool"), patch.object(
                video_qc, "_run", return_value=json.dumps(probe)
            ), patch.object(video_qc.subprocess, "run", return_value=successful_scan), patch(
                "scenedetect.open_video", side_effect=RuntimeError("decode failure")
            ), patch("scenedetect.SceneManager", side_effect=RuntimeError("scene failure")):
                report = video_qc.inspect_video(str(video), use_scene_detect=True)
        self.assertTrue(report["scene_detection"].startswith("error:"))
        self.assertTrue(any("Scene-change analysis failed" in item for item in report["warnings"]))

    def test_missing_video_raises(self):
        with self.assertRaises(FileNotFoundError):
            video_qc.inspect_video("missing-test-video.mp4")

if __name__ == "__main__":
    unittest.main()
