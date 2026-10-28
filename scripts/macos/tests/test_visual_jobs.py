import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
BINARY = ROOT / "build/macos/Core/Libraries/visual_jobs_test"


@unittest.skipUnless(BINARY.exists(), "Build visual_jobs_test to exercise parallel visual work")
class VisualJobTests(unittest.TestCase):
    def test_job_lifetimes_sort_order_and_worker_trace(self):
        for workers in (0, 1, 2, 4):
            with self.subTest(workers=workers), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "profile.jsonl"
                result = subprocess.run([str(BINARY), str(path)], check=True, capture_output=True, text=True,
                                        env=dict(os.environ, GENERALS_VISUAL_WORKERS=str(workers)), timeout=30)
                self.assertIn("45 sort cases passed", result.stdout)
                events = [json.loads(line) for line in path.read_text().splitlines()]
                self.assertEqual(events[-1], dict(kind="footer", dropped_events=0, write_error=False))
                scopes = [e for e in events if e["kind"] == "scope" and e["thread"].startswith("visual.")]
                self.assertEqual(bool(scopes), bool(workers))
                self.assertTrue(all(e["frame"] == 1 and e["logic"] == 200 for e in scopes))


if __name__ == "__main__":
    unittest.main()
