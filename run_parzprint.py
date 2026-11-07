"""Lançador usado pelo PyInstaller (o pacote usa imports relativos)."""
import sys

from parzprint.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
