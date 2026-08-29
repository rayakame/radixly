"""``uv run python -m benchmarks`` — the suite's only entry point."""

from __future__ import annotations

import sys

from benchmarks import cli

if __name__ == "__main__":
    sys.exit(cli.main(sys.argv[1:]))
