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

For a normal user install, use the versioned installer in `dist\`. It shows the installed version (if present), the version bundled into the installer, and the current GitHub version. You then choose whether to install the GitHub copy or the bundled installer copy; if GitHub cannot be reached, the bundled copy remains available. Use `winfetch --update` to check GitHub for a newer release.

When it runs, it copies the app into `%LOCALAPPDATA%\Programs\winfetch` and creates `%LOCALAPPDATA%\Microsoft\WindowsApps\winfetch.cmd`. After it says `Done. Open a new terminal to try it out.`, open a new PowerShell or CMD window and run:

```powershell
winfetch
```

## Usage

```powershell
winfetch                        # run with default art
winfetch --ascii path\to\art    # use custom .ansi, .html, or .htm art
winfetch --color red            # set info label color (also --color1)
winfetch --color2 "light cyan"  # set info value color
winfetch --cfgs                 # list saved named configs
winfetch --cfg save work        # save the current settings as "work"
winfetch --cfg work             # use a saved named config for this run
winfetch --cfg delete work      # delete a saved config
winfetch --config               # show config file locations
winfetch --update               # check GitHub and interactively install a newer version
winfetch --version              # show the installed version
winfetch --no-color             # disable colors
```

Colors accept palette numbers `1-16` or names such as `red` and `light cyan`. Custom art, label color, and value color are saved automatically for next time.

## Config

Stored at `%APPDATA%\winfetch\config.json`.

## Testing

```powershell
$env:PYTHONPATH = "src"
py -m unittest
```

## Build installer exe

With PyInstaller installed, build the versioned one-file installer executable:

```powershell
py -m PyInstaller --onefile --name install-winfetch-1.1 --add-data "src\winfetch;src\winfetch" scripts\install_winfetch.py
```

The executable will be at `dist\install-winfetch-1.1.exe`.

## Licence
MIT
