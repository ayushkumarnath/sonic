#!/usr/bin/env bash

set -u

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SRC_BINARY="$SCRIPT_DIR/dist/sonic"
TARGET_DIR="${HOME:?HOME must be set}/.local/bin"
TARGET_BINARY="$TARGET_DIR/sonic"

if [[ ! -f "$SRC_BINARY" || ! -x "$SRC_BINARY" ]]; then
  printf "Error: packaged SONIC executable not found at '%s'\n" "$SRC_BINARY" >&2
  printf "Build the Python application with PyInstaller before running this installer.\n" >&2
  exit 1
fi

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
