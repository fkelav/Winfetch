from __future__ import annotations

import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path
import re


APP_NAME = "winfetch"
GITHUB_ZIP_URL = "https://github.com/fkelav/Winfetch/archive/refs/heads/main.zip"
GITHUB_RAW_VERSION_URL = "https://raw.githubusercontent.com/fkelav/Winfetch/main/src/winfetch/__init__.py"
VERSION_RE = re.compile(r"^\s*__version__\s*=\s*[\"']([^\"']+)[\"']\s*$", re.MULTILINE)


def main() -> int:
    installed_version = current_installed_version()
    installer_version = bundled_version()
    if installer_version is None:
        print("Installer does not contain a valid winfetch version.", file=sys.stderr)
        wait_before_exit()
        return 1

    print(f"Installed version: {installed_version or 'not installed'}")
    print(f"Installer version: {installer_version}")
    try:
        latest_version = github_version()
    except OSError as exc:
        latest_version = None
        print(f"GitHub version:    unavailable ({exc})")
    else:
        print(f"GitHub version:    {latest_version}")

    source = choose_install_source(installed_version, installer_version, latest_version)
    if source is None:
        print("Installation cancelled.")
        wait_before_exit()
        return 0

    temp_root: Path | None = None
    try:
        if source == "github":
            source_dir, temp_root = download_latest_source()
        else:
            source_dir = bundled_source_dir()
            if not source_dir.is_dir():
                raise FileNotFoundError(f"Could not find bundled package source: {source_dir}")
        install(source_dir)
    except Exception as exc:
        print(f"Install failed: {exc}", file=sys.stderr)
        wait_before_exit()
        return 1
    finally:
        if temp_root is not None:
            shutil.rmtree(temp_root, ignore_errors=True)
    print()
    print("Done. Open a new terminal to try it out.")
    wait_before_exit()
    return 0


def current_installed_version() -> str | None:
    local_appdata = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    version_file = local_appdata / "Programs" / APP_NAME / APP_NAME / "__init__.py"
    try:
        source = version_file.read_text(encoding="utf-8")
    except OSError:
        return None
    match = VERSION_RE.search(source)
    return match.group(1) if match is not None else None


def bundled_version() -> str | None:
    try:
        source = (bundled_source_dir() / "__init__.py").read_text(encoding="utf-8")
    except OSError:
        return None
    match = VERSION_RE.search(source)
    return match.group(1) if match is not None else None


def github_version() -> str:
    request = urllib.request.Request(GITHUB_RAW_VERSION_URL, headers={"User-Agent": "winfetch-installer"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            source = response.read().decode("utf-8", errors="replace")
    except OSError:
        raise
    match = VERSION_RE.search(source)
    if match is None:
        raise OSError("GitHub did not provide a valid winfetch version")
    return match.group(1)


def compare_versions(installed: str, latest: str) -> int:
    def normalized(value: str) -> tuple[int, ...]:
        if not re.fullmatch(r"\d+(?:\.\d+)*", value):
            raise OSError(f"Unsupported version format: {value}")
        return tuple(int(part) for part in value.split("."))

    left, right = normalized(installed), normalized(latest)
    width = max(len(left), len(right))
    left += (0,) * (width - len(left))
    right += (0,) * (width - len(right))
    return (left > right) - (left < right)


def choose_install_source(
    installed_version: str | None, installer_version: str, github_latest_version: str | None
) -> str | None:
    """Let the user explicitly choose the GitHub or bundled installer copy."""
    if installed_version is not None:
        try:
            comparison = compare_versions(installed_version, github_latest_version or installer_version)
        except OSError:
            print("Could not compare the installed version with the available versions.")
        else:
            if comparison > 0:
                print("Your installed version is newer than the newest available version.")
            elif comparison == 0:
                print("Your installed version matches the newest available version.")

    print("\nChoose the version to install:")
    if github_latest_version is not None:
        print(f"  [g] GitHub version {github_latest_version}")
    print(f"  [i] This installer version {installer_version}")
    print("  [n] Cancel")
    try:
        answer = input("Choice: ").strip().lower()
    except EOFError:
        return None
    if answer in {"i", "installer"}:
        return "installer"
    if github_latest_version is not None and answer in {"g", "github"}:
        return "github"
    return None


def download_latest_source() -> tuple[Path, Path]:
    temp_root = Path(tempfile.mkdtemp(prefix="winfetch-install-"))
    try:
        zip_path = temp_root / "winfetch-main.zip"
        extract_dir = temp_root / "repo"

        request = urllib.request.Request(
            GITHUB_ZIP_URL,
            headers={"User-Agent": "winfetch-installer"},
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            zip_path.write_bytes(response.read())

        with zipfile.ZipFile(zip_path) as archive:
            safe_extract(archive, extract_dir)

        matches = list(extract_dir.glob("*/src/winfetch"))
        if not matches:
            raise FileNotFoundError("Downloaded repo did not contain src/winfetch")
        return matches[0], temp_root
    except Exception:
        shutil.rmtree(temp_root, ignore_errors=True)
        raise


def safe_extract(archive: zipfile.ZipFile, destination: Path) -> None:
    destination = destination.resolve()
    for member in archive.infolist():
        target = (destination / member.filename).resolve()
        if not target.is_relative_to(destination):
            raise ValueError(f"Unsafe path in downloaded archive: {member.filename}")
    archive.extractall(destination)


def install(source_dir: Path) -> None:
    local_appdata = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    install_dir = local_appdata / "Programs" / APP_NAME
    package_dir = install_dir / APP_NAME
    shim_dir = local_appdata / "Microsoft" / "WindowsApps"
    shim_path = shim_dir / f"{APP_NAME}.cmd"

    install_dir.mkdir(parents=True, exist_ok=True)
    staging_root = Path(tempfile.mkdtemp(prefix=".winfetch-", dir=install_dir))
    staging_package = staging_root / APP_NAME
    backup_dir = install_dir / f".{APP_NAME}-previous"
    installed = False
    try:
        shutil.copytree(source_dir, staging_package)
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        if package_dir.exists():
            package_dir.replace(backup_dir)
        try:
            staging_package.replace(package_dir)
            installed = True
        except Exception:
            if backup_dir.exists():
                backup_dir.replace(package_dir)
            raise
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)
        if installed:
            shutil.rmtree(backup_dir, ignore_errors=True)

    shim_dir.mkdir(parents=True, exist_ok=True)
    shim_path.write_text(
        "@echo off\r\n"
        "setlocal\r\n"
        f"set \"PYTHONPATH={install_dir}\"\r\n"
        f"where py >nul 2>nul && py -m {APP_NAME} %* && exit /b %ERRORLEVEL%\r\n"
        f"python -m {APP_NAME} %*\r\n",
        encoding="utf-8",
    )


def bundled_source_dir() -> Path:
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        return Path(bundle_dir) / "src" / APP_NAME
    return Path(__file__).resolve().parents[1] / "src" / APP_NAME


def wait_before_exit() -> None:
    if sys.stdin is None or not sys.stdin.isatty():
        return
    try:
        input("Press Enter to close this installer...")
    except EOFError:
        pass


if __name__ == "__main__":
    raise SystemExit(main())
