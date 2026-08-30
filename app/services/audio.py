"""Detection of the audio output the system is currently sending sound to."""

from __future__ import annotations

import json
import subprocess
import sys

from app.constants.audio import (
    AUDIO_PROBE_TIMEOUT_SECONDS,
    MACOS_AUDIO_PROBE,
    MACOS_DEFAULT_OUTPUT_FLAG,
)


def detect_output_device() -> str | None:
    """Return the name of the default audio output, or None when unknown.

    Only macOS is covered. Everywhere else the caller falls back to the name of
    the mpv output driver, which is all the backend reports.
    """
    if sys.platform != "darwin":
        return None

    try:
        result = subprocess.run(
            MACOS_AUDIO_PROBE,
            capture_output=True,
            text=True,
            timeout=AUDIO_PROBE_TIMEOUT_SECONDS,
            check=False,
        )
        payload = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return None

    for group in payload.get("SPAudioDataType", []):
        for item in group.get("_items", []):
            if (
                item.get("coreaudio_default_audio_output_device")
                == MACOS_DEFAULT_OUTPUT_FLAG
            ):
                name = item.get("_name")
                return str(name) if name else None
    return None
