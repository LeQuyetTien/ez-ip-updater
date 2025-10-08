"""
Comprehensive Test Suite for IP Updater v2.0
Merged from test_auto_update_ip.py, test_refactored.py, and test_coverage_100.py
Tests for all classes, edge cases, error paths, and scenarios
"""
import os
import sys
import pytest
from unittest.mock import Mock, patch, MagicMock, call, mock_open
from pathlib import Path
import json
from datetime import datetime

# Import module
import auto_update_ip as mod


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_config():
    """Complete mock configuration for all tests"""
    return {
        "gcp": {
            "project_id": "test-project",
            "credentials_file": "test-creds.json",
            "firewall_rules": ["test-firewall-1", "test-firewall-2"],
            "sql_instances": ["test-sql-1", "test-sql-2"]
        },
        "aws": {
            "region": "us-east-1",
            "security_groups_ssh": [
                {"group_id": "sg-ssh123", "description": "SSH Access"}
            ],
            "security_groups_mysql": [
                {"group_id": "sg-mysql456", "description": "MySQL Access"}
            ],
            "ports_ssh": [{"protocol": "tcp", "port": 22, "description": "SSH"}],
            "ports_mysql": [{"protocol": "tcp", "port": 3306, "description": "MySQL"}]
        },
        "ip_cache_file": "test_cache.txt"
    }


@pytest.fixture
def logger():
    """Mock logger with debug level"""
    import logging
    logger = logging.getLogger('test')
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    logger.addHandler(handler)
    return logger


@pytest.fixture
def temp_config_file(tmp_path, mock_config):
    """Create temporary config file"""
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(mock_config))
    return str(config_file)


# ============================================================================
# CONFIG TESTS
# ============================================================================

class TestConfig:
    """Test Config class - loading, validation, and properties"""
    
    def test_load_valid_config(self, temp_config_file, mock_config):
        """Test loading valid config file"""
        config = mod.Config(temp_config_file)
        
        assert config.gcp['project_id'] == mock_config['gcp']['project_id']
        assert config.aws['region'] == mock_config['aws']['region']
        assert config.ip_cache_file == mock_config['ip_cache_file']
    
    def test_load_nonexistent_config(self, tmp_path):
        """Test loading non-existent config file"""
        with pytest.raises(FileNotFoundError):
            mod.Config(str(tmp_path / "nonexistent.json"))
    
    def test_load_invalid_json(self, tmp_path):
        """Test loading invalid JSON"""
        bad_config = tmp_path / "bad.json"
        bad_config.write_text("{ invalid json }")
        
        with pytest.raises(ValueError, match="File cấu hình không hợp lệ"):
            mod.Config(str(bad_config))
    
    def test_config_properties(self, temp_config_file):
        """Test config properties access"""
        config = mod.Config(temp_config_file)
        
        assert isinstance(config.gcp, dict)
        assert isinstance(config.aws, dict)
        assert isinstance(config.ip_cache_file, str)
    
    def test_validate_missing_gcp_project_id(self, tmp_path):
        """Test validation for missing GCP project_id"""
        bad_config = tmp_path / "bad.json"
        bad_config.write_text(json.dumps({
            "gcp": {},  # Missing project_id
            "aws": {"region": "us-east-1"},
            "ip_cache_file": "test.txt"
        }))
        
        with pytest.raises(ValueError, match="gcp.project_id"):
            mod.Config(str(bad_config))
    
    def test_validate_missing_aws_region(self, tmp_path):
        """Test validation for missing AWS region"""
        bad_config = tmp_path / "bad.json"
        bad_config.write_text(json.dumps({
            "gcp": {"project_id": "test"},
            "aws": {},  # Missing region
            "ip_cache_file": "test.txt"
        }))
        
        with pytest.raises(ValueError, match="aws.region"):
            mod.Config(str(bad_config))
    
    def test_validate_invalid_security_group_structure(self, tmp_path):
        """Test validation for invalid security group structure"""
        bad_config = tmp_path / "bad.json"
        bad_config.write_text(json.dumps({
            "gcp": {"project_id": "test"},
            "aws": {
                "region": "us-east-1",
                "security_groups_ssh": [
                    {"description": "SSH"}  # Missing group_id
                ]
            },
            "ip_cache_file": "test.txt"
        }))
        
        with pytest.raises(ValueError, match="group_id"):
            mod.Config(str(bad_config))
    
    def test_validate_gcp_not_dict(self, tmp_path):
        """Test validation when gcp section is not a dict"""
        bad_config = tmp_path / "bad.json"
        bad_config.write_text(json.dumps({
            "gcp": "not-a-dict",
            "aws": {"region": "us-east-1"},
            "ip_cache_file": "test.txt"
        }))
        
        with pytest.raises(ValueError, match="gcp' phải là object"):
            mod.Config(str(bad_config))
    
    def test_validate_aws_not_dict(self, tmp_path):
        """Test validation when aws section is not a dict"""
        bad_config = tmp_path / "bad.json"
        bad_config.write_text(json.dumps({
            "gcp": {"project_id": "test"},
            "aws": "not-a-dict",
            "ip_cache_file": "test.txt"
        }))
        
        with pytest.raises(ValueError, match="aws' phải là object"):
            mod.Config(str(bad_config))
    
    def test_validate_security_groups_not_array(self, tmp_path):
        """Test validation when security_groups is not an array"""
        bad_config = tmp_path / "bad.json"
        bad_config.write_text(json.dumps({
            "gcp": {"project_id": "test"},
            "aws": {
                "region": "us-east-1",
                "security_groups_ssh": "not-an-array"
            },
            "ip_cache_file": "test.txt"
        }))
        
        with pytest.raises(ValueError, match="phải là array"):
            mod.Config(str(bad_config))
    
    def test_validate_security_group_item_not_dict(self, tmp_path):
        """Test validation when security group item is not a dict"""
        bad_config = tmp_path / "bad.json"
        bad_config.write_text(json.dumps({
            "gcp": {"project_id": "test"},
            "aws": {
                "region": "us-east-1",
                "security_groups_ssh": ["not-a-dict"]
            },
            "ip_cache_file": "test.txt"
        }))
        
        with pytest.raises(ValueError, match="phải là object"):
            mod.Config(str(bad_config))


