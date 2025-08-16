from __future__ import annotations
import re
from typing import Optional, List, Dict, Any
from .base import BaseParser
from .types import DeviceStatusRRF10

_MAC = re.compile(r'^[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}$')

class RRF10Parser(BaseParser):
    """RRF,10,<slaveID>,<mac>,<sinaldB>,<macPai>,<modelo>,<versaoHW>,<versaoFW>,<data>,<n-saidas>,<n-entradas>,<nome>"""

    def match(self, line: str) -> bool:
        return line.startswith("RRF,10,")

    def parse(self, line: str) -> Optional[DeviceStatusRRF10]:
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 13:
            return None
        try:
            slave_id      = int(parts[2])
            mac           = parts[3]
            sinal_db      = int(parts[4])
            parent_mac    = parts[5]
            modelo        = parts[6]
            versao_hw     = int(parts[7])
            versao_fw     = int(parts[8])
            data_producao = parts[9]
            n_saidas      = int(parts[10])
            n_entradas    = int(parts[11])
            nome          = ",".join(parts[12:]).strip()

            if not _MAC.match(mac):
                mac = mac.lower()
            if not _MAC.match(parent_mac):
                parent_mac = parent_mac.lower()

            return DeviceStatusRRF10(
                slave_id=slave_id, mac=mac, sinal_db=sinal_db, parent_mac=parent_mac,
                modelo=modelo, versao_hw=versao_hw, versao_fw=versao_fw,
                data_producao=data_producao, n_saidas=n_saidas, n_entradas=n_entradas,
                nome=nome, raw=line
            )
        except Exception:
            return None

def parse_rrf10_lines(text: str) -> List[Dict[str, Any]]:
    """Helper procedural compatível com versões antigas."""
    out: list[dict] = []
    if not text:
        return out
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("RRF,10,"):
            continue
        p = RRF10Parser().parse(line)
        if p is None:
            continue
        out.append({
            "slave_id": p.slave_id,
            "mac": p.mac,
            "sinal_db": p.sinal_db,
            "parent_mac": p.parent_mac,
            "modelo": p.modelo,
            "versao_hw": p.versao_hw,
            "versao_fw": p.versao_fw,
            "data_producao": p.data_producao,
            "n_saidas": p.n_saidas,
            "n_entradas": p.n_entradas,
            "nome": p.nome,
            "raw": p.raw,
        })
    return out
