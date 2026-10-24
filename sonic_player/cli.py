"""Command-line parsing, validation, and application startup."""

import fcntl
import importlib.util
import os
import shutil
import sys

from .models import PlayerOptions
from .player import Player
from .settings import (
    NEXT_SONG_KEY,
    PAUSE_KEY,
    PREVIOUS_SONG_KEY,
    QUIT_KEY,
    RED,
    RESET,
    SKIP_BACKWARD_KEY,
    SKIP_FORWARD_KEY,
    SKIP_LENGTH_MS,
    VERSION,
)


class CLIError(Exception):
    pass


INSTANCE_LOCK_PATH = f"/tmp/sonic-{os.getuid()}.lock"


def acquire_instance_lock():
    """Acquire and return the process-wide playback lock."""
    flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(INSTANCE_LOCK_PATH, flags, 0o600)
    lock_file = os.fdopen(descriptor, "a+")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        lock_file.close()
        raise CLIError("another SONIC instance is already running") from error
    except BaseException:
        lock_file.close()
        raise
    return lock_file


def print_error(message):
    print(f"Error: {message}", file=sys.stderr)
    print("See --help for more info", file=sys.stderr)


def print_help():
    print("SONIC - Terminal Music Player\n")
    print("Usage:")
    print("\tsonic <file>")
    print("\tsonic -f <folder>")
    print("\tsonic <file> [-l]")
    print("\tsonic -f <folder> [-l]")
    print()

    print("Options:")
    print("\t%-24s %s" % ("-h, --help", "Show help"))
    print("\t%-24s %s" % ("-l, --loop", "Loop song or playlist"))
    print("\t%-24s %s" % ("-f, --play-folder", "Play songs from the specified folder"))
    print("\t%-24s %s" % ("-v, --version", "Show version info"))
    print()

    print("Controls:")
    print("\t%-1s %s" % (PAUSE_KEY, "Pause/Play music"))
    print("\t%-1s %s" % (NEXT_SONG_KEY, "Next song"))
    print("\t%-1s %s" % (PREVIOUS_SONG_KEY, "Previous song"))
    print(
        "\t%-1s %s"
        % (SKIP_BACKWARD_KEY, f"Seek backward {SKIP_LENGTH_MS // 1000} seconds")
    )
    print(
        "\t%-1s %s"
        % (SKIP_FORWARD_KEY, f"Seek forward {SKIP_LENGTH_MS // 1000} seconds")
    )
    print("\t%-1s %s" % (QUIT_KEY, "Quit"))


def parse_arguments(args):
    loop_enabled = False
    file_path = None
    folder_path = None
    args = list(args)

    if not args:
        return None

    while args:
        argument = args[0]
        if argument in ("-h", "--help"):
            print_help()
            return None
        if argument in ("-v", "--version"):
            print(f"SONIC v{VERSION}")
            return None
        if argument in ("-l", "--loop"):
            loop_enabled = True
            args = args[1:]
        elif argument in ("-f", "--play-folder"):
            if len(args) < 2 or not args[1]:
                raise CLIError(f"'{argument}' requires a folder")
            if folder_path is not None:
                raise CLIError("play-folder may only be specified once")
            folder_path = os.path.normpath(args[1])
            args = args[2:]
        elif argument.startswith("-"):
            raise CLIError(f"unknown option '{argument}'")
        else:
            if file_path is not None:
                raise CLIError("cannot play multiple files")
            file_path = argument
            args = args[1:]

    return PlayerOptions(
        loop_enabled=loop_enabled,
        file_path=file_path,
        folder_path=folder_path,
    )


def check_dependencies():
    missing = [name for name in ("ffplay", "ffprobe") if shutil.which(name) is None]
    if importlib.util.find_spec("prompt_toolkit") is None:
        missing.append(
            "Python package 'prompt_toolkit' (install with: python -m pip install prompt_toolkit)"
        )

    if missing:
        for dependency in missing:
            print(
                f"{RED}Error:{RESET} dependency '{dependency}' not found",
                file=sys.stderr,
            )
        print("Please install the required dependencies\n", file=sys.stderr)
        raise CLIError("missing dependencies")


def validate_options(options):
    if options.file_path and options.folder_path:
        raise CLIError("cannot play file and folder together")
    if options.file_path and not os.path.isfile(options.file_path):
        raise CLIError("invalid file")
    if options.folder_path and not os.path.isdir(options.folder_path):
        raise CLIError("invalid folder")


def build_playlist(options):
    if options.folder_path:
        playlist = []
        for entry in sorted(os.listdir(options.folder_path)):
            if entry.startswith("."):
                continue
            path = os.path.join(options.folder_path, entry)
            if os.path.isfile(path) and path.lower().endswith(".mp3"):
                playlist.append(path)

        if not playlist:
            raise CLIError(
                f"Only mp3 files are supported\n'{options.folder_path}' has no mp3 files"
            )
        return playlist

    if not options.file_path:
        raise CLIError("provide a file or folder")
    if not options.file_path.lower().endswith(".mp3"):
        raise CLIError("only mp3 files are supported")
    return [options.file_path]


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        print_help()
        return 0

    try:
        options = parse_arguments(argv)
        if options is None:
            return 0
        check_dependencies()
    except CLIError as error:
        if str(error) != "missing dependencies":
            print_error(str(error))
        return 1
    except OSError as error:
        print_error(str(error))
        return 1

    try:
        lock_file = acquire_instance_lock()
    except CLIError as error:
        print_error(str(error))
        return 1
    except OSError as error:
        print_error(f"could not acquire instance lock: {error}")
        return 1

    try:
        validate_options(options)
        playlist = build_playlist(options)
        return Player(options, playlist).run()
    except CLIError as error:
        if str(error) != "missing dependencies":
            print_error(str(error))
        return 1
    except OSError as error:
        print_error(str(error))
        return 1
    finally:
        lock_file.close()
