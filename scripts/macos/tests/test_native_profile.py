import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
BINARY = ROOT / "build/macos/Dependencies/D3D8Metal/native_profile_test"


@unittest.skipUnless(BINARY.exists(), "Build native_profile_test to exercise the recorder")
class NativeRecorderTests(unittest.TestCase):
    def test_nested_scopes_threads_and_shutdown(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.jsonl"
            subprocess.run([str(BINARY), str(path)], check=True)
            events = [json.loads(line) for line in path.read_text().splitlines()]
        frames = [e for e in events if e["kind"] == "frame"]
        self.assertEqual([(e["frame"], e["logic"]) for e in frames if e["thread"] == "main"], [(1,200),(2,201)])
        self.assertEqual(next(e for e in frames if e["thread"] == "renderer")["frame"], 1)
        outer = next(e for e in events if e.get("name") == "outer")
        child = next(e for e in events if e.get("name") == 'sleep "quoted"')
        self.assertGreater(child["wall_us"], 9000)
        self.assertGreater(child["wall_us"] - child["cpu_us"], 5000)
        self.assertAlmostEqual(outer["self_cpu_us"] + child["cpu_us"], outer["cpu_us"], delta=1)
        self.assertEqual(next(e for e in events if e.get("name") == "draw_calls")["wall_us"], 5)
        self.assertEqual(sum(e["kind"] == "gpu" for e in events), 1)
        self.assertEqual(events[-1], dict(kind="footer", dropped_events=0, write_error=False))

    def test_capture_window_keeps_late_gpu_completions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.jsonl"
            env = dict(os.environ, GENERALS_PROFILE_START_LOGIC="200", GENERALS_PROFILE_END_LOGIC="201")
            subprocess.run([str(BINARY), str(path)], check=True, env=env)
            events = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual(len([e for e in events if e["kind"] == "frame"]), 2)
        self.assertTrue(all(e["logic"] == 200 for e in events if e["kind"] in ("frame", "gpu", "scope")))
        self.assertEqual(sum(e["kind"] == "gpu" for e in events), 1)

    def test_capture_window_discards_outside_gpu_results(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.jsonl"
            env = dict(os.environ, GENERALS_PROFILE_START_LOGIC="201", GENERALS_PROFILE_END_LOGIC="202")
            subprocess.run([str(BINARY), str(path)], check=True, env=env)
            events = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual(len([e for e in events if e["kind"] == "frame"]), 1)
        self.assertFalse(any(e["kind"] in ("gpu", "scope") for e in events))


if __name__ == "__main__":
    unittest.main()
