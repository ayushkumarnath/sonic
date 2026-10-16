"""Playback orchestration and mutable player state."""

import asyncio
import os
import signal
import sys

from .input import CONTROL_C, KeyReader
from .media import MediaBackend
from .models import PlaybackSnapshot, PlayerOptions
from .settings import (
    NEXT_SONG_KEY,
    PAUSE_KEY,
    PREVIOUS_SONG_KEY,
    QUIT_KEY,
    SKIP_BACKWARD_KEY,
    SKIP_FORWARD_KEY,
    SKIP_LENGTH_MS,
)
from .terminal import TerminalUI
from .timing import PlaybackClock, format_ms_to_seconds


class Player:
    def __init__(self, options: PlayerOptions, playlist):
        self.options = options
        self.playlist = playlist
        self.song_index = 0
        self.song = ""
        self.song_title = ""
        self.media_duration_ms = 0
        self.paused = False
        self.render_tick = 0
        self.first_render = True
        self.zero_duration_tracks = 0
        self.error_message = None
        self.clock = PlaybackClock()
        self.media = MediaBackend()
        self.terminal = TerminalUI()

    def run(self):
        previous_handler = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, self._handle_interrupt)
        interrupted = False

        try:
            self.terminal.enter()
            asyncio.run(self._run_playlist())
        except KeyboardInterrupt:
            interrupted = True
        finally:
            try:
                self.media.stop()
            finally:
                try:
                    self.terminal.leave()
                finally:
                    signal.signal(signal.SIGINT, previous_handler)

        if interrupted:
            print("\nInterrupted. Exiting...")
        elif self.error_message:
            print(self.error_message, file=sys.stderr)
        else:
            print()

        return 0

    @staticmethod
    def _handle_interrupt(signum, frame):
        raise KeyboardInterrupt

    async def _run_playlist(self):
        while 0 <= self.song_index < len(self.playlist):
            self.song = self.playlist[self.song_index]
            self.song_title = os.path.basename(self.song)
            self.media_duration_ms = MediaBackend.probe_duration_ms(self.song)

            if self.media_duration_ms == 0:
                self.zero_duration_tracks += 1
                if self.zero_duration_tracks >= len(self.playlist):
                    self.error_message = "No tracks with a readable duration were found."
                    return

                self._select_next_song()
                continue

            self.zero_duration_tracks = 0
            key = await self._play_current_track()

            if key == QUIT_KEY:
                return
            elif key == NEXT_SONG_KEY:
                self._select_next_song()
            elif key == PREVIOUS_SONG_KEY:
                self._select_previous_song()
            else:
                self._select_next_song()

    async def _play_current_track(self):
        self.paused = False
        self.clock.reset()
        self.render_tick = 0
        self.first_render = True

        self.media.start(self.song)
        self.clock.start_segment()
        key = await self._handle_playback_input()
        self.media.finish()
        return key

    async def _handle_playback_input(self):
        with KeyReader() as key_reader:
            while self.media.is_running():
                key = await key_reader.read_key(0.1)
                self.render_tick += 1

                if self.render_tick == 10 and not self.paused:
                    self.clock.commit()
                    self.clock.start_segment()

                if self.render_tick > 10:
                    self.render_tick %= 10

                if key == CONTROL_C:
                    raise KeyboardInterrupt
                if key == PAUSE_KEY:
                    self._toggle_pause()
                elif key == SKIP_FORWARD_KEY:
                    self._skip_forward()
                elif key == SKIP_BACKWARD_KEY:
                    self._skip_backward()
                elif key in (NEXT_SONG_KEY, PREVIOUS_SONG_KEY, QUIT_KEY):
                    return key

                self.terminal.render(self._snapshot())
                if self.first_render:
                    self.first_render = False

        return ""

    def _snapshot(self) -> PlaybackSnapshot:
        return PlaybackSnapshot(
            song_title=self.song_title,
            playback_position_ms=self.clock.position_ms(),
            media_duration_ms=self.media_duration_ms,
            paused=self.paused,
            loop_enabled=self.options.loop_enabled,
            render_tick=self.render_tick,
            first_render=self.first_render,
        )

    def _toggle_pause(self):
        if not self.paused:
            self.clock.commit()
            self.media.pause()
            self.paused = True
        else:
            self.media.stop()
            self.media.start(
                self.song,
                format_ms_to_seconds(self.clock.total_duration_ms),
            )
            self.paused = False
            self.clock.start_segment()

    def _skip_forward(self):
        self._seek(SKIP_LENGTH_MS)

    def _skip_backward(self):
        self._seek(-SKIP_LENGTH_MS)

    def _seek(self, offset_ms):
        if not self.paused:
            self.clock.commit()

        if offset_ms > 0:
            self.clock.seek_forward(offset_ms)
        else:
            self.clock.seek_backward(-offset_ms)

        if not self.paused:
            self.media.stop()
            self.media.start(
                self.song,
                format_ms_to_seconds(self.clock.total_duration_ms),
            )
            self.clock.start_segment()

    def _select_next_song(self):
        if self.options.loop_enabled:
            self.song_index = (self.song_index + 1) % len(self.playlist)
        else:
            self.song_index += 1

    def _select_previous_song(self):
        if self.options.loop_enabled:
            self.song_index = (self.song_index - 1) % len(self.playlist)
        else:
            self.song_index -= 1
