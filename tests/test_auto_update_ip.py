import os
import pytest
from unittest.mock import Mock, patch
import json

# Mock config before importing the module to prevent load_config from running at import time
TEST_CONFIG = {
    "gcp": {
        "project_id": "test-project",
        "credentials_file": "test-credentials.json",
        "firewall_rules": ["test-rule"],
        "sql_instances": ["test-instance"]
    },
    "aws": {
        "region": "us-east-1",
        "security_groups_ssh": [{"group_id": "sg-test", "description": "Test"}],
        "security_groups_mysql": [{"group_id": "sg-test-mysql", "description": "Test MySQL"}],
        "ports_ssh": [{"protocol": "tcp", "port": 22, "description": "SSH"}],
        "ports_mysql": [{"protocol": "tcp", "port": 3306, "description": "MySQL"}]
    },
    "ip_cache_file": "test_cache.txt"
}

with patch('builtins.open', create=True) as mock_open:
    mock_open.return_value.__enter__ = lambda s: s
    mock_open.return_value.__exit__ = Mock()
    mock_open.return_value.read.return_value = json.dumps(TEST_CONFIG)
    import auto_update_ip as mod
    # Override the loaded config with our test config
    mod.CONFIG = TEST_CONFIG
    mod.GCP_PROJECT_ID = TEST_CONFIG['gcp']['project_id']
    mod.GCP_CREDENTIALS_FILE = TEST_CONFIG['gcp']['credentials_file']
    mod.GCP_FIREWALL_RULES = TEST_CONFIG['gcp']['firewall_rules']
    mod.GCP_SQL_INSTANCES = TEST_CONFIG['gcp']['sql_instances']
    mod.AWS_REGION = TEST_CONFIG['aws']['region']
    mod.AWS_SECURITY_GROUPS_SSH = TEST_CONFIG['aws']['security_groups_ssh']
    mod.AWS_SECURITY_GROUPS_MYSQL = TEST_CONFIG['aws']['security_groups_mysql']
    mod.PORTS_TO_OPEN_SSH = TEST_CONFIG['aws']['ports_ssh']
    mod.PORTS_TO_OPEN_MYSQL = TEST_CONFIG['aws']['ports_mysql']
    mod.IP_CACHE_FILE = TEST_CONFIG['ip_cache_file']


def test_get_public_ip_success(monkeypatch):
    class Resp:
        status_code = 200
        text = "1.2.3.4\n"

    monkeypatch.setattr(mod, 'requests', Mock(get=Mock(return_value=Resp())))
    assert mod.get_public_ip() == "1.2.3.4"


def test_get_public_ip_all_fail(monkeypatch):
    def fail(*args, **kwargs):
        raise Exception("network")

    monkeypatch.setattr(mod, 'requests', Mock(get=fail))
    assert mod.get_public_ip() is None


def test_cache_save_and_get(tmp_path, monkeypatch):
    temp_file = tmp_path / "cached_ip.txt"
    monkeypatch.setattr(mod, 'IP_CACHE_FILE', str(temp_file))

    mod.save_cached_ip('9.8.7.6')
    assert mod.get_cached_ip() == '9.8.7.6'


def test_update_gcp_cloud_sql_skips_when_discovery_missing(caplog, monkeypatch):
    # Simulate googleapiclient not installed
    monkeypatch.setattr(mod, 'discovery', None)

    with caplog.at_level('WARNING'):
        mod.update_gcp_cloud_sql(None, '1.2.3.4')
        # When discovery is None, the early-return warning is logged
        assert any('googleapiclient' in rec.message and ('bỏ qua' in rec.message or 'Cloud SQL' in rec.message) for rec in caplog.records)


def test_update_gcp_firewall_rules_handles_missing_credentials(caplog, monkeypatch):
    # Make the compute client constructor raise (simulate missing ADC)
    def bad_constructor(*args, **kwargs):
        raise Exception('ADC missing')

    monkeypatch.setattr(mod.compute_v1, 'FirewallsClient', bad_constructor)

    with caplog.at_level('ERROR'):
        mod.update_gcp_firewall_rules(None, '1.2.3.4')
        assert any('Lỗi GCP Firewall' in rec.message for rec in caplog.records)


def test_update_aws_security_groups_duplicate_rule_logged(caplog, monkeypatch):
    # Build a fake ec2 client where authorize raises ClientError with Duplicate code
    ClientError = getattr(mod, 'ClientError')

    class FakeEC2:
        def revoke_security_group_ingress(self, **kwargs):
            return None

        def authorize_security_group_ingress(self, **kwargs):
            raise ClientError({"Error": {"Code": "InvalidPermission.Duplicate", "Message": "Duplicate"}}, "AuthorizeSecurityGroupIngress")

    def fake_boto3_client(service_name, **kwargs):
        return FakeEC2()

    monkeypatch.setattr(mod, 'boto3', Mock(client=fake_boto3_client))

    with caplog.at_level('INFO'):
        mod.update_aws_security_groups_ssh(None, '1.2.3.4')
        assert any('Rule đã tồn tại' in rec.message or 'Rule đã tồn tại cho port' in rec.message for rec in caplog.records)
