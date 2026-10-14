"""Exercise application-owned JavaScript adapters without third-party dependencies."""
from pathlib import Path
import shutil
import subprocess
import unittest


class RuntimeAdapterTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is required for JavaScript runtime tests')
    def test_error_handler_preserves_application_semantics(self):
        result = subprocess.run(
            [shutil.which('node'), str(Path(__file__).with_name('test_error_handler.cjs'))],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
