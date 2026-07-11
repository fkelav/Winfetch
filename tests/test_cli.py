import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from winfetch import cli


class CliTests(unittest.TestCase):
    def test_config_option_prints_locations(self):
        with patch("winfetch.cli.config_path") as config_path, patch("winfetch.cli.ascii_dir") as ascii_dir:
            config_path.return_value = Path("config.json")
            ascii_dir.return_value = Path("ascii")
            with patch("sys.stdout", new_callable=StringIO) as stdout:
                self.assertEqual(cli.main(["--config"]), 0)
        output = stdout.getvalue()
        self.assertIn("Config: config.json", output)
        self.assertIn("ASCII art folder: ascii", output)

    def test_gpu_name_uses_cim_before_wmic(self):
        with patch("winfetch.cli.platform.system", return_value="Windows"), patch(
            "winfetch.cli.run_command", return_value="GPU One\nGPU Two\n"
        ) as run_command:
            self.assertEqual(cli.gpu_name(), "GPU One, GPU Two")
        self.assertEqual(run_command.call_count, 1)
        self.assertIn("Get-CimInstance", run_command.call_args.args[0][-1])

    def test_gpu_name_falls_back_to_wmic(self):
        with patch("winfetch.cli.platform.system", return_value="Windows"), patch(
            "winfetch.cli.run_command", side_effect=["", "Name=GPU One\n"]
        ) as run_command:
            self.assertEqual(cli.gpu_name(), "GPU One")
        self.assertEqual(run_command.call_count, 2)

    def test_named_config_does_not_overwrite_default_settings(self):
        config = {"configs": {"work": {"info_color": 2}}}
        with patch("winfetch.cli.load_config", return_value=config), patch(
            "winfetch.cli.load_art", return_value=cli.Art(["art"])
        ), patch("winfetch.cli.collect_stats", return_value=[]), patch(
            "winfetch.cli.save_settings"
        ) as save_settings, patch("sys.stdout", new_callable=StringIO):
            self.assertEqual(cli.main(["--cfg", "work", "--color", "red", "--no-color"]), 0)
        save_settings.assert_not_called()


if __name__ == "__main__":
    unittest.main()
