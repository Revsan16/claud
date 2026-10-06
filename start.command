#!/bin/zsh
# Double-click to start. Close the window or press Control-C to stop.
cd "$(dirname "$0")" || exit 1

if [ ! -x ".venv/bin/python" ]; then
  echo ""
  echo "  Not set up yet. Double-click setup.command first."
  echo ""
  read "?  Press Return to close."
  exit 1
fi

# Finder-launched scripts get a bare PATH; the summary step needs `claude`.
export PATH="$HOME/.local/bin:/usr/local/bin:/opt/homebrew/bin:$PATH"

./.venv/bin/python server.py
