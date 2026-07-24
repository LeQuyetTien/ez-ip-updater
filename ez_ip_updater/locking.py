"""Small cross-platform process lock based on atomic file creation."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path


class AlreadyRunningError(RuntimeError):
    pass


class ProcessLock:
    def __init__(self, path: str | Path, stale_after: int = 3600):
        self.path = Path(path)
        self.stale_after = stale_after
        self.acquired = False

    def _is_stale(self) -> bool:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            return time.time() - float(payload["created_at"]) > self.stale_after
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            return True

    def __enter__(self) -> "ProcessLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for attempt in range(2):
            try:
                descriptor = os.open(
                    self.path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o600,
                )
                with os.fdopen(descriptor, "w", encoding="utf-8") as file:
                    json.dump({"pid": os.getpid(), "created_at": time.time()}, file)
                self.acquired = True
                return self
            except FileExistsError:
                if attempt == 0 and self._is_stale():
                    self.path.unlink(missing_ok=True)
                    continue
                raise AlreadyRunningError("EZ IP Updater đang chạy ở process khác")
        raise AlreadyRunningError("Không thể lấy process lock")

    def __exit__(self, *_args: object) -> None:
        if self.acquired:
            self.path.unlink(missing_ok=True)
            self.acquired = False
