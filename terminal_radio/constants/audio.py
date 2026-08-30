"""System audio detection constants."""

AUDIO_PROBE_TIMEOUT_SECONDS = 3.0
MACOS_AUDIO_PROBE = ("system_profiler", "SPAudioDataType", "-json")
MACOS_DEFAULT_OUTPUT_FLAG = "spaudio_yes"
