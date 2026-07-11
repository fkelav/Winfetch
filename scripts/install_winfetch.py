from __future__ import annotations

import os
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path


APP_NAME = "winfetch"
GITHUB_ZIP_URL = "https://github.com/fkelav/Winfetch/archive/refs/heads/main.zip"


def main() -> int:
    temp_root: Path | None = None
    try:
        source_dir, temp_root = resolve_source_dir()
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


def resolve_source_dir() -> tuple[Path, Path | None]:
    try:
        source_dir, temp_root = download_latest_source()
        print("Installed latest winfetch from GitHub.")
        return source_dir, temp_root
    except Exception as exc:
        print(f"Could not download latest winfetch from GitHub: {exc}")
        print("Installing the bundled winfetch copy instead.")
        source_dir = bundled_source_dir()
        if not source_dir.is_dir():
            raise FileNotFoundError(f"Could not find bundled package source: {source_dir}")
        return source_dir, None


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
