from __future__ import annotations

import argparse
import ctypes
import getpass
import html
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import timedelta
from html.parser import HTMLParser
from pathlib import Path
from contextlib import suppress

from . import __version__


GITHUB_RAW_VERSION_URL = "https://raw.githubusercontent.com/fkelav/Winfetch/main/src/winfetch/__init__.py"
GITHUB_ZIP_URL = "https://github.com/fkelav/Winfetch/archive/refs/heads/main.zip"
ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
STYLE_COLOR_RE = re.compile(r"(?:^|;)\s*color\s*:\s*([^;]+)", re.IGNORECASE)
VERSION_RE = re.compile(r"^\s*__version__\s*=\s*[\"']([^\"']+)[\"']\s*$", re.MULTILINE)

RESET = "\x1b[0m"
BOLD = "\x1b[1m"
CYAN = "\x1b[38;2;86;214;214m"
GREEN = "\x1b[38;2;87;242;135m"
YELLOW = "\x1b[38;2;249;226;175m"
PINK = "\x1b[38;2;245;194;231m"
BLUE = "\x1b[38;2;137;180;250m"
RED = "\x1b[38;2;243;139;168m"

PALETTE: tuple[tuple[int, int, int], ...] = (
    (40, 42, 54),
    (255, 85, 85),
    (80, 250, 123),
    (241, 250, 140),
    (98, 114, 164),
    (255, 121, 198),
    (139, 233, 253),
    (248, 248, 242),
    (68, 71, 90),
    (255, 110, 110),
    (105, 255, 148),
    (255, 255, 165),
    (125, 141, 191),
    (255, 146, 223),
    (164, 255, 255),
    (255, 255, 255),
)

COLOR_NAMES = {
    "black": 1,
    "red": 2,
    "green": 3,
    "yellow": 4,
    "blue": 5,
    "magenta": 6,
    "pink": 6,
    "cyan": 7,
    "white": 8,
    "gray": 9,
    "grey": 9,
    "light black": 9,
    "light red": 10,
    "light green": 11,
    "light yellow": 12,
    "light blue": 13,
    "light magenta": 14,
    "light pink": 14,
    "light cyan": 15,
    "light white": 16,
}


@dataclass
class Art:
    lines: list[str]
    warning: str | None = None


