#!/usr/bin/env bash

set -u

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SRC_BINARY="$SCRIPT_DIR/dist/sonic"
TARGET_DIR="${HOME:?HOME must be set}/.local/bin"
TARGET_BINARY="$TARGET_DIR/sonic"

PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  printf "Error: Python executable '%s' was not found. Install Python 3 to build SONIC.\n" "$PYTHON" >&2
  exit 1
fi

printf "Preparing the build environment...\n"
BUILD_PYTHON="$SCRIPT_DIR/build/venv/bin/python"
if ! "$PYTHON" -m venv "$SCRIPT_DIR/build/venv"; then
  printf "Error: could not create the build environment. Install Python 3 venv support and try again.\n" >&2
  exit 1
fi
if ! "$BUILD_PYTHON" -m pip install -r "$SCRIPT_DIR/requirements-build.txt"; then
  printf "Error: could not install build dependencies. Check your network connection and try again.\n" >&2
  exit 1
fi

printf "Removing previous SONIC build artifacts...\n"
if ! rm -rf -- "$SRC_BINARY" "$SCRIPT_DIR/build/work" "$SCRIPT_DIR/build/sonic.spec"; then
  printf "Error: could not remove previous build artifacts.\n" >&2
  exit 1
fi

printf "Building SONIC from source...\n"
if ! "$BUILD_PYTHON" -m PyInstaller \
  --clean --noconfirm --onefile --name sonic \
  --specpath "$SCRIPT_DIR/build" \
  --workpath "$SCRIPT_DIR/build/work" \
  --distpath "$SCRIPT_DIR/dist" \
  "$SCRIPT_DIR/sonic.py"; then
  printf "Error: SONIC build failed. See the build output above.\n" >&2
  exit 1
fi
if [[ ! -f "$SRC_BINARY" || ! -x "$SRC_BINARY" ]]; then
  printf "Error: build completed without producing executable '%s'.\n" "$SRC_BINARY" >&2
  exit 1
fi

printf "Checking for FFmpeg tools...\n"
missing_deps=()
for dependency in ffplay ffprobe; do
  if ! command -v "$dependency" >/dev/null 2>&1; then
    missing_deps+=("$dependency")
  fi
done

if ((${#missing_deps[@]})); then
  for dependency in "${missing_deps[@]}"; do
    printf "Warning: dependency '%s' was not found in PATH.\n" "$dependency" >&2
  done
  printf "Install FFmpeg (which provides ffplay and ffprobe) before playing music.\n" >&2
fi

printf "Installing freshly built SONIC to '%s'...\n" "$TARGET_BINARY"
if ! mkdir -p "$TARGET_DIR"; then
  printf "Error: could not create install directory '%s'.\n" "$TARGET_DIR" >&2
  exit 1
fi

if ! cp -- "$SRC_BINARY" "$TARGET_BINARY" || ! chmod 755 "$TARGET_BINARY"; then
  printf "Error: could not install SONIC to '%s'.\n" "$TARGET_BINARY" >&2
  exit 1
fi

printf "Installed SONIC to '%s'.\n" "$TARGET_BINARY"

case ":${PATH:-}:" in
  *":$TARGET_DIR:"*) ;;
  *)
    printf "Add this directory to your PATH to run 'sonic' from anywhere:\n"
    printf '  export PATH="$HOME/.local/bin:$PATH"\n'
    ;;
esac
