import io
import unittest
from unittest.mock import patch

from sonic_player.models import PlaybackSnapshot
from sonic_player.settings import (
    EXIT_TERM_ALT_BUF,
    PROGRESS_BAR_LEN,
    PROGRESS_EMPTY_BLOCK_ICON,
    PROGRESS_FILLED_BLOCK_ICON,
)
from sonic_player.terminal import TerminalUI


def snapshot(position=0, duration=100_000, **overrides):
    values = dict(
        song_title="song.mp3",
        playback_position_ms=position,
        media_duration_ms=duration,
        paused=False,
        loop_enabled=False,
        render_tick=0,
        first_render=True,
    )
    values.update(overrides)
    return PlaybackSnapshot(**values)


class TerminalUITests(unittest.TestCase):
    def test_enter_and_leave_restore_terminal_modes(self):
        ui = TerminalUI()
        output = io.StringIO()
        with patch("sonic_player.terminal.sys.stdout", output):
            ui.enter()
            ui.leave()
        self.assertIn(EXIT_TERM_ALT_BUF, output.getvalue())
        self.assertFalse(ui._owned)
        self.assertFalse(ui._cursor_hidden)

    def test_leave_is_safe_before_enter_and_idempotent_after(self):
        ui = TerminalUI()
        output = io.StringIO()
        with patch("sonic_player.terminal.sys.stdout", output):
            ui.leave()
            ui.enter()
            ui.leave()
            ui.leave()
        self.assertEqual(output.getvalue().count(EXIT_TERM_ALT_BUF), 1)

    def test_render_outputs_title_controls_and_progress(self):
        ui = TerminalUI()
        output = io.StringIO()
        with patch("sonic_player.terminal.sys.stdout", output):
            ui.render(snapshot(position=50_000, loop_enabled=True))
        rendered = output.getvalue()
        self.assertIn("[Now playing]: song.mp3", rendered)
        self.assertIn("00:00:50 / 00:01:40", rendered)
        self.assertIn(PROGRESS_FILLED_BLOCK_ICON * (PROGRESS_BAR_LEN // 2), rendered)
        self.assertIn(PROGRESS_EMPTY_BLOCK_ICON * (PROGRESS_BAR_LEN // 2), rendered)

    def test_progress_is_clamped_to_bar_for_positions_outside_duration(self):
        filled = TerminalUI._render_progress(snapshot(position=120_000))
        before_start = TerminalUI._render_progress(snapshot(position=-1_000))
        self.assertIn(PROGRESS_FILLED_BLOCK_ICON * PROGRESS_BAR_LEN, filled)
        self.assertNotIn(PROGRESS_EMPTY_BLOCK_ICON, filled)
        self.assertIn(PROGRESS_EMPTY_BLOCK_ICON * PROGRESS_BAR_LEN, before_start)
        self.assertNotIn(PROGRESS_FILLED_BLOCK_ICON, before_start)

    def test_long_title_scrolls_and_short_title_does_not(self):
        ui = TerminalUI()
        long_title = "x" * 80
        first = ui._render_title(long_title)
        second = ui._render_title(long_title)
        self.assertIn("...", first)
        self.assertNotEqual(first, second)
        ui._render_title("short.mp3")
        self.assertEqual(ui._scroll_title, "short.mp3")


if __name__ == "__main__":
    unittest.main()
