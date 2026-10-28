import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("benchmark", Path(__file__).parents[1] / "benchmark.py")
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)


def event(kind, frame, logic=200, wall=1000, name="main", thread="main", cpu=500, self_cpu=300):
    return dict(kind=kind, frame=frame, logic=logic, wall_us=wall, start_us=frame*10000,
                name=name, thread=thread, cpu_us=cpu, self_cpu_us=self_cpu, self_wall_us=wall)


class BenchmarkTests(unittest.TestCase):
    def test_compare_rejects_mixed_audio_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.json"
            runs = [dict(metadata=dict(diagnostic=False, mode="frames", units_per_side=500, repeat=0,
                                       label=label, audio_disabled=disabled))
                    for label, disabled in (("serial", True), ("serial-candidate", False))]
            path.write_text(json.dumps(runs))
            with self.assertRaisesRegex(ValueError, "audio"):
                bench.compare(path)

    def test_percentiles(self):
        self.assertIsNone(bench.percentile([], 99))
        self.assertEqual(bench.percentile([7], 95), 7)
        self.assertEqual(bench.percentile([20, 0, 10], 95), 19)

    def test_late_gpu_results_correlate_by_frame_not_arrival(self):
        events = [event("frame", 1, 100), event("frame", 2), event("frame", 3, 300),
                  event("gpu", 1, 100, 999999, "command: render", "GPU"),
                  event("gpu", 2, 200, 2000, "command: render", "GPU")]
        result, selected = bench.summarize(events, 180, 300)
        self.assertEqual(result["frames"], 1)
        self.assertEqual(result["gpu"][0]["per_frame_ms"]["mean"], 2)
        self.assertEqual(result["gpu_frame_coverage"], 1)
        self.assertTrue(all(e["frame"] == 2 for e in selected))

    def test_gpu_passes_not_added_to_command_totals(self):
        events = [event("frame", 1), event("frame", 2),
                  event("gpu", 1, wall=2000, name="command: render", thread="GPU"),
                  event("gpu", 1, wall=1500, name="pass: terrain", thread="GPU"),
                  event("gpu", 1, wall=1000, name="pass: models", thread="GPU")]
        result, _ = bench.summarize(events, 180, 300)
        rows = {r["name"]:r for r in result["gpu"]}
        self.assertEqual(rows["command: render"]["per_frame_ms"]["mean"], 1)
        self.assertEqual(rows["pass: terrain"]["per_frame_ms"]["mean"], 1.5)
        self.assertEqual(result["gpu_frame_coverage"], 0.5)
        self.assertEqual(result["gpu_pass_sampled_frames"], 1)

    def test_scope_cost_includes_zero_call_frames(self):
        events = [event("frame", 1), event("frame", 2),
                  event("scope", 1, name="logic", cpu=6000, self_cpu=2000),
                  event("scope", 1, name="logic", cpu=4000, self_cpu=1000)]
        result, _ = bench.summarize(events, 180, 300)
        scope = result["cpu_scopes"][0]
        self.assertEqual(scope["cpu_ms"]["mean"], 5)
        self.assertEqual(scope["self_cpu_ms"]["mean"], 1.5)

    def test_missing_or_duplicate_frames_fail(self):
        with self.assertRaises(ValueError): bench.summarize([], 180, 300)
        with self.assertRaises(ValueError): bench.summarize([event("frame", 1),event("frame", 1)], 180, 300)

    def test_dropped_records_are_visible(self):
        result, _ = bench.summarize([event("frame", 1), dict(kind="footer", dropped_events=3)], 180, 300)
        self.assertTrue(result["issues"])

    def test_incomplete_capture_is_not_silently_accepted(self):
        result, _ = bench.summarize([event("frame", 1)], 180, 300)
        self.assertTrue(any("shutdown footer" in issue for issue in result["issues"]))
        self.assertTrue(any("not fully captured" in issue for issue in result["issues"]))

    def test_complete_window_has_no_recording_warnings(self):
        result, _ = bench.summarize([event("frame", 1, 180), event("frame", 2, 299),
                                     dict(kind="footer", dropped_events=0, write_error=False)], 180, 300)
        self.assertEqual(result["issues"], [])


if __name__ == "__main__":
    unittest.main()
