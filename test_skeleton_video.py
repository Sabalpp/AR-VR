import struct
import tempfile
import unittest
from pathlib import Path

import numpy as np
import skeleton_video as video


class VideoTests(unittest.TestCase):
    def test_risk_thresholds_and_invalid_values(self):
        self.assertEqual([video._risk_level(x) for x in (0, 15, 35, 60)],
                         ['normal', 'low', 'med', 'high'])
        for value in (float('nan'), float('inf'), -1):
            with self.assertRaises(ValueError):
                video._risk_level(value)

    def test_invalid_options(self):
        for options in ({'fps': 0}, {'fps': float('nan')}, {'step': True},
                        {'step': 0}, {'width': 321}, {'height': 0}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                video.make_video('missing.skel', 'out.mp4', **options)

    def test_bad_recordings_preserve_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'input.skel'
            output = Path(directory) / 'out.mp4'
            output.write_bytes(b'existing video')
            for data in (b'', struct.pack('<II', 1, 84),
                         struct.pack('<II', 0, 84),
                         struct.pack('<II', 1, 84) + struct.pack('<f', 0)
                         + np.full((84, 3), np.nan, dtype='<f4').tobytes()):
                source.write_bytes(data)
                with self.assertRaises(ValueError):
                    video.make_video(source, output)
                self.assertEqual(output.read_bytes(), b'existing video')

    def test_truncated_video_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.mp4'
            path.write_bytes(b'bad')
            with self.assertRaises(RuntimeError):
                video._validate_video(path, 1, (320, 400))

    def test_coordinate_conversion(self):
        joints = np.zeros((84, 3))
        joints[1] = [1, 2, 3]
        self.assertEqual(video._pos(joints, 'hips'), (1, 3, 2))


if __name__ == '__main__':
    unittest.main()
