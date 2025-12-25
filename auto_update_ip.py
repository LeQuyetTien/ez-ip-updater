#!/usr/bin/env python3
"""
IP Updater - Tự động cập nhật IP công cộng vào Cloud Infrastructure

Script này tự động phát hiện IP công cộng và cập nhật vào:
- Google Cloud Firewall Rules
- Google Cloud SQL Authorized Networks  
- AWS Security Groups

Author: IP Updater Team
Version: 2.0.0
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import requests

# Google Cloud (optional imports)
try:
    from google.cloud import compute_v1
    from google.oauth2 import service_account
    GCP_AVAILABLE = True
except ImportError:
    GCP_AVAILABLE = False

try:
    from googleapiclient import discovery
    from googleapiclient.errors import HttpError
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False

# AWS (optional imports)
try:
    import boto3
    from botocore.exceptions import ClientError
    AWS_AVAILABLE = True
except ImportError:
    AWS_AVAILABLE = False


class Config:
    """Configuration management class"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self._data = self._load()
        
    def _load(self) -> dict:
        """Load and validate configuration"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self._validate(data)
            return data
        except FileNotFoundError:
            raise FileNotFoundError(
                f"File cấu hình '{self.config_path}' không tồn tại. "
                f"Tạo file từ: cp config.json.example config.json"
            )
        except json.JSONDecodeError as e:
            raise ValueError(f"File cấu hình không hợp lệ: {e}")
    
    def _validate(self, data: dict):
        """Validate required configuration keys"""
        required_keys = ['gcp', 'aws', 'ip_cache_file']
        missing = [key for key in required_keys if key not in data]
        
        if missing:
            raise ValueError(
                f"File cấu hình thiếu các trường bắt buộc: {', '.join(missing)}"
            )
        
        # Validate GCP section
        gcp = data.get('gcp', {})
        if not isinstance(gcp, dict):
            raise ValueError("Section 'gcp' phải là object")
        if 'project_id' not in gcp:
            raise ValueError("Missing required field: gcp.project_id")
        
        # Validate AWS section
        aws = data.get('aws', {})
        if not isinstance(aws, dict):
            raise ValueError("Section 'aws' phải là object")
        if 'region' not in aws:
            raise ValueError("Missing required field: aws.region")
        
        # Validate security groups structure
        for sg_list in ['security_groups_ssh', 'security_groups_mysql']:
            if sg_list in aws:
                if not isinstance(aws[sg_list], list):
                    raise ValueError(f"aws.{sg_list} phải là array")
                for sg in aws[sg_list]:
                    if not isinstance(sg, dict):
                        raise ValueError(f"Security group trong {sg_list} phải là object")
                    if 'group_id' not in sg:
                        raise ValueError(f"Security group trong {sg_list} thiếu 'group_id'")
    
    @property
    def gcp(self) -> dict:
        return self._data.get('gcp', {})
    
    @property
    def aws(self) -> dict:
        return self._data.get('aws', {})
    
    @property
    def ip_cache_file(self) -> str:
        return self._data.get('ip_cache_file', 'last_known_ip.txt')


class IPService:
    """Service for managing public IP detection and caching"""
    
    IP_SERVICES = [
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://icanhazip.com"
    ]
    
    def __init__(self, cache_file: str, logger: logging.Logger):
        self.cache_file = cache_file
        self.logger = logger
    
    def get_current_ip(self) -> Optional[str]:
        """Lấy IP công cộng hiện tại từ các service"""
        for service in self.IP_SERVICES:
            try:
                response = requests.get(service, timeout=5)
                if response.status_code == 200:
                    ip = response.text.strip()
                    self.logger.info(f"✓ Phát hiện IP công cộng: {ip}")
                    return ip
            except Exception as e:
                self.logger.debug(f"Service {service} thất bại: {e}")
                continue
        
        self.logger.error("✗ Không thể lấy IP công cộng từ các service")
        return None
    
    def get_cached_ip(self) -> Optional[str]:
        """Đọc IP đã lưu từ lần chạy trước"""
        try:
            with open(self.cache_file, 'r') as f:
                ip = f.read().strip()
                self.logger.debug(f"IP cached: {ip}")
                return ip
        except FileNotFoundError:
            self.logger.debug("Không tìm thấy file cache IP")
            return None
    
    def save_ip(self, ip: str):
        """Lưu IP vào cache"""
        with open(self.cache_file, 'w') as f:
            f.write(ip)
        self.logger.debug(f"Đã lưu IP vào cache: {ip}")
    
    def check_ip_change(self, custom_ip: Optional[str] = None) -> Tuple[Optional[str], Optional[str], bool]:
        """
        Kiểm tra thay đổi IP
        Args:
            custom_ip: IP tùy chỉnh (nếu có)
        Returns: (cached_ip, current_ip, changed)
        """
        cached_ip = self.get_cached_ip()
        
        # Ưu tiên custom IP nếu được cung cấp
        if custom_ip:
            self.logger.info(f"🎯 Sử dụng custom IP: {custom_ip}")
            current_ip = custom_ip
        else:
            current_ip = self.get_current_ip()
        
        if current_ip is None:
            return cached_ip, None, False
        
        changed = cached_ip != current_ip
        return cached_ip, current_ip, changed


class GCPUpdater:
    """Google Cloud Platform IP updater"""
    
    def __init__(self, config: dict, logger: logging.Logger, dry_run: bool = False):
        self.config = config
        self.logger = logger
        self.dry_run = dry_run
        self.credentials = self._load_credentials()
    
    def _load_credentials(self) -> Optional[service_account.Credentials]:
        """Load GCP credentials"""
        if not GCP_AVAILABLE:
            return None
        
        creds_file = self.config.get('credentials_file')
        if creds_file and os.path.exists(creds_file):
            try:
                creds = service_account.Credentials.from_service_account_file(creds_file)
                self.logger.debug(f"Loaded GCP credentials từ {creds_file}")
                return creds
            except Exception as e:
                self.logger.warning(f"Không thể load credentials từ {creds_file}: {e}")
        
        self.logger.debug("Sử dụng Application Default Credentials")
        return None
    
    def update_firewall_rules(self, old_ip: Optional[str], new_ip: str) -> bool:
        """Cập nhật GCP Firewall Rules"""
        if not GCP_AVAILABLE:
            self.logger.warning("⊘ Google Cloud SDK chưa được cài đặt")
            return False
        
        rules = self.config.get('firewall_rules', [])
        if not rules:
            self.logger.debug("Không có firewall rules để cập nhật")
            return True
        
        try:
            if self.credentials:
                client = compute_v1.FirewallsClient(credentials=self.credentials)
            else:
                client = compute_v1.FirewallsClient()
            
            project_id = self.config.get('project_id')
            success_count = 0
            
            for rule_name in rules:
                if self._update_single_firewall_rule(client, project_id, rule_name, old_ip, new_ip):
                    success_count += 1
            
            return success_count == len(rules)
            
        except Exception as e:
            self.logger.error(f"✗ Lỗi GCP Firewall: {e}")
            return False
    
    def _update_single_firewall_rule(
        self, 
        client: compute_v1.FirewallsClient,
        project_id: str,
        rule_name: str,
        old_ip: Optional[str],
        new_ip: str
    ) -> bool:
        """Cập nhật một firewall rule"""
        try:
            firewall = client.get(project=project_id, firewall=rule_name)
            
            old_cidr = f"{old_ip}/32" if old_ip else None
            new_cidr = f"{new_ip}/32"
            
            source_ranges = list(firewall.source_ranges)
            
            # Xóa IP cũ
            if old_cidr and old_cidr in source_ranges:
                source_ranges.remove(old_cidr)
                self.logger.debug(f"  Xóa IP cũ: {old_cidr}")
            
            # Thêm IP mới
            if new_cidr not in source_ranges:
                source_ranges.append(new_cidr)
                self.logger.debug(f"  Thêm IP mới: {new_cidr}")
            else:
                self.logger.info(f"  IP {new_cidr} đã tồn tại trong rule {rule_name}")
                return True
            
            if self.dry_run:
                self.logger.info(f"[DRY-RUN] Sẽ cập nhật firewall rule: {rule_name}")
                return True
            
            # Cập nhật
            firewall.source_ranges = source_ranges
            operation = client.update(
                project=project_id,
                firewall=rule_name,
                firewall_resource=firewall
            )
            operation.result()
            
            self.logger.info(f"✓ Đã cập nhật GCP Firewall rule: {rule_name}")
            return True
            
        except Exception as e:
            if "not found" in str(e).lower():
                self.logger.warning(f"⚠ Không tìm thấy firewall rule: {rule_name}")
            else:
                self.logger.error(f"✗ Lỗi khi cập nhật rule {rule_name}: {e}")
            return False
    
    def update_cloud_sql(self, old_ip: Optional[str], new_ip: str) -> bool:
        """Cập nhật GCP Cloud SQL Authorized Networks"""
        if not GOOGLE_API_AVAILABLE:
            self.logger.warning("⊘ Google API Python Client chưa được cài đặt")
            return False
        
        instances = self.config.get('sql_instances', [])
        if not instances:
            self.logger.debug("Không có Cloud SQL instances để cập nhật")
            return True
        
        try:
            if self.credentials:
                service = discovery.build('sqladmin', 'v1beta4', credentials=self.credentials)
            else:
                service = discovery.build('sqladmin', 'v1beta4')
            
            project_id = self.config.get('project_id')
            success_count = 0
            
            for instance_name in instances:
                if self._update_single_sql_instance(service, project_id, instance_name, old_ip, new_ip):
                    success_count += 1
            
            return success_count == len(instances)
            
        except Exception as e:
            self.logger.error(f"✗ Lỗi Cloud SQL: {e}")
            return False
    
    def _update_single_sql_instance(
        self,
        service,
        project_id: str,
        instance_name: str,
        old_ip: Optional[str],
        new_ip: str
    ) -> bool:
        """Cập nhật một Cloud SQL instance"""
        try:
            # Lấy instance hiện tại
            instance = service.instances().get(
                project=project_id,
                instance=instance_name
            ).execute()
            
            # Lấy authorized networks
            settings = instance.get('settings', {})
            ip_config = settings.get('ipConfiguration', {})
            authorized_networks = ip_config.get('authorizedNetworks', [])
            
            # Xóa IP cũ
            if old_ip:
                authorized_networks = [
                    net for net in authorized_networks 
                    if net.get('value') not in [old_ip, f"{old_ip}/32"]
                ]
            
            # Kiểm tra IP mới
            ip_exists = any(
                net.get('value') in [new_ip, f"{new_ip}/32"] 
                for net in authorized_networks
            )
            
            if not ip_exists:
                new_entry = {
                    'value': new_ip,
                    'name': f'auto-ip-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
                }
                authorized_networks.append(new_entry)
            else:
                self.logger.info(f"  IP {new_ip} đã tồn tại trong {instance_name}")
                return True
            
            if self.dry_run:
                self.logger.info(f"[DRY-RUN] Sẽ cập nhật Cloud SQL: {instance_name}")
                return True
            
            # Cập nhật
            ip_config['authorizedNetworks'] = authorized_networks
            settings['ipConfiguration'] = ip_config
            
            service.instances().patch(
                project=project_id,
                instance=instance_name,
                body={'settings': settings}
            ).execute()
            
            self.logger.info(f"✓ Đã cập nhật Cloud SQL: {instance_name}")
            return True
            
        except HttpError as e:
            if e.resp.status == 404:
                self.logger.warning(f"⚠ Không tìm thấy Cloud SQL instance: {instance_name}")
            else:
                self.logger.error(f"✗ Lỗi khi cập nhật {instance_name}: {e}")
            return False


class AWSUpdater:
    """AWS IP updater"""
    
    def __init__(self, config: dict, logger: logging.Logger, dry_run: bool = False, profile: Optional[str] = None):
        self.config = config
        self.logger = logger
        self.dry_run = dry_run
        self.profile = profile or config.get('profile')
    
    def update_security_groups(self, old_ip: Optional[str], new_ip: str) -> bool:
        """Cập nhật tất cả AWS Security Groups"""
        if not AWS_AVAILABLE:
            self.logger.warning("⊘ Boto3 (AWS SDK) chưa được cài đặt")
            return False
        
        # Cập nhật SSH và MySQL security groups
        ssh_success = self._update_security_group_type(
            old_ip, new_ip, 
            self.config.get('security_groups_ssh', []),
            self.config.get('ports_ssh', []),
            "SSH"
        )
        
        mysql_success = self._update_security_group_type(
            old_ip, new_ip,
            self.config.get('security_groups_mysql', []),
            self.config.get('ports_mysql', []),
            "MySQL"
        )
        
        return ssh_success and mysql_success
    
    def _update_security_group_type(
        self,
        old_ip: Optional[str],
        new_ip: str,
        security_groups: List[dict],
        ports: List[dict],
        group_type: str
    ) -> bool:
        """Cập nhật một loại security group (SSH/MySQL)"""
        if not security_groups:
            self.logger.debug(f"Không có {group_type} security groups để cập nhật")
            return True
        
        try:
            # Tạo boto3 client với profile nếu có
            client_kwargs = {'region_name': self.config.get('region')}
            if self.profile:
                session = boto3.Session(profile_name=self.profile)
                ec2 = session.client('ec2', region_name=self.config.get('region'))
                self.logger.debug(f"Sử dụng AWS profile: {self.profile}")
            else:
                ec2 = boto3.client('ec2', **client_kwargs)
            success_count = 0
            
            for sg in security_groups:
                if self._update_single_security_group(ec2, sg, old_ip, new_ip, ports, group_type):
                    success_count += 1
            
            return success_count == len(security_groups)
            
        except Exception as e:
            self.logger.error(f"✗ Lỗi AWS Security Groups {group_type}: {e}")
            return False
    
    def _update_single_security_group(
        self,
        ec2,
        sg: dict,
        old_ip: Optional[str],
        new_ip: str,
        ports: List[dict],
        group_type: str
    ) -> bool:
        """Cập nhật một security group"""
        group_id = sg['group_id']
        
        try:
            # Xóa rules với IP cũ
            if old_ip:
                self._revoke_old_rules(ec2, group_id, old_ip, ports)
            
            # Thêm rules với IP mới
            self._authorize_new_rules(ec2, group_id, new_ip, ports, sg.get('description', ''))
            
            self.logger.info(f"✓ Đã cập nhật AWS Security Group {group_type}: {group_id}")
            return True
            
        except ClientError as e:
            self.logger.error(f"✗ Lỗi khi cập nhật {group_type} {group_id}: {e}")
            return False
    
    def _revoke_old_rules(self, ec2, group_id: str, old_ip: str, ports: List[dict]):
        """Xóa rules với IP cũ"""
        for port_rule in ports:
            try:
                if self.dry_run:
                    self.logger.info(f"[DRY-RUN] Sẽ xóa rule {old_ip}::{port_rule['port']}")
                    continue
                
                ec2.revoke_security_group_ingress(
                    GroupId=group_id,
                    IpPermissions=[{
                        'IpProtocol': port_rule['protocol'],
                        'FromPort': port_rule['port'],
                        'ToPort': port_rule['port'],
                        'IpRanges': [{'CidrIp': f"{old_ip}/32"}]
                    }]
                )
                self.logger.debug(f"  Đã xóa rule cũ port {port_rule['port']}")
            except ClientError as e:
                if 'InvalidPermission.NotFound' not in str(e):
                    self.logger.warning(f"  Không thể xóa rule cũ: {e}")
    
    def _authorize_new_rules(
        self, 
        ec2, 
        group_id: str, 
        new_ip: str, 
        ports: List[dict],
        description: str
    ):
        """Thêm rules với IP mới"""
        for port_rule in ports:
            try:
                if self.dry_run:
                    self.logger.info(f"[DRY-RUN] Sẽ thêm rule {new_ip}::{port_rule['port']}")
                    continue
                
                ec2.authorize_security_group_ingress(
                    GroupId=group_id,
                    IpPermissions=[{
                        'IpProtocol': port_rule['protocol'],
                        'FromPort': port_rule['port'],
                        'ToPort': port_rule['port'],
                        'IpRanges': [{
                            'CidrIp': f"{new_ip}/32",
                            'Description': f"{port_rule['description']} - {description}"
                        }]
                    }]
                )
                self.logger.debug(f"  Đã thêm rule mới port {port_rule['port']}")
            except ClientError as e:
                if 'InvalidPermission.Duplicate' in str(e):
                    self.logger.debug(f"  Rule đã tồn tại cho port {port_rule['port']}")
                else:
                    raise


class IPUpdater:
    """Main IP updater orchestrator"""
    
    def __init__(self, config_path: str, dry_run: bool = False, verbose: bool = False, custom_ip: Optional[str] = None, aws_profile: Optional[str] = None):
        self.dry_run = dry_run
        self.custom_ip = custom_ip
        self.logger = self._setup_logger(verbose)
        self.config = Config(config_path)
        self.ip_service = IPService(self.config.ip_cache_file, self.logger)
        self.gcp_updater = GCPUpdater(self.config.gcp, self.logger, dry_run)
        self.aws_updater = AWSUpdater(self.config.aws, self.logger, dry_run, aws_profile)
    
    def _setup_logger(self, verbose: bool) -> logging.Logger:
        """Setup logging configuration"""
        level = logging.DEBUG if verbose else logging.INFO
        
        logger = logging.getLogger('ip_updater')
        logger.setLevel(level)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_format = logging.Formatter('%(levelname)s - %(message)s')
        console_handler.setFormatter(console_format)
        
        # File handler
        file_handler = logging.FileHandler('ip_update.log')
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_format)
        
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        
        return logger
    
    def run(self, force: bool = False) -> int:
        """
        Chạy IP updater
        Returns: 0 nếu thành công, 1 nếu thất bại
        """
        self.logger.info("=" * 60)
        self.logger.info("IP UPDATER - BẮT ĐẦU")
        if self.dry_run:
            self.logger.info("[DRY-RUN MODE] - Không thực hiện thay đổi thực tế")
        self.logger.info("=" * 60)
        
        # Kiểm tra thay đổi IP
        cached_ip, current_ip, changed = self.ip_service.check_ip_change(self.custom_ip)
        
        if current_ip is None:
            self.logger.error("✗ Không thể lấy IP công cộng. Dừng.")
            return 1
        
        if not changed and not force:
            self.logger.info(f"✓ IP không thay đổi ({current_ip}). Không cần cập nhật.")
            return 0
        
        if force:
            self.logger.info(f"⚡ Force mode: Cập nhật với IP hiện tại {current_ip}")
        else:
            self.logger.info(f"🔄 IP đã thay đổi: {cached_ip} → {current_ip}")
        
        # Cập nhật cloud providers
        success = True
        
        self.logger.info("\n--- Google Cloud Platform ---")
        gcp_firewall_ok = self.gcp_updater.update_firewall_rules(cached_ip, current_ip)
        gcp_sql_ok = self.gcp_updater.update_cloud_sql(cached_ip, current_ip)
        success = success and gcp_firewall_ok and gcp_sql_ok
        
        self.logger.info("\n--- Amazon Web Services ---")
        aws_ok = self.aws_updater.update_security_groups(cached_ip, current_ip)
        success = success and aws_ok
        
        # Lưu IP mới
        if not self.dry_run and success:
            self.ip_service.save_ip(current_ip)
        
        self.logger.info("\n" + "=" * 60)
        if success:
            self.logger.info("✓ HOÀN THÀNH CẬP NHẬT")
        else:
            self.logger.warning("⚠ CẬP NHẬT HOÀN THÀNH VỚI MỘT SỐ LỖI")
        self.logger.info("=" * 60)
        
        return 0 if success else 1


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Tự động cập nhật IP công cộng vào Cloud Infrastructure',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Chạy với config mặc định
  %(prog)s --config prod.json       # Dùng config file khác
  %(prog)s --dry-run                # Chạy thử không thay đổi thật
  %(prog)s --force                  # Buộc cập nhật kể cả IP không đổi
  %(prog)s --custom-ip 203.0.113.5  # Dùng IP tùy chỉnh thay vì tự phát hiện
  %(prog)s --verbose                # Hiển thị log chi tiết
        """
    )
    
    parser.add_argument(
        '-c', '--config',
        default='config.json',
        help='Đường dẫn file cấu hình (default: config.json)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Chạy thử, không thực hiện thay đổi thực tế'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Buộc cập nhật kể cả khi IP không thay đổi'
    )
    parser.add_argument(
        '--custom-ip',
        type=str,
        help='Sử dụng IP tùy chỉnh thay vì tự động phát hiện (VD: 203.0.113.5)'
    )
    parser.add_argument(
        '--aws-profile',
        type=str,
        help='AWS profile name để sử dụng (default: profile trong config hoặc default)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Hiển thị log chi tiết (DEBUG level)'
    )
    parser.add_argument(
        '--version',
        action='version',
        version='IP Updater 2.0.0'
    )
    
    args = parser.parse_args()
    
    try:
        updater = IPUpdater(
            config_path=args.config,
            dry_run=args.dry_run,
            verbose=args.verbose,
            custom_ip=args.custom_ip,
            aws_profile=args.aws_profile
        )
        sys.exit(updater.run(force=args.force))
    except Exception as e:
        logging.error(f"Lỗi nghiêm trọng: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
