"""Configurações do Parzprint: padrões, leitura e escrita em settings.json."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

import platformdirs

MODIFIERS = ("Ctrl", "Shift", "Alt", "Win")
IMAGE_FORMATS = ("PNG", "JPG")
OCR_ENGINES = ("indra",)
DEFAULT_HOTKEY = "Ctrl+Shift+S"


def DEFAULT_PICTURES_DIR() -> str:
    try:
        return platformdirs.user_pictures_dir()
    except Exception:  # noqa: BLE001
        return str(Path.home())


@dataclass
class Settings:
    hotkey: str = DEFAULT_HOTKEY
    autostart: bool = True
    save_dir: str = field(default_factory=DEFAULT_PICTURES_DIR)
    image_format: str = "PNG"
    ocr_engine: str = "indra"


def settings_path() -> Path:
    app = "Parzprint" if sys.platform == "win32" else "parzprint"
    return Path(platformdirs.user_config_dir(app, appauthor=False)) / "settings.json"


def is_valid_hotkey(text: str) -> bool:
    if not isinstance(text, str) or not text:
        return False
    parts = text.split("+")
    if len(parts) < 2:
        return False
    *mods, key = parts
    if not key or key in MODIFIERS:
        return False
    return all(m in MODIFIERS for m in mods) and len(set(mods)) == len(mods)


def _valid(name: str, value: object) -> bool:
    if name == "hotkey":
        return is_valid_hotkey(value)  # type: ignore[arg-type]
    if name == "autostart":
        return isinstance(value, bool)
    if name == "save_dir":
        return isinstance(value, str) and bool(value)
    if name == "image_format":
        return value in IMAGE_FORMATS
    if name == "ocr_engine":
        return value in OCR_ENGINES
    return False


def load_settings(path: Path | None = None) -> Settings:
    path = path or settings_path()
    defaults = Settings()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return defaults
    except (OSError, ValueError):
        raw = None
    if not isinstance(raw, dict):
        try:
            save_settings(defaults, path)
        except OSError:
            pass
        return defaults
    values = {
        f.name: raw[f.name]
        for f in fields(Settings)
        if f.name in raw and _valid(f.name, raw[f.name])
    }
    return Settings(**values)


def save_settings(settings: Settings, path: Path | None = None) -> None:
    path = path or settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), indent=2, ensure_ascii=False), encoding="utf-8")
