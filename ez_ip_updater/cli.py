"""Command-line entrypoint."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Optional, Sequence

from . import __version__
from .config import Config
from .locking import AlreadyRunningError, ProcessLock
from .orchestrator import IPUpdater


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Tự động cập nhật IPv4 công cộng vào GCP/AWS"
    )
    parser.add_argument("-c", "--config", default="config.json")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--custom-ip")
    parser.add_argument("--aws-profile")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument(
        "--version",
        action="version",
        version=f"EZ IP Updater {__version__}",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config_path = Path(args.config).expanduser().resolve()
        config = Config(config_path)
        with ProcessLock(config.lock_file):
            updater = IPUpdater(
                config_path=str(config_path),
                dry_run=args.dry_run,
                verbose=args.verbose,
                custom_ip=args.custom_ip,
                aws_profile=args.aws_profile,
            )
            return updater.run(force=args.force)
    except AlreadyRunningError as exc:
        logging.info("%s; bỏ qua lần chạy này", exc)
        return 0
    except (FileNotFoundError, ValueError) as exc:
        logging.error("%s", exc)
        return 2
    except Exception:
        logging.exception("Lỗi nghiêm trọng")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
