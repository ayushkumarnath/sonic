"""Data objects shared by the command-line and playback layers."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PlayerOptions:
    loop_enabled: bool = False
    file_path: Optional[str] = None
    folder_path: Optional[str] = None


@dataclass(frozen=True)
class PlaybackSnapshot:
    song_title: str
    playback_position_ms: int
    media_duration_ms: int
    paused: bool
    loop_enabled: bool
    render_tick: int
    first_render: bool
