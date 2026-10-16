"""ffplay and ffprobe process management."""

import math
import signal
import subprocess
import time


class MediaBackend:
    def __init__(self):
        self.process = None

    @staticmethod
    def probe_duration_ms(song):
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=nw=1:nk=1",
                str(song),
            ],
            check=False,
            text=True,
            capture_output=True,
        )

        if result.returncode != 0 or not result.stdout:
            return 0

        try:
            duration_seconds = float(result.stdout.strip())
        except ValueError:
            return 0

        if not math.isfinite(duration_seconds) or duration_seconds <= 0:
            return 0

        return int(duration_seconds * 1000)

    def start(self, song, position_seconds=None):
        command = ["ffplay", "-nodisp", "-autoexit", "-nostats", "-hide_banner"]
        if position_seconds is not None:
            command.extend(["-ss", str(position_seconds)])
        command.append(str(song))
        self.process = subprocess.Popen(command)

    def is_running(self):
        return self.process is not None and self.process.poll() is None

    def pause(self):
        if self.is_running():
            try:
                self.process.send_signal(signal.SIGSTOP)
            except ProcessLookupError:
                pass

    def stop(self):
        process = self.process
        if process is None:
            return

        if process.poll() is None:
            try:
                process.send_signal(signal.SIGCONT)
            except ProcessLookupError:
                pass

            if process.poll() is None:
                time.sleep(0.2)
                try:
                    process.terminate()
                except ProcessLookupError:
                    pass

        process.wait()
        self.process = None

    def finish(self):
        self.stop()
