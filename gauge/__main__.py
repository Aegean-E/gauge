"""Allow `python -m gauge` as the command-line entry point."""

import sys

from gauge.cli import main

if __name__ == "__main__":
    sys.exit(main())
