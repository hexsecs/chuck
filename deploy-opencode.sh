#!/bin/sh
# Link optional native profiles, without overwriting user files.
# Usage: sh chuck/deploy-opencode.sh [agents-directory]
set -eu
src=$(CDPATH= cd -- "$(dirname -- "$0")/opencode/agents" && pwd -P)
dest=${1:-${XDG_CONFIG_HOME:-$HOME/.config}/opencode/agents}

# Check all conflicts before installing any profiles.
for file in "$src"/*.md; do
  target="$dest/${file##*/}"
  if [ -e "$target" ] || [ -L "$target" ]; then
    if [ ! -L "$target" ] || [ "$(readlink "$target")" != "$file" ]; then
      echo "Refusing to overwrite: $target" >&2
      exit 1
    fi
  fi
done
mkdir -p "$dest"
for file in "$src"/*.md; do
  target="$dest/${file##*/}"
  if [ ! -L "$target" ]; then
    ln -s "$file" "$target"
  fi
  printf '%s -> %s\n' "$target" "$file"
done
