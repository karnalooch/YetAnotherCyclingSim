"""Isolated Julka entrypoint; no production YACS modules are imported."""

from julka_core.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
