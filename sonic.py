import sys, time, os, shutil, asyncio, importlib.util
import subprocess, signal
from collections import deque

write = sys.stdout.write

# Version number
VERSION = "1.2.1"

# Global constants
ESC = "\033"
RESET = f"{ESC}[0m"
CR = "\r"

# Colors
RED = f"{ESC}[0;31m"

# Configuration states
loop_enabled = False
play_folder_enabled = False

# Terminal state
ENTER_TERM_ALT_BUF = f"{ESC}[?1049h"
EXIT_TERM_ALT_BUF = f"{ESC}[?1049l"
CLEAR_TERM_ALT_BUF = f"{ESC}[2J"
is_term_owned = False

# Cursor actions
CURSOR_SAVE = f"{ESC}[s"
CURSOR_RESTORE = f"{ESC}[u"
CURSOR_ERASE_LINE = f"{ESC}[K"
CURSOR_MOVE_HOME = f"{ESC}[H"
CURSOR_HIDE = f"{ESC}[?25l"
CURSOR_SHOW = f"{ESC}[?25h"

# Media playback
SKIP_LENGTH_MS = 10000
file = ""
folder = ""
song = ""

# Playback state
playback_start_time_ms = 0
total_playback_duration_ms = 0
is_paused = False

# UI icons
play_icon = "\uf04b"
pause_icon = "\uf04c"
loop_icon = "\uf01e"
progress_filled_block_icon = "\u2588"
progress_empty_block_icon = "\u2591"

# UI state
MAX_SONG_TITLE_LEN = 50
song_title = ""
current_media_duration = 0
current_media_duration_clock = ""
render_tick = 0
is_cursor_hidden = False
ui_first_render = True

# Playback control keys
PAUSE_KEY = "k"
NEXT_SONG_KEY = "n"
PREVIOUS_SONG_KEY = "p"
SKIP_FORWARD_KEY = "l"
SKIP_BACKWARD_KEY = "j"
QUIT_KEY = "q"
key = ""


# ===== UTILITY FUNCTIONS ===== #
def print_error(err_msg):
    print(f"Error: {err_msg}", file=sys.stderr)
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
    write("\t%-24s %s\n" % ("-h, --help", "Show help"))
    write("\t%-24s %s\n" % ("-l, --loop", "Loop song or playlist"))
    write(
        "\t%-24s %s\n" % ("-f, --play-folder", "Play songs from the specified folder")
    )
    write("\t%-24s %s\n" % ("-v, --version", "Show version info"))

    print()

    print("Controls:")
    write("\t%-1s %s\n" % (PAUSE_KEY, "Pause/Play music"))
    write("\t%-1s %s\n" % (NEXT_SONG_KEY, "Next song"))
    write("\t%-1s %s\n" % (PREVIOUS_SONG_KEY, "Previous song"))
    write(
        "\t%-1s %s\n"
        % (SKIP_BACKWARD_KEY, f"Seek backward {int(SKIP_LENGTH_MS / 1000)} seconds")
    )
    write(
        "\t%-1s %s\n"
        % (SKIP_FORWARD_KEY, f"Seek forward {int(SKIP_LENGTH_MS / 1000)} seconds")
    )
    write("\t%-1s %s\n" % (QUIT_KEY, "Quit"))


def print_version_info():
    print(f"SONIC v{VERSION}")


# ===== TERMINAL STATE ===== #
def term_borrow_ownership():
    global is_term_owned, is_cursor_hidden

    write(ENTER_TERM_ALT_BUF)
    write(f"{CLEAR_TERM_ALT_BUF}{CURSOR_MOVE_HOME}")

    if not is_cursor_hidden:
        write(CURSOR_HIDE)
        is_cursor_hidden = True

    is_term_owned = True


def term_release_ownership():
    global is_cursor_hidden, is_term_owned

    if is_cursor_hidden:
        write(CURSOR_SHOW)
        is_cursor_hidden = False

    write(f"{CLEAR_TERM_ALT_BUF}{CURSOR_MOVE_HOME}")
    write(EXIT_TERM_ALT_BUF)
    is_term_owned = False


# ===== TIME UTILITIES ===== #
def current_time_ms():
    return int(time.time() * 1000)


# Converts time from ms to seconds and returns it
def format_ms_to_seconds(sec):
    return f"{int(sec / 1000)}.{sec % 1000:03d}"


