# winfetch

A neofetch-style system info tool for Windows terminals. Prints colored ASCII art next to your PC stats, right in CMD, PowerShell, or Windows Terminal.

No dependencies - just Python's standard library.

<img width="1027" height="264" alt="image" src="Preview image.png" />

## Install from source

```powershell
py -m pip install -e .
winfetch
```

## One-file Windows installer

For a normal user install, use `dist\install-winfetch.exe`. The EXE downloads the latest `src\winfetch` from GitHub, installs it, and creates the global `winfetch` command. If GitHub is unavailable, it installs the bundled copy inside the EXE instead.

When it runs, it copies the app into `%LOCALAPPDATA%\Programs\winfetch` and creates `%LOCALAPPDATA%\Microsoft\WindowsApps\winfetch.cmd`. After it says `Done. Open a new terminal to try it out.`, open a new PowerShell or CMD window and run:

```powershell
winfetch
```

## Usage

```powershell
winfetch                        # run with default art
winfetch --ascii path\to\art    # use custom .ansi, .html, or .htm art
winfetch --color1 1-16          # set info label color
winfetch --color2 1-16          # set info value color
winfetch --cfgs                 # list saved named configs
winfetch --cfg save work        # save the current settings as "work"
winfetch --cfg work             # use a saved named config for this run
winfetch --config               # show config file locations
winfetch --no-color             # disable colors
```

Custom art, label color, and value color are saved automatically for next time.

## Config

Stored at `%APPDATA%\winfetch\config.json`.

## Testing

```powershell
$env:PYTHONPATH = "src"
py -m unittest
```

## Build installer exe

With PyInstaller installed, build the self-updating one-file installer executable:

```powershell
py -m PyInstaller --onefile --name install-winfetch --add-data "src\winfetch;winfetch" scripts\install_winfetch.py
```

The executable will be at `dist\install-winfetch.exe`.

## Licence
MIT
