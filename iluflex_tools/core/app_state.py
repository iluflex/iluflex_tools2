# iluflex_tools/core/app_state.py
"""AppState global baseado em **classe** (simples e direto).

- Encapsula leitura/gravação e persistência opcional
- Coerção automática de tipos (str/int/bool/float)
- Disponível como singleton `STATE`

Uso rápido:

```py
from iluflex_tools.core.app_state import STATE

# Boot
STATE.sync_from_settings()

# Ler (direto)
print(STATE.data.ip, STATE.data.port)

# Atualizar campo genérico
STATE.set("ip", "192.168.1.70")
STATE.set("port", "4999")         # vira int
STATE.set("auto_reconnect", "yes") # vira bool

# Atalho
STATE.set_ip_port("192.168.1.80", 5000)

# Vários de uma vez
STATE.set_many({"ip": "192.168.1.90", "port": "5001", "connected": True})
```
"""
from __future__ import annotations
from dataclasses import dataclass, fields
from typing import Any

# ----------------- modelo de estado -----------------
@dataclass
class AppState:
    ip: str = "192.168.1.50"
    port: int = 4999
    connected: bool = False
    auto_reconnect: bool = False
    theme: str = "system"            # "system" | "dark" | "light"
    discovery_timeout_ms: int = 5000 # tempo padrão para buscar interfaces na rede via UDP para conexão via socket
    mesh_discovery_timeout_sec: int = 120 # tempo padrão para Descorir Novos Dispositivos na Rede Mesh


# ----------------- gerenciador -----------------
class AppStateManager:
    def __init__(self, initial: AppState | None = None, *, persist_default: bool = True) -> None:
        self.data: AppState = initial or AppState()
        self._persist_default = persist_default
        self._field_types = {f.name: f.type for f in fields(AppState)}
        # imports tardios para evitar dependência cíclica
        try:
            from iluflex_tools.core.settings import load_settings, save_settings  # type: ignore
        except Exception:  # ambiente de testes
            load_settings = save_settings = None  # type: ignore
        self._load_settings = load_settings  # type: ignore
        self._save_settings = save_settings  # type: ignore

    # -------------- helpers --------------
    @staticmethod
    def _coerce(value: Any, target_type: type) -> Any:
        # Aceita valores vindos de UI (string) e converte de forma tolerante
        try:
            if target_type is bool:
                if isinstance(value, str):
                    v = value.strip().lower()
                    if v in {"1", "true", "t", "yes", "y", "on", "sim"}:
                        return True
                    if v in {"0", "false", "f", "no", "n", "off", "nao", "não", ""}:
                        return False
                return bool(value)
            if target_type is int:
                return int(value)
            if target_type is float:
                return float(value)
            if target_type is str:
                return str(value)
        except Exception:
            pass
        return value

    def _persist_field(self, field: str, value: Any) -> None:
        if not (self._load_settings and self._save_settings):
            return
        try:
            s = self._load_settings()
            for name in (f"last_{field}", field):
                if hasattr(s, name):
                    setattr(s, name, value)
                    self._save_settings(s)
                    return
        except Exception:
            pass

    # -------------- API --------------
    def sync_from_settings(self) -> None:
        """Carrega valores iniciais (se houver settings)."""
        if not self._load_settings:
            return
        try:
            s = self._load_settings()
            if hasattr(s, "last_ip") and getattr(s, "last_ip"):
                self.data.ip = str(s.last_ip)
            if hasattr(s, "last_port") and getattr(s, "last_port"):
                self.data.port = int(s.last_port)
            if hasattr(s, "theme") and getattr(s, "theme"):
                self.data.theme = str(s.theme)
            if hasattr(s, "discovery_timeout_ms") and getattr(s, "discovery_timeout_ms"):
                self.data.discovery_timeout_ms = int(s.discovery_timeout_ms)
            if hasattr(s, "mesh_discovery_timeout_sec") and getattr(s, "mesh_discovery_timeout_sec"):
                self.data.mesh_discovery_timeout_sec = int(s.mesh_discovery_timeout_sec)

        except Exception:
            pass

    def set(self, field: str, value: Any, *, persist: bool | None = None) -> None:
        """Atualiza um campo do estado (com coerção) e persiste opcionalmente."""
        if not hasattr(self.data, field):
            return
        target = self._field_types.get(field, type(getattr(self.data, field)))
        coerced = self._coerce(value, target)
        setattr(self.data, field, coerced)
        if (self._persist_default if persist is None else persist):
            self._persist_field(field, coerced)

    # alias solicitado: nome "set_settings"
    set_settings = set

    def set_many(self, updates: dict[str, Any], *, persist: bool | None = None) -> None:
        for k, v in updates.items():
            self.set(k, v, persist=persist)

    def set_ip_port(self, ip: Any, port: Any, *, persist: bool | None = None) -> None:
        self.set("ip", ip, persist=persist)
        self.set("port", port, persist=persist)


# Singleton global
STATE = AppStateManager()


