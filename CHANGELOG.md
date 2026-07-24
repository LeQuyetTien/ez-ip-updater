# Changelog

All notable changes to **IP Updater** are documented here.

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- One-command autostart installer and uninstaller for macOS and Windows.
- Tests for LaunchAgent and Windows Scheduled Task generation.
- Per-provider state, atomic writes, process locking, and rotating logs.
- Provider enable/disable flags and strict IPv4 validation.
- Installable CLI commands for updater and autostart management.

### Changed

- Reduced `requirements.txt` to direct project dependencies.
- Ignored local backup exports and launchd logs.
- Refactored the single module into the `ez_ip_updater` package.
- AWS now authorizes the new IP before revoking the old IP.
- Python 3.10 is now the minimum supported version.

### Fixed

- Optional GCP dependencies no longer cause an import-time annotation error.
- GCP removes stale IPs even when the desired IP already exists.
- Partial provider success is persisted without advancing failed providers.

### Removed

- Legacy root scripts and compatibility module.
- Shared `last_known_ip.txt` cache; provider state is now authoritative.

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