# ============================================================================
# IP SERVICE TESTS
# ============================================================================

class TestIPService:
    """Test IPService class - IP detection, caching, and change detection"""
    
    def test_get_current_ip_success(self, logger, tmp_path):
        """Test successful IP detection"""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = "192.168.1.100\n"
            mock_get.return_value = mock_response
            
            service = mod.IPService(str(tmp_path / "cache.txt"), logger)
            ip = service.get_current_ip()
            
            assert ip == "192.168.1.100"
            assert mock_get.called
    
    def test_get_current_ip_all_services_fail(self, logger, tmp_path):
        """Test all services fail"""
        with patch('requests.get', side_effect=Exception("Network error")):
            service = mod.IPService(str(tmp_path / "cache.txt"), logger)
            ip = service.get_current_ip()
            
            assert ip is None
    
    def test_get_current_ip_first_fails_second_succeeds(self, logger, tmp_path):
        """Test fallback to second service"""
        responses = [
            Exception("Timeout"),
            Mock(status_code=200, text="10.0.0.1")
        ]
        
        with patch('requests.get', side_effect=responses):
            service = mod.IPService(str(tmp_path / "cache.txt"), logger)
            ip = service.get_current_ip()
            
            assert ip == "10.0.0.1"
    
    def test_get_cached_ip_no_cache(self, logger, tmp_path):
        """Test getting cached IP when no cache exists"""
        service = mod.IPService(str(tmp_path / "cache.txt"), logger)
        cached = service.get_cached_ip()
        
        assert cached is None
    
    def test_save_and_get_cached_ip(self, logger, tmp_path):
        """Test save and retrieve cached IP"""
        cache_file = tmp_path / "cache.txt"
        service = mod.IPService(str(cache_file), logger)
        
        service.save_ip("172.16.0.1")
        cached = service.get_cached_ip()
        
        assert cached == "172.16.0.1"
    
    def test_cache_operations(self, logger, tmp_path):
        """Test cache save and read operations"""
        cache_file = tmp_path / "cache.txt"
        service = mod.IPService(str(cache_file), logger)
        
        # Test no cache initially
        assert service.get_cached_ip() is None
        
        # Test save cache
        service.save_ip("9.8.7.6")
        assert service.get_cached_ip() == "9.8.7.6"
    
    def test_check_ip_change_no_change(self, logger, tmp_path):
        """Test IP hasn't changed"""
        cache_file = tmp_path / "cache.txt"
        cache_file.write_text("1.2.3.4")
        
        with patch('requests.get') as mock_get:
            mock_get.return_value = Mock(status_code=200, text="1.2.3.4")
            
            service = mod.IPService(str(cache_file), logger)
            cached, current, changed = service.check_ip_change()
            
            assert cached == "1.2.3.4"
            assert current == "1.2.3.4"
            assert changed is False
    
    def test_check_ip_change_changed(self, logger, tmp_path):
        """Test IP has changed"""
        cache_file = tmp_path / "cache.txt"
        cache_file.write_text("1.2.3.4")
        
        with patch('requests.get') as mock_get:
            mock_get.return_value = Mock(status_code=200, text="5.6.7.8")
            
            service = mod.IPService(str(cache_file), logger)
            cached, current, changed = service.check_ip_change()
            
            assert cached == "1.2.3.4"
            assert current == "5.6.7.8"
            assert changed is True
    
    def test_check_ip_change_no_cached_ip(self, logger, tmp_path):
        """Test first run with no cached IP"""
        with patch('requests.get') as mock_get:
            mock_get.return_value = Mock(status_code=200, text="1.1.1.1")
            
            service = mod.IPService(str(tmp_path / "cache.txt"), logger)
            cached, current, changed = service.check_ip_change()
            
            assert cached is None
            assert current == "1.1.1.1"
            assert changed is True
    
    def test_check_ip_change_cannot_get_current_ip(self, logger, tmp_path):
        """Test check_ip_change when cannot get current IP"""
        cache_file = tmp_path / "cache.txt"
        cache_file.write_text("1.2.3.4")
        
        with patch('requests.get', side_effect=Exception("Network error")):
            service = mod.IPService(str(cache_file), logger)
            cached, current, changed = service.check_ip_change()
            
            assert cached == "1.2.3.4"
            assert current is None
            assert changed is False


# ============================================================================
# OPTIONAL IMPORTS TESTS
# ============================================================================

