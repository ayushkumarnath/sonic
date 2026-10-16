"""Terminal ownership and playback UI rendering."""

import sys

from .models import PlaybackSnapshot
from .settings import (
    CLEAR_TERM_ALT_BUF,
    CR,
    CURSOR_ERASE_LINE,
    CURSOR_HIDE,
    CURSOR_MOVE_HOME,
    CURSOR_SHOW,
    ENTER_TERM_ALT_BUF,
    EXIT_TERM_ALT_BUF,
    ESC,
    LOOP_ICON,
    MAX_SONG_TITLE_LEN,
    PAUSE_ICON,
    PLAY_ICON,
    PROGRESS_BAR_LEN,
    PROGRESS_EMPTY_BLOCK_ICON,
    PROGRESS_FILLED_BLOCK_ICON,
)
from .timing import format_ms_to_clock


class TerminalUI:
    def __init__(self):
        self._owned = False
        self._cursor_hidden = False
        self._source_title = None
        self._scroll_title = ""

    def enter(self):
        self._write(ENTER_TERM_ALT_BUF)
        self._write(f"{CLEAR_TERM_ALT_BUF}{CURSOR_MOVE_HOME}")
        if not self._cursor_hidden:
            self._write(CURSOR_HIDE)
            self._cursor_hidden = True
        self._owned = True

    def leave(self):
        if self._cursor_hidden:
            self._write(CURSOR_SHOW)
            self._cursor_hidden = False
        if self._owned:
            self._write(f"{CLEAR_TERM_ALT_BUF}{CURSOR_MOVE_HOME}")
            self._write(EXIT_TERM_ALT_BUF)
            self._owned = False

    def render(self, snapshot: PlaybackSnapshot):
        frame = []
        if snapshot.first_render or snapshot.render_tick in (5, 10):
            frame.append(self._render_title(snapshot.song_title))

        frame.append(f"{ESC}[2B{CR}")
        frame.append(f"{PLAY_ICON if snapshot.paused else PAUSE_ICON}  ")
        if snapshot.loop_enabled:
            frame.append(f"{LOOP_ICON}  ")

        if snapshot.first_render or snapshot.render_tick == 10:
            frame.append(self._render_progress(snapshot))

        frame.append(f"{ESC}[2A")
        self._write("".join(frame))

    def _render_title(self, title):
        if title != self._source_title:
            self._source_title = title
            self._scroll_title = f"  {title}  " if len(title) > MAX_SONG_TITLE_LEN else title

        rendered_title = self._scroll_title
        if len(self._scroll_title) > MAX_SONG_TITLE_LEN:
            self._scroll_title = self._scroll_title[1:] + self._scroll_title[:1]
            rendered_title = f"{self._scroll_title[: MAX_SONG_TITLE_LEN - 3]}..."

        return f"{CR}{CURSOR_ERASE_LINE}[Now playing]: {rendered_title}"

    @staticmethod
    def _render_progress(snapshot):
        position_ms = snapshot.playback_position_ms
        ratio = position_ms / snapshot.media_duration_ms
        filled_blocks = min(PROGRESS_BAR_LEN, max(0, int(ratio * PROGRESS_BAR_LEN)))

        blocks = "".join(
            PROGRESS_FILLED_BLOCK_ICON if index < filled_blocks else PROGRESS_EMPTY_BLOCK_ICON
            for index in range(PROGRESS_BAR_LEN)
        )
        return (
            f"[{blocks}] {CURSOR_ERASE_LINE}"
            f"{format_ms_to_clock(position_ms)} / "
            f"{format_ms_to_clock(snapshot.media_duration_ms)}"
        )

    @staticmethod
    def _write(content):
        sys.stdout.write(content)
        sys.stdout.flush()
