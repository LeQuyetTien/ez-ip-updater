# IP Updater v2.0 - Tự Động Cập Nhật IP Công Cộng

[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

IP Updater là script tự động phát hiện thay đổi IP công cộng và cập nhật vào:

- **Google Cloud Platform**: Firewall Rules, Cloud SQL Authorized Networks
- **Amazon Web Services**: Security Groups (SSH, MySQL, custom ports)

---

## 🚀 Tính Năng Mới v2.0

- **Kiến trúc OOP**: Tách lớp rõ ràng, dễ mở rộng
- **CLI Arguments**: Hỗ trợ `--dry-run`, `--force`, `--verbose`
- **Xử lý lỗi chi tiết**
- **Logging nâng cao**: Console & file, nhiều cấp độ
- **Không lặp code**: Tuân thủ nguyên tắc DRY
- **Test coverage >85%**
- **Cài đặt phụ thuộc linh hoạt**: Chỉ cần SDK bạn sử dụng

---

## 📋 Yêu Cầu

- Python 3.7+
- Phụ thuộc (tùy provider):
  - GCP: `google-cloud-compute`, `google-api-python-client`
  - AWS: `boto3`
  - Chung: `requests`

---

## ⚡ Cài Đặt Nhanh

### 1. Clone & Cài Dependencies

```bash
git clone https://github.com/lequyettien/ip-updater.git
cd ip-updater
python3 -m pip install -r requirements.txt
```

### 2. Tạo & Chỉnh Sửa File Cấu Hình

```bash
cp config.json.example config.json
# Sửa config.json theo thông tin của bạn
```

### 3. Cấu Hình Credentials

#### Google Cloud Platform

```bash
# Cách 1: Biến môi trường (khuyến nghị)
export GOOGLE_APPLICATION_CREDENTIALS="$PWD/gcp-credentials.json"

# Cách 2: Gcloud ADC
gcloud auth application-default login
```

#### Amazon Web Services

```bash
# Cách 1: AWS CLI
aws configure

# Cách 2: Biến môi trường
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"
```

### 4. Chạy Script

```bash
python3 auto_update_ip.py                # Chạy bình thường
python3 auto_update_ip.py --dry-run      # Chạy thử, không thay đổi thật
python3 auto_update_ip.py --force        # Buộc cập nhật kể cả IP không đổi
python3 auto_update_ip.py --verbose      # Hiển thị log chi tiết
```

---

## 🛠️ Sử Dụng

### CLI Options

```bash
usage: auto_update_ip.py [-h] [-c CONFIG] [--dry-run] [--force] [-v] [--version]

options:
  -h, --help            Hiển thị help
  -c, --config CONFIG   Đường dẫn file cấu hình (default: config.json)
  --dry-run             Chạy thử, không thực hiện thay đổi thực tế
  --force               Buộc cập nhật kể cả khi IP không thay đổi
  -v, --verbose         Hiển thị log chi tiết (DEBUG level)
  --version             Hiển thị version
```

**Ví dụ:**

```bash
python3 auto_update_ip.py                          # Chạy với config mặc định
python3 auto_update_ip.py --config prod.json       # Dùng config file khác
python3 auto_update_ip.py --dry-run                # Chạy thử
python3 auto_update_ip.py --force                  # Buộc cập nhật
python3 auto_update_ip.py --verbose                # Log chi tiết
```

---

### Cấu Trúc config.json

```json
{
  "gcp": {
    "project_id": "your-gcp-project",
    "credentials_file": "gcp-credentials.json",
    "firewall_rules": ["allow-office-ssh", "allow-office-https"],
    "sql_instances": ["production-mysql", "staging-postgres"]
  },
  "aws": {
    "region": "ap-southeast-1",
    "security_groups_ssh": [
      {
        "group_id": "sg-xxxxxxxxx",
        "description": "Office SSH Access"
      }
    ],
    "security_groups_mysql": [
      {
        "group_id": "sg-yyyyyyyyy",
        "description": "Office MySQL Access"
      }
    ],
    "ports_ssh": [
      {"protocol": "tcp", "port": 22, "description": "SSH"}
    ],
    "ports_mysql": [
      {"protocol": "tcp", "port": 3306, "description": "MySQL"}
    ]
  },
  "ip_cache_file": "last_known_ip.txt"
}
```

---

## ⏰ Chạy Định Kỳ

### Cron

Chạy mỗi 5 phút:

```cron
*/5 * * * * cd /path/to/ip-updater && /usr/bin/python3 auto_update_ip.py >> /var/log/ip_update.log 2>&1
```

Chạy mỗi giờ:

```cron
0 * * * * cd /path/to/ip-updater && /usr/bin/python3 auto_update_ip.py
```

### Systemd Timer (Linux)

Tạo service file `/etc/systemd/system/ip-updater.service`:

```ini
[Unit]
Description=IP Updater Service
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/path/to/ip-updater
ExecStart=/usr/bin/python3 /path/to/ip-updater/auto_update_ip.py
User=your-user
Environment="GOOGLE_APPLICATION_CREDENTIALS=/path/to/gcp-credentials.json"

[Install]
WantedBy=multi-user.target
```

Tạo timer file `/etc/systemd/system/ip-updater.timer`:

```ini
[Unit]
Description=IP Updater Timer
Requires=ip-updater.service

[Timer]
OnBootSec=5min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
```

Kích hoạt timer:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ip-updater.timer
sudo systemctl start ip-updater.timer
sudo systemctl status ip-updater.timer
```

---

## 🧪 Testing

### Chạy tests

```bash
python3 -m pip install pytest pytest-cov
pytest -v
pytest --cov=auto_update_ip --cov-report=html
```

**Coverage hiện tại:** >85%

- IP detection & caching
- Load & validate config
- Update GCP Firewall & Cloud SQL
- Update AWS Security Groups
- Error handling
- Dry-run mode

---

## 📂 Cấu Trúc Thư Mục

```
ip-updater/
├── auto_update_ip.py          # Main script (v2.0)
├── config.json                # Config cá nhân (gitignored)
├── config.json.example        # Mẫu config
├── gcp-credentials.json       # GCP credentials (gitignored)
├── requirements.txt           # Python dependencies
├── pytest.ini                 # Pytest config
├── .gitignore                 # Git ignore rules
├── README.md                  # Tài liệu này
├── CHANGELOG.md               # Lịch sử phiên bản
├── LICENSE                    # MIT License
├── tests/
│   ├── conftest.py
│   └── test_auto_update_ip.py
└── ip_update.log              # Log file (tự động tạo)
```

---

## 🔐 Security Best Practices

### Credentials

- Không commit credentials vào git
- Dùng `.gitignore` để loại trừ file nhạy cảm
- Sử dụng environment variables khi có thể
- Set quyền file: `chmod 600 gcp-credentials.json`

### IAM Permissions

#### GCP

- Roles: `roles/compute.securityAdmin`, `roles/cloudsql.admin`
- Hoặc custom role:

```yaml
compute.firewalls.get
compute.firewalls.update
cloudsql.instances.get
cloudsql.instances.update
```

#### AWS

IAM policy tối thiểu:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:AuthorizeSecurityGroupIngress",
        "ec2:RevokeSecurityGroupIngress",
        "ec2:DescribeSecurityGroups"
      ],
      "Resource": "*"
    }
  ]
}
```

### Network Security

- Chỉ mở port cần thiết
- Sử dụng CIDR `/32` cho IP đơn
- Kiểm tra log thường xuyên
- Thiết lập cảnh báo khi có thay đổi

---

## 🐛 Troubleshooting

### Lỗi cấu hình

```bash
cp config.json.example config.json
# Sửa lại config.json
```

### Lỗi GCP credentials

```bash
ls -la gcp-credentials.json
export GOOGLE_APPLICATION_CREDENTIALS="$PWD/gcp-credentials.json"
gcloud auth application-default login
```

### Lỗi AWS credentials

```bash
aws configure
cat ~/.aws/credentials
aws sts get-caller-identity
```

### Không phát hiện thay đổi IP

```bash
rm last_known_ip.txt
python3 auto_update_ip.py --force --verbose
```

### Test dry-run

```bash
python3 auto_update_ip.py --dry-run --verbose
```

### Kiểm tra logs

```bash
tail -f ip_update.log
tail -f ip_update.log | grep "ERROR\|WARNING"
```

---

## 📝 Changelog

### v2.0.0 (2025-10-08)

- Refactor OOP
- Thêm CLI arguments
- Logging & error handling nâng cao
- Loại bỏ lặp code
- Optional dependencies
- Test suite đầy đủ
- Cập nhật tài liệu

### v1.0.0

- Ra mắt ban đầu
- Update IP cho GCP Firewall, Cloud SQL, AWS Security Groups

---

## 🤝 Đóng Góp

Chào mừng mọi đóng góp!

1. Fork repo
2. Tạo branch mới (`git checkout -b feature/AmazingFeature`)
3. Commit thay đổi (`git commit -m 'Add AmazingFeature'`)
4. Push lên branch (`git push origin feature/AmazingFeature`)
5. Mở Pull Request

---

## 📄 License

Dự án theo MIT License - xem [LICENSE](LICENSE) để biết chi tiết.

---

## 👥 Tác Giả

- **Le Quyet Tien**

---

## 🙏 Cảm Ơn

- Google Cloud Python SDK
- AWS Boto3
- Python Requests library
- Các contributor

---

## 📞 Hỗ Trợ

- 📧 Email: [lequyettien.it@gmail.com](mailto:lequyettien.it@gmail.com)
- 🐛 Issues: [GitHub Issues](https://github.com/lequyettien/ip-updater/issues)
- 📖 Docs: [Wiki](https://github.com/lequyettien/ip-updater/wiki)

---

Made with ❤️ by Le Quyet Tien
