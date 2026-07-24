import plistlib
from pathlib import Path
from unittest.mock import patch

from ez_ip_updater import autostart


def test_command_uses_module_and_absolute_config(tmp_path):
    config = tmp_path / "config.json"
    command = autostart.command_for(config, Path("/tmp/python"))
    assert command[:3] == [
        str(Path("/tmp/python").resolve()),
        "-m",
        "ez_ip_updater.cli",
    ]
    assert command[-1] == str(config.resolve())


def test_install_macos_writes_plist(tmp_path):
    config = tmp_path / "project" / "config.json"
    config.parent.mkdir()
    config.write_text("{}")
    home = tmp_path / "home"
    with (
        patch.object(Path, "home", return_value=home),
        patch.object(autostart.os, "getuid", return_value=501),
        patch.object(autostart.subprocess, "run") as run,
    ):
        target = autostart.install_macos(config)
    payload = plistlib.loads(target.read_bytes())
    assert payload["RunAtLoad"] is True
    assert payload["StartInterval"] == 300
    assert payload["WorkingDirectory"] == str(config.parent)
    assert run.call_count == 3


def test_uninstall_macos_removes_plist(tmp_path):
    home = tmp_path / "home"
    target = home / "Library" / "LaunchAgents" / f"{autostart.LABEL}.plist"
    target.parent.mkdir(parents=True)
    target.write_text("temporary")
    with (
        patch.object(Path, "home", return_value=home),
        patch.object(autostart.os, "getuid", return_value=501),
        patch.object(autostart.subprocess, "run"),
    ):
        autostart.uninstall_macos()
    assert not target.exists()


def test_install_windows_creates_logon_and_interval_tasks(tmp_path):
    config = tmp_path / "config.json"
    with (
        patch.object(autostart.shutil, "which", return_value="schtasks.exe"),
        patch.object(autostart.subprocess, "run") as run,
    ):
        autostart.install_windows(config)
    commands = [item.args[0] for item in run.call_args_list]
    assert "ONLOGON" in commands[0]
    assert "MINUTE" in commands[1]
