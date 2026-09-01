"""Limits of the check for a newer release."""

PYPI_RELEASE_URL = "https://pypi.org/pypi/{distribution}/json"

# Short, because the check runs while the listener is trying to hear a radio.
# Missing it costs nothing: the notice simply waits for the next launch.
UPDATE_CHECK_TIMEOUT_SECONDS = 4.0

# Once a day is often enough to hear about a release, and rare enough that
# opening the radio ten times in an evening asks the index once.
UPDATE_CHECK_INTERVAL_SECONDS = 24 * 60 * 60

# A listener who has said no three times has answered. The count starts again
# when a version they have not been told about appears.
UPDATE_NOTICE_LIMIT = 3