class ColoredHtmlParser(HTMLParser):
    def __init__(self, color: bool) -> None:
        super().__init__(convert_charrefs=True)
        self.color = color
        self.parts: list[str] = []
        self.color_stack: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "svg", "img"}:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag == "br":
            self.parts.append("\n")
            return
        if tag in {"div", "p"} and self.parts and not self.parts[-1].endswith("\n"):
            self.parts.append("\n")
        if tag in {"span", "font", "b", "strong"}:
            attrs_dict = {name.lower(): value or "" for name, value in attrs}
            sequence = ""
            if tag in {"b", "strong"}:
                sequence += BOLD
            style_match = STYLE_COLOR_RE.search(attrs_dict.get("style", ""))
            color_value = style_match.group(1).strip() if style_match else attrs_dict.get("color", "").strip()
            ansi = color_to_ansi(color_value) if color_value else ""
            sequence += ansi
            self.color_stack.append(sequence)
            if self.color and sequence:
                self.parts.append(sequence)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "svg", "img"} and self.skip_depth:
            self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if tag in {"span", "font", "b", "strong"} and self.color_stack:
            self.color_stack.pop()
            if self.color:
                self.parts.append(RESET)
                for sequence in self.color_stack:
                    if sequence:
                        self.parts.append(sequence)
        if tag in {"div", "p", "pre"} and self.parts and not self.parts[-1].endswith("\n"):
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(data)

    def get_text(self) -> str:
        text = "".join(self.parts)
        return text + (RESET if self.color and text and not text.endswith(RESET) else "")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Show system info beside colored ASCII art.")
    parser.add_argument("--ascii", dest="ascii_path", help="Path to a .ansi or .html ASCII art file and save it as the default.")
    parser.add_argument(
        "--color",
        "--color1",
        dest="info_color",
        nargs="+",
        metavar="COLOR",
        help='Set the info label color by palette number or name, like "black" or "light red".',
    )
    parser.add_argument(
        "--color2",
        dest="data_color",
        nargs="+",
        metavar="COLOR",
        help='Set the info value color by palette number or name, like "white" or "light cyan".',
    )
    parser.add_argument("--cfgs", action="store_true", help="Show the list of named configs and exit.")
    parser.add_argument(
        "--cfg",
        nargs="+",
        metavar="NAME",
        help="Use a named config, save one with: --cfg save NAME, or delete one with: --cfg delete NAME.",
    )
    parser.add_argument("--config", action="store_true", help="Print config file paths and exit.")
    parser.add_argument("--update", action="store_true", help="Check GitHub for a newer version and install it after confirmation.")
    parser.add_argument("--no-color", action="store_true", help="Disable all terminal colors.")
    parser.add_argument("--version", action="version", version=f"winfetch {__version__}")
    args = parser.parse_args(argv)

    enable_windows_ansi()
    color = not args.no_color

    config = load_config()
    active_config = dict(config)

    if args.config:
        print_config_info()
        return 0

    if args.update:
        return update_from_github()

    if args.cfgs:
        print_named_configs(config)
        return 0

    cfg_name = selected_cfg_name(args.cfg)
    if cfg_name is not None:
        named_config = get_named_config(config, cfg_name)
        if named_config is None:
            print(f"Config not found: {cfg_name}", file=sys.stderr)
            return 1
        active_config.update(named_config)

    cfg_delete_name = cfg_delete_target(args.cfg)
    if cfg_delete_name is not None:
        return delete_named_config(config, cfg_delete_name)

    selected_art_path = Path(args.ascii_path).expanduser() if args.ascii_path else None
    art_path = selected_art_path or configured_art_path(active_config)
    selected_info_color = parse_palette_color(args.info_color, "--color") if args.info_color is not None else None
    selected_data_color = parse_palette_color(args.data_color, "--color2") if args.data_color is not None else None
    info_color = selected_info_color if selected_info_color is not None else configured_info_color(active_config)
    data_color = selected_data_color if selected_data_color is not None else configured_data_color(active_config)

    cfg_save_name = cfg_save_target(args.cfg)
    if cfg_save_name is not None:
        save_named_config(config, cfg_save_name, art_path, info_color, data_color)
        print(f"Saved config: {cfg_save_name}")

    art = load_art(art_path, color=color)
    stats = collect_stats(color=color, info_color=info_color, data_color=data_color)

    if art.warning:
        print(colorize(f"warning: {art.warning}", RED, color), file=sys.stderr)
    if cfg_name is None and not art.warning and (
        selected_art_path is not None or selected_info_color is not None or selected_data_color is not None
    ):
        save_settings(ascii_path=selected_art_path, info_color=selected_info_color, data_color=selected_data_color)

    print(render(art.lines, stats, color=color))
    return 0


def update_from_github() -> int:
    """Offer to replace a normal-installer package with the current GitHub copy."""
    try:
        latest_version = github_version()
        comparison = compare_versions(__version__, latest_version)
    except OSError as exc:
        print(f"Could not check GitHub for updates: {exc}", file=sys.stderr)
        return 1

    print(f"Installed version: {__version__}")
    print(f"GitHub version:    {latest_version}")
    if comparison >= 0:
        print("You already have the latest version." if comparison == 0 else "Your installed version is newer than GitHub.")
        return 0

    try:
        answer = input(f"Update winfetch to {latest_version}? [y/N]: ").strip().lower()
    except EOFError:
        answer = ""
    if answer not in {"y", "yes"}:
        print("Update cancelled.")
        return 0

    try:
        update_installed_package()
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"Update failed: {exc}", file=sys.stderr)
        return 1
    print(f"Updated winfetch to {latest_version}.")
    return 0


def github_version() -> str:
    request = urllib.request.Request(GITHUB_RAW_VERSION_URL, headers={"User-Agent": "winfetch"})
    with urllib.request.urlopen(request, timeout=10) as response:
        source = response.read().decode("utf-8", errors="replace")
    match = VERSION_RE.search(source)
    if match is None:
        raise OSError("GitHub did not provide a valid winfetch version")
    return match.group(1)


