# Changelog

All notable changes to **IP Updater** are documented here.

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

### v2.0.0 (Planned)

- [ ] Refactor to OOP design
- [ ] Add CLI arguments for dry-run, force update, verbose logging
- [ ] Improve logging and error handling
- [ ] Optional dependencies for AWS and GCP
- [ ] Comprehensive test suite
- [ ] Update documentation

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
