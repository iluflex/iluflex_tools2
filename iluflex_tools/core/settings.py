from __future__ import annotations
import json, os
from dataclasses import dataclass, asdict

APP_DIR = os.path.join(os.path.expanduser("~"), ".iluflex_tools")
SETTINGS_PATH = os.path.join(APP_DIR, "settings.json")

@dataclass
class Settings:
    theme: str = "system"            # "system" | "dark" | "light"
    discovery_timeout_ms: int = 2000 # tempo padrão para "procurar não dispositivos não cadastrados"
    last_ip: str = "192.168.1.70"
    last_port: int = 4999


def load_settings() -> Settings:
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Settings(**data)
    except Exception:
        return Settings()

def save_settings(s: Settings) -> None:
    os.makedirs(APP_DIR, exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(asdict(s), f, ensure_ascii=False, indent=2)
