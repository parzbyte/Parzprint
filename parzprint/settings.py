"""Configurações do Parzprint: padrões, leitura e escrita em settings.json."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

import platformdirs

from parzprint.translate.languages import AUTO, LANGUAGES, MAX_RECENT

MODIFIERS = ("Ctrl", "Shift", "Alt", "Win")
IMAGE_FORMATS = ("PNG", "JPG")
OCR_ENGINES = ("indra",)
DEFAULT_HOTKEY = "Ctrl+Shift+S"
DEFAULT_PTT_HOTKEY = "Ctrl+Alt+Space"
DEFAULT_TRANSLATE_HOTKEY = "Ctrl+Alt+T" if sys.platform == "win32" else "Ctrl+Alt+Y"
TRANSLATE_MIN_SIZE = (320, 160)
_LANG_CODES = frozenset(code for code, _ in LANGUAGES)
REC_RESOLUTIONS = ("original", "1080", "720", "480")
REC_FPS = (30, 15)
REC_QUALITIES = ("alta", "media", "leve")
MIC_MODES = ("off", "always", "ptt")


def DEFAULT_PICTURES_DIR() -> str:
    try:
        return platformdirs.user_pictures_dir()
    except Exception:  # noqa: BLE001
        return str(Path.home())


def DEFAULT_VIDEOS_DIR() -> str:
    try:
        base = platformdirs.user_videos_dir()
    except Exception:  # noqa: BLE001
        base = str(Path.home())
    return str(Path(base) / "Parzprint")


@dataclass
class Settings:
    hotkey: str = DEFAULT_HOTKEY
    autostart: bool = True
    save_dir: str = field(default_factory=DEFAULT_PICTURES_DIR)
    image_format: str = "PNG"
    ocr_engine: str = "indra"
    video_dir: str = field(default_factory=DEFAULT_VIDEOS_DIR)
    rec_resolution: str = "original"
    rec_fps: int = 30
    rec_quality: str = "media"
    rec_compress: bool = True
    rec_countdown: bool = True
    ptt_hotkey: str = DEFAULT_PTT_HOTKEY
    mic_device: str = ""
    mic_mode: str = "always"
    system_audio: bool = True
    translate_hotkey: str = DEFAULT_TRANSLATE_HOTKEY
    translate_grab_selection: bool = True
    translate_source: str = AUTO
    translate_target: str = "pt"
    translate_recent: list[str] = field(default_factory=list)
    translate_size: list[int] = field(default_factory=lambda: [640, 300])
    translate_pinned: bool = False


def hotkey_conflict(s: Settings) -> str | None:
    """Mensagem se dois atalhos entre captura, falar e tradutor forem iguais."""
    names = (("captura", s.hotkey), ("aperte para falar", s.ptt_hotkey), ("tradutor", s.translate_hotkey))
    for i, (a_name, a) in enumerate(names):
        for b_name, b in names[i + 1 :]:
            if a == b:
                return f"O atalho {a} está repetido em: {a_name} e {b_name}."
    return None


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
    if name in ("rec_compress", "rec_countdown", "system_audio"):
        return isinstance(value, bool)
    if name == "video_dir":
        return isinstance(value, str) and bool(value)
    if name == "rec_resolution":
        return value in REC_RESOLUTIONS
    if name == "rec_fps":
        return isinstance(value, int) and not isinstance(value, bool) and value in REC_FPS
    if name == "rec_quality":
        return value in REC_QUALITIES
    if name == "ptt_hotkey":
        return is_valid_hotkey(value)  # type: ignore[arg-type]
    if name == "mic_device":
        return isinstance(value, str)
    if name == "mic_mode":
        return value in MIC_MODES
    if name == "translate_hotkey":
        return is_valid_hotkey(value)  # type: ignore[arg-type]
    if name in ("translate_grab_selection", "translate_pinned"):
        return isinstance(value, bool)
    if name == "translate_source":
        return isinstance(value, str) and (value == AUTO or value in _LANG_CODES)
    if name == "translate_target":
        return isinstance(value, str) and value in _LANG_CODES
    if name == "translate_recent":
        return (
            isinstance(value, list)
            and len(value) <= MAX_RECENT
            and all(isinstance(c, str) and c in _LANG_CODES for c in value)
        )
    if name == "translate_size":
        return (
            isinstance(value, list)
            and len(value) == 2
            and all(isinstance(n, int) and not isinstance(n, bool) for n in value)
            and value[0] >= TRANSLATE_MIN_SIZE[0]
            and value[1] >= TRANSLATE_MIN_SIZE[1]
        )
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
