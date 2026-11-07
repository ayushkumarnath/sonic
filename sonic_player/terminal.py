"""Terminal ownership and playback UI rendering."""

import sys

from .models import PlaybackSnapshot
from .settings import (
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
    def __init__(self, screen):
        self._owned = False
        self._cursor_hidden = False
        self._source_title = None
        self._scroll_title = ""
        self._screen = screen

    def render(self, snapshot: PlaybackSnapshot):
        line_no = 0

        if snapshot.first_render or snapshot.render_tick in (5, 10):
            self._screen.addstr(
                line_no, 0, f"{self._render_title(snapshot.song_title)}"
            )

        line_no += 2

        self._screen.addstr(
            line_no, 0, f"{PLAY_ICON if snapshot.paused else PAUSE_ICON}"
        )

        y, x = self._screen.getyx()

        if snapshot.loop_enabled:
            self._screen.addstr(y, x + 2, f"{LOOP_ICON}")
            y, x = self._screen.getyx()

        if snapshot.first_render or snapshot.render_tick == 10:
            self._screen.addstr(y, x + 2, f"{self._render_progress(snapshot)}")
            y, x = self._screen.getyx()
            self._screen.clrtoeol()
            self._screen.addstr(y, x + 1, f"{self._render_progress_timer(snapshot)}")
        self._screen.refresh()

    def _render_title(self, title):
        if title != self._source_title:
            self._source_title = title
            self._scroll_title = (
                f"  {title}  " if len(title) > MAX_SONG_TITLE_LEN else title
            )

        rendered_title = self._scroll_title
        if len(self._scroll_title) > MAX_SONG_TITLE_LEN:
            self._scroll_title = self._scroll_title[1:] + self._scroll_title[:1]
            rendered_title = f"{self._scroll_title[: MAX_SONG_TITLE_LEN - 3]}..."

        self._screen.move(0, 0)
        self._screen.clrtoeol()
        return f"[Now playing]: {rendered_title}"

    @staticmethod
    def _render_progress(snapshot):
        ratio = snapshot.playback_position_ms / snapshot.media_duration_ms
        filled_blocks = min(PROGRESS_BAR_LEN, max(0, int(ratio * PROGRESS_BAR_LEN)))

        blocks = "".join(
            PROGRESS_FILLED_BLOCK_ICON
            if index < filled_blocks
            else PROGRESS_EMPTY_BLOCK_ICON
            for index in range(PROGRESS_BAR_LEN)
        )
        return f"[{blocks}]"

    @staticmethod
    def _render_progress_timer(snapshot):
        position_ms = snapshot.playback_position_ms
        return (
            f"{format_ms_to_clock(position_ms)} / "
            f"{format_ms_to_clock(snapshot.media_duration_ms)}"
        )
