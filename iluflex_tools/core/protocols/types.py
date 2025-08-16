from __future__ import annotations
from dataclasses import dataclass

@dataclass
class DeviceStatusRRF10:
    slave_id: int
    mac: str
    sinal_db: int
    parent_mac: str
    modelo: str
    versao_hw: int
    versao_fw: int
    data_producao: str
    n_saidas: int
    n_entradas: int
    nome: str
    raw: str

@dataclass
class DiscoveryFoundRaw:
    raw: str
