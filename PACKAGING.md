# Packaging and publishing

## Build

```bash
python -m pip install --upgrade build twine
python -m build
python -m twine check dist/*
```

Wheel chứa package `ez_ip_updater` và ba console commands:

- `ez-ip-updater`
- `ez-ip-updater-install`
- `ez-ip-updater-uninstall`

## Verify locally

```bash
python -m venv /tmp/ez-ip-updater-check
/tmp/ez-ip-updater-check/bin/python -m pip install "dist/ez_ip_updater-2.1.0-py3-none-any.whl[all]"
/tmp/ez-ip-updater-check/bin/ez-ip-updater --version
```

Trên Windows, dùng `Scripts\python.exe` thay cho `bin/python`.

## Publish

GitHub workflow publish khi push tag `v*`. TestPyPI là đích mặc định và cần
repository secret `TEST_PYPI_API_TOKEN`.

```bash
git tag v2.1.0
git push origin v2.1.0
```

Để publish PyPI thật, đặt `PUBLISH_TO: pypi` trong workflow và thêm secret
`PYPI_API_TOKEN`.
