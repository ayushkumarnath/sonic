# SONIC - Terminal Music Player

A lightweight terminal music player built on top of `ffplay`.

SONIC provides a simple command-line interface for playing MP3 files and playlists directly from the terminal, with support for pausing, seeking, looping, and playlist navigation.

## Features

* Play individual MP3 files
* Play all MP3 files from a folder
* Pause and resume playback
* Seek forward and backward by 10 seconds
* Skip to the next or previous song
* Loop songs or playlists
* Millisecond-precision playback tracking
* Lightweight Bash implementation
* Uses `ffplay` as the playback backend

## Requirements

NOTE: SONIC currently supports Linux only.

* `bash` version 5.0+

To check `bash` version:

```shell
bash --version
```

* `ffplay`

To verify that `ffplay` is installed:

```shell
ffplay -version
```

## Installation

Download the latest release from GitHub and extract it:

```shell
tar -xvzf sonic-<version>.tar.gz
cd sonic-<version>
```

Make the installer executable and run it:

```shell
chmod +x install.sh
./install.sh
```

After installation, the `sonic` command can be invoked from anywhere in your terminal.

## Usage

### Play a single song

```shell
sonic song.mp3
```

### Play all MP3 files in a folder

```shell
sonic -f music/
```

### Loop a single song

```shell
sonic song.mp3 --loop
```

### Loop a playlist

```shell
sonic -f music/ --loop
```

## Command-Line Options

| Option                         | Description                       |
| ------------------------------ | --------------------------------- |
| `-h`, `--help`                 | Show help                         |
| `-v`, `--version`              | Show version information          |
| `-l`, `--loop`                 | Loop the current song or playlist |
| `-f`, `--play-folder <folder>` | Play all MP3 files in a folder    |

## Playback Controls

While a song is playing:

| Key | Action                   |
| --- | ------------------------ |
| `k` | Pause / Resume           |
| `j` | Seek backward 10 seconds |
| `l` | Seek forward 10 seconds  |
| `n` | Next song                |
| `p` | Previous song            |
| `q` | Quit                     |

## Supported Formats

Currently SONIC supports:

* MP3 (`.mp3`)

## Examples

Play a song:

```shell
sonic ~/Music/song.mp3
```

Play a folder:

```shell
sonic -f ~/Music
```

Loop a folder:

```shell
sonic -f ~/Music --loop
```
