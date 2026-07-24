import json
import logging
import time
from pathlib import Path
from unittest.mock import Mock, call, patch

import pytest
import requests

from ez_ip_updater.config import Config
from ez_ip_updater.ip_service import IPService
from ez_ip_updater.locking import AlreadyRunningError, ProcessLock
from ez_ip_updater.orchestrator import IPUpdater
from ez_ip_updater.providers.aws import AWSUpdater
from ez_ip_updater.providers.gcp import GCPUpdater
from ez_ip_updater.state import StateStore


@pytest.fixture
def logger():
    return logging.getLogger("ez-ip-updater-tests")


@pytest.fixture
def config_data():
    return {
        "gcp": {
            "enabled": True,
            "project_id": "project",
            "firewall_rules": ["office"],
            "sql_instances": ["database"],
        },
        "aws": {
            "enabled": True,
            "region": "ap-southeast-1",
            "security_groups_ssh": [{"group_id": "sg-1"}],
            "security_groups_mysql": [],
            "ports_ssh": [{"protocol": "tcp", "port": 22}],
            "ports_mysql": [],
        },
    }


@pytest.fixture
def config_file(tmp_path, config_data):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config_data))
    return path


def test_config_resolves_local_state_paths(config_file):
    config = Config(config_file)
    assert config.state_file == config_file.parent / "ip_state.json"


def test_config_allows_disabled_empty_providers(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({
        "gcp": {"enabled": False},
        "aws": {"enabled": False},
    }))
    config = Config(path)
    assert not Config.provider_enabled(config.gcp, ("firewall_rules",))


def test_config_requires_project_for_enabled_gcp(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"gcp": {"enabled": True}, "aws": {}}))
    with pytest.raises(ValueError, match="gcp.project_id"):
        Config(path)


def test_config_validates_port_rules(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({
        "gcp": {},
        "aws": {"ports_ssh": [{"port": 22}]},
    }))
    with pytest.raises(ValueError, match="protocol"):
        Config(path)


def test_ip_service_rejects_invalid_response_then_falls_back(logger, tmp_path):
    session = Mock()
    session.headers = {}
    first = Mock(text="<html>error</html>")
    first.raise_for_status.return_value = None
    second = Mock(text="203.0.113.10\n")
    second.raise_for_status.return_value = None
    session.get.side_effect = [first, second]
    service = IPService(logger, session)
    assert service.get_current_ip() == "203.0.113.10"
    assert session.get.call_count == 2


def test_ip_service_rejects_ipv6(logger, tmp_path):
    with pytest.raises(ValueError):
        IPService(logger).validate_ipv4("2001:db8::1")


def test_ip_service_custom_ip_is_validated(logger, tmp_path):
    service = IPService(logger)
    with pytest.raises(ValueError):
        service.resolve("not-an-ip")


def test_state_store_tracks_components_independently(tmp_path):
    state = StateStore(tmp_path / "state.json")
    state.set("aws", "203.0.113.1")
    state.set("gcp_firewall", "203.0.113.2")
    reloaded = StateStore(tmp_path / "state.json")
    assert reloaded.get("aws") == "203.0.113.1"
    assert reloaded.get("gcp_firewall") == "203.0.113.2"


def test_process_lock_blocks_second_process(tmp_path):
    path = tmp_path / "lock"
    with ProcessLock(path):
        with pytest.raises(AlreadyRunningError):
            with ProcessLock(path):
                pass
    assert not path.exists()


def test_process_lock_recovers_stale_lock(tmp_path):
    path = tmp_path / "lock"
    path.write_text(json.dumps({"pid": 1, "created_at": time.time() - 1000}))
    with ProcessLock(path, stale_after=10):
        assert path.exists()
    assert not path.exists()


def test_gcp_firewall_removes_old_even_if_new_exists(logger):
    firewall = Mock(source_ranges=["203.0.113.1/32", "203.0.113.2/32"])
    client = Mock()
    client.get.return_value = firewall
    client.update.return_value.result.return_value = None
    updater = GCPUpdater({"project_id": "p"}, logger)
    assert updater._update_single_firewall_rule(
        client, "p", "office", "203.0.113.1", "203.0.113.2"
    )
    assert firewall.source_ranges == ["203.0.113.2/32"]
    client.update.assert_called_once()


def test_gcp_firewall_noop_does_not_patch(logger):
    firewall = Mock(source_ranges=["203.0.113.2/32"])
    client = Mock()
    client.get.return_value = firewall
    updater = GCPUpdater({"project_id": "p"}, logger)
    assert updater._update_single_firewall_rule(
        client, "p", "office", "203.0.113.1", "203.0.113.2"
    )
    client.update.assert_not_called()


