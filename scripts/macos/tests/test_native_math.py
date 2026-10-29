from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[3]
BINARY = ROOT / "build/macos/Core/Libraries/native_math_test"


@unittest.skipUnless(BINARY.exists(), "Build native_math_test first")
class NativeMathTests(unittest.TestCase):
    def test_replay_precision_and_subunit_integer_conversion(self):
        result = subprocess.run([str(BINARY)], check=True, capture_output=True,
                                text=True, timeout=30)
        self.assertIn("73737 native math compatibility checks passed", result.stdout)
