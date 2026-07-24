"""Google Cloud firewall and Cloud SQL reconciliation."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    from google.cloud import compute_v1
    from google.oauth2 import service_account

    GCP_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on optional installation
    compute_v1 = None
    service_account = None
    GCP_AVAILABLE = False

try:
    from googleapiclient import discovery
    from googleapiclient.errors import HttpError

    GOOGLE_API_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on optional installation
    discovery = None
    HttpError = Exception
    GOOGLE_API_AVAILABLE = False


class GCPUpdater:
    def __init__(
        self,
        config: dict[str, Any],
        logger: logging.Logger,
        dry_run: bool = False,
    ):
        self.config = config
        self.logger = logger
        self.dry_run = dry_run
        self.credentials = self._load_credentials()

    def _load_credentials(self) -> Any:
        if not GCP_AVAILABLE:
            return None
        credentials_file = self.config.get("credentials_file")
        if not credentials_file:
            return None
        path = Path(credentials_file)
        if not path.is_file():
            self.logger.warning("Không tìm thấy GCP credentials: %s", path)
            return None
        try:
            return service_account.Credentials.from_service_account_file(str(path))
        except Exception as exc:
            self.logger.warning("Không thể load GCP credentials %s: %s", path, exc)
            return None

    def update_firewall_rules(
        self, old_ip: Optional[str], new_ip: str
    ) -> bool:
        rules = self.config.get("firewall_rules", [])
        if not rules:
            return True
        if not GCP_AVAILABLE:
            self.logger.error("Google Cloud SDK chưa được cài đặt")
            return False
        try:
            kwargs = {"credentials": self.credentials} if self.credentials else {}
            client = compute_v1.FirewallsClient(**kwargs)
            results = [
                self._update_single_firewall_rule(
                    client,
                    self.config["project_id"],
                    rule_name,
                    old_ip,
                    new_ip,
                )
                for rule_name in rules
            ]
            return all(results)
        except Exception as exc:
            self.logger.error("✗ Lỗi GCP Firewall: %s", exc)
            return False

    def _update_single_firewall_rule(
        self,
        client: Any,
        project_id: str,
        rule_name: str,
        old_ip: Optional[str],
        new_ip: str,
    ) -> bool:
        try:
            firewall = client.get(project=project_id, firewall=rule_name)
            original = list(firewall.source_ranges)
            old_cidr = f"{old_ip}/32" if old_ip else None
            new_cidr = f"{new_ip}/32"

            desired = [
                value for value in original
                if not old_cidr or value != old_cidr
            ]
            if new_cidr not in desired:
                desired.append(new_cidr)

            if desired == original:
                self.logger.info("Firewall rule %s đã đúng trạng thái", rule_name)
                return True
            if self.dry_run:
                self.logger.info("[DRY-RUN] Sẽ cập nhật firewall rule: %s", rule_name)
                return True

            firewall.source_ranges = desired
            operation = client.update(
                project=project_id,
                firewall=rule_name,
                firewall_resource=firewall,
            )
            operation.result(timeout=120)
            self.logger.info("✓ Đã cập nhật GCP Firewall rule: %s", rule_name)
            return True
        except Exception as exc:
            self.logger.error("✗ Lỗi khi cập nhật firewall %s: %s", rule_name, exc)
            return False

    def update_cloud_sql(self, old_ip: Optional[str], new_ip: str) -> bool:
        instances = self.config.get("sql_instances", [])
        if not instances:
            return True
        if not GOOGLE_API_AVAILABLE:
            self.logger.error("Google API Python Client chưa được cài đặt")
            return False
        try:
            kwargs = {"credentials": self.credentials} if self.credentials else {}
            service = discovery.build(
                "sqladmin",
                "v1beta4",
                cache_discovery=False,
                **kwargs,
            )
            results = [
                self._update_single_sql_instance(
                    service,
                    self.config["project_id"],
                    instance_name,
                    old_ip,
                    new_ip,
                )
                for instance_name in instances
            ]
            return all(results)
        except Exception as exc:
            self.logger.error("✗ Lỗi Cloud SQL: %s", exc)
            return False

    def _update_single_sql_instance(
        self,
        service: Any,
        project_id: str,
        instance_name: str,
        old_ip: Optional[str],
        new_ip: str,
    ) -> bool:
        try:
            instance = service.instances().get(
                project=project_id,
                instance=instance_name,
            ).execute()
            settings = instance.get("settings", {})
            ip_config = settings.get("ipConfiguration", {})
            original = list(ip_config.get("authorizedNetworks", []))

            old_values = {old_ip, f"{old_ip}/32"} if old_ip else set()
            desired = [
                network for network in original
                if network.get("value") not in old_values
            ]
            new_values = {new_ip, f"{new_ip}/32"}
            if not any(network.get("value") in new_values for network in desired):
                desired.append({
                    "value": new_ip,
                    "name": "ez-ip-updater-"
                    + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"),
                })

            if desired == original:
                self.logger.info("Cloud SQL %s đã đúng trạng thái", instance_name)
                return True
            if self.dry_run:
                self.logger.info("[DRY-RUN] Sẽ cập nhật Cloud SQL: %s", instance_name)
                return True

            body: dict[str, Any] = {
                "settings": {
                    "ipConfiguration": {"authorizedNetworks": desired}
                }
            }
            if "settingsVersion" in settings:
                body["settings"]["settingsVersion"] = settings["settingsVersion"]
            service.instances().patch(
                project=project_id,
                instance=instance_name,
                body=body,
            ).execute()
            self.logger.info("✓ Đã cập nhật Cloud SQL: %s", instance_name)
            return True
        except HttpError as exc:
            status = getattr(getattr(exc, "resp", None), "status", None)
            if status == 404:
                self.logger.warning("Không tìm thấy Cloud SQL: %s", instance_name)
            else:
                self.logger.error("✗ Lỗi Cloud SQL %s: %s", instance_name, exc)
            return False
        except Exception as exc:
            self.logger.error("✗ Lỗi Cloud SQL %s: %s", instance_name, exc)
            return False