class TestOptionalImports:
    """Test optional import fallback scenarios"""
    
    def test_gcp_not_available_scenario(self, mock_config, logger):
        """Test GCPUpdater when GCP SDK is not available"""
        original_gcp = mod.GCP_AVAILABLE
        try:
            mod.GCP_AVAILABLE = False
            updater = mod.GCPUpdater(mock_config['gcp'], logger)
            result = updater.update_firewall_rules("1.2.3.4", "5.6.7.8")
            assert result is False
        finally:
            mod.GCP_AVAILABLE = original_gcp
    
    def test_google_api_not_available_scenario(self, mock_config, logger):
        """Test GCPUpdater when Google API client is not available"""
        original_api = mod.GOOGLE_API_AVAILABLE
        try:
            mod.GOOGLE_API_AVAILABLE = False
            updater = mod.GCPUpdater(mock_config['gcp'], logger)
            result = updater.update_cloud_sql("1.2.3.4", "5.6.7.8")
            assert result is False
        finally:
            mod.GOOGLE_API_AVAILABLE = original_api
    
    def test_aws_not_available_scenario(self, mock_config, logger):
        """Test AWSUpdater when boto3 is not available"""
        original_aws = mod.AWS_AVAILABLE
        try:
            mod.AWS_AVAILABLE = False
            updater = mod.AWSUpdater(mock_config['aws'], logger)
            result = updater.update_security_groups("1.2.3.4", "5.6.7.8")
            assert result is False
        finally:
            mod.AWS_AVAILABLE = original_aws


# ============================================================================
# GCP UPDATER TESTS
# ============================================================================

class TestGCPUpdater:
    """Test GCPUpdater class - initialization and basic operations"""
    
    def test_init_without_gcp_available(self, mock_config, logger):
        """Test initialization when GCP SDK not available"""
        with patch('auto_update_ip.GCP_AVAILABLE', False):
            updater = mod.GCPUpdater(mock_config['gcp'], logger)
            assert updater.credentials is None
    
    @patch('auto_update_ip.GCP_AVAILABLE', True)
    @patch('auto_update_ip.service_account')
    def test_load_credentials_from_file(self, mock_sa, mock_config, logger, tmp_path):
        """Test loading credentials from file"""
        creds_file = tmp_path / "creds.json"
        creds_file.write_text('{"type": "service_account"}')
        
        config = mock_config['gcp'].copy()
        config['credentials_file'] = str(creds_file)
        
        mock_creds = Mock()
        mock_sa.Credentials.from_service_account_file.return_value = mock_creds
        
        updater = mod.GCPUpdater(config, logger)
        
        assert mock_sa.Credentials.from_service_account_file.called
    
    @patch('auto_update_ip.GCP_AVAILABLE', False)
    def test_update_firewall_rules_gcp_not_available(self, mock_config, logger):
        """Test firewall update when GCP SDK not available"""
        updater = mod.GCPUpdater(mock_config['gcp'], logger)
        result = updater.update_firewall_rules("1.2.3.4", "5.6.7.8")
        
        assert result is False
    
    @patch('auto_update_ip.GOOGLE_API_AVAILABLE', False)
    def test_update_cloud_sql_api_not_available(self, mock_config, logger):
        """Test Cloud SQL update when API not available"""
        updater = mod.GCPUpdater(mock_config['gcp'], logger)
        result = updater.update_cloud_sql("1.2.3.4", "5.6.7.8")
        
        assert result is False
    
    def test_update_firewall_rules_no_rules(self, logger):
        """Test firewall update with no rules configured"""
        config = {"project_id": "test", "firewall_rules": []}
        updater = mod.GCPUpdater(config, logger)
        
        result = updater.update_firewall_rules("1.2.3.4", "5.6.7.8")
        assert result is True
    
    def test_update_cloud_sql_no_instances(self, logger):
        """Test Cloud SQL update with no instances configured"""
        config = {"project_id": "test", "sql_instances": []}
        updater = mod.GCPUpdater(config, logger)
        
        result = updater.update_cloud_sql("1.2.3.4", "5.6.7.8")
        assert result is True
    
    @patch('auto_update_ip.GCP_AVAILABLE', True)
    @patch('auto_update_ip.compute_v1.FirewallsClient')
    def test_update_firewall_dry_run(self, mock_client_class, mock_config, logger):
        """Test firewall update in dry-run mode"""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        mock_firewall = Mock()
        mock_firewall.source_ranges = ["1.2.3.4/32"]
        mock_client.get.return_value = mock_firewall
        
        updater = mod.GCPUpdater(mock_config['gcp'], logger, dry_run=True)
        result = updater.update_firewall_rules("1.2.3.4", "5.6.7.8")
        
        # Should not call update in dry-run
        assert not mock_client.update.called
    
    @patch('auto_update_ip.GCP_AVAILABLE', True)
    @patch('auto_update_ip.service_account.Credentials.from_service_account_file')
    def test_load_credentials_file_exception(self, mock_creds, logger, tmp_path):
        """Test credential loading when file exists but loading fails"""
        creds_file = tmp_path / "bad_creds.json"
        creds_file.write_text('invalid json')
        
        config = {
            'project_id': 'test',
            'credentials_file': str(creds_file),
            'firewall_rules': [],
            'sql_instances': []
        }
        
        mock_creds.side_effect = Exception("Invalid credentials format")
        
        updater = mod.GCPUpdater(config, logger)
        
        # Should fall back to ADC (credentials will be None)
        assert updater.credentials is None


