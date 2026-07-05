# winfetch

A neofetch-style system info tool for Windows terminals. Prints colored ASCII art next to your PC stats, right in CMD, PowerShell, or Windows Terminal.

No dependencies — just Python's standard library.

<img width="1027" height="264" alt="image" src="Preview image.png" />


## Install

```powershell
py -m pip install -e .
winfetch
```

## Usage

```powershell
winfetch                        # run with default art
winfetch --ascii path\to\art    # use custom .ansi, .html, or .htm art
winfetch --color 1-16           # set info label color
winfetch --no-color             # disable colors
winfetch --config               # show config file paths
```

Custom art and label color are saved automatically for next time.

## Config

Stored at `%APPDATA%\winfetch\config.json`.

## Testing

```powershell
$env:PYTHONPATH = "src"
py -m unittest
```

## Licence
MIT
