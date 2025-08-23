from __future__ import annotations
import json, os
from dataclasses import dataclass, asdict, fields
from typing import Any
from iluflex_tools.core.protocols.types import Settings, AppState

APP_DIR = os.path.join(os.path.expanduser("~"), ".iluflex_tools")
SETTINGS_PATH = os.path.join(APP_DIR, "settings.json")

def _coerce(value, typ, default):
    """Coerção defensiva para tipos simples (int, float, str)."""
    try:
        if typ is int:
            return int(value)
        if typ is float:
            return float(value)
        if typ is str:
            return str(value)
        return value
    except Exception:
        return default


def load_settings() -> Settings:
    """Carrega settings, mesclando com defaults e corrigindo tipos."""
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
    except Exception:
        return Settings()

    s = Settings()  # defaults
    for f in fields(Settings):
        cur_default = getattr(s, f.name)
        raw = data.get(f.name, cur_default)
        setattr(s, f.name, _coerce(raw, f.type, cur_default))
    return s


def save_settings(s: Settings) -> None:
    """Grava settings no disco (cria pasta se necessário)."""
    os.makedirs(APP_DIR, exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(asdict(s), f, ensure_ascii=False, indent=2)
