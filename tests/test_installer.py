import importlib.util
import tempfile
import unittest
import zipfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "install_winfetch.py"
SPEC = importlib.util.spec_from_file_location("install_winfetch", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class InstallerTests(unittest.TestCase):
    def test_user_can_cancel_after_seeing_all_versions(self):
        with patch.object(installer, "current_installed_version", return_value="0.1.0"), patch.object(
            installer, "bundled_version", return_value="0.2.0"
        ), patch.object(installer, "github_version", return_value="0.3.0"), patch("builtins.input", return_value="n"), patch.object(
            installer, "download_latest_source"
        ) as download, patch.object(
            installer, "install"
        ), patch.object(installer, "wait_before_exit"), patch("sys.stdout", new_callable=StringIO) as stdout:
            self.assertEqual(installer.main(), 0)
        download.assert_not_called()
        output = stdout.getvalue()
        self.assertIn("Installed version: 0.1.0", output)
        self.assertIn("Installer version: 0.2.0", output)
        self.assertIn("GitHub version:    0.3.0", output)
        self.assertIn("Installation cancelled.", output)

    def test_user_can_choose_installer_copy_when_github_is_newer(self):
        with tempfile.TemporaryDirectory() as temporary:
            bundled_source = Path(temporary) / "winfetch"
            bundled_source.mkdir()
            with patch.object(installer, "current_installed_version", return_value=None), patch.object(
                installer, "bundled_version", return_value="0.2.0"
            ), patch.object(installer, "github_version", return_value="0.3.0"), patch("builtins.input", return_value="i"), patch.object(
                installer, "bundled_source_dir", return_value=bundled_source
            ), patch.object(installer, "download_latest_source") as download, patch.object(installer, "install") as install, patch.object(
                installer, "wait_before_exit"
            ):
                self.assertEqual(installer.main(), 0)
            install.assert_called_once_with(bundled_source)
            download.assert_not_called()

    def test_user_can_choose_github_copy(self):
        source_dir = Path("C:/temp/winfetch")
        temp_root = Path("C:/temp")
        with patch.object(installer, "current_installed_version", return_value="0.1.0"), patch.object(
            installer, "bundled_version", return_value="0.2.0"
        ), patch.object(installer, "github_version", return_value="0.3.0"), patch("builtins.input", return_value="g"), patch.object(
            installer, "download_latest_source", return_value=(source_dir, temp_root)
        ), patch.object(installer, "install") as install, patch.object(installer.shutil, "rmtree"), patch.object(
            installer, "wait_before_exit"
        ):
            self.assertEqual(installer.main(), 0)
        install.assert_called_once_with(source_dir)

    def test_github_unavailable_offers_installer_copy_only(self):
        with patch("builtins.input", return_value="g"), patch("sys.stdout", new_callable=StringIO) as stdout:
            choice = installer.choose_install_source("0.1.0", "0.2.0", None)
        self.assertIsNone(choice)
        self.assertNotIn("[g]", stdout.getvalue())

    def test_bundled_source_dir_uses_frozen_bundle_layout(self):
        with patch.object(installer.sys, "_MEIPASS", "C:/bundle", create=True):
            self.assertEqual(installer.bundled_source_dir(), Path("C:/bundle/src/winfetch"))

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