def format_ms_to_clock(msec):
    seconds = int(msec / 1000)
    minutes = 0
    hours = 0

    if seconds >= 60:
        minutes = int(seconds / 60)
        seconds %= 60

        if minutes >= 60:
            hours = int(minutes / 60)
            minutes %= 60

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


# ===== TIMING STATE ===== #
def timing_start_segment():
    global playback_start_time_ms
    playback_start_time_ms = current_time_ms()


# Return current timestamp of media (ig)
def timing_get_position():
    if is_paused:
        return total_playback_duration_ms
    else:
        return total_playback_duration_ms + (current_time_ms() - playback_start_time_ms)


def timing_commit_position():
    global total_playback_duration_ms

    position = timing_get_position()
    total_playback_duration_ms = position


def timing_seek_forward(seek_len):
    global total_playback_duration_ms
    total_playback_duration_ms += seek_len


def timing_seek_backward(seek_len):
    global total_playback_duration_ms

    if total_playback_duration_ms <= seek_len:
        total_playback_duration_ms = 0
    else:
        total_playback_duration_ms -= seek_len


def timing_reset():
    global playback_start_time_ms, total_playback_duration_ms

    playback_start_time_ms = 0
    total_playback_duration_ms = 0


# ===== UI RENDERING ===== #
def title_overflows():
    return len(song_title) > MAX_SONG_TITLE_LEN


def render_title(frame):
    global song_title

    frame["curr"] += f"{CR}{CURSOR_ERASE_LINE}[Now playing]: "

    if title_overflows():
        song_title = song_title[1:] + song_title[:1]
        frame["curr"] += f"{song_title[: MAX_SONG_TITLE_LEN - 3]}..."
    else:
        frame["curr"] += song_title


def render_playback_control(frame):
    frame["curr"] += f"{CR}"
    if is_paused:
        frame["curr"] += f"{play_icon}  "
    else:
        frame["curr"] += f"{pause_icon}  "


def render_loop_indicator(frame):
    frame["curr"] += f"{loop_icon}  "


def render_progress(frame):
    PLAYBACK_POSITION = timing_get_position()
    PROGRESS_BAR_LEN = 20
    NUM_FILLED_BLOCKS = int(
        PLAYBACK_POSITION / current_media_duration * PROGRESS_BAR_LEN
    )

    frame["curr"] += "["

    i = 1
    while i <= PROGRESS_BAR_LEN:
        if i <= NUM_FILLED_BLOCKS:
            frame["curr"] += progress_filled_block_icon
        else:
            frame["curr"] += progress_empty_block_icon
        i += 1

    frame["curr"] += "] "

    frame["curr"] += (
        f"{CURSOR_ERASE_LINE}{format_ms_to_clock(PLAYBACK_POSITION)} / {current_media_duration_clock}"
    )


def render_ui():
    frame = {"curr": ""}

    # Render title
    if ui_first_render or render_tick == 5 or render_tick == 10:
        render_title(frame)

    # Move two rows down
    frame["curr"] += f"{ESC}[2B"

    # Render pause/play icon
    render_playback_control(frame)

    # Render loop symbol if enabled
    if loop_enabled:
        render_loop_indicator(frame)

    # Render progress
    if ui_first_render or render_tick == 10:
        render_progress(frame)

    # Move two rows up
    frame["curr"] += f"{ESC}[2A"

    write(frame["curr"])
    sys.stdout.flush()


# ===== LOW LEVEL ===== #
def start_ffplay(song, pos=None):
    global ffplay_process, ffplay_pid

    command = ["ffplay", "-nodisp", "-autoexit", "-nostats", "-hide_banner"]

    if pos:
        command.extend(["-ss", str(pos)])

    command.append(str(song))
    ffplay_process = subprocess.Popen(command)
    ffplay_pid = ffplay_process.pid


def ffplay_exists(pid):
    return pid and ffplay_process.poll() is None


def stop_ffplay():
    global ffplay_pid

    if ffplay_exists(ffplay_pid):
        ffplay_process.send_signal(signal.SIGCONT)
        time.sleep(0.2)
        ffplay_process.terminate()
        ffplay_process.wait()
        ffplay_pid = None


