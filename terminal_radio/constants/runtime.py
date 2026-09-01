"""Timings and limits of the process that owns the player."""

# How long a client waits for a daemon it just started to begin listening.
DAEMON_START_TIMEOUT_SECONDS = 10.0
SOCKET_POLL_SECONDS = 0.05

# A headless owner with nothing to play and nobody asking is doing no good, so
# it stands down and lets the next command start a fresh one.
DAEMON_IDLE_EXIT_SECONDS = 300.0
DAEMON_IDLE_CHECK_SECONDS = 15.0

# The control socket is private to the user who started the radio.
CONTROL_SOCKET_MODE = 0o600
