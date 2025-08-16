from dataclasses import dataclass

@dataclass
class AppState:
    connected: bool = False
    ip: str = "192.168.0.10"
    port: int = 4999