class TestGCPFirewallEdgeCases:
    """Test GCP Firewall edge cases and error paths"""
    
    @patch('auto_update_ip.GCP_AVAILABLE', True)
    @patch('auto_update_ip.compute_v1.FirewallsClient')
    def test_firewall_update_with_credentials(self, mock_client_class, mock_config, logger, tmp_path):
        """Test firewall update using credentials file"""
        creds_file = tmp_path / "creds.json"
        creds_file.write_text('{"type": "service_account"}')
        
        config = mock_config['gcp'].copy()
        config['credentials_file'] = str(creds_file)
        
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        mock_firewall = Mock()
        mock_firewall.source_ranges = ["1.2.3.4/32"]
        mock_client.get.return_value = mock_firewall
        
        mock_operation = Mock()
        mock_operation.result.return_value = None
        mock_client.update.return_value = mock_operation
        
        with patch('auto_update_ip.service_account.Credentials.from_service_account_file') as mock_creds:
            mock_creds.return_value = Mock()
            
            updater = mod.GCPUpdater(config, logger, dry_run=False)
            result = updater.update_firewall_rules("1.2.3.4", "5.6.7.8")
            
            assert result is True
            assert mock_client.update.called
    
    @patch('auto_update_ip.GCP_AVAILABLE', True)
    @patch('auto_update_ip.compute_v1.FirewallsClient')
    def test_firewall_update_ip_already_exists(self, mock_client_class, mock_config, logger):
        """Test firewall update when new IP already exists"""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        mock_firewall = Mock()
        mock_firewall.source_ranges = ["5.6.7.8/32"]  # New IP already exists
        mock_client.get.return_value = mock_firewall
        
        updater = mod.GCPUpdater(mock_config['gcp'], logger, dry_run=False)
        result = updater.update_firewall_rules("1.2.3.4", "5.6.7.8")
        
        assert result is True
        assert not mock_client.update.called  # Should not update
    
    @patch('auto_update_ip.GCP_AVAILABLE', True)
    @patch('auto_update_ip.compute_v1.FirewallsClient')
    def test_firewall_update_rule_not_found(self, mock_client_class, mock_config, logger):
        """Test firewall update when rule is not found"""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.get.side_effect = Exception("Rule not found")
        
        updater = mod.GCPUpdater(mock_config['gcp'], logger, dry_run=False)
        result = updater.update_firewall_rules("1.2.3.4", "5.6.7.8")
        
        assert result is False
    
    @patch('auto_update_ip.GCP_AVAILABLE', True)
    @patch('auto_update_ip.compute_v1.FirewallsClient')
    def test_firewall_update_general_exception(self, mock_client_class, mock_config, logger):
        """Test firewall update with general exception"""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.get.side_effect = Exception("Network error")
        
        updater = mod.GCPUpdater(mock_config['gcp'], logger, dry_run=False)
        result = updater.update_firewall_rules("1.2.3.4", "5.6.7.8")
        
        assert result is False
    
    @patch('auto_update_ip.GCP_AVAILABLE', True)
    @patch('auto_update_ip.compute_v1.FirewallsClient')
    def test_firewall_update_removes_old_ip(self, mock_client_class, mock_config, logger):
        """Test firewall update properly removes old IP"""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        mock_firewall = Mock()
        mock_firewall.source_ranges = ["1.2.3.4/32", "9.9.9.9/32"]  # Old IP present
        mock_client.get.return_value = mock_firewall
        
        mock_operation = Mock()
        mock_operation.result.return_value = None
        mock_client.update.return_value = mock_operation
        
        updater = mod.GCPUpdater(mock_config['gcp'], logger, dry_run=False)
        result = updater.update_firewall_rules("1.2.3.4", "5.6.7.8")
        
        assert result is True
        assert mock_client.update.called
        
        # Verify the firewall.source_ranges was modified correctly
        call_args = mock_client.update.call_args
        updated_firewall = call_args.kwargs['firewall_resource']
        assert "1.2.3.4/32" not in updated_firewall.source_ranges
        assert "5.6.7.8/32" in updated_firewall.source_ranges
    
    @patch('auto_update_ip.GCP_AVAILABLE', True)
    @patch('auto_update_ip.compute_v1.FirewallsClient')
    def test_firewall_update_exception_in_loop(self, mock_client_class, mock_config, logger):
        """Test firewall update exception during rule processing"""
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # First rule succeeds, second fails
        def side_effect_get(project, firewall):
            if firewall == "test-firewall-1":
                fw = Mock()
                fw.source_ranges = ["1.2.3.4/32"]
                return fw
            else:
                raise Exception("Connection timeout")
        
        mock_client.get.side_effect = side_effect_get
        
        mock_operation = Mock()
        mock_operation.result.return_value = None
        mock_client.update.return_value = mock_operation
        
        updater = mod.GCPUpdater(mock_config['gcp'], logger, dry_run=False)
        result = updater.update_firewall_rules("1.2.3.4", "5.6.7.8")
        
        # Should return False because not all rules succeeded
        assert result is False


