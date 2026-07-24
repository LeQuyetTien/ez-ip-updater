"""Atomic per-provider state storage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


class StateStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._state = self._load()

    def _load(self) -> dict[str, str]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}

    def get(self, key: str, fallback: Optional[str] = None) -> Optional[str]:
        value = self._state.get(key)
        return value if isinstance(value, str) else fallback

    def set(self, key: str, value: str) -> None:
        self._state[key] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(
            json.dumps(self._state, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)
