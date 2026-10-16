import unittest
from unittest.mock import patch

from sonic_player.timing import (
    PlaybackClock,
    format_ms_to_clock,
    format_ms_to_seconds,
)


class PlaybackClockTests(unittest.TestCase):
    def test_position_advances_from_monotonic_clock(self):
        clock = PlaybackClock()
        with patch("sonic_player.timing.time.monotonic", side_effect=[10.0, 12.345]):
            clock.start_segment()
            self.assertEqual(clock.position_ms(), 2345)

    def test_commit_accumulates_segment_and_stops_running_segment(self):
        clock = PlaybackClock()
        with patch("sonic_player.timing.time.monotonic", side_effect=[1.0, 3.5]):
            clock.start_segment()
            clock.commit()

        self.assertEqual(clock.total_duration_ms, 2500)
        self.assertIsNone(clock.segment_started_ms)
        self.assertEqual(clock.position_ms(), 2500)

    def test_seeks_and_backward_seek_clamps_at_zero(self):
        clock = PlaybackClock()
        clock.seek_forward(10_000)
        clock.seek_backward(3_000)
        self.assertEqual(clock.total_duration_ms, 7_000)
        clock.seek_backward(9_000)
        self.assertEqual(clock.total_duration_ms, 0)

    def test_reset_clears_committed_and_running_time(self):
        clock = PlaybackClock()
        clock.total_duration_ms = 5_000
        clock.segment_started_ms = 10
        clock.reset()
        self.assertEqual(clock.total_duration_ms, 0)
        self.assertIsNone(clock.segment_started_ms)

    def test_time_formatters_keep_milliseconds_and_hours(self):
        self.assertEqual(format_ms_to_seconds(12_345), "12.345")
        self.assertEqual(format_ms_to_seconds(5), "0.005")
        self.assertEqual(format_ms_to_clock(3_723_000), "01:02:03")
        self.assertEqual(format_ms_to_clock(59_999), "00:00:59")


if __name__ == "__main__":
    unittest.main()