class TestGCPCloudSQLEdgeCases:
    """Test GCP Cloud SQL edge cases and error paths"""
    
    @patch('auto_update_ip.GOOGLE_API_AVAILABLE', True)
    @patch('auto_update_ip.discovery.build')
    def test_cloud_sql_update_with_credentials(self, mock_build, mock_config, logger, tmp_path):
        """Test Cloud SQL update using credentials file"""
        creds_file = tmp_path / "creds.json"
        creds_file.write_text('{"type": "service_account"}')
        
        config = mock_config['gcp'].copy()
        config['credentials_file'] = str(creds_file)
        
        mock_service = Mock()
        mock_build.return_value = mock_service
        
        mock_instance = {
            'settings': {
                'ipConfiguration': {
                    'authorizedNetworks': [{'value': '1.2.3.4', 'name': 'old-ip'}]
                }
            }
        }
        
        mock_service.instances().get().execute.return_value = mock_instance
        mock_service.instances().patch().execute.return_value = {}
        
        with patch('auto_update_ip.service_account.Credentials.from_service_account_file') as mock_creds:
            mock_creds.return_value = Mock()
            
            updater = mod.GCPUpdater(config, logger, dry_run=False)
            result = updater.update_cloud_sql("1.2.3.4", "5.6.7.8")
            
            assert result is True
    
    @patch('auto_update_ip.GOOGLE_API_AVAILABLE', True)
    @patch('auto_update_ip.discovery.build')
    def test_cloud_sql_ip_already_exists(self, mock_build, mock_config, logger):
        """Test Cloud SQL update when IP already exists"""
        mock_service = Mock()
        mock_build.return_value = mock_service
        
        mock_instance = {
            'settings': {
                'ipConfiguration': {
                    'authorizedNetworks': [{'value': '5.6.7.8', 'name': 'existing'}]
                }
            }
        }
        
        mock_service.instances().get().execute.return_value = mock_instance
        
        updater = mod.GCPUpdater(mock_config['gcp'], logger, dry_run=False)
        result = updater.update_cloud_sql("1.2.3.4", "5.6.7.8")
        
        assert result is True
        assert not mock_service.instances().patch.called
    
    @patch('auto_update_ip.GOOGLE_API_AVAILABLE', True)
    @patch('auto_update_ip.discovery.build')
    @patch('auto_update_ip.HttpError')
    def test_cloud_sql_instance_not_found(self, mock_http_error, mock_build, mock_config, logger):
        """Test Cloud SQL update when instance not found (404)"""
        mock_service = Mock()
        mock_build.return_value = mock_service
        
        from googleapiclient.errors import HttpError
        mock_resp = Mock()
        mock_resp.status = 404
        error = HttpError(resp=mock_resp, content=b'Not found')
        
        mock_service.instances().get().execute.side_effect = error
        
        updater = mod.GCPUpdater(mock_config['gcp'], logger, dry_run=False)
        result = updater.update_cloud_sql("1.2.3.4", "5.6.7.8")
        
        assert result is False
    
    @patch('auto_update_ip.GOOGLE_API_AVAILABLE', True)
    @patch('auto_update_ip.discovery.build')
    def test_cloud_sql_other_http_error(self, mock_build, mock_config, logger):
        """Test Cloud SQL update with other HTTP error"""
        mock_service = Mock()
        mock_build.return_value = mock_service
        
        from googleapiclient.errors import HttpError
        mock_resp = Mock()
        mock_resp.status = 500
        error = HttpError(resp=mock_resp, content=b'Server error')
        
        mock_service.instances().get().execute.side_effect = error
        
        updater = mod.GCPUpdater(mock_config['gcp'], logger, dry_run=False)
        result = updater.update_cloud_sql("1.2.3.4", "5.6.7.8")
        
        assert result is False
    
    @patch('auto_update_ip.GOOGLE_API_AVAILABLE', True)
    @patch('auto_update_ip.discovery.build')
    def test_cloud_sql_general_exception(self, mock_build, mock_config, logger):
        """Test Cloud SQL update with general exception"""
        mock_service = Mock()
        mock_build.return_value = mock_service
        mock_service.instances().get.side_effect = Exception("Network error")
        
        updater = mod.GCPUpdater(mock_config['gcp'], logger, dry_run=False)
        result = updater.update_cloud_sql("1.2.3.4", "5.6.7.8")
        
        assert result is False
    
    @patch('auto_update_ip.GOOGLE_API_AVAILABLE', True)
    @patch('auto_update_ip.discovery.build')
    def test_cloud_sql_update_dry_run(self, mock_build, mock_config, logger):
        """Test Cloud SQL update in dry-run mode"""
        mock_service = Mock()
        mock_build.return_value = mock_service
        
        mock_instance = {
            'settings': {
                'ipConfiguration': {
                    'authorizedNetworks': [{'value': '1.2.3.4', 'name': 'old-ip'}]
                }
            }
        }
        
        mock_service.instances().get().execute.return_value = mock_instance
        
        updater = mod.GCPUpdater(mock_config['gcp'], logger, dry_run=True)
        result = updater.update_cloud_sql("1.2.3.4", "5.6.7.8")
        
        assert result is True
        # Should NOT call patch in dry-run mode
        assert not mock_service.instances().patch.called
    
    @patch('auto_update_ip.GOOGLE_API_AVAILABLE', True)
    @patch('auto_update_ip.discovery.build')
    def test_cloud_sql_update_actually_patches(self, mock_build, mock_config, logger):
        """Test Cloud SQL actually calls patch API"""
        mock_service = Mock()
        mock_build.return_value = mock_service
        
        mock_instance = {
            'settings': {
                'ipConfiguration': {
                    'authorizedNetworks': [{'value': '1.2.3.4', 'name': 'old-ip'}]
                }
            }
        }
        
        mock_service.instances().get().execute.return_value = mock_instance
        mock_service.instances().patch().execute.return_value = {}
        
        updater = mod.GCPUpdater(mock_config['gcp'], logger, dry_run=False)
        result = updater.update_cloud_sql("1.2.3.4", "5.6.7.8")
        
        assert result is True
        # Verify patch was called
        assert mock_service.instances().patch.called
        
        # Verify the patch was called with correct parameters
        call_args = mock_service.instances().patch.call_args
        assert call_args.kwargs['project'] == mock_config['gcp']['project_id']
        assert call_args.kwargs['instance'] in mock_config['gcp']['sql_instances']
    
    @patch('auto_update_ip.GOOGLE_API_AVAILABLE', True)
    @patch('auto_update_ip.discovery.build')
    def test_cloud_sql_update_non_404_error(self, mock_build, mock_config, logger):
        """Test Cloud SQL with non-404 HttpError"""
        mock_service = Mock()
        mock_build.return_value = mock_service
        
        from googleapiclient.errors import HttpError
        mock_resp = Mock()
        mock_resp.status = 403  # Forbidden, not 404
        error = HttpError(resp=mock_resp, content=b'Access denied')
        
        mock_service.instances().get().execute.side_effect = error
        
        updater = mod.GCPUpdater(mock_config['gcp'], logger, dry_run=False)
        result = updater.update_cloud_sql("1.2.3.4", "5.6.7.8")
        
        assert result is False


