import contextlib
import io
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

from sonic_player.cli import (
    CLIError,
    build_playlist,
    main,
    parse_arguments,
    validate_options,
)
from sonic_player.models import PlayerOptions


class ArgumentTests(unittest.TestCase):
    def test_parses_file_and_loop_options_in_either_order(self):
        self.assertEqual(
            parse_arguments(["song.mp3", "--loop"]),
            PlayerOptions(loop_enabled=True, file_path="song.mp3"),
        )
        self.assertEqual(
            parse_arguments(["-l", "song.mp3"]),
            PlayerOptions(loop_enabled=True, file_path="song.mp3"),
        )

    def test_folder_option_removes_one_trailing_slash(self):
        self.assertEqual(parse_arguments(["-f", "music/"]).folder_path, "music")
        self.assertEqual(parse_arguments(["-f", "/"]).folder_path, "/")

    def test_help_version_and_empty_args_return_none(self):
        for args in ([], ["--help"], ["--version"]):
            with self.subTest(args=args), contextlib.redirect_stdout(io.StringIO()):
                self.assertIsNone(parse_arguments(args))

    def test_rejects_invalid_or_repeated_arguments(self):
        cases = [
            (["--unknown"], "unknown option"),
            (["-f"], "requires a folder"),
            (["-f", ""], "requires a folder"),
            (["-f", "one", "-f", "two"], "only be specified once"),
            (["one.mp3", "two.mp3"], "multiple files"),
        ]
        for args, expected in cases:
            with self.subTest(args=args), self.assertRaisesRegex(CLIError, expected):
                parse_arguments(args)


class ValidationAndPlaylistTests(unittest.TestCase):
    def test_validate_rejects_file_and_folder_together(self):
        with self.assertRaisesRegex(CLIError, "file and folder"):
            validate_options(PlayerOptions(file_path="song.mp3", folder_path="music"))

    def test_validate_rejects_missing_file_and_folder(self):
        with self.assertRaisesRegex(CLIError, "invalid file"):
            validate_options(PlayerOptions(file_path="missing.mp3"))
        with self.assertRaisesRegex(CLIError, "invalid folder"):
            validate_options(PlayerOptions(folder_path="missing-folder"))

    def test_build_playlist_sorts_mp3_files_and_skips_hidden_and_non_files(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ("b.MP3", "a.mp3", ".hidden.mp3", "notes.txt"):
                open(os.path.join(folder, name), "w").close()
            os.mkdir(os.path.join(folder, "dir.mp3"))
            result = build_playlist(PlayerOptions(folder_path=folder))
            self.assertEqual(result, [os.path.join(folder, "a.mp3"), os.path.join(folder, "b.MP3")])

    def test_build_playlist_requires_mp3_and_nonempty_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(CLIError, "no mp3 files"):
                build_playlist(PlayerOptions(folder_path=folder))
            with self.assertRaisesRegex(CLIError, "only mp3"):
                build_playlist(PlayerOptions(file_path="song.wav"))
            with self.assertRaisesRegex(CLIError, "provide a file or folder"):
                build_playlist(PlayerOptions())

    def test_main_help_does_not_check_dependencies(self):
        with patch("sonic_player.cli.check_dependencies") as dependencies:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--help"]), 0)
            dependencies.assert_not_called()

    def test_main_reports_cli_error_and_returns_one(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self.assertEqual(main(["--invalid"]), 1)
        self.assertIn("unknown option", stderr.getvalue())

    @patch("sonic_player.cli.Player")
    @patch("sonic_player.cli.check_dependencies")
    def test_main_validates_and_starts_player(self, dependencies, player_class):
        with tempfile.NamedTemporaryFile(suffix=".mp3") as song:
            player_class.return_value.run.return_value = 0
            self.assertEqual(main([song.name]), 0)
        dependencies.assert_called_once_with()
        player_class.return_value.run.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
