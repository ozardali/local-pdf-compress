#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

print_done() {
  echo
  echo "Setup is complete."
  echo "Ghostscript is ready."
  echo
  echo "How to start the app:"
  echo "  1. Double-click start.command"
  echo "  2. Or run: python3 server.py"
  echo
  echo "Your browser should open http://127.0.0.1:8765"
}

if command -v gs >/dev/null 2>&1; then
  echo "Ghostscript is already installed."
  print_done
  exit 0
fi

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is not installed."
  echo "Install Homebrew from https://brew.sh"
  echo "Then run this script again: ./setup.sh"
  exit 1
fi

echo "Installing Ghostscript with Homebrew..."
brew install ghostscript

if command -v gs >/dev/null 2>&1; then
  print_done
  exit 0
fi

echo "Setup did not finish. Ghostscript is still missing."
echo "Try: brew install ghostscript"
exit 1
