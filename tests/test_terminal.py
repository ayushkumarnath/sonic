import unittest

from sonic_player.models import PlaybackSnapshot
from sonic_player.settings import (
    LOOP_ICON,
    PAUSE_ICON,
    PLAY_ICON,
    PROGRESS_BAR_LEN,
    PROGRESS_EMPTY_BLOCK_ICON,
    PROGRESS_FILLED_BLOCK_ICON,
)
from sonic_player.terminal import TerminalUI


class FakeScreen:
    def __init__(self):
        self.cursor = (0, 0)
        self.writes = []
        self.cleared_lines = []
        self.refresh_count = 0

    def addstr(self, y, x, text):
        self.writes.append((y, x, text))
        self.cursor = (y, x + len(text))

    def getyx(self):
        return self.cursor

    def move(self, y, x):
        self.cursor = (y, x)

    def clrtoeol(self):
        self.cleared_lines.append(self.cursor)

    def refresh(self):
        self.refresh_count += 1


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
    def test_render_draws_title_controls_progress_and_timer(self):
        screen = FakeScreen()
        ui = TerminalUI(screen)

        ui.render(snapshot(position=50_000, loop_enabled=True))

        writes = {(y, x): body for y, x, body in screen.writes}
        self.assertEqual(writes[(0, 0)], "[Now playing]: song.mp3")
        self.assertEqual(writes[(2, 0)], PAUSE_ICON)
        self.assertEqual(writes[(2, 3)], LOOP_ICON)
        progress = writes[(2, 6)]
        self.assertEqual(progress.count(PROGRESS_FILLED_BLOCK_ICON), PROGRESS_BAR_LEN // 2)
        self.assertEqual(progress.count(PROGRESS_EMPTY_BLOCK_ICON), PROGRESS_BAR_LEN // 2)
        self.assertEqual(writes[(2, 39)], "00:00:50 / 00:01:40")
        self.assertEqual(screen.cleared_lines[-1], (2, 38))
        self.assertEqual(screen.refresh_count, 1)

    def test_progress_is_clamped_to_bar_for_positions_outside_duration(self):
        filled = TerminalUI._render_progress(snapshot(position=120_000))
        before_start = TerminalUI._render_progress(snapshot(position=-1_000))
        self.assertEqual(filled, f"[{PROGRESS_FILLED_BLOCK_ICON * PROGRESS_BAR_LEN}]")
        self.assertEqual(before_start, f"[{PROGRESS_EMPTY_BLOCK_ICON * PROGRESS_BAR_LEN}]")

    def test_long_title_scrolls_and_short_title_does_not(self):
        ui = TerminalUI(FakeScreen())
        long_title = "x" * 80

        first = ui._render_title(long_title)
        second = ui._render_title(long_title)
        self.assertIn("...", first)
        self.assertNotEqual(first, second)

        ui._render_title("short.mp3")
        self.assertEqual(ui._scroll_title, "short.mp3")

    def test_paused_icon_and_progress_update_on_refresh_tick(self):
        screen = FakeScreen()
        ui = TerminalUI(screen)

        ui.render(
            snapshot(
                position=25_000,
                paused=True,
                first_render=False,
                render_tick=10,
            )
        )

        writes = {(y, x): body for y, x, body in screen.writes}
        self.assertEqual(writes[(2, 0)], PLAY_ICON)
        self.assertIn((2, 3), writes)
        self.assertEqual(writes[(2, 36)], "00:00:25 / 00:01:40")
        self.assertEqual(writes[(0, 0)], "[Now playing]: song.mp3")


if __name__ == "__main__":
    unittest.main()
