import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from replay_tatico.video import frame_at, open_video, probe


class VideoTests(unittest.TestCase):
    def test_invalid_video(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.mp4"
            path.write_text("<html>not a video</html>")
            with self.assertRaisesRegex(ValueError, "Vídeo inválido"):
                probe(path)

    def test_frame_numbers_and_original_fps(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.mp4"
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 25, (64, 48))
            self.assertTrue(writer.isOpened())
            try:
                for value in (20, 40, 100, 160):
                    writer.write(np.full((48, 64, 3), value, dtype=np.uint8))
            finally:
                writer.release()
            info = probe(path)
            self.assertEqual((info["width"], info["height"], info["frames"]), (64, 48, 4))
            self.assertAlmostEqual(info["fps"], 25)
            self.assertAlmostEqual(info["duration_seconds"], 0.16)
            self.assertTrue(info["constant_fps"])
            with open_video(path) as capture:
                self.assertAlmostEqual(frame_at(capture, 3).mean(), 160, delta=5)
                self.assertAlmostEqual(frame_at(capture, 1).mean(), 40, delta=5)
                with self.assertRaisesRegex(ValueError, "quadro"):
                    frame_at(capture, 4)
