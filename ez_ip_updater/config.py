"""Configuration loading and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class Config:
    """Load and validate an EZ IP Updater configuration."""

    def __init__(self, config_path: str | Path = "config.json"):
        self.path = Path(config_path).expanduser().resolve()
        self.config_path = str(self.path)
        self._data = self._load()

    def _load(self) -> dict[str, Any]:
        try:
            with self.path.open(encoding="utf-8") as file:
                data = json.load(file)
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                f"File cấu hình '{self.path}' không tồn tại. "
                "Tạo file từ config.json.example."
            ) from exc
        except json.JSONDecodeError as exc:
            raise ValueError(f"File cấu hình không hợp lệ: {exc}") from exc
        self._validate(data)
        return data

    @staticmethod
    def _validate(data: Any) -> None:
        if not isinstance(data, dict):
            raise ValueError("Cấu hình gốc phải là object")

        for provider in ("gcp", "aws"):
            section = data.get(provider, {})
            if not isinstance(section, dict):
                raise ValueError(f"Section '{provider}' phải là object")

        gcp = data.get("gcp", {})
        gcp_enabled = gcp.get("enabled", bool(
            gcp.get("firewall_rules") or gcp.get("sql_instances")
        ))
        if gcp_enabled and not gcp.get("project_id"):
            raise ValueError("Missing required field: gcp.project_id")

        aws = data.get("aws", {})
        aws_enabled = aws.get("enabled", bool(
            aws.get("security_groups_ssh") or aws.get("security_groups_mysql")
        ))
        if aws_enabled and not aws.get("region"):
            raise ValueError("Missing required field: aws.region")

        for group_key in ("security_groups_ssh", "security_groups_mysql"):
            groups = aws.get(group_key, [])
            if not isinstance(groups, list):
                raise ValueError(f"aws.{group_key} phải là array")
            for group in groups:
                if not isinstance(group, dict):
                    raise ValueError(f"Security group trong {group_key} phải là object")
                if not group.get("group_id"):
                    raise ValueError(
                        f"Security group trong {group_key} thiếu 'group_id'"
                    )

        for ports_key in ("ports_ssh", "ports_mysql"):
            ports = aws.get(ports_key, [])
            if not isinstance(ports, list):
                raise ValueError(f"aws.{ports_key} phải là array")
            for rule in ports:
                if not isinstance(rule, dict):
                    raise ValueError(f"Port rule trong {ports_key} phải là object")
                if "protocol" not in rule or "port" not in rule:
                    raise ValueError(
                        f"Port rule trong {ports_key} cần protocol và port"
                    )

    @property
    def gcp(self) -> dict[str, Any]:
        config = dict(self._data.get("gcp", {}))
        credentials = config.get("credentials_file")
        if credentials:
            path = Path(credentials)
            if not path.is_absolute():
                config["credentials_file"] = str(self.path.parent / path)
        return config

    @property
    def aws(self) -> dict[str, Any]:
        return dict(self._data.get("aws", {}))

    @property
    def state_file(self) -> Path:
        value = Path(self._data.get("state_file", "ip_state.json"))
        return value if value.is_absolute() else self.path.parent / value

    @property
    def lock_file(self) -> Path:
        value = Path(self._data.get("lock_file", ".ip_updater.lock"))
        return value if value.is_absolute() else self.path.parent / value

    @staticmethod
    def provider_enabled(section: dict[str, Any], resource_keys: tuple[str, ...]) -> bool:
        if "enabled" in section:
            return bool(section["enabled"])
        return any(section.get(key) for key in resource_keys)
