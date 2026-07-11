import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "install_winfetch.py"
SPEC = importlib.util.spec_from_file_location("install_winfetch", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class InstallerTests(unittest.TestCase):
    def test_safe_extract_rejects_paths_outside_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path = root / "test.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("../outside.txt", "unsafe")
            with zipfile.ZipFile(archive_path) as archive:
                with self.assertRaises(ValueError):
                    installer.safe_extract(archive, root / "extract")
            self.assertFalse((root / "outside.txt").exists())

    def test_safe_extract_allows_normal_project_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive_path = root / "test.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("Winfetch-main/src/winfetch/cli.py", "pass\n")
            with zipfile.ZipFile(archive_path) as archive:
                installer.safe_extract(archive, root / "extract")
            self.assertEqual(
                (root / "extract" / "Winfetch-main" / "src" / "winfetch" / "cli.py").read_text(),
                "pass\n",
            )


if __name__ == "__main__":
    unittest.main()
