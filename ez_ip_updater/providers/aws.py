"""AWS Security Group reconciliation."""

from __future__ import annotations

import logging
from typing import Any, Optional

try:
    import boto3
    from botocore.exceptions import ClientError

    AWS_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on optional installation
    boto3 = None
    ClientError = Exception
    AWS_AVAILABLE = False


class AWSUpdater:
    def __init__(
        self,
        config: dict[str, Any],
        logger: logging.Logger,
        dry_run: bool = False,
        profile: Optional[str] = None,
    ):
        self.config = config
        self.logger = logger
        self.dry_run = dry_run
        self.profile = profile or config.get("profile")

    def update_security_groups(
        self, old_ip: Optional[str], new_ip: str
    ) -> bool:
        groups_present = bool(
            self.config.get("security_groups_ssh")
            or self.config.get("security_groups_mysql")
        )
        if not groups_present:
            return True
        if not AWS_AVAILABLE:
            self.logger.error("Boto3 chưa được cài đặt")
            return False

        results = [
            self._update_security_group_type(
                old_ip,
                new_ip,
                self.config.get("security_groups_ssh", []),
                self.config.get("ports_ssh", []),
                "SSH",
            ),
            self._update_security_group_type(
                old_ip,
                new_ip,
                self.config.get("security_groups_mysql", []),
                self.config.get("ports_mysql", []),
                "MySQL",
            ),
        ]
        return all(results)

    def _client(self) -> Any:
        region = self.config["region"]
        if self.profile:
            return boto3.Session(profile_name=self.profile).client(
                "ec2", region_name=region
            )
        return boto3.client("ec2", region_name=region)

    def _update_security_group_type(
        self,
        old_ip: Optional[str],
        new_ip: str,
        security_groups: list[dict[str, Any]],
        ports: list[dict[str, Any]],
        group_type: str,
    ) -> bool:
        if not security_groups:
            return True
        if not ports:
            self.logger.error("%s có security group nhưng không có port rule", group_type)
            return False
        try:
            client = self._client()
            results = [
                self._update_single_security_group(
                    client, group, old_ip, new_ip, ports, group_type
                )
                for group in security_groups
            ]
            return all(results)
        except Exception as exc:
            self.logger.error("✗ Lỗi AWS Security Groups %s: %s", group_type, exc)
            return False

    def _update_single_security_group(
        self,
        ec2: Any,
        group: dict[str, Any],
        old_ip: Optional[str],
        new_ip: str,
        ports: list[dict[str, Any]],
        group_type: str,
    ) -> bool:
        group_id = group["group_id"]
        try:
            # Add first. Losing access is worse than briefly having both IPs.
            self._authorize_new_rules(
                ec2, group_id, new_ip, ports, group.get("description", "")
            )
            if old_ip and old_ip != new_ip:
                self._revoke_old_rules(ec2, group_id, old_ip, ports)
            self.logger.info(
                "✓ Đã reconcile AWS Security Group %s: %s",
                group_type,
                group_id,
            )
            return True
        except ClientError as exc:
            self.logger.error(
                "✗ Lỗi khi reconcile %s %s: %s", group_type, group_id, exc
            )
            return False

    @staticmethod
    def _permission(ip: str, rule: dict[str, Any], description: str = "") -> dict:
        ip_range = {"CidrIp": f"{ip}/32"}
        if description:
            ip_range["Description"] = description[:255]
        return {
            "IpProtocol": rule["protocol"],
            "FromPort": int(rule["port"]),
            "ToPort": int(rule.get("to_port", rule["port"])),
            "IpRanges": [ip_range],
        }

    def _authorize_new_rules(
        self,
        ec2: Any,
        group_id: str,
        new_ip: str,
        ports: list[dict[str, Any]],
        group_description: str,
    ) -> None:
        for rule in ports:
            if self.dry_run:
                self.logger.info(
                    "[DRY-RUN] Sẽ thêm %s/32 port %s", new_ip, rule["port"]
                )
                continue
            description = " - ".join(filter(None, (
                str(rule.get("description", "")),
                group_description,
            )))
            try:
                ec2.authorize_security_group_ingress(
                    GroupId=group_id,
                    IpPermissions=[self._permission(new_ip, rule, description)],
                )
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code")
                if code != "InvalidPermission.Duplicate":
                    raise

    def _revoke_old_rules(
        self,
        ec2: Any,
        group_id: str,
        old_ip: str,
        ports: list[dict[str, Any]],
    ) -> None:
        for rule in ports:
            if self.dry_run:
                self.logger.info(
                    "[DRY-RUN] Sẽ xoá %s/32 port %s", old_ip, rule["port"]
                )
                continue
            try:
                ec2.revoke_security_group_ingress(
                    GroupId=group_id,
                    IpPermissions=[self._permission(old_ip, rule)],
                )
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code")
                if code != "InvalidPermission.NotFound":
                    raise
