import asyncio
import signal
import unittest
from unittest.mock import AsyncMock, Mock, patch

from sonic_player.models import PlayerOptions
from sonic_player.player import Player
from sonic_player.settings import NEXT_SONG_KEY, PREVIOUS_SONG_KEY, QUIT_KEY


class PlaylistFlowTests(unittest.TestCase):
    def make_player(self, playlist, loop=False):
        player = Player(PlayerOptions(loop_enabled=loop), playlist)
        player.media = Mock()
        player.terminal = Mock()
        return player

    @patch("sonic_player.player.MediaBackend.probe_duration_ms", return_value=1_000)
    def test_next_and_previous_keys_select_expected_tracks(self, _probe):
        player = self.make_player(["one.mp3", "two.mp3", "three.mp3"])
        player._play_current_track = AsyncMock(
            side_effect=[NEXT_SONG_KEY, PREVIOUS_SONG_KEY, QUIT_KEY]
        )
        asyncio.run(player._run_playlist())
        self.assertEqual(player.song, "one.mp3")
        self.assertEqual(player.song_index, 0)
        self.assertEqual(player._play_current_track.call_count, 3)

    @patch("sonic_player.player.MediaBackend.probe_duration_ms", return_value=1_000)
    def test_non_looping_previous_from_first_track_exits_playlist(self, _probe):
        player = self.make_player(["one.mp3", "two.mp3"])
        player._play_current_track = AsyncMock(return_value=PREVIOUS_SONG_KEY)
        asyncio.run(player._run_playlist())
        self.assertEqual(player.song_index, -1)
        self.assertEqual(player._play_current_track.call_count, 1)

    @patch("sonic_player.player.MediaBackend.probe_duration_ms", return_value=1_000)
    def test_looping_next_and_previous_wrap_indices(self, _probe):
        player = self.make_player(["one.mp3", "two.mp3"], loop=True)
        player.song_index = 1
        player._select_next_song()
        self.assertEqual(player.song_index, 0)
        player._select_previous_song()
        self.assertEqual(player.song_index, 1)

    @patch("sonic_player.player.MediaBackend.probe_duration_ms", side_effect=[0, 0, 1_000])
    def test_skips_bad_duration_tracks_until_a_valid_track(self, _probe):
        player = self.make_player(["bad1.mp3", "bad2.mp3", "good.mp3"])
        player._play_current_track = AsyncMock(return_value=QUIT_KEY)
        asyncio.run(player._run_playlist())
        self.assertEqual(player.song, "good.mp3")
        self.assertEqual(player.zero_duration_tracks, 0)
        player._play_current_track.assert_called_once_with()

    @patch("sonic_player.player.MediaBackend.probe_duration_ms", side_effect=[0, 0])
    def test_all_bad_duration_tracks_report_error_and_do_not_play(self, _probe):
        player = self.make_player(["bad1.mp3", "bad2.mp3"])
        player._play_current_track = Mock()
        asyncio.run(player._run_playlist())
        self.assertEqual(player.error_message, "No tracks with a readable duration were found.")
        player._play_current_track.assert_not_called()


class PlayerShutdownTests(unittest.TestCase):
    def test_termination_signal_stops_media_before_player_exits(self):
        player = Player(PlayerOptions(), ["song.mp3"])
        player.media = Mock()
        player.terminal = Mock()
        installed_handlers = {}

        def set_handler(signum, handler):
            installed_handlers[signum] = handler

        def terminate_player(coroutine):
            coroutine.close()
            installed_handlers[signal.SIGTERM](signal.SIGTERM, None)

        with patch("sonic_player.player.signal.getsignal", return_value=signal.SIG_DFL), patch(
            "sonic_player.player.signal.signal", side_effect=set_handler
        ), patch("sonic_player.player.asyncio.run", side_effect=terminate_player):
            self.assertEqual(player.run(), 0)

        player.media.stop.assert_called_once_with()
        player.terminal.leave.assert_called_once_with()
        for signum in (
            signal.SIGINT,
            signal.SIGTERM,
            signal.SIGHUP,
            signal.SIGQUIT,
        ):
            self.assertIn(signum, installed_handlers)


class PlaybackControlTests(unittest.TestCase):
    def make_player(self):
        player = Player(PlayerOptions(), ["song.mp3"])
        player.media = Mock()
        player.terminal = Mock()
        player.media.is_running.side_effect = [True, False]
        return player

    def test_handle_playback_input_returns_navigation_key_without_extra_render(self):
        player = self.make_player()

        class FakeKeyReader:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            async def read_key(self, _timeout):
                return NEXT_SONG_KEY

        with patch("sonic_player.player.KeyReader", FakeKeyReader):
            result = asyncio.run(player._handle_playback_input())

        self.assertEqual(result, NEXT_SONG_KEY)
        # Navigation keys return immediately without rendering another frame.
        player.terminal.render.assert_not_called()

    def test_toggle_pause_commits_clock_and_resumes_from_saved_position(self):
        player = self.make_player()
        player.song = "song.mp3"
        player.clock.total_duration_ms = 4_500
        with patch.object(player.clock, "commit") as commit:
            player._toggle_pause()
        commit.assert_called_once_with()
        player.media.pause.assert_called_once_with()
        self.assertTrue(player.paused)

        player._toggle_pause()
        player.media.stop.assert_called_once_with()
        player.media.start.assert_called_once_with("song.mp3", "4.500")
        self.assertFalse(player.paused)

    def test_seek_updates_clock_and_restarts_media_when_playing(self):
        player = self.make_player()
        player.song = "song.mp3"
        player.clock.total_duration_ms = 20_000
        with patch.object(player.clock, "commit") as commit:
            player._skip_forward()
        commit.assert_called_once_with()
        self.assertEqual(player.clock.total_duration_ms, 30_000)
        player.media.stop.assert_called_once_with()
        player.media.start.assert_called_once_with("song.mp3", "30.000")

    def test_seek_while_paused_does_not_restart_media(self):
        player = self.make_player()
        player.paused = True
        player.clock.total_duration_ms = 20_000
        player._skip_backward()
        self.assertEqual(player.clock.total_duration_ms, 10_000)
        player.media.stop.assert_not_called()
        player.media.start.assert_not_called()


if __name__ == "__main__":
    unittest.main()
