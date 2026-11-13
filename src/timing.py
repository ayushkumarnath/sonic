"""Playback position tracking and time formatting."""

import time


class PlaybackClock:
    def __init__(self):
        self.total_duration_ms = 0
        self.segment_started_ms = None

    def start_segment(self):
        self.segment_started_ms = time.monotonic() * 1000

    def position_ms(self):
        if self.segment_started_ms is None:
            return self.total_duration_ms

        elapsed_ms = time.monotonic() * 1000 - self.segment_started_ms
        return self.total_duration_ms + int(elapsed_ms)

    def commit(self):
        self.total_duration_ms = self.position_ms()
        self.segment_started_ms = None

    def seek_forward(self, seek_length_ms):
        self.total_duration_ms += seek_length_ms

    def seek_backward(self, seek_length_ms):
        self.total_duration_ms = max(0, self.total_duration_ms - seek_length_ms)

    def reset(self):
        self.total_duration_ms = 0
        self.segment_started_ms = None


def format_ms_to_seconds(milliseconds):
    seconds, remaining_ms = divmod(milliseconds, 1000)
    return f"{seconds}.{remaining_ms:03d}"


def format_ms_to_clock(milliseconds):
    seconds = int(milliseconds / 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
