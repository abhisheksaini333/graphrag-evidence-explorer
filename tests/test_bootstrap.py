import importlib.util
from pathlib import Path
import tempfile
import unittest


class BootstrapTests(unittest.TestCase):
    def test_unknown_platform_and_corrupt_archive_are_rejected(self):
        spec = importlib.util.spec_from_file_location(
            "bootstrap", Path(__file__).parents[1] / "scripts/bootstrap_lancedb.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with self.assertRaises(ValueError):
            module.platform_record("unsupported")
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "bad.conda"
            source.write_bytes(b"not a verified artifact")
            with self.assertRaises(ValueError):
                module.repack(source, Path(root) / "wheel", "0" * 64)
