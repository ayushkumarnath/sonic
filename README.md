# SONIC - Terminal Music Player

SONIC is a terminal music player for Linux. It plays MP3 files and playlists with `ffplay`, and provides playback controls, seeking, and looping.

## Features

- Play an MP3 file or all MP3 files in a folder
- Pause and resume playback
- Seek forward or backward by 10 seconds
- Move to the next or previous song
- Loop a song or playlist
- Display playback progress and elapsed time

## Requirements

- Linux x86_64. Prebuilt releases target Ubuntu 22.04 and compatible systems.
- `ffplay` and `ffprobe`, provided by FFmpeg. On Ubuntu, install them with:

  ```shell
  sudo apt install ffmpeg
  ```

- A Nerd Font is recommended for the playback icons.

The packaged executable includes Python. Curses is provided by Python; FFmpeg remains an external dependency.

## Install a release

Download the Linux x86_64 archive from the project's GitHub Releases page and extract it. From the extracted directory, run the installer:

```shell
tar -xzf sonic-<version>-linux-x86_64.tar.gz
cd sonic-<version>
./install.sh
```

The installer copies the packaged executable from `dist/sonic` to `~/.local/bin/sonic`. It does not edit shell startup files. If `~/.local/bin` is not in your `PATH`, the installer prints a command to add it for the current shell.

Check the installation with:

```shell
sonic --version
```

## Run from source

Install Python 3 with curses support and FFmpeg, then run the entry point:

```shell
python3 sonic.py --help
```

## Build a standalone executable

Install the pinned build dependencies in a virtual environment and build the one-file Linux executable:

```shell
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-build.txt
.venv/bin/python -m PyInstaller --clean --noconfirm --onefile --name sonic --specpath build --workpath build/work --distpath dist sonic.py
```

The executable is written to `dist/sonic`. Test it with:

```shell
./dist/sonic --help
./dist/sonic --version
```

To install this local build, run `./install.sh` from the project root. If `dist/sonic` is missing, the installer creates an isolated build environment under `build/`, installs the pinned build dependencies, and builds the executable before installing it. This requires Python 3, Python venv support, and network access for the initial dependency install. Build Linux binaries on Linux for the target architecture; the executable still requires compatible system libraries and FFmpeg tools.

## Run the tests

From the project root, run:

```shell
python3 -m unittest discover -s tests -v
```

## Usage

Play one song:

```shell
sonic ~/Music/song.mp3
```

Play all MP3 files in a folder:

```shell
sonic -f ~/Music
```

Loop a song or folder playlist:

```shell
sonic ~/Music/song.mp3 --loop
sonic -f ~/Music --loop
```

## Command-line options

| Option | Description |
| --- | --- |
| `-h`, `--help` | Show help |
| `-v`, `--version` | Show version |
| `-l`, `--loop` | Loop a song or playlist |
| `-f`, `--play-folder <folder>` | Play MP3 files from a folder |

## Playback controls

| Key | Action |
| --- | --- |
| `k`, `Space` | Pause or resume |
| `j`, `←` | Seek backward 10 seconds |
| `l`, `→` | Seek forward 10 seconds |
| `n` | Next song |
| `p` | Previous song |
| `q` | Quit |

SONIC currently supports MP3 (`.mp3`) files.
