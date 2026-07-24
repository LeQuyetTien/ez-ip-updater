"""EZ IP Updater public API."""

from .config import Config
from .ip_service import IPService
from .orchestrator import IPUpdater
from .providers.aws import AWSUpdater, AWS_AVAILABLE
from .providers.gcp import (
    GCPUpdater,
    GCP_AVAILABLE,
    GOOGLE_API_AVAILABLE,
)

__all__ = [
    "AWSUpdater",
    "AWS_AVAILABLE",
    "Config",
    "GCPUpdater",
    "GCP_AVAILABLE",
    "GOOGLE_API_AVAILABLE",
    "IPService",
    "IPUpdater",
]

__version__ = "2.1.0"