def test_cloud_sql_removes_old_even_if_new_exists(logger):
    service = Mock()
    service.instances().get().execute.return_value = {
        "settings": {
            "settingsVersion": "12",
            "ipConfiguration": {
                "authorizedNetworks": [
                    {"name": "old", "value": "203.0.113.1"},
                    {"name": "new", "value": "203.0.113.2"},
                ]
            },
        }
    }
    updater = GCPUpdater({"project_id": "p"}, logger)
    assert updater._update_single_sql_instance(
        service, "p", "database", "203.0.113.1", "203.0.113.2"
    )
    body = service.instances().patch.call_args.kwargs["body"]
    networks = body["settings"]["ipConfiguration"]["authorizedNetworks"]
    assert networks == [{"name": "new", "value": "203.0.113.2"}]
    assert body["settings"]["settingsVersion"] == "12"


def test_empty_provider_succeeds_without_optional_sdk(logger):
    gcp = GCPUpdater({}, logger)
    aws = AWSUpdater({}, logger)
    with (
        patch("ez_ip_updater.providers.gcp.GCP_AVAILABLE", False),
        patch("ez_ip_updater.providers.gcp.GOOGLE_API_AVAILABLE", False),
        patch("ez_ip_updater.providers.aws.AWS_AVAILABLE", False),
    ):
        assert gcp.update_firewall_rules(None, "203.0.113.2")
        assert gcp.update_cloud_sql(None, "203.0.113.2")
        assert aws.update_security_groups(None, "203.0.113.2")


def test_aws_adds_new_before_removing_old(logger):
    updater = AWSUpdater({"region": "ap-southeast-1"}, logger)
    ec2 = Mock()
    updater._update_single_security_group(
        ec2,
        {"group_id": "sg-1"},
        "203.0.113.1",
        "203.0.113.2",
        [{"protocol": "tcp", "port": 22}],
        "SSH",
    )
    assert ec2.method_calls[0][0] == "authorize_security_group_ingress"
    assert ec2.method_calls[1][0] == "revoke_security_group_ingress"


def test_aws_does_not_revoke_if_authorize_fails(logger):
    from botocore.exceptions import ClientError

    updater = AWSUpdater({"region": "ap-southeast-1"}, logger)
    ec2 = Mock()
    ec2.authorize_security_group_ingress.side_effect = ClientError(
        {"Error": {"Code": "UnauthorizedOperation"}}, "authorize"
    )
    assert not updater._update_single_security_group(
        ec2,
        {"group_id": "sg-1"},
        "203.0.113.1",
        "203.0.113.2",
        [{"protocol": "tcp", "port": 22}],
        "SSH",
    )
    ec2.revoke_security_group_ingress.assert_not_called()


def test_aws_revoke_error_marks_update_failed(logger):
    from botocore.exceptions import ClientError

    updater = AWSUpdater({"region": "ap-southeast-1"}, logger)
    ec2 = Mock()
    ec2.revoke_security_group_ingress.side_effect = ClientError(
        {"Error": {"Code": "UnauthorizedOperation"}}, "revoke"
    )
    assert not updater._update_single_security_group(
        ec2,
        {"group_id": "sg-1"},
        "203.0.113.1",
        "203.0.113.2",
        [{"protocol": "tcp", "port": 22}],
        "SSH",
    )


def test_orchestrator_persists_only_successful_component(config_file):
    updater = IPUpdater(str(config_file))
    with (
        patch.object(updater.ip_service, "resolve", return_value="203.0.113.2"),
        patch.object(updater.gcp_updater, "update_firewall_rules", return_value=True),
        patch.object(updater.gcp_updater, "update_cloud_sql", return_value=False),
        patch.object(updater.aws_updater, "update_security_groups", return_value=True),
    ):
        assert updater.run() == 1
    state = StateStore(config_file.parent / "ip_state.json")
    assert state.get("gcp_firewall") == "203.0.113.2"
    assert state.get("aws") == "203.0.113.2"
    assert state.get("gcp_sql") is None


def test_orchestrator_skips_component_already_current(config_file):
    state = StateStore(config_file.parent / "ip_state.json")
    for key in ("gcp_firewall", "gcp_sql", "aws"):
        state.set(key, "203.0.113.2")
    updater = IPUpdater(str(config_file))
    with (
        patch.object(updater.ip_service, "resolve", return_value="203.0.113.2"),
        patch.object(updater.gcp_updater, "update_firewall_rules") as firewall,
        patch.object(updater.gcp_updater, "update_cloud_sql") as sql,
        patch.object(updater.aws_updater, "update_security_groups") as aws,
    ):
        assert updater.run() == 0
    firewall.assert_not_called()
    sql.assert_not_called()
    aws.assert_not_called()
