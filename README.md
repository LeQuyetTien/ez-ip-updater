# EZ IP Updater

Tự động phát hiện IPv4 public và reconcile quyền truy cập vào:

- Google Cloud Firewall Rules
- Google Cloud SQL Authorized Networks
- AWS Security Groups

Chương trình chỉ thay đổi cloud khi IP của từng provider chưa ở trạng thái mong
muốn. State được lưu riêng cho từng provider, vì vậy lỗi AWS không làm GCP chạy
lại và ngược lại.

## Yêu cầu

- Python 3.10 trở lên
- macOS hoặc Windows nếu sử dụng trình cài autostart
- Credentials GCP/AWS có quyền tối thiểu phù hợp

## Cài đặt

```bash
git clone https://github.com/lequyettien/ip-updater.git
cd ip-updater
python -m venv .venv
```

Kích hoạt virtual environment:

```bash
# macOS/Linux
source .venv/bin/activate

# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

Cài package và tất cả provider:

```bash
python -m pip install -e ".[all]"
```

Tạo cấu hình:

```bash
# macOS/Linux
cp config.json.example config.json

# Windows PowerShell
Copy-Item config.json.example config.json
```

Sau đó sửa `config.json` theo tài nguyên của bạn.

## Cấu hình

```json
{
  "gcp": {
    "enabled": true,
    "project_id": "your-project",
    "credentials_file": "gcp-credentials.json",
    "firewall_rules": ["allow-office-ssh"],
    "sql_instances": ["production-db"]
  },
  "aws": {
    "enabled": true,
    "profile": "default",
    "region": "ap-southeast-1",
    "security_groups_ssh": [
      {
        "group_id": "sg-xxxxxxxx",
        "description": "Office SSH"
      }
    ],
    "security_groups_mysql": [],
    "ports_ssh": [
      {
        "protocol": "tcp",
        "port": 22,
        "description": "SSH"
      }
    ],
    "ports_mysql": []
  },
  "state_file": "ip_state.json",
  "lock_file": ".ip_updater.lock"
}
```

Đặt `enabled: false` cho provider không sử dụng. SDK của provider bị tắt không
cần được cài.

Không commit `config.json`, credentials, cache hoặc state. Các file này đã nằm
trong `.gitignore`.

## Chạy

```bash
ez-ip-updater
ez-ip-updater --dry-run
ez-ip-updater --force
ez-ip-updater --verbose
ez-ip-updater --custom-ip 203.0.113.10
```

`--dry-run` vẫn đọc trạng thái cloud nhưng không ghi thay đổi và không cập nhật
state local.

## Tự động chạy

Cài cho user hiện tại:

```bash
ez-ip-updater-install
```

Trình cài đặt sẽ:

- macOS: tạo LaunchAgent.
- Windows: tạo task lúc đăng nhập và task mỗi 5 phút.
- Chạy ngay khi đăng nhập và thử lại mỗi 5 phút.
- Dùng process lock để các lần chạy không chồng lên nhau.

Xem trước mà không thay đổi hệ thống:

```bash
ez-ip-updater-install --dry-run
```

Gỡ:

```bash
ez-ip-updater-uninstall
```

Nếu di chuyển hoặc xoá virtual environment/thư mục dự án, hãy gỡ autostart và
cài lại để scheduler nhận đường dẫn Python mới.

## Cơ chế an toàn

- Chỉ chấp nhận IPv4 hợp lệ.
- AWS thêm quyền cho IP mới trước khi xoá IP cũ.
- Reconcile idempotent: chạy lại không tạo rule trùng.
- State tách riêng `gcp_firewall`, `gcp_sql` và `aws`.
- File cache/state được ghi atomic.
- Process lock ngăn hai scheduler cùng sửa firewall.
- Log tự rotate: tối đa 5 MB, giữ ba bản backup.

## Credentials

GCP hỗ trợ service-account file trong cấu hình hoặc Application Default
Credentials. AWS hỗ trợ profile trong cấu hình/CLI và credential chain mặc định
của Boto3.

Nếu AWS báo `InvalidGroup.NotFound`, kiểm tra tài khoản đang sử dụng bằng
`aws sts get-caller-identity` (thêm `--profile TEN_PROFILE` nếu cần), rồi kiểm
tra `aws.region` và các `group_id` trong `config.json` với AWS Console. Security
group chỉ tồn tại trong một region và tài khoản; hãy cập nhật ID nếu group đã
bị xoá hoặc thay thế. Có thể chọn profile bằng `aws.profile` hoặc
`ez-ip-updater --aws-profile TEN_PROFILE`.

Chỉ cấp quyền cần thiết:

- GCP: đọc/cập nhật firewall và Cloud SQL instance được cấu hình.
- AWS: `ec2:AuthorizeSecurityGroupIngress`,
  `ec2:RevokeSecurityGroupIngress` và `ec2:DescribeSecurityGroups`.

## Test

```bash
python -m pip install -e ".[all]" pytest
python -m pytest
```

Test tập trung vào failure mode: IP không hợp lệ, lock cạnh tranh, state từng
provider, add-before-remove của AWS và reconcile IP cũ khi IP mới đã tồn tại.

## Cấu trúc

```text
ez_ip_updater/
├── autostart.py
├── cli.py
├── config.py
├── ip_service.py
├── locking.py
├── logging_utils.py
├── orchestrator.py
├── state.py
└── providers/
    ├── aws.py
    └── gcp.py
```