# ===== MEDIA METADATA ===== #
def probe_media_duration(song):
    ffprobe_result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(song),
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    if ffprobe_result.returncode != 0:
        media_duration_seconds = 0

    try:
        if ffprobe_result.stdout is None:
            raise ValueError("ffprobe returned nothing")

        media_duration_seconds = float(ffprobe_result.stdout.strip())

    except ValueError:
        media_duration_seconds = 0

    return int(media_duration_seconds * 1000)


# ===== MEDIA PLAYER ===== #
def finish_current_playback():
    global ffplay_pid

    if ffplay_exists(ffplay_pid):
        ffplay_process.send_signal(signal.SIGCONT)
        time.sleep(0.2)
        ffplay_process.terminate()
    ffplay_process.wait()
    ffplay_pid = None


def start_playback(song, pos=None):
    if pos:
        start_ffplay(song, pos)
    else:
        start_ffplay(song)


def stop_playback():
    stop_ffplay()


def pause_playback():
    global is_paused

    ffplay_process.send_signal(signal.SIGSTOP)
    is_paused = True


def resume_playback():
    global is_paused

    stop_playback()
    start_playback(song, format_ms_to_seconds(total_playback_duration_ms))
    is_paused = False


def toggle_pause():
    if not is_paused:
        pause_playback()
        timing_commit_position()
    else:
        resume_playback()
        timing_start_segment()


def select_next_song():
    global song_index

    len_playlist = len(playlist)

    if loop_enabled:
        song_index = (song_index + 1) % len_playlist
    else:
        song_index += 1


def select_previous_song():
    global song_index

    len_playlist = len(playlist)

    if loop_enabled:
        song_index = (song_index - 1 + len_playlist) % len_playlist
    else:
        song_index -= 1


def skip_forward():
    if is_paused:
        timing_seek_forward(SKIP_LENGTH_MS)
    else:
        timing_commit_position()
        timing_seek_forward(SKIP_LENGTH_MS)
        stop_playback()
        start_playback(song, format_ms_to_seconds(total_playback_duration_ms))
        timing_start_segment()


def skip_backward():
    if is_paused:
        timing_seek_backward(SKIP_LENGTH_MS)
    else:
        timing_commit_position()
        stop_playback()
        timing_seek_backward(SKIP_LENGTH_MS)
        start_playback(song, format_ms_to_seconds(total_playback_duration_ms))
        timing_start_segment()


# ===== QUIT ===== #
def quit():
    stop_playback()

    if is_term_owned:
        term_release_ownership()

    sys.exit(0)


# ===== EXIT HANDLING ===== #
# python's cleanup handler requires 'signum' and 'frame'
# they are not related to any of the program's functionality
def cleanup(signum, frame):
    stop_playback()

    if is_term_owned:
        term_release_ownership()

    print("\nInterrupted. Exiting...")
    sys.exit(0)


signal.signal(signal.SIGINT, cleanup)


# ===== EVENT HANDLING ===== #
async def handle_playback_input():
    global render_tick, ui_first_render
    from prompt_toolkit.input import create_input
    from prompt_toolkit.keys import Keys

    input = create_input()
    key_queue = deque()

    def keys_ready():
        for key_press in input.read_keys():
            if key_press.key == Keys.ControlC:
                cleanup(None, None)
            elif key_press.data:
                key_queue.append(key_press.data)

    with input.raw_mode():
        with input.attach(keys_ready):
            while ffplay_exists(ffplay_pid):
                await asyncio.sleep(0.1)
                key = key_queue.popleft() if key_queue else ""

                render_tick += 1

                if render_tick == 10 and not is_paused:
                    timing_commit_position()
                    timing_start_segment()

                if render_tick > 10:
                    render_tick %= 10

                if key:
                    if key == PAUSE_KEY:
                        toggle_pause()
                    elif key == SKIP_FORWARD_KEY:
                        skip_forward()
                    elif key == SKIP_BACKWARD_KEY:
                        skip_backward()
                    elif key in (NEXT_SONG_KEY, PREVIOUS_SONG_KEY, QUIT_KEY):
                        return key

                render_ui()

                if ui_first_render:
                    ui_first_render = False

    return ""


def process_playback_key():
    if key == NEXT_SONG_KEY:
        select_next_song()
    elif key == PREVIOUS_SONG_KEY:
        select_previous_song()
    elif key == QUIT_KEY:
        quit()


