"""Entry point: ``python -m traffic_flow <subcommand> ...``."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
