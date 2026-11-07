import sys

import pytest

from parzprint import autostart
from parzprint.autostart import desktop_entry, executable_command, is_autostart_enabled, set_autostart


def test_desktop_entry_contains_exec():
    e = desktop_entry("/opt/parzprint")
    assert e.startswith("[Desktop Entry]")
    assert "Type=Application" in e
    assert "Name=Parzprint" in e
    assert "Exec=/opt/parzprint" in e
    assert "X-GNOME-Autostart-enabled=true" in e


def test_executable_command_not_frozen():
    cmd = executable_command()
    assert "python" in cmd.lower() and cmd.endswith("-m parzprint")
    if sys.platform == "win32":
        assert "pythonw" in cmd.lower()


def test_executable_command_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert executable_command() == f'"{sys.executable}"'


def test_linux_enable_disable(tmp_path):
    p = tmp_path / "autostart" / "parzprint.desktop"
    set_autostart(True, platform="linux", command="x", linux_path=p)
    assert p.exists() and "Exec=x" in p.read_text(encoding="utf-8")
    assert is_autostart_enabled(platform="linux", linux_path=p)
    set_autostart(False, platform="linux", linux_path=p)
    assert not p.exists()
    assert not is_autostart_enabled(platform="linux", linux_path=p)
    set_autostart(False, platform="linux", linux_path=p)  # idempotent


@pytest.mark.skipif(sys.platform != "win32", reason="windows")
def test_windows_enable_disable(monkeypatch):
    monkeypatch.setattr(autostart, "_windows_key_path", lambda: r"Software\ParzprintTest\Run")
    try:
        set_autostart(True, platform="win32", command="C:/x.exe")
        assert is_autostart_enabled(platform="win32")
        set_autostart(False, platform="win32")
        assert not is_autostart_enabled(platform="win32")
        set_autostart(False, platform="win32")  # idempotent
    finally:
        import winreg

        for k in (r"Software\ParzprintTest\Run", r"Software\ParzprintTest"):
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, k)
            except OSError:
                pass
