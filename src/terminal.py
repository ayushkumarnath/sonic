"""Terminal ownership and playback UI rendering."""

import random
import unicodedata

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
        self._spectrum_height = 10
        self._spectrum_width = 30
        self._spectrum_elem_y = 12
        self._title_width = self._display_width("[Now playing]: ") + MAX_SONG_TITLE_LEN
        self._title_elem_y = 2
        self._progress_elem_y = 1

    def get_win_dimensions(self):
        return self._screen.getmaxyx()

    def _get_ui_height(self):
        return self._spectrum_elem_y + self._title_elem_y + self._progress_elem_y

    def _get_ui_width(self):
        return max(self._spectrum_width, self._title_width, self._media_ctrl_bar_width)

    @staticmethod
    def _display_width(text):
        width = 0
        for char in text:
            category = unicodedata.category(char)
            if category.startswith("M") or category == "Cf":
                continue
            width += 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
        return width

    @classmethod
    def _truncate_to_display_width(cls, text, max_width):
        return text[: max_width - 3] + "..." if len(text) > max_width else text

    def event_win_resize(self):
        self._screen.clear()

    def render(self, snapshot: PlaybackSnapshot):
        self._media_ctrl_bar = f"{PLAY_ICON if snapshot.paused else PAUSE_ICON} {' ' + LOOP_ICON + ' ' if snapshot.loop_enabled else ''} {self._render_progress(snapshot)} {self._render_progress_timer(snapshot)}"
        self._media_ctrl_bar_width = self._display_width(self._media_ctrl_bar)
        self._height, self._width = self.get_win_dimensions()
        self._origin_y, self._origin_x = int(self._height / 2), int(self._width / 2)
        self._box_y, self._box_x = self._get_ui_height(), self._get_ui_width()

        # Handle window resize event by displaying filler text to let the user know
        # if it has become impossible to render the UI with such screen dimensions
        if self._height <= self._box_y or self._width <= self._box_x:
            self._screen.clear()
            novisual_text = ""
            if self._height <= self._box_y:
                novisual_text = "Screen height is too small"
            elif self._width <= self._box_x:
                novisual_text = "Screen width is too small"
            novisual_text = self._truncate_to_display_width(novisual_text, self._width)
            self._screen.addstr(
                self._origin_y,
                max(0, self._origin_x - self._display_width(novisual_text) // 2),
                novisual_text,
            )
            self._screen.refresh()
            return

        line = self._origin_y - int(self._box_y / 2)

        # Render spectrum visualizer
        if not snapshot.paused and (
            snapshot.first_render or snapshot.render_tick in (3, 6, 9)
        ):
            self._render_spectrum_visualizer(line)
        line += self._spectrum_elem_y

        # Render title string
        if snapshot.first_render or snapshot.render_tick in (5, 10):
            self._render_title(line, snapshot.song_title)
        line += self._title_elem_y

        # Render media control bar
        self._render_media_ctrl_bar(line)

        self._screen.refresh()

    def _generate_spectrum_matrix(self):
        visualizer_matrix = [
            [" " for _ in range(self._spectrum_width)]
            for _ in range(self._spectrum_height + 1)
        ]

        for col in range(self._spectrum_width):
            height = random.randint(1, self._spectrum_height)
            for row in range(self._spectrum_height, -1, -1):
                if row == self._spectrum_height:
                    visualizer_matrix[row][col] = "-"
                elif row >= self._spectrum_height - height:
                    visualizer_matrix[row][col] = "."
                elif row < self._spectrum_height - height:
                    visualizer_matrix[row][col] = " "

        return visualizer_matrix

    def _render_spectrum_visualizer(self, line):
        spectr_matrix = self._generate_spectrum_matrix()
        for row, _ in enumerate(spectr_matrix):
            for col, col_el in enumerate(spectr_matrix[row]):
                self._screen.addstr(
                    line + row,
                    self._origin_x - int(self._spectrum_width / 2) + col,
                    col_el,
                )

    def _generate_title(self, title):
        if title != self._source_title:
            self._source_title = title
            self._scroll_title = (
                f"  {title}  "
                if self._display_width(title) > MAX_SONG_TITLE_LEN
                else title
            )

        rendered_title = self._scroll_title
        if self._display_width(self._scroll_title) > MAX_SONG_TITLE_LEN:
            self._scroll_title = self._scroll_title[1:] + self._scroll_title[:1]
            rendered_title = f"{self._scroll_title[: MAX_SONG_TITLE_LEN - 3]}..."

        title_elem = f"[Now playing]: {rendered_title}"

        return title_elem

    def _render_title(self, line, song_title):
        self._screen.move(
            self._origin_y - int(self._box_y / 2) + self._spectrum_elem_y,
            self._origin_x - int(self._box_x / 2),
        )
        self._screen.clrtoeol()

        title_text = self._generate_title(song_title)
        title_x = self._origin_x - self._display_width(title_text) // 2
        self._screen.addstr(line, title_x, title_text)

    def _render_progress(self, snapshot):
        ratio = (
            snapshot.playback_position_ms / snapshot.media_duration_ms
            if snapshot.media_duration_ms > 0
            else 0
        )
        filled_blocks = min(PROGRESS_BAR_LEN, max(0, int(ratio * PROGRESS_BAR_LEN)))

        blocks = "".join(
            PROGRESS_FILLED_BLOCK_ICON
            if index < filled_blocks
            else PROGRESS_EMPTY_BLOCK_ICON
            for index in range(PROGRESS_BAR_LEN)
        )

        progress_elem = f"[{blocks}]"
        return progress_elem

    def _render_progress_timer(self, snapshot):
        position_ms = snapshot.playback_position_ms
        progress_timer_elem = (
            f"{format_ms_to_clock(position_ms)} / "
            f"{format_ms_to_clock(snapshot.media_duration_ms)}"
        )
        return progress_timer_elem

    def _render_media_ctrl_bar(self, line):
        self._screen.addstr(
            line,
            self._origin_x - int(self._media_ctrl_bar_width / 2),
            self._media_ctrl_bar,
        )
