"""Iniciar com o sistema: registro Run no Windows, arquivo .desktop no Linux."""

from __future__ import annotations

import sys
from pathlib import Path

WINDOWS_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
WINDOWS_VALUE = "Parzprint"


def _windows_key_path() -> str:
    return WINDOWS_RUN_KEY


def executable_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    exe = Path(sys.executable)
    if sys.platform == "win32":
        pythonw = exe.with_name("pythonw.exe")
        if pythonw.exists():
            exe = pythonw
    return f'"{exe}" -m parzprint'


def desktop_entry(command: str) -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Parzprint\n"
        "Comment=Captura de tela com OCR\n"
        f"Exec={command}\n"
        "Terminal=false\n"
        "X-GNOME-Autostart-enabled=true\n"
    )


def linux_autostart_path() -> Path:
    return Path.home() / ".config" / "autostart" / "parzprint.desktop"


def set_autostart(
    enabled: bool,
    *,
    platform: str = sys.platform,
    command: str | None = None,
    linux_path: Path | None = None,
) -> None:
    if platform == "win32":
        import winreg

        if enabled:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _windows_key_path()) as key:
                winreg.SetValueEx(key, WINDOWS_VALUE, 0, winreg.REG_SZ, command or executable_command())
        else:
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _windows_key_path(), 0, winreg.KEY_SET_VALUE) as key:
                    winreg.DeleteValue(key, WINDOWS_VALUE)
            except FileNotFoundError:
                pass
        return
    path = linux_path or linux_autostart_path()
    if enabled:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(desktop_entry(command or executable_command()), encoding="utf-8")
    else:
        path.unlink(missing_ok=True)


def is_autostart_enabled(*, platform: str = sys.platform, linux_path: Path | None = None) -> bool:
    if platform == "win32":
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _windows_key_path()) as key:
                winreg.QueryValueEx(key, WINDOWS_VALUE)
            return True
        except FileNotFoundError:
            return False
    return (linux_path or linux_autostart_path()).exists()
