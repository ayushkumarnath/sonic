import unittest

from src.models import PlaybackSnapshot
from src.settings import (
    LOOP_ICON,
    PAUSE_ICON,
    PLAY_ICON,
    PROGRESS_BAR_LEN,
    PROGRESS_EMPTY_BLOCK_ICON,
    PROGRESS_FILLED_BLOCK_ICON,
)
from src.terminal import TerminalUI


class FakeScreen:
    def __init__(self, height=30, width=100):
        self.cursor = (0, 0)
        self.writes = []
        self.cleared_lines = []
        self.refresh_count = 0
        self.clear_count = 0
        self.height = height
        self.width = width

    def getmaxyx(self):
        return self.height, self.width

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

    def clear(self):
        self.clear_count += 1
        self.writes.clear()


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
    def test_render_draws_centered_spectrum_title_and_control_bar(self):
        screen = FakeScreen()
        ui = TerminalUI(screen)

        ui.render(snapshot(position=50_000, loop_enabled=True))

        title_text = "[Now playing]: song.mp3"
        title_y = 20
        title_x = screen.width // 2 - len(title_text) // 2
        self.assertIn((title_y, title_x, title_text), screen.writes)

        control_bar = ui._media_ctrl_bar
        control_y = 22
        control_x = screen.width // 2 - len(control_bar) // 2
        self.assertIn((control_y, control_x, control_bar), screen.writes)
        self.assertIn(LOOP_ICON, control_bar)
        progress = ui._render_progress(snapshot(position=50_000))
        self.assertEqual(progress.count(PROGRESS_FILLED_BLOCK_ICON), PROGRESS_BAR_LEN // 2)
        self.assertEqual(progress.count(PROGRESS_EMPTY_BLOCK_ICON), PROGRESS_BAR_LEN // 2)
        self.assertEqual(screen.refresh_count, 1)

    def test_progress_is_clamped_to_bar_for_positions_outside_duration(self):
        ui = TerminalUI(FakeScreen())
        filled = ui._render_progress(snapshot(position=120_000))
        before_start = ui._render_progress(snapshot(position=-1_000))
        self.assertEqual(filled, f"[{PROGRESS_FILLED_BLOCK_ICON * PROGRESS_BAR_LEN}]")
        self.assertEqual(before_start, f"[{PROGRESS_EMPTY_BLOCK_ICON * PROGRESS_BAR_LEN}]")

    def test_progress_is_empty_when_duration_is_zero(self):
        ui = TerminalUI(FakeScreen())
        progress = ui._render_progress(snapshot(position=5_000, duration=0))
        self.assertEqual(progress, f"[{PROGRESS_EMPTY_BLOCK_ICON * PROGRESS_BAR_LEN}]")

    def test_title_truncation_uses_character_count(self):
        ui = TerminalUI(FakeScreen())
        self.assertEqual(ui._truncate_to_display_width("abcdefgh", 6), "abc...")
        self.assertEqual(ui._truncate_to_display_width("abc", 6), "abc")

    def test_long_title_scrolls_and_short_title_does_not(self):
        ui = TerminalUI(FakeScreen())
        long_title = "x" * 80

        first = ui._generate_title(long_title)
        second = ui._generate_title(long_title)
        self.assertIn("...", first)
        self.assertNotEqual(first, second)

        ui._generate_title("short.mp3")
        self.assertEqual(ui._scroll_title, "short.mp3")

    def test_paused_render_ticks_do_not_draw_spectrum(self):
        for render_tick in (3, 6, 9):
            with self.subTest(render_tick=render_tick):
                ui = TerminalUI(FakeScreen())
                ui._render_spectrum_visualizer = lambda line: self.fail("spectrum rendered while paused")

                ui.render(
                    snapshot(
                        paused=True,
                        first_render=False,
                        render_tick=render_tick,
                    )
                )

    def test_paused_control_bar_updates_on_refresh_tick(self):
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

        control_bar = ui._media_ctrl_bar
        control_y = 22
        control_x = screen.width // 2 - len(control_bar) // 2
        self.assertIn((control_y, control_x, control_bar), screen.writes)
        self.assertTrue(control_bar.startswith(PLAY_ICON))
        self.assertIn("00:00:25 / 00:01:40", control_bar)
        self.assertTrue(any(text == "[Now playing]: song.mp3" for _, _, text in screen.writes))

    def test_small_screen_displays_message_and_skips_ui(self):
        screen = FakeScreen(height=10, width=40)
        ui = TerminalUI(screen)

        ui.render(snapshot())

        self.assertIn((5, 7, "Screen height is too small"), screen.writes)
        self.assertEqual(screen.refresh_count, 1)
        self.assertFalse(any(text == ui._media_ctrl_bar for _, _, text in screen.writes))

        ui.render(snapshot())
        self.assertEqual(screen.clear_count, 2)

        screen.height = 30
        screen.width = 100
        ui.render(snapshot())
        self.assertEqual(screen.clear_count, 2)


if __name__ == "__main__":
    unittest.main()
