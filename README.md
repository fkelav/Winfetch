# winfetch

A dependency-free, neofetch-style system-info tool for Windows terminals. It prints colored ASCII art beside local PC stats in CMD, PowerShell, and Windows Terminal.

<img width="1027" height="264" alt="winfetch preview" src="Preview image.png" />

## Install

### From source

```powershell
py -m pip install -e .
winfetch
```

### Windows installer

Run the versioned `install-winfetch-*.exe` in `dist\`. It shows the installed, bundled, and latest GitHub versions, then lets you install either the bundled copy or the latest GitHub copy. If GitHub is unavailable, the bundled copy can still be installed.

The installer creates the global `winfetch` command. Open a new terminal when it finishes, then run:

```powershell
winfetch
```

## Commands

```powershell
winfetch                              # show system information
winfetch --help                       # show all command help
winfetch --version                    # show the installed version
winfetch --ascii path\to\art.html      # set .ansi, .html, or .htm art
winfetch --color "light red"           # set label color (also --color1)
winfetch --color2 "light cyan"         # set value color
winfetch --no-color                   # disable ANSI colors
winfetch --config                     # show config and art-folder paths
winfetch --cfgs                       # list saved configurations
winfetch --cfg save work              # save current art and colors as "work"
winfetch --cfg work                   # use the "work" configuration once
winfetch --cfg delete work            # delete the "work" configuration
```

Colors accept `1` through `16` or names such as `red` and `light cyan`. Art and color choices are saved as the default after a successful run.

## Updating

For a normal Windows-installer installation, check and install the latest GitHub version with:

```powershell
winfetch --update
```

It displays the installed and available versions, then asks for confirmation. Source installs should be updated by installing the latest source again.

## Config

Settings are stored in `%APPDATA%\winfetch\config.json`. The `--config` command also prints the optional ASCII-art folder location.

## Testing

```powershell
$env:PYTHONPATH = "src"
py -m unittest discover -s tests -v
```

## Build installer

With PyInstaller installed:

```powershell
py -m PyInstaller --onefile --name install-winfetch-1.1 --add-data "src\winfetch;src\winfetch" scripts\install_winfetch.py
```

The executable is created at `dist\install-winfetch-1.1.exe`.

## Licence

MIT