def compare_versions(installed: str, latest: str) -> int:
    """Compare numeric dotted versions without adding a packaging dependency."""
    def normalized(value: str) -> tuple[int, ...]:
        if not re.fullmatch(r"\d+(?:\.\d+)*", value):
            raise OSError(f"Unsupported version format: {value}")
        return tuple(int(part) for part in value.split("."))

    left, right = normalized(installed), normalized(latest)
    width = max(len(left), len(right))
    return (left + (0,) * (width - len(left)) > right + (0,) * (width - len(right))) - (
        left + (0,) * (width - len(left)) < right + (0,) * (width - len(right))
    )


def update_installed_package() -> None:
    """Download main and atomically replace the package used by the Windows installer."""
    package_dir = Path(__file__).resolve().parent
    install_dir = package_dir.parent
    expected_install_dir = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Programs" / "winfetch"
    if install_dir != expected_install_dir or package_dir.name != "winfetch":
        raise OSError("--update is available only for the normal Windows installer; run the latest installer instead")

    temp_root = Path(tempfile.mkdtemp(prefix="winfetch-update-"))
    try:
        archive_path = temp_root / "winfetch-main.zip"
        request = urllib.request.Request(GITHUB_ZIP_URL, headers={"User-Agent": "winfetch"})
        with urllib.request.urlopen(request, timeout=20) as response:
            archive_path.write_bytes(response.read())
        extract_dir = temp_root / "repo"
        with zipfile.ZipFile(archive_path) as archive:
            safe_extract(archive, extract_dir)
        matches = list(extract_dir.glob("*/src/winfetch"))
        if len(matches) != 1:
            raise OSError("Downloaded update did not contain src/winfetch")

        staging_dir = install_dir / ".winfetch-update"
        backup_dir = install_dir / ".winfetch-previous"
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        shutil.copytree(matches[0], staging_dir)
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        package_dir.replace(backup_dir)
        try:
            staging_dir.replace(package_dir)
        except OSError:
            backup_dir.replace(package_dir)
            raise
        shutil.rmtree(backup_dir, ignore_errors=True)
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
    destination = destination.resolve()
    for member in archive.infolist():
        target = (destination / member.filename).resolve()
        if not target.is_relative_to(destination):
            raise ValueError(f"Unsafe path in downloaded archive: {member.filename}")
    archive.extractall(destination)


def app_dir() -> Path:
    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / "winfetch"
    return Path.home() / ".config" / "winfetch"


def config_path() -> Path:
    return app_dir() / "config.json"


def ascii_dir() -> Path:
    return app_dir() / "ascii"


def print_config_info() -> None:
    print(f"Config: {config_path()}")
    print(f"ASCII art folder: {ascii_dir()}")
    print('Example config: {"ascii": "C:\\\\path\\\\to\\\\logo.ansi"}')


def load_config() -> dict[str, object]:
    path = config_path()
    try:
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_config(config: dict[str, object]) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def save_settings(
    ascii_path: Path | None = None,
    info_color: int | None = None,
    data_color: int | None = None,
) -> None:
    config = load_config()
    if ascii_path is not None:
        try:
            config["ascii"] = str(ascii_path.resolve())
        except OSError:
            config["ascii"] = str(ascii_path)
    if info_color is not None:
        config["info_color"] = info_color
    if data_color is not None:
        config["data_color"] = data_color
    save_config(config)


def configs_dict(config: dict[str, object]) -> dict[str, object]:
    configs = config.get("configs")
    return configs if isinstance(configs, dict) else {}


def print_named_configs(config: dict[str, object]) -> None:
    names = sorted(name for name in configs_dict(config) if isinstance(name, str))
    if not names:
        print("No named configs saved.")
        return
    for name in names:
        print(name)


def selected_cfg_name(values: list[str] | None) -> str | None:
    if not values or values[0].lower() in {"delete", "save"}:
        return None
    if len(values) != 1:
        raise SystemExit("--cfg expects a single config name, --cfg save NAME, or --cfg delete NAME")
    name = values[0].strip()
    if not name:
        raise SystemExit("--cfg expects a non-empty config name")
    return name


def cfg_save_target(values: list[str] | None) -> str | None:
    if not values or values[0].lower() != "save":
        return None
    if len(values) != 2:
        raise SystemExit("--cfg save expects a config name")
    return values[1].strip()


def cfg_delete_target(values: list[str] | None) -> str | None:
    if not values or values[0].lower() != "delete":
        return None
    if len(values) != 2:
        raise SystemExit("--cfg delete expects a config name")
    name = values[1].strip()
    if not name:
        raise SystemExit("--cfg delete expects a non-empty config name")
    return name