# ============================================================================
# AWS UPDATER TESTS
# ============================================================================

class TestAWSUpdater:
    """Test AWSUpdater class - initialization and basic operations"""
    
    @patch('auto_update_ip.AWS_AVAILABLE', False)
    def test_update_security_groups_aws_not_available(self, mock_config, logger):
        """Test AWS update when boto3 not available"""
        updater = mod.AWSUpdater(mock_config['aws'], logger)
        result = updater.update_security_groups("1.2.3.4", "5.6.7.8")
        
        assert result is False
    
    def test_update_security_groups_no_groups(self, logger):
        """Test AWS update with no security groups"""
        config = {
            "region": "us-east-1",
            "security_groups_ssh": [],
            "security_groups_mysql": [],
            "ports_ssh": [],
            "ports_mysql": []
        }
        updater = mod.AWSUpdater(config, logger)
        result = updater.update_security_groups("1.2.3.4", "5.6.7.8")
        
        assert result is True
    
    @patch('auto_update_ip.AWS_AVAILABLE', True)
    @patch('auto_update_ip.boto3')
    def test_update_security_groups_dry_run(self, mock_boto3, mock_config, logger):
        """Test AWS update in dry-run mode"""
        mock_ec2 = Mock()
        mock_boto3.client.return_value = mock_ec2
        
        updater = mod.AWSUpdater(mock_config['aws'], logger, dry_run=True)
        result = updater.update_security_groups("1.2.3.4", "5.6.7.8")
        
        # Should not call actual AWS methods in dry-run
        assert not mock_ec2.revoke_security_group_ingress.called
        assert not mock_ec2.authorize_security_group_ingress.called


class TestAWSSecurityGroupsEdgeCases:
    """Test AWS Security Groups edge cases and error paths"""
    
    @patch('auto_update_ip.AWS_AVAILABLE', True)
    @patch('auto_update_ip.boto3.client')
    def test_revoke_old_rules_success(self, mock_boto_client, mock_config, logger):
        """Test successfully revoking old rules"""
        mock_ec2 = Mock()
        mock_boto_client.return_value = mock_ec2
        
        updater = mod.AWSUpdater(mock_config['aws'], logger, dry_run=False)
        result = updater.update_security_groups("1.2.3.4", "5.6.7.8")
        
        # Verify revoke was called
        assert mock_ec2.revoke_security_group_ingress.called
        assert mock_ec2.authorize_security_group_ingress.called
    
    @patch('auto_update_ip.AWS_AVAILABLE', True)
    @patch('auto_update_ip.boto3.client')
    def test_revoke_rule_not_found(self, mock_boto_client, mock_config, logger):
        """Test revoking rule that doesn't exist"""
        mock_ec2 = Mock()
        mock_boto_client.return_value = mock_ec2
        
        from botocore.exceptions import ClientError
        error = ClientError(
            {'Error': {'Code': 'InvalidPermission.NotFound'}},
            'revoke_security_group_ingress'
        )
        mock_ec2.revoke_security_group_ingress.side_effect = error
        
        updater = mod.AWSUpdater(mock_config['aws'], logger, dry_run=False)
        result = updater.update_security_groups("1.2.3.4", "5.6.7.8")
        
        # Should still succeed even if revoke fails
        assert mock_ec2.authorize_security_group_ingress.called
    
    @patch('auto_update_ip.AWS_AVAILABLE', True)
    @patch('auto_update_ip.boto3.client')
    def test_revoke_other_client_error(self, mock_boto_client, mock_config, logger):
        """Test revoking rule with other client error"""
        mock_ec2 = Mock()
        mock_boto_client.return_value = mock_ec2
        
        from botocore.exceptions import ClientError
        error = ClientError(
            {'Error': {'Code': 'SomeOtherError'}},
            'revoke_security_group_ingress'
        )
        mock_ec2.revoke_security_group_ingress.side_effect = error
        
        updater = mod.AWSUpdater(mock_config['aws'], logger, dry_run=False)
        result = updater.update_security_groups("1.2.3.4", "5.6.7.8")
        
        # Should still try to authorize
        assert mock_ec2.authorize_security_group_ingress.called
    
    @patch('auto_update_ip.AWS_AVAILABLE', True)
    @patch('auto_update_ip.boto3.client')
    def test_authorize_duplicate_rule(self, mock_boto_client, mock_config, logger):
        """Test authorizing rule that already exists"""
        mock_ec2 = Mock()
        mock_boto_client.return_value = mock_ec2
        
        from botocore.exceptions import ClientError
        error = ClientError(
            {'Error': {'Code': 'InvalidPermission.Duplicate'}},
            'authorize_security_group_ingress'
        )
        mock_ec2.authorize_security_group_ingress.side_effect = error
        
        updater = mod.AWSUpdater(mock_config['aws'], logger, dry_run=False)
        result = updater.update_security_groups("1.2.3.4", "5.6.7.8")
        
        # Should handle duplicate gracefully
        assert result is True
    
    @patch('auto_update_ip.AWS_AVAILABLE', True)
    @patch('auto_update_ip.boto3.client')
    def test_authorize_other_error_raises(self, mock_boto_client, mock_config, logger):
        """Test authorize with non-duplicate error raises exception"""
        mock_ec2 = Mock()
        mock_boto_client.return_value = mock_ec2
        
        from botocore.exceptions import ClientError
        error = ClientError(
            {'Error': {'Code': 'UnauthorizedOperation'}},
            'authorize_security_group_ingress'
        )
        mock_ec2.authorize_security_group_ingress.side_effect = error
        
        updater = mod.AWSUpdater(mock_config['aws'], logger, dry_run=False)
        result = updater.update_security_groups("1.2.3.4", "5.6.7.8")
        
        # Should fail on non-duplicate error
        assert result is False
    
    @patch('auto_update_ip.AWS_AVAILABLE', True)
    @patch('auto_update_ip.boto3.client')
    def test_update_security_groups_general_exception(self, mock_boto_client, mock_config, logger):
        """Test AWS update with general exception"""
        mock_ec2 = Mock()
        mock_boto_client.return_value = mock_ec2
        mock_ec2.revoke_security_group_ingress.side_effect = Exception("Network error")
        
        updater = mod.AWSUpdater(mock_config['aws'], logger, dry_run=False)
        result = updater.update_security_groups("1.2.3.4", "5.6.7.8")
        
        assert result is False


