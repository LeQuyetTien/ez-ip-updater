"""Public IPv4 discovery."""

from __future__ import annotations

import logging
from ipaddress import IPv4Address
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class IPService:
    IP_SERVICES = (
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://icanhazip.com",
    )

    def __init__(
        self,
        logger: logging.Logger,
        session: requests.Session | None = None,
    ):
        self.logger = logger
        self.session = session or self._build_session()
        self.session.headers.setdefault("User-Agent", "ez-ip-updater/2.1")

    @staticmethod
    def _build_session() -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=2,
            connect=2,
            read=2,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
        )
        session.mount("https://", HTTPAdapter(max_retries=retry))
        return session

    @staticmethod
    def validate_ipv4(value: str) -> str:
        return str(IPv4Address(value.strip()))

    def get_current_ip(self) -> Optional[str]:
        for service in self.IP_SERVICES:
            try:
                response = self.session.get(service, timeout=(3.05, 5))
                response.raise_for_status()
                ip = self.validate_ipv4(response.text)
                self.logger.info("✓ Phát hiện IP công cộng: %s", ip)
                return ip
            except (requests.RequestException, ValueError) as exc:
                self.logger.debug("Service %s thất bại: %s", service, exc)
        self.logger.error("✗ Không thể lấy IPv4 công cộng hợp lệ")
        return None

    def resolve(self, custom_ip: Optional[str] = None) -> Optional[str]:
        if custom_ip:
            ip = self.validate_ipv4(custom_ip)
            self.logger.info("🎯 Sử dụng custom IP: %s", ip)
            return ip
        return self.get_current_ip()
