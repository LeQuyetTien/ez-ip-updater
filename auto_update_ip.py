#!/usr/bin/env python3
"""
Script tự động cập nhật IP công cộng vào:
- Google Cloud Firewall Rules
- Google Cloud SQL Authorized Networks
- AWS Security Groups

Yêu cầu:
- pip install google-cloud-compute google-api-python-client boto3 requests
- Cấu hình credentials cho GCP và AWS
"""

import requests
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional

# Google Cloud
from google.cloud import compute_v1
from googleapiclient import discovery
from googleapiclient.errors import HttpError
from google.oauth2 import service_account
import os

# AWS
import boto3
from botocore.exceptions import ClientError

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ip_update.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ======================== CẤU HÌNH ========================

def load_config(config_path: str = "config.json") -> dict:
    """Load configuration from JSON file"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"File cấu hình {config_path} không tồn tại")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Lỗi khi đọc file cấu hình: {e}")
        raise

# Load configuration
CONFIG = load_config()

# Extract config values for easy access
GCP_PROJECT_ID = CONFIG['gcp']['project_id']
GCP_CREDENTIALS_FILE = CONFIG['gcp']['credentials_file']
GCP_FIREWALL_RULES = CONFIG['gcp']['firewall_rules']
GCP_SQL_INSTANCES = CONFIG['gcp']['sql_instances']

AWS_REGION = CONFIG['aws']['region']
AWS_SECURITY_GROUPS_SSH = CONFIG['aws']['security_groups_ssh']
AWS_SECURITY_GROUPS_MYSQL = CONFIG['aws']['security_groups_mysql']
PORTS_TO_OPEN_SSH = CONFIG['aws']['ports_ssh']
PORTS_TO_OPEN_MYSQL = CONFIG['aws']['ports_mysql']

IP_CACHE_FILE = CONFIG['ip_cache_file']

# ======================== HÀM CHÍNH ========================

def get_public_ip() -> Optional[str]:
    """Lấy IP công cộng hiện tại"""
    try:
        # Thử nhiều service để tăng độ tin cậy
        services = [
            "https://api.ipify.org",
            "https://ifconfig.me/ip",
            "https://icanhazip.com"
        ]
        
        for service in services:
            try:
                response = requests.get(service, timeout=5)
                if response.status_code == 200:
                    ip = response.text.strip()
                    logger.info(f"IP công cộng hiện tại: {ip}")
                    return ip
            except:
                continue
        
        logger.error("Không thể lấy IP công cộng")
        return None
    except Exception as e:
        logger.error(f"Lỗi khi lấy IP: {e}")
        return None

def get_cached_ip() -> Optional[str]:
    """Đọc IP đã lưu từ lần chạy trước"""
    try:
        with open(IP_CACHE_FILE, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return None

def save_cached_ip(ip: str):
    """Lưu IP hiện tại vào cache"""
    with open(IP_CACHE_FILE, 'w') as f:
        f.write(ip)

# ======================== GOOGLE CLOUD ========================

def update_gcp_firewall_rules(old_ip: Optional[str], new_ip: str):
    """Cập nhật GCP Firewall Rules"""
    try:
        client = compute_v1.FirewallsClient()
        
        for rule_name in GCP_FIREWALL_RULES:
            try:
                # Lấy rule hiện tại
                firewall = client.get(project=GCP_PROJECT_ID, firewall=rule_name)
                
                # Cập nhật source ranges
                old_cidr = f"{old_ip}/32" if old_ip else None
                new_cidr = f"{new_ip}/32"
                
                source_ranges = list(firewall.source_ranges)
                
                # Xóa IP cũ nếu có
                if old_cidr and old_cidr in source_ranges:
                    source_ranges.remove(old_cidr)
                
                # Thêm IP mới nếu chưa có
                if new_cidr not in source_ranges:
                    source_ranges.append(new_cidr)
                
                # Update firewall rule
                firewall.source_ranges = source_ranges
                operation = client.update(
                    project=GCP_PROJECT_ID,
                    firewall=rule_name,
                    firewall_resource=firewall
                )
                
                # Đợi operation hoàn thành
                operation.result()
                
                logger.info(f"✓ Đã cập nhật GCP Firewall rule: {rule_name}")
                
            except Exception as e:
                if "not found" in str(e).lower():
                    logger.warning(f"Không tìm thấy firewall rule: {rule_name}")
                else:
                    logger.error(f"Lỗi khi cập nhật firewall rule {rule_name}: {e}")
                
    except Exception as e:
        logger.error(f"Lỗi GCP Firewall: {e}")

def update_gcp_cloud_sql(old_ip: Optional[str], new_ip: str):
    """Cập nhật GCP Cloud SQL Authorized Networks"""
    try:
        if discovery is None:
            logger.warning(
                "googleapiclient chưa được cài đặt; bỏ qua cập nhật Cloud SQL. "
                "Cài đặt bằng: pip install google-api-python-client"
            )
            return
        
        # Load credentials for Cloud SQL API: prefer explicit service account file, fall back to ADC
        creds = None
        if os.path.exists(GCP_CREDENTIALS_FILE):
            try:
                creds = service_account.Credentials.from_service_account_file(
                    GCP_CREDENTIALS_FILE
                )
                logger.info(f"Sử dụng credentials từ {GCP_CREDENTIALS_FILE} cho Cloud SQL API")
            except Exception as e:
                logger.warning(f"Không thể load credentials từ file {GCP_CREDENTIALS_FILE}: {e}")

        try:
            if creds:
                service = discovery.build('sqladmin', 'v1beta4', credentials=creds)
            else:
                # Let discovery try ADC; if ADC missing this will raise
                service = discovery.build('sqladmin', 'v1beta4')
        except Exception as e:
            logger.error(
                "Không thể khởi tạo client Cloud SQL. Vui lòng cài đặt ADC hoặc đặt "
                "GOOGLE_APPLICATION_CREDENTIALS tới file service account, hoặc cung cấp file gcp-credentials.json."
            )
            logger.error(f"Lỗi Cloud SQL: {e}")
            return

        for instance_name in GCP_SQL_INSTANCES:
            try:
                # Lấy instance hiện tại
                request = service.instances().get(
                    project=GCP_PROJECT_ID,
                    instance=instance_name
                )
                instance = request.execute()
                
                # Lấy authorized networks hiện tại
                settings = instance.get('settings', {})
                ip_config = settings.get('ipConfiguration', {})
                authorized_networks = ip_config.get('authorizedNetworks', [])
                
                # Xóa IP cũ nếu có
                if old_ip:
                    authorized_networks = [
                        net for net in authorized_networks 
                        if net.get('value') not in [old_ip, f"{old_ip}/32"]
                    ]
                
                # Thêm IP mới nếu chưa có
                new_network_entry = {
                    'value': new_ip,
                    'name': f'office-ip-{datetime.now().strftime("%Y%m%d-%H%M")}'
                }
                
                # Kiểm tra xem IP mới đã tồn tại chưa
                ip_exists = any(
                    net.get('value') in [new_ip, f"{new_ip}/32"] 
                    for net in authorized_networks
                )
                
                if not ip_exists:
                    authorized_networks.append(new_network_entry)
                
                # Update instance
                ip_config['authorizedNetworks'] = authorized_networks
                settings['ipConfiguration'] = ip_config
                
                body = {
                    'settings': settings
                }
                
                request = service.instances().patch(
                    project=GCP_PROJECT_ID,
                    instance=instance_name,
                    body=body
                )
                operation = request.execute()
                
                logger.info(f"✓ Đã cập nhật Cloud SQL: {instance_name}")
                
            except HttpError as e:
                if e.resp.status == 404:
                    logger.warning(f"Không tìm thấy Cloud SQL instance: {instance_name}")
                else:
                    logger.error(f"Lỗi khi cập nhật Cloud SQL {instance_name}: {e}")
            except Exception as e:
                logger.error(f"Lỗi khi cập nhật Cloud SQL {instance_name}: {e}")
                
    except Exception as e:
        logger.error(f"Lỗi Cloud SQL: {e}")

# ======================== AWS ========================

def update_aws_security_groups_ssh(old_ip: Optional[str], new_ip: str):
    """Cập nhật AWS Security Groups"""
    try:
        ec2 = boto3.client('ec2', region_name=AWS_REGION)
        
        for sg in AWS_SECURITY_GROUPS_SSH:
            group_id = sg['group_id']
            
            try:
                # Xóa rules với IP cũ
                if old_ip:
                    try:
                        for port_rule in PORTS_TO_OPEN_SSH:
                            ec2.revoke_security_group_ingress(
                                GroupId=group_id,
                                IpPermissions=[{
                                    'IpProtocol': port_rule['protocol'],
                                    'FromPort': port_rule['port'],
                                    'ToPort': port_rule['port'],
                                    'IpRanges': [{'CidrIp': f"{old_ip}/32"}]
                                }]
                            )
                        logger.info(f"  Đã xóa IP cũ {old_ip} khỏi {group_id}")
                    except ClientError as e:
                        if 'InvalidPermission.NotFound' not in str(e):
                            logger.warning(f"Không thể xóa IP cũ: {e}")
                
                # Thêm rules với IP mới
                for port_rule in PORTS_TO_OPEN_SSH:
                    try:
                        ec2.authorize_security_group_ingress(
                            GroupId=group_id,
                            IpPermissions=[{
                                'IpProtocol': port_rule['protocol'],
                                'FromPort': port_rule['port'],
                                'ToPort': port_rule['port'],
                                'IpRanges': [{
                                    'CidrIp': f"{new_ip}/32",
                                    'Description': f"{port_rule['description']} - {sg['description']}"
                                }]
                            }]
                        )
                    except ClientError as e:
                        if 'InvalidPermission.Duplicate' in str(e):
                            logger.info(f"  Rule đã tồn tại cho port {port_rule['port']}")
                        else:
                            raise
                
                logger.info(f"✓ Đã cập nhật AWS Security Group SSH: {group_id}")
                
            except ClientError as e:
                logger.error(f"Lỗi khi cập nhật Security Group SSH {group_id}: {e}")
                
    except Exception as e:
        logger.error(f"Lỗi AWS Security Groups SSH: {e}")

def update_aws_security_groups_mysql(old_ip: Optional[str], new_ip: str):
    """Cập nhật AWS Security Groups"""
    try:
        ec2 = boto3.client('ec2', region_name=AWS_REGION)
        
        for sg in AWS_SECURITY_GROUPS_MYSQL:
            group_id = sg['group_id']
            
            try:
                # Xóa rules với IP cũ
                if old_ip:
                    try:
                        for port_rule in PORTS_TO_OPEN_MYSQL:
                            ec2.revoke_security_group_ingress(
                                GroupId=group_id,
                                IpPermissions=[{
                                    'IpProtocol': port_rule['protocol'],
                                    'FromPort': port_rule['port'],
                                    'ToPort': port_rule['port'],
                                    'IpRanges': [{'CidrIp': f"{old_ip}/32"}]
                                }]
                            )
                        logger.info(f"  Đã xóa IP cũ {old_ip} khỏi {group_id}")
                    except ClientError as e:
                        if 'InvalidPermission.NotFound' not in str(e):
                            logger.warning(f"Không thể xóa IP cũ: {e}")
                
                # Thêm rules với IP mới
                for port_rule in PORTS_TO_OPEN_MYSQL:
                    try:
                        ec2.authorize_security_group_ingress(
                            GroupId=group_id,
                            IpPermissions=[{
                                'IpProtocol': port_rule['protocol'],
                                'FromPort': port_rule['port'],
                                'ToPort': port_rule['port'],
                                'IpRanges': [{
                                    'CidrIp': f"{new_ip}/32",
                                    'Description': f"{port_rule['description']} - {sg['description']}"
                                }]
                            }]
                        )
                    except ClientError as e:
                        if 'InvalidPermission.Duplicate' in str(e):
                            logger.info(f"  Rule đã tồn tại cho port {port_rule['port']}")
                        else:
                            raise
                
                logger.info(f"✓ Đã cập nhật AWS Security Group MySQL: {group_id}")
                
            except ClientError as e:
                logger.error(f"Lỗi khi cập nhật Security Group MySQL {group_id}: {e}")
                
    except Exception as e:
        logger.error(f"Lỗi AWS Security Groups MySQL: {e}")

# ======================== MAIN ========================

def main():
    """Hàm chính"""
    logger.info("=" * 60)
    logger.info("BẮT ĐẦU KIỂM TRA VÀ CẬP NHẬT IP")
    logger.info("=" * 60)
    
    # Lấy IP hiện tại
    current_ip = get_public_ip()
    if not current_ip:
        logger.error("Không thể lấy IP công cộng. Dừng script.")
        return
    
    # Lấy IP đã lưu
    cached_ip = get_cached_ip()
    
    # So sánh IP
    if cached_ip == current_ip:
        logger.info(f"IP không thay đổi ({current_ip}). Không cần cập nhật.")
        return
    
    logger.info(f"IP đã thay đổi: {cached_ip} → {current_ip}")
    
    # Cập nhật Google Cloud
    logger.info("\n--- Cập nhật Google Cloud ---")
    update_gcp_firewall_rules(cached_ip, current_ip)
    update_gcp_cloud_sql(cached_ip, current_ip)
    
    # Cập nhật AWS
    logger.info("\n--- Cập nhật AWS ---")
    update_aws_security_groups_ssh(cached_ip, current_ip)
    update_aws_security_groups_mysql(cached_ip, current_ip)
    
    # Lưu IP mới
    save_cached_ip(current_ip)
    
    logger.info("\n" + "=" * 60)
    logger.info("HOÀN THÀNH CẬP NHẬT")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()