"""Install and remove per-user background tasks on macOS and Windows."""

from __future__ import annotations

import argparse
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence

LABEL = "com.lequyettien.ez-ip-updater"
WINDOWS_TASKS = ("EZ IP Updater - Logon", "EZ IP Updater - Interval")
INTERVAL_SECONDS = 300


def project_root() -> Path:
    return Path.cwd().resolve()


def find_config(config: str | Path = "config.json") -> Path:
    return Path(config).expanduser().resolve()


def command_for(
    config: str | Path = "config.json",
    python: Optional[Path] = None,
) -> list[str]:
    executable = (python or Path(sys.executable)).resolve()
    return [
        str(executable),
        "-m",
        "ez_ip_updater.cli",
        "--config",
        str(find_config(config)),
    ]


def validate(config: Path) -> None:
    if not config.is_file():
        raise SystemExit(
            f"Thiếu {config}. Hãy sao chép config.json.example thành config.json."
        )
    try:
        import ez_ip_updater  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "Package chưa được cài. Chạy: python -m pip install -e .[all]"
        ) from exc


def install_macos(config: Path, dry_run: bool = False) -> Path:
    root = config.parent
    target = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
    payload = {
        "Label": LABEL,
        "ProgramArguments": command_for(config),
        "WorkingDirectory": str(root),
        "RunAtLoad": True,
        "StartInterval": INTERVAL_SECONDS,
        "ProcessType": "Background",
        "StandardOutPath": str(root / "launchd-output.log"),
        "StandardErrorPath": str(root / "launchd-error.log"),
    }
    if dry_run:
        print(plistlib.dumps(payload).decode())
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(plistlib.dumps(payload))
    domain = f"gui/{os.getuid()}"
    subprocess.run(
        ["launchctl", "bootout", domain, str(target)],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(["launchctl", "bootstrap", domain, str(target)], check=True)
    subprocess.run(
        ["launchctl", "kickstart", "-k", f"{domain}/{LABEL}"], check=True
    )
    return target


def windows_action(config: Path) -> str:
    return subprocess.list2cmdline(command_for(config))


def install_windows(config: Path, dry_run: bool = False) -> tuple[str, ...]:
    schtasks = shutil.which("schtasks")
    if not schtasks:
        raise SystemExit("Không tìm thấy schtasks.exe.")
    action = windows_action(config)
    commands = [
        [
            schtasks, "/Create", "/TN", WINDOWS_TASKS[0], "/SC", "ONLOGON",
            "/TR", action, "/F",
        ],
        [
            schtasks, "/Create", "/TN", WINDOWS_TASKS[1], "/SC", "MINUTE",
            "/MO", str(INTERVAL_SECONDS // 60), "/TR", action, "/F",
        ],
    ]
    if dry_run:
        for command in commands:
            print(subprocess.list2cmdline(command))
        return WINDOWS_TASKS
    for command in commands:
        subprocess.run(command, check=True)
    return WINDOWS_TASKS


def uninstall_macos() -> None:
    target = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
    domain = f"gui/{os.getuid()}"
    subprocess.run(
        ["launchctl", "bootout", domain, str(target)],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    target.unlink(missing_ok=True)


def uninstall_windows() -> None:
    schtasks = shutil.which("schtasks")
    if not schtasks:
        raise SystemExit("Không tìm thấy schtasks.exe.")
    for task in WINDOWS_TASKS:
        subprocess.run(
            [schtasks, "/Delete", "/TN", task, "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def install_main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Cài EZ IP Updater tự chạy trên macOS hoặc Windows."
    )
    parser.add_argument("-c", "--config", default="config.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    config = find_config(args.config)
    validate(config)
    if sys.platform == "darwin":
        print(f"✓ LaunchAgent: {install_macos(config, args.dry_run)}")
    elif sys.platform == "win32":
        install_windows(config, args.dry_run)
        print("✓ Đã cấu hình Windows Scheduled Tasks")
    else:
        raise SystemExit("Hiện chỉ hỗ trợ macOS và Windows.")
    return 0


def uninstall_main(_argv: Optional[Sequence[str]] = None) -> int:
    if sys.platform == "darwin":
        uninstall_macos()
    elif sys.platform == "win32":
        uninstall_windows()
    else:
        raise SystemExit("Hiện chỉ hỗ trợ macOS và Windows.")
    print("✓ Đã gỡ cấu hình tự động chạy")
    return 0