# ===== PLAYBACK LOGIC ===== #
def run_playback_loop():
    global song, song_title, song_index
    global current_media_duration, current_media_duration_clock
    global is_paused, render_tick, ui_first_render, key

    len_playlist = len(playlist)

    song_index = 0
    while True:
        song = playlist[song_index]

        song_title = os.path.basename(song)

        if title_overflows():
            song_title = f"  {song_title}  "

        current_media_duration = probe_media_duration(song)
        if current_media_duration == 0:
            return

        current_media_duration_clock = format_ms_to_clock(current_media_duration)

        is_paused = False
        timing_reset()
        render_tick = 0
        ui_first_render = True

        start_playback(song)
        timing_start_segment()

        key = asyncio.run(handle_playback_input())

        process_playback_key()

        finish_current_playback()

        if not key or (key != NEXT_SONG_KEY and key != PREVIOUS_SONG_KEY):
            select_next_song()

        if (song_index < 0 or song_index >= len_playlist) and not loop_enabled:
            break


def run_player():
    term_borrow_ownership()

    run_playback_loop()

    term_release_ownership()


# ===== ARGUMENT PARSING ===== #
def parse_arguments(args):
    global loop_enabled, play_folder_enabled
    global file, folder

    if not args:
        print_help()
        sys.exit(0)

    while args:
        if args[0] == "-h" or args[0] == "--help":
            print_help()
            sys.exit(0)
        elif args[0] == "-v" or args[0] == "--version":
            print_version_info()
            sys.exit(0)
        elif args[0] == "-l" or args[0] == "--loop":
            loop_enabled = True
            args = args[1:]
        elif args[0] == "-f" or args[0] == "--play-folder":
            if len(args) == 1 or not args[1]:
                print_error(f"'{args[0]}' requires a folder")
                sys.exit(1)

            play_folder_enabled = True
            folder = args[1][:-1] if args[1].endswith("/") else args[1]
            args = args[2:]
        elif args[0].startswith("-"):
            print_error(f"unknown option '{args[0]}'")
            sys.exit(1)
        else:
            if file:
                print_error("cannot play multiple files")
                sys.exit(1)
            file = args[0]
            args = args[1:]


# ===== DEPENDENCY CHECK ===== #
def require(dependency, missing_deps):
    if shutil.which(dependency) is None:
        missing_deps.append(dependency)


def check_dependencies():
    missing_deps = []
    dependencies = ["ffplay", "ffprobe"]

    for dependency in dependencies:
        require(dependency, missing_deps)

    if importlib.util.find_spec("prompt_toolkit") is None:
        missing_deps.append(
            "Python package 'prompt_toolkit' (install with: python -m pip install prompt_toolkit)"
        )

    if missing_deps:
        for dependency in missing_deps:
            print(
                f"{RED}Error:{RESET} dependency '{dependency}' not found",
                file=sys.stderr,
            )
        print("Please install the required dependencies\n", file=sys.stderr)
        sys.exit(1)


# ===== ARGUMENT VALIDATION ===== #
def validate_arguments():
    if file and folder:
        print_error("cannot play file and folder together")
        sys.exit(1)

    if file and not os.path.isfile(file):
        print_error("invalid file")
        sys.exit(1)

    if folder and not os.path.isdir(folder):
        print_error("invalid folder")
        sys.exit(1)


# ===== BUILD PLAYLIST ===== #
def build_playlist():
    global playlist
    playlist = []

    if play_folder_enabled:
        # Sort the files in alphabetical order
        for entry in sorted(os.listdir(folder)):
            # Skips hidden files
            if entry.startswith("."):
                continue

            path = os.path.join(folder, entry)
            if os.path.isfile(path) and path.lower().endswith(".mp3"):
                playlist.append(path)

        if not playlist:
            print("Only mp3 files are supported", file=sys.stderr)
            print(f"'{folder}' has no mp3 files", file=sys.stderr)
            sys.exit(1)
    else:
        if not file.lower().endswith(".mp3"):
            print("Error: only mp3 files are supported", file=sys.stderr)
            sys.exit(1)

        playlist.append(file)


# ===== MAIN ===== #
def main(args):
    parse_arguments(args)
    check_dependencies()
    validate_arguments()
    build_playlist()
    run_player()

    print()

    return 0


# ===== PROGRAM STARTS ===== #
if __name__ == "__main__":
    main(sys.argv[1:])