def get_named_config(config: dict[str, object], name: str) -> dict[str, object] | None:
    value = configs_dict(config).get(name)
    return value if isinstance(value, dict) else None


def save_named_config(
    config: dict[str, object],
    name: str,
    ascii_path: Path | None,
    info_color: int | None,
    data_color: int | None,
) -> None:
    name = name.strip()
    if not name:
        raise SystemExit("--cfg save expects a non-empty config name")

    named: dict[str, object] = {}
    if ascii_path is not None:
        try:
            named["ascii"] = str(ascii_path.resolve())
        except OSError:
            named["ascii"] = str(ascii_path)
    if info_color is not None:
        named["info_color"] = info_color
    if data_color is not None:
        named["data_color"] = data_color

    configs = dict(configs_dict(config))
    configs[name] = named
    config["configs"] = configs
    save_config(config)


def delete_named_config(config: dict[str, object], name: str) -> int:
    configs = dict(configs_dict(config))
    if name not in configs:
        print(f"Config not found: {name}", file=sys.stderr)
        return 1
    del configs[name]
    config["configs"] = configs
    save_config(config)
    print(f"Deleted config: {name}")
    return 0


def configured_art_path(config: dict[str, object]) -> Path | None:
    value = config.get("ascii")
    if isinstance(value, str) and value.strip():
        candidate = Path(value).expanduser()
        if not candidate.is_absolute():
            candidate = ascii_dir() / candidate
        return candidate
    return None


def configured_info_color(config: dict[str, object]) -> int | None:
    value = config.get("info_color")
    if isinstance(value, int) and 1 <= value <= len(PALETTE):
        return value
    return None


def configured_data_color(config: dict[str, object]) -> int | None:
    value = config.get("data_color")
    if isinstance(value, int) and 1 <= value <= len(PALETTE):
        return value
    return None


def parse_palette_color(values: list[str], option_name: str) -> int:
    raw_value = " ".join(values).strip().lower().replace("-", " ").replace("_", " ")
    raw_value = " ".join(raw_value.split())
    if raw_value.isdigit():
        index = int(raw_value)
        if 1 <= index <= len(PALETTE):
            return index
    if raw_value in COLOR_NAMES:
        return COLOR_NAMES[raw_value]
    raise SystemExit(
        f"{option_name} expects 1-{len(PALETTE)} or one of: {', '.join(sorted(COLOR_NAMES))}"
    )


def load_art(path: Path | None, color: bool) -> Art:
    if path is None:
        return Art(default_art(color))
    try:
        resolved = path.resolve()
    except OSError:
        return Art(default_art(color), f"Could not read art path: {path}")
    if not resolved.exists() or not resolved.is_file():
        return Art(default_art(color), f"Art file not found: {resolved}")

    suffix = resolved.suffix.lower()
    try:
        if suffix == ".ansi":
            text = resolved.read_text(encoding="utf-8", errors="replace")
            if not color:
                text = strip_ansi(text)
            return Art(clean_loaded_art(split_lines(text)))
        if suffix in {".html", ".htm"}:
            source = resolved.read_text(encoding="utf-8", errors="replace")
            parser = ColoredHtmlParser(color=color)
            parser.feed(source)
            parser.close()
            return Art(clean_loaded_art(split_lines(html.unescape(parser.get_text()))))
        return Art(default_art(color), f"Unsupported art format: {resolved.suffix}. Use .ansi or .html.")
    except OSError as exc:
        return Art(default_art(color), f"Could not load art file: {exc}")


def default_art(color: bool) -> list[str]:
    lines = [
        " __        ___       _       ",
        " \\ \\      / (_)_ __ | |      ",
        "  \\ \\ /\\ / /| | '_ \\| |      ",
        "   \\ V  V / | | | | |_|      ",
        "    \\_/\\_/  |_|_| |_(_)      ",
        "                             ",
        "          winfetch           ",
    ]
    colors = [CYAN, BLUE, GREEN, YELLOW, PINK, CYAN, GREEN]
    if not color:
        return lines
    return [f"{colors[index]}{line}{RESET}" for index, line in enumerate(lines)]


