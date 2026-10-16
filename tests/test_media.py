import math
import subprocess
import unittest
from unittest.mock import Mock, patch

from sonic_player.media import MediaBackend


class ProbeDurationTests(unittest.TestCase):
    @patch("sonic_player.media.subprocess.run")
    def test_parses_valid_duration_to_milliseconds(self, run):
        run.return_value = Mock(returncode=0, stdout="123.456\n")
        self.assertEqual(MediaBackend.probe_duration_ms("song.mp3"), 123_456)
        self.assertEqual(run.call_args.kwargs["check"], False)
        self.assertTrue(run.call_args.kwargs["capture_output"])

    @patch("sonic_player.media.subprocess.run")
    def test_returns_zero_for_probe_errors_and_invalid_values(self, run):
        cases = [
            Mock(returncode=1, stdout="42"),
            Mock(returncode=0, stdout=""),
            Mock(returncode=0, stdout="unknown"),
            Mock(returncode=0, stdout="nan"),
            Mock(returncode=0, stdout="inf"),
            Mock(returncode=0, stdout="-inf"),
            Mock(returncode=0, stdout="0"),
            Mock(returncode=0, stdout="-1"),
        ]
        for result in cases:
            with self.subTest(stdout=result.stdout, returncode=result.returncode):
                run.return_value = result
                self.assertEqual(MediaBackend.probe_duration_ms("bad.mp3"), 0)


class MediaLifecycleTests(unittest.TestCase):
    @patch("sonic_player.media.subprocess.Popen")
    def test_start_builds_ffplay_command_with_optional_seek(self, popen):
        backend = MediaBackend()
        backend.start("song.mp3", "12.345")
        self.assertEqual(
            popen.call_args.args[0],
            ["ffplay", "-nodisp", "-autoexit", "-nostats", "-hide_banner", "-ss", "12.345", "song.mp3"],
        )
        backend.start("next.mp3")
        self.assertEqual(popen.call_args.args[0][-1], "next.mp3")
        self.assertNotIn("-ss", popen.call_args.args[0])

    def test_is_running_checks_current_process(self):
        backend = MediaBackend()
        self.assertFalse(backend.is_running())
        backend.process = Mock()
        backend.process.poll.return_value = None
        self.assertTrue(backend.is_running())
        backend.process.poll.return_value = 0
        self.assertFalse(backend.is_running())

    @patch("sonic_player.media.time.sleep")
    def test_stop_resumes_then_terminates_and_waits(self, sleep):
        process = Mock()
        process.poll.side_effect = [None, None]
        backend = MediaBackend()
        backend.process = process
        backend.stop()
        process.send_signal.assert_called_once()
        process.terminate.assert_called_once_with()
        process.wait.assert_called_once_with()
        sleep.assert_called_once_with(0.2)
        self.assertIsNone(backend.process)

    @patch("sonic_player.media.time.sleep")
    def test_stop_waits_without_terminating_finished_process(self, sleep):
        process = Mock()
        process.poll.return_value = 0
        backend = MediaBackend()
        backend.process = process
        backend.stop()
        process.terminate.assert_not_called()
        process.send_signal.assert_not_called()
        process.wait.assert_called_once_with()
        sleep.assert_not_called()
        self.assertIsNone(backend.process)

    def test_stop_without_process_is_safe(self):
        backend = MediaBackend()
        backend.stop()
        self.assertIsNone(backend.process)

    @patch("sonic_player.media.time.sleep")
    def test_stop_tolerates_process_disappearing_during_signal(self, sleep):
        process = Mock()
        process.poll.return_value = None
        process.send_signal.side_effect = ProcessLookupError
        backend = MediaBackend()
        backend.process = process
        backend.stop()
        process.terminate.assert_called_once_with()
        process.wait.assert_called_once_with()
        sleep.assert_called_once_with(0.2)


if __name__ == "__main__":
    unittest.main()
