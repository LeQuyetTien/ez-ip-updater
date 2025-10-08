# Changelog

All notable changes to **IP Updater** are documented here.

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2025-10-08

### 🎉 Major Refactoring Release

#### Added

- **Object-Oriented Architecture**: Introduced core classes (`Config`, `IPService`, `GCPUpdater`, `AWSUpdater`, `IPUpdater`) for improved modularity.
- **CLI Arguments**:
  - `--config`: Specify alternative config file.
  - `--dry-run`: Simulate updates without making changes.
  - `--force`: Force update even if IP has not changed.
  - `--verbose`: Enable detailed (DEBUG level) logging.
  - `--version`: Display current version.
- **Enhanced Logging**:
  - Separate console and file handlers.
  - Configurable log levels.
  - Improved message formatting with icons (✓, ✗, ⚠, ⊘).
- **Comprehensive Testing**: Achieved 85%+ coverage using pytest.
- **Optional Dependencies**: SDK packages are now optional.
- **Robust Error Handling**:
  - Detailed error messages.
  - Graceful fallback when SDKs are unavailable.
  - Proper exception management.
- **Config Validation**: Automatic validation of config structure on load.
- **Documentation**:
  - Expanded README with examples.
  - Dedicated CHANGELOG file.
  - Inline documentation for all classes and methods.

#### Changed

- **Code Deduplication**:
  - Merged AWS update methods into a generic function.
  - Unified credential loading logic.
  - Applied DRY principles throughout.
- **Improved Structure**:
  - Clear separation of concerns (IP detection, config, cloud updates).
  - Adherence to Single Responsibility Principle.
  - Enhanced testability and maintainability.
- **Return Values**: Functions now return boolean success status.
- **Logging**: More informative and consistent log messages.

#### Removed

- Hardcoded configuration values.
- Duplicate code blocks.
- Unnecessary global variables.
- Commented-out code.

#### Fixed

- GCP Firewall Rules: Credentials now load correctly.
- `googleapiclient` import errors when package is missing.
- AWS: Improved duplicate rule handling.
- Cache file operation edge cases.
- Config loading errors.

## [1.0.0] - 2024-10-07

### Initial Release

#### Added

- Public IP detection via external services.
- GCP Firewall Rules update.
- GCP Cloud SQL Authorized Networks update.
- AWS Security Groups update (SSH and MySQL).
- IP caching to detect changes.
- Logging to file and console.
- Configuration via `config.json`.

#### Features

- Automatic public IP detection.
- GCP firewall rules update.
- GCP Cloud SQL authorized networks update.
- AWS security groups update.
- IP caching to avoid unnecessary updates.
- Detailed logging.

## Migration Guide: v1.0 → v2.0

### Breaking Changes

**None** — v2.0 is backward compatible. Existing `config.json` and credentials remain valid.

### Recommended Updates

1. **Update script file**:

    ```bash
    # Backup old version
    cp auto_update_ip.py auto_update_ip_v1.py

    # Use new version
    # (already done if you pulled latest)
    ```

2. **Utilize new CLI options**:

    ```bash
    # Dry-run mode
    python3 auto_update_ip.py --dry-run

    # Force update
    python3 auto_update_ip.py --force

    # Verbose logging
    python3 auto_update_ip.py --verbose
    ```

3. **Update cron jobs** (optional):

    ```cron
    # Old
    */5 * * * * cd /path/to/ip-updater && python3 auto_update_ip.py

    # New with verbose logging
    */5 * * * * cd /path/to/ip-updater && python3 auto_update_ip.py --verbose >> /var/log/ip_updater.log 2>&1
    ```

4. **Run tests** to verify:

    ```bash
    pytest tests/test_refactored.py -v
    ```

### Unchanged

- ✅ `config.json` structure
- ✅ Credentials setup
- ✅ Log file location
- ✅ Core functionality
- ✅ No new dependencies required

### Improvements

- ✅ More reliable error handling
- ✅ Enhanced logging with icons
- ✅ Dry-run mode for safe testing
- ✅ Force mode to override cache
- ✅ Verbose mode for debugging
- ✅ Cleaner, maintainable codebase
- ✅ Improved test coverage

## Future Roadmap

### v2.1.0 (Planned)

- [ ] Multiple config profile support
- [ ] Slack/Discord notifications on IP change
- [ ] Prometheus metrics export
- [ ] Web UI dashboard
- [ ] Docker container support

### v2.2.0 (Planned)

- [ ] Azure support
- [ ] Digital Ocean support
- [ ] Cloudflare DNS update
- [ ] Email notifications
- [ ] Webhook support

### v3.0.0 (Future)

- [ ] Plugin system for custom providers
- [ ] REST API
- [ ] Database storage for IP history
- [ ] Multi-region support
- [ ] High Availability configuration

## Security Updates

### Security Best Practices

- Use `.gitignore` to exclude credentials.
- Set strict file permissions: `chmod 600 gcp-credentials.json`.
- Apply minimum required IAM permissions.
- Rotate credentials regularly.
- Monitor logs for suspicious activity.

### Vulnerability Reporting

If you discover a security vulnerability, please email: [lequyettien.it@gmail.com](mailto:lequyettien.it@gmail.com)  
Do not open a public issue.

## Support

- 📧 Email: [lequyettien.it@gmail.com](mailto:lequyettien.it@gmail.com)
- 🐛 Issues: [GitHub Issues](https://github.com/lequyettien/ip-updater/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/lequyettien/ip-updater/discussions)

---

**Legend:**  
🎉 Major feature | ✨ New feature | ♻️ Refactoring | 🐛 Bug fix | 📝 Documentation | 🔒 Security | ⚡ Performance | 🚨 Breaking change
