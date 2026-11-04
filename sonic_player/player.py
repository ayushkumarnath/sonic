"""Playback orchestration and mutable player state."""

import os
import signal
import sys
import curses
from curses.ascii import ctrl

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
    SPACE_KEY,
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

    def run(self):
        handled_signals = [
            signal.SIGINT,
            signal.SIGTERM,
            signal.SIGHUP,
            signal.SIGQUIT,
        ]
        previous_handlers = {
            signum: signal.getsignal(signum) for signum in handled_signals
        }
        for signum in handled_signals:
            signal.signal(signum, self._handle_interrupt)
        interrupted = False

        try:
            curses.wrapper(self._run_with_curses)
        except KeyboardInterrupt:
            interrupted = True
        finally:
            for signum in handled_signals:
                signal.signal(signum, signal.SIG_IGN)
            try:
                self.media.stop()
            finally:
                for signum, handler in previous_handlers.items():
                    signal.signal(signum, handler)

        if interrupted:
            print("\nInterrupted. Exiting...")
        elif self.error_message:
            print(self.error_message, file=sys.stderr)
        else:
            print()

        return 0

    def _run_with_curses(self, screen):
        self._screen = screen

        try:
            curses.curs_set(0)  # Hides cursor
        except curses.error:
            pass

        self._screen.keypad(True)  # Enables detection of arrow keys
        self._screen.timeout(100)  # Waits for 0.1s for user input

        self.terminal = TerminalUI(screen)
        self._run_playlist()

    @staticmethod
    def _handle_interrupt(signum, frame):
        raise KeyboardInterrupt

    def _run_playlist(self):
        while 0 <= self.song_index < len(self.playlist):
            self.song = self.playlist[self.song_index]
            self.song_title = os.path.basename(self.song)
            self.media_duration_ms = MediaBackend.probe_duration_ms(self.song)

            if self.media_duration_ms == 0:
                self.zero_duration_tracks += 1
                if self.zero_duration_tracks >= len(self.playlist):
                    self.error_message = (
                        "No tracks with a readable duration were found."
                    )
                    return

                self._select_next_song()
                continue

            self.zero_duration_tracks = 0
            key = self._play_current_track()

            if key == ord(QUIT_KEY):
                return
            elif key == ord(NEXT_SONG_KEY):
                self._select_next_song()
            elif key == ord(PREVIOUS_SONG_KEY):
                self._select_previous_song()
            else:
                self._select_next_song()

    def _play_current_track(self):
        self.paused = False
        self.clock.reset()
        self.render_tick = 0
        self.first_render = True

        self.media.start(self.song)
        self.clock.start_segment()
        key = self._handle_playback_input()
        self.media.finish()
        return key

    def _handle_playback_input(self):
        while self.media.is_running():
            key = self._screen.getch()
            self.render_tick += 1

            if self.render_tick == 10 and not self.paused:
                self.clock.commit()
                self.clock.start_segment()

            if self.render_tick > 10:
                self.render_tick %= 10

            if key == ctrl("C"):
                raise KeyboardInterrupt
            if key == ord(PAUSE_KEY) or key == ord(SPACE_KEY):
                self._toggle_pause()
            elif key == ord(SKIP_FORWARD_KEY) or key == curses.KEY_RIGHT:
                self._skip_forward()
            elif key == ord(SKIP_BACKWARD_KEY) or key == curses.KEY_LEFT:
                self._skip_backward()
            elif key in (ord(NEXT_SONG_KEY), ord(PREVIOUS_SONG_KEY), ord(QUIT_KEY)):
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