def collect_stats(color: bool, info_color: int | None = None, data_color: int | None = None) -> list[str]:
    username = getpass.getuser()
    hostname = socket.gethostname()
    label_sequence = palette_foreground(info_color) + BOLD if info_color is not None else CYAN + BOLD
    data_sequence = palette_foreground(data_color) if data_color is not None else ""
    label = lambda text: colorize(f"{text:<10}", label_sequence, color)
    value = lambda text: colorize(text, data_sequence, color) if data_sequence else text
    values = {
        "User": f"{username}@{hostname}",
        "OS": os_name(),
        "Kernel": platform.release(),
        "CPU": cpu_name(),
        "GPU": gpu_name(),
        "Memory": memory_info(),
        "Disk": disk_info(),
        "Shell": shell_name(),
        "Uptime": uptime(),
    }
    stats = [f"{label(key)} {value(raw_value)}" for key, raw_value in values.items() if raw_value]
    if color:
        stats.extend(["", *color_blocks()])
    return stats


def os_name() -> str:
    edition = platform.platform(terse=True)
    return edition or f"{platform.system()} {platform.release()}".strip()


def cpu_name() -> str:
    if platform.system().lower() == "windows":
        registry_name = windows_cpu_name_from_registry()
        if registry_name:
            return registry_name
        cim_name = run_command(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name)",
            ]
        )
        if cim_name:
            return cim_name.splitlines()[0].strip()
        name = run_command(["wmic", "cpu", "get", "Name", "/value"])
        parsed = parse_wmic_value(name, "Name")
        if parsed:
            return parsed
    processor = platform.processor()
    return processor or "Unknown CPU"


def windows_cpu_name_from_registry() -> str:
    with suppress(ImportError, OSError):
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
            value, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            if isinstance(value, str):
                return value.strip()
    return ""


def gpu_name() -> str:
    if platform.system().lower() != "windows":
        return ""
    output = run_command(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name",
        ]
    )
    names = [line.strip() for line in output.splitlines() if line.strip()]
    if not names:
        output = run_command(["wmic", "path", "win32_VideoController", "get", "Name", "/value"])
        names = [line.split("=", 1)[1].strip() for line in output.splitlines() if line.startswith("Name=")]
    return ", ".join(name for name in names if name)[:120]


def memory_info() -> str:
    if platform.system().lower() == "windows":
        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            total = status.ullTotalPhys
            available = status.ullAvailPhys
            return f"{format_bytes(total - available)} / {format_bytes(total)}"
    return "Unavailable"


def disk_info() -> str:
    root = Path(os.environ.get("SystemDrive", Path.home().anchor or "C:")) / "\\"
    try:
        usage = shutil.disk_usage(str(root))
    except OSError:
        usage = shutil.disk_usage(str(Path.cwd().anchor or "."))
    return f"{format_bytes(usage.used)} / {format_bytes(usage.total)}"


def shell_name() -> str:
    parent = os.environ.get("ComSpec", "")
    terminal = os.environ.get("WT_SESSION")
    shell = Path(parent).name if parent else ""
    if terminal:
        return f"Windows Terminal ({shell or 'shell'})"
    return shell or os.environ.get("SHELL", "") or "Unknown"


def uptime() -> str:
    if platform.system().lower() == "windows":
        milliseconds = ctypes.windll.kernel32.GetTickCount64()
        return human_duration(int(milliseconds / 1000))
    try:
        with open("/proc/uptime", encoding="utf-8") as handle:
            seconds = int(float(handle.read().split()[0]))
        return human_duration(seconds)
    except (OSError, ValueError, IndexError):
        return "Unavailable"


def human_duration(seconds: int) -> str:
    delta = timedelta(seconds=max(0, seconds))
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes = remainder // 60
    pieces = []
    if days:
        pieces.append(f"{days}d")
    if hours:
        pieces.append(f"{hours}h")
    pieces.append(f"{minutes}m")
    return " ".join(pieces)


def run_command(command: list[str]) -> str:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
            creationflags=subprocess.CREATE_NO_WINDOW if platform.system().lower() == "windows" else 0,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return completed.stdout.strip()


def parse_wmic_value(output: str, key: str) -> str:
    prefix = f"{key}="
    for line in output.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return ""


