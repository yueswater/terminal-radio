#!/bin/sh
# Install the radio command and the mpv backend it plays through.
#
#   curl -LsSf https://raw.githubusercontent.com/yueswater/terminal-radio/main/install.sh | sh
#
# Every command that changes the machine is printed before it runs. On Linux the
# audio backend needs a package manager, so that one step asks for a password;
# sudo reads it from the terminal, which a pipe does not take away.
#
# Set RADIO_SKIP_MPV=1 to install only the command and leave mpv alone.

set -eu

PACKAGE="radiotui-tw"
COMMAND="radio"

say() { printf '%s\n' "$*"; }
fail() { printf '%s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

run() {
    say "  \$ $*"
    "$@"
}

# Root already has the rights, and a container often has no sudo at all.
if [ "$(id -u)" = "0" ]; then
    SUDO=""
elif have sudo; then
    SUDO="sudo"
else
    SUDO=""
fi

as_root() {
    if [ -n "${SUDO}" ]; then
        run "${SUDO}" "$@"
    else
        run "$@"
    fi
}

install_mpv() {
    if have brew; then
        # Homebrew owns a user writable prefix, so this needs no password.
        run brew install mpv
    elif have apt-get; then
        as_root apt-get update
        as_root apt-get install -y mpv
    elif have dnf; then
        as_root dnf install -y mpv
    elif have pacman; then
        as_root pacman -S --noconfirm mpv
    elif have zypper; then
        as_root zypper install -y mpv
    elif have apk; then
        as_root apk add mpv
    else
        say ""
        say "No package manager was recognised, so mpv has to be installed by hand:"
        say "  https://mpv.io/installation/"
        return 1
    fi
}

# uv owns the tool environment, so the app never touches the system Python.
if ! have uv; then
    say "Installing uv, which will hold ${COMMAND} in its own environment."
    curl -LsSf https://astral.sh/uv/install.sh | sh || fail "Could not install uv."

    for candidate in "${XDG_BIN_HOME:-}" "${HOME}/.local/bin" "${CARGO_HOME:-${HOME}/.cargo}/bin"; do
        if [ -n "${candidate}" ] && [ -x "${candidate}/uv" ]; then
            PATH="${candidate}:${PATH}"
            export PATH
            break
        fi
    done

    have uv || fail "uv was installed but is not on PATH. Open a new shell and run this again."
fi

if have mpv; then
    say "mpv is already installed."
elif [ "${RADIO_SKIP_MPV:-0}" = "1" ]; then
    say "Skipping mpv, as asked."
else
    say "Installing mpv, which ${COMMAND} plays through."
    install_mpv || say "Carrying on without it. ${COMMAND} will not play until mpv is installed."
fi

say "Installing ${PACKAGE}."
run uv tool install --force "${PACKAGE}"

if ! have "${COMMAND}"; then
    say ""
    say "${COMMAND} was installed, but its directory is not on PATH yet."
    say "Run this, then open a new shell:"
    say ""
    say "  uv tool update-shell"
fi

say ""
say "Done. Run ${COMMAND} to start listening."
