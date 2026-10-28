from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[3]
BINARY = ROOT / 'build/macos/Core/Libraries/cost_bucket_index_test'


@unittest.skipUnless(BINARY.exists(), 'Build cost_bucket_index_test first')
class CostBucketIndexTests(unittest.TestCase):
    def test_ordering_boundaries_removal_repricing_and_reset(self):
        result = subprocess.run([str(BINARY)], check=True, capture_output=True, text=True, timeout=30)
        self.assertIn('100000 stable queue operations passed', result.stdout)