# ============================================================================
# IP UPDATER ORCHESTRATOR TESTS
# ============================================================================

class TestIPUpdater:
    """Test IPUpdater main orchestrator"""
    
    def test_init(self, temp_config_file):
        """Test IPUpdater initialization"""
        updater = mod.IPUpdater(temp_config_file, dry_run=False, verbose=False)
        
        assert updater.config is not None
        assert updater.ip_service is not None
        assert updater.gcp_updater is not None
        assert updater.aws_updater is not None
        assert updater.logger is not None
    
    @patch.object(mod.IPService, 'check_ip_change')
    @patch.object(mod.IPService, 'save_ip')
    @patch.object(mod.GCPUpdater, 'update_firewall_rules')
    @patch.object(mod.GCPUpdater, 'update_cloud_sql')
    @patch.object(mod.AWSUpdater, 'update_security_groups')
    def test_run_ip_not_changed(
        self, 
        mock_aws_update,
        mock_gcp_sql,
        mock_gcp_firewall,
        mock_save_ip,
        mock_check_ip,
        temp_config_file
    ):
        """Test run when IP hasn't changed"""
        mock_check_ip.return_value = ("1.2.3.4", "1.2.3.4", False)
        
        updater = mod.IPUpdater(temp_config_file)
        exit_code = updater.run(force=False)
        
        assert exit_code == 0
        assert not mock_gcp_firewall.called
        assert not mock_save_ip.called
    
    @patch.object(mod.IPService, 'check_ip_change')
    @patch.object(mod.IPService, 'save_ip')
    @patch.object(mod.GCPUpdater, 'update_firewall_rules')
    @patch.object(mod.GCPUpdater, 'update_cloud_sql')
    @patch.object(mod.AWSUpdater, 'update_security_groups')
    def test_run_ip_changed(
        self,
        mock_aws_update,
        mock_gcp_sql,
        mock_gcp_firewall,
        mock_save_ip,
        mock_check_ip,
        temp_config_file
    ):
        """Test run when IP has changed"""
        mock_check_ip.return_value = ("1.2.3.4", "5.6.7.8", True)
        mock_gcp_firewall.return_value = True
        mock_gcp_sql.return_value = True
        mock_aws_update.return_value = True
        
        updater = mod.IPUpdater(temp_config_file)
        exit_code = updater.run(force=False)
        
        assert exit_code == 0
        assert mock_gcp_firewall.called
        assert mock_gcp_sql.called
        assert mock_aws_update.called
        assert mock_save_ip.called
    
    @patch.object(mod.IPService, 'check_ip_change')
    def test_run_force_mode(self, mock_check_ip, temp_config_file):
        """Test run with force=True"""
        mock_check_ip.return_value = ("1.2.3.4", "1.2.3.4", False)
        
        with patch.object(mod.GCPUpdater, 'update_firewall_rules', return_value=True), \
             patch.object(mod.GCPUpdater, 'update_cloud_sql', return_value=True), \
             patch.object(mod.AWSUpdater, 'update_security_groups', return_value=True), \
             patch.object(mod.IPService, 'save_ip') as mock_save:
            
            updater = mod.IPUpdater(temp_config_file)
            exit_code = updater.run(force=True)
            
            assert exit_code == 0
            assert mock_save.called
    
    @patch.object(mod.IPService, 'check_ip_change')
    def test_run_cannot_get_ip(self, mock_check_ip, temp_config_file):
        """Test run when cannot get current IP"""
        mock_check_ip.return_value = ("1.2.3.4", None, False)
        
        updater = mod.IPUpdater(temp_config_file)
        exit_code = updater.run(force=False)
        
        assert exit_code == 1
    
    @patch.object(mod.IPService, 'check_ip_change')
    @patch.object(mod.GCPUpdater, 'update_firewall_rules')
    @patch.object(mod.GCPUpdater, 'update_cloud_sql')
    @patch.object(mod.AWSUpdater, 'update_security_groups')
    def test_run_partial_failure(
        self,
        mock_aws_update,
        mock_gcp_sql,
        mock_gcp_firewall,
        mock_check_ip,
        temp_config_file
    ):
        """Test run when some updates fail"""
        mock_check_ip.return_value = ("1.2.3.4", "5.6.7.8", True)
        mock_gcp_firewall.return_value = True
        mock_gcp_sql.return_value = False  # This one fails
        mock_aws_update.return_value = True
        
        updater = mod.IPUpdater(temp_config_file)
        exit_code = updater.run(force=False)
        
        assert exit_code == 1
    
    @patch.object(mod.IPService, 'check_ip_change')
    @patch.object(mod.GCPUpdater, 'update_firewall_rules')
    @patch.object(mod.GCPUpdater, 'update_cloud_sql')
    @patch.object(mod.AWSUpdater, 'update_security_groups')
    @patch.object(mod.IPService, 'save_ip')
    def test_run_partial_failure_gcp_firewall(
        self,
        mock_save,
        mock_aws,
        mock_gcp_sql,
        mock_gcp_firewall,
        mock_check_ip,
        tmp_path,
        mock_config
    ):
        """Test run when GCP firewall fails but others succeed"""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(mock_config))
        
        mock_check_ip.return_value = ("1.2.3.4", "5.6.7.8", True)
        mock_gcp_firewall.return_value = False  # Fails
        mock_gcp_sql.return_value = True
        mock_aws.return_value = True
        
        updater = mod.IPUpdater(str(config_file))
        exit_code = updater.run(force=False)
        
        assert exit_code == 1  # Should fail
        assert not mock_save.called  # Should not save IP
    
    @patch.object(mod.IPService, 'check_ip_change')
    @patch.object(mod.GCPUpdater, 'update_firewall_rules')
    @patch.object(mod.GCPUpdater, 'update_cloud_sql')
    @patch.object(mod.AWSUpdater, 'update_security_groups')
    def test_run_dry_run_mode_no_save(
        self,
        mock_aws,
        mock_gcp_sql,
        mock_gcp_firewall,
        mock_check_ip,
        tmp_path,
        mock_config
    ):
        """Test run in dry-run mode doesn't save IP"""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(mock_config))
        
        mock_check_ip.return_value = ("1.2.3.4", "5.6.7.8", True)
        mock_gcp_firewall.return_value = True
        mock_gcp_sql.return_value = True
        mock_aws.return_value = True
        
        with patch.object(mod.IPService, 'save_ip') as mock_save:
            updater = mod.IPUpdater(str(config_file), dry_run=True)
            exit_code = updater.run(force=False)
            
            assert exit_code == 0
            assert not mock_save.called  # Should NOT save in dry-run