def render(art_lines: list[str], stats: list[str], color: bool) -> str:
    columns = shutil.get_terminal_size(fallback=(100, 24)).columns
    art_width = max((visible_width(line) for line in art_lines), default=0)
    stats_width = max((visible_width(line) for line in stats), default=0)
    gap = 4

    if art_width + gap + stats_width > columns and columns < 100:
        plain_break = colorize("-" * min(columns, max(20, art_width)), BLUE, color)
        return "\n".join([*art_lines, plain_break, *stats])

    stat_offset = max(0, (len(art_lines) - len(stats)) // 2)
    rows = max(len(art_lines), len(stats) + stat_offset)
    output: list[str] = []
    for index in range(rows):
        left = art_lines[index] if index < len(art_lines) else ""
        stat_index = index - stat_offset
        right = stats[stat_index] if 0 <= stat_index < len(stats) else ""
        padding = " " * max(1, art_width - visible_width(left) + gap)
        output.append(f"{left}{padding}{right}".rstrip())
    return "\n".join(output)


def split_lines(text: str) -> list[str]:
    lines = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while lines and lines[-1] == "":
        lines.pop()
    return lines or [""]


def trim_blank_edges(lines: list[str]) -> list[str]:
    while lines and strip_ansi(lines[0]).strip() == "":
        lines.pop(0)
    while lines and strip_ansi(lines[-1]).strip() == "":
        lines.pop()
    return lines or [""]


def clean_loaded_art(lines: list[str]) -> list[str]:
    lines = trim_blank_edges(lines)
    while lines and strip_ansi(lines[0]).strip().lower() in {"ascii art", "ascii"}:
        lines.pop(0)
        lines = trim_blank_edges(lines)

    if len(lines) > 2 and is_plain_heading(lines[0]) and any(is_art_line(line) for line in lines[1:8]):
        lines.pop(0)
        lines = trim_blank_edges(lines)
    return lines or [""]


def is_plain_heading(line: str) -> bool:
    text = strip_ansi(line).strip()
    return bool(text) and visible_width(text) <= 32 and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._-]*", text) is not None


def is_art_line(line: str) -> bool:
    text = strip_ansi(line).strip()
    if visible_width(text) < 8:
        return False
    art_chars = sum(1 for char in text if not char.isalnum() and not char.isspace())
    return art_chars >= 3


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def visible_width(text: str) -> int:
    return len(strip_ansi(text))


def colorize(text: str, sequence: str, color: bool) -> str:
    return f"{sequence}{text}{RESET}" if color else text


def palette_foreground(index: int | None) -> str:
    if index is None:
        return CYAN
    r, g, b = PALETTE[index - 1]
    return f"\x1b[38;2;{r};{g};{b}m"


def palette_background(index: int) -> str:
    r, g, b = PALETTE[index]
    return f"\x1b[48;2;{r};{g};{b}m"


def color_blocks() -> list[str]:
    block = "   "
    rows = []
    for start in (0, 8):
        rows.append("".join(f"{palette_background(index)}{block}{RESET}" for index in range(start, start + 8)))
    return rows


def color_to_ansi(value: str) -> str:
    value = value.strip().strip("\"'")
    named = {
        "black": (0, 0, 0),
        "red": (255, 85, 85),
        "green": (80, 250, 123),
        "yellow": (241, 250, 140),
        "blue": (98, 114, 164),
        "magenta": (255, 121, 198),
        "purple": (189, 147, 249),
        "cyan": (139, 233, 253),
        "white": (248, 248, 242),
        "orange": (255, 184, 108),
    }
    if value.lower() in named:
        r, g, b = named[value.lower()]
        return f"\x1b[38;2;{r};{g};{b}m"
    if re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        r = int(value[1:3], 16)
        g = int(value[3:5], 16)
        b = int(value[5:7], 16)
        return f"\x1b[38;2;{r};{g};{b}m"
    rgb_match = re.fullmatch(r"rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)", value)
    if rgb_match:
        r, g, b = [max(0, min(255, int(part))) for part in rgb_match.groups()]
        return f"\x1b[38;2;{r};{g};{b}m"
    return ""


def format_bytes(value: int) -> str:
    amount = float(value)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if amount < 1024 or unit == "TB":
            return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024
    return f"{amount:.1f} TB"


def enable_windows_ansi() -> None:
    if platform.system().lower() != "windows":
        return
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]
