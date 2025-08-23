from __future__ import annotations
from typing import Optional, List
from .base import BaseParser
from .types import IPv4Snapshot, IPv4Config

class RRF16_6Parser(BaseParser):
    """RRF,16,6,{IP},{NETMASK},{GATEWAY},{DNS1},{DNS2},{MAC},{DHCP},{NAME_HOST}"""
    def match(self, line: str) -> bool:
        return line.startswith("RRF,16,6,")

    def parse(self, line: str) -> Optional[IPv4Snapshot]:
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 11:
            return None
        ip, mask, gw, dns1, dns2, mac, dhcp, host = parts[3:11]
        return IPv4Snapshot(
            ip=ip, netmask=mask, gateway=gw, dns1=dns1, dns2=dns2,
            mac=mac, dhcp_flag=dhcp, hostname=host, raw=line.strip()
        )

class RRF16_9Parser(BaseParser):
    """RRF,16,9,{IP},{NETMASK},{GATEWAY},{DNS1},{DNS2},{MAC},{DHCP},{NAME_HOST} (preview próximo boot)"""
    def match(self, line: str) -> bool:
        return line.startswith("RRF,16,9,")

    def parse(self, line: str) -> Optional[IPv4Snapshot]:
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 11:
            return None
        ip, mask, gw, dns1, dns2, mac, dhcp, host = parts[3:11]
        return IPv4Snapshot(
            ip=ip, netmask=mask, gateway=gw, dns1=dns1, dns2=dns2,
            mac=mac, dhcp_flag=dhcp, hostname=host, raw=line.strip()
        )

def build_srf16_sequence(cfg: IPv4Config, *, mesh_ssid: str|None=None, mesh_pass: str|None=None, mesh_channel: int|None=None) -> List[str]:
    """
    Gera a sequência SRF para aplicar cfg (ordem correta).
    Sempre termina com 'SRF,16,9' para conferência.
    """
    cmds: list[str] = []
    # 0=dinâmico (DHCP), 1=fixed
    dhcp_flag = "0" if cfg.dhcp else "1"

    if not cfg.dhcp:
        if cfg.ip:      cmds.append(f"SRF,16,0,{cfg.ip}")
        if cfg.gateway: cmds.append(f"SRF,16,1,{cfg.gateway}")
        if cfg.netmask: cmds.append(f"SRF,16,2,{cfg.netmask}")
        if cfg.dns1:    cmds.append(f"SRF,16,3,{cfg.dns1}")
        if cfg.dns2:    cmds.append(f"SRF,16,4,{cfg.dns2}")

    cmds.append(f"SRF,16,5,{dhcp_flag}")
    if cfg.hostname:
        cmds.append(f"SRF,16,7,{cfg.hostname}")

    # Mesh (opcional)
    if mesh_ssid and mesh_pass and mesh_channel:
        cmds.append(f"SRF,15,0,0,{mesh_ssid},{mesh_pass},{mesh_channel}")

    # Preview do próximo boot
    cmds.append("SRF,16,9")
    return cmds
