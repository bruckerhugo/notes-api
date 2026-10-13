"""PyInstaller entry point for the standalone desktop app."""

import sys

from desktop.app import main

if __name__ == "__main__":
    sys.exit(main())
