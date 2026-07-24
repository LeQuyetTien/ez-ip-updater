"""Application orchestration."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional

from .config import Config
from .ip_service import IPService
from .logging_utils import setup_logger
from .providers.aws import AWSUpdater
from .providers.gcp import GCPUpdater
from .state import StateStore


class IPUpdater:
    def __init__(
        self,
        config_path: str,
        dry_run: bool = False,
        verbose: bool = False,
        custom_ip: Optional[str] = None,
        aws_profile: Optional[str] = None,
    ):
        self.dry_run = dry_run
        self.custom_ip = custom_ip
        self.config = Config(config_path)
        self.logger = self._setup_logger(
            verbose, self.config.path.parent / "ip_update.log"
        )
        self.ip_service = IPService(self.logger)
        self.state = StateStore(self.config.state_file)
        self.gcp_updater = GCPUpdater(self.config.gcp, self.logger, dry_run)
        self.aws_updater = AWSUpdater(
            self.config.aws, self.logger, dry_run, aws_profile
        )

    @staticmethod
    def _setup_logger(verbose: bool, log_file: Path) -> logging.Logger:
        return setup_logger(verbose, log_file)

    def _reconcile_component(
        self,
        key: str,
        current_ip: str,
        force: bool,
        update: Callable[[Optional[str], str], bool],
    ) -> bool:
        previous_ip = self.state.get(key)
        if previous_ip == current_ip and not force:
            self.logger.info("✓ %s đã dùng IP %s", key, current_ip)
            return True
        successful = update(previous_ip, current_ip)
        if successful and not self.dry_run:
            self.state.set(key, current_ip)
        return successful

    def run(self, force: bool = False) -> int:
        current_ip = self.ip_service.resolve(self.custom_ip)
        if current_ip is None:
            return 1

        results: list[bool] = []
        gcp = self.config.gcp
        if Config.provider_enabled(gcp, ("firewall_rules", "sql_instances")):
            if gcp.get("firewall_rules"):
                results.append(self._reconcile_component(
                    "gcp_firewall",
                    current_ip,
                    force,
                    self.gcp_updater.update_firewall_rules,
                ))
            if gcp.get("sql_instances"):
                results.append(self._reconcile_component(
                    "gcp_sql",
                    current_ip,
                    force,
                    self.gcp_updater.update_cloud_sql,
                ))

        aws = self.config.aws
        if Config.provider_enabled(
            aws, ("security_groups_ssh", "security_groups_mysql")
        ):
            results.append(self._reconcile_component(
                "aws",
                current_ip,
                force,
                self.aws_updater.update_security_groups,
            ))

        successful = all(results)
        if successful:
            self.logger.info("✓ Hoàn thành reconcile IP %s", current_ip)
        else:
            self.logger.error("✗ Một hoặc nhiều provider cập nhật thất bại")
        return 0 if successful else 1