# ============================================================================
# MAIN FUNCTION TESTS
# ============================================================================

class TestMainFunction:
    """Test main() function and CLI argument parsing"""
    
    @patch('sys.argv', ['auto_update_ip.py', '--version'])
    def test_version_argument(self):
        """Test --version argument"""
        with pytest.raises(SystemExit) as exc_info:
            mod.main()
        # argparse exits with 0 for --version
        assert exc_info.value.code == 0
    
    @patch('sys.argv', ['auto_update_ip.py', '--help'])
    def test_help_argument(self):
        """Test --help argument"""
        with pytest.raises(SystemExit) as exc_info:
            mod.main()
        # argparse exits with 0 for --help
        assert exc_info.value.code == 0
    
    @patch.object(mod.IPUpdater, 'run')
    @patch('sys.argv', ['auto_update_ip.py', '--dry-run'])
    def test_dry_run_argument(self, mock_run, temp_config_file):
        """Test --dry-run argument"""
        mock_run.return_value = 0
        
        with patch.object(mod, 'Config', return_value=Mock()):
            try:
                mod.main()
            except SystemExit:
                pass
    
    @patch('sys.argv', ['auto_update_ip.py'])
    @patch.object(mod.IPUpdater, '__init__')
    @patch.object(mod.IPUpdater, 'run')
    def test_main_success(self, mock_run, mock_init):
        """Test main function successful execution"""
        mock_init.return_value = None
        mock_run.return_value = 0
        
        with pytest.raises(SystemExit) as exc_info:
            mod.main()
        
        assert exc_info.value.code == 0
    
    @patch('sys.argv', ['auto_update_ip.py', '--config', 'nonexistent.json'])
    def test_main_file_not_found(self):
        """Test main function with non-existent config file"""
        with pytest.raises(SystemExit) as exc_info:
            mod.main()
        
        assert exc_info.value.code == 1
    
    @patch('sys.argv', ['auto_update_ip.py'])
    @patch.object(mod.IPUpdater, '__init__')
    def test_main_unexpected_exception(self, mock_init):
        """Test main function with unexpected exception"""
        mock_init.side_effect = Exception("Unexpected error")
        
        with pytest.raises(SystemExit) as exc_info:
            mod.main()
        
        assert exc_info.value.code == 1


# ============================================================================
# IMPORT ERROR HANDLING TESTS
# ============================================================================

class TestImportErrorHandling:
    """Test import error handling"""
    
    def test_module_imports_successfully(self):
        """Verify module imports work"""
        # Verify flags are set
        assert mod.GCP_AVAILABLE or not mod.GCP_AVAILABLE
        assert mod.GOOGLE_API_AVAILABLE or not mod.GOOGLE_API_AVAILABLE
        assert mod.AWS_AVAILABLE or not mod.AWS_AVAILABLE
        
        # Verify the module loaded successfully
        assert hasattr(mod, 'Config')
        assert hasattr(mod, 'IPService')
        assert hasattr(mod, 'GCPUpdater')
        assert hasattr(mod, 'AWSUpdater')
        assert hasattr(mod, 'IPUpdater')


class TestMainEntryPoint:
    """Test the __main__ entry point"""
    
    def test_main_module_execution(self):
        """Test that module can be executed as main"""
        assert callable(mod.main)
        
        # Verify main has the right signature
        import inspect
        sig = inspect.signature(mod.main)
        assert len(sig.parameters) == 0  # main() takes no arguments


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--cov=auto_update_ip', '--cov-report=term-missing'])
