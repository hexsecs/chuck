#!/bin/sh
# Link chuck's agent profiles for one runtime, without overwriting user files.
# Usage: sh deploy.sh claude|opencode [agents-directory]
#   claude   -> agents/claude/*.md   into ~/.claude/agents
#   opencode -> agents/opencode/*.md into ${XDG_CONFIG_HOME:-~/.config}/opencode/agents
set -eu
runtime=${1:-}
case $runtime in
  claude) default=$HOME/.claude/agents ;;
  opencode) default=${XDG_CONFIG_HOME:-$HOME/.config}/opencode/agents ;;
  *) echo "Usage: sh deploy.sh claude|opencode [agents-directory]" >&2; exit 2 ;;
esac
src=$(CDPATH= cd -- "$(dirname -- "$0")/agents/$runtime" && pwd -P)
dest=${2:-$default}

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
