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

@dataclass
class IPv4Config:
    """Config desejada para aplicar via SRF,16."""
    dhcp: bool
    ip: str = ""
    netmask: str = ""
    gateway: str = ""
    dns1: str = ""
    dns2: str = ""
    hostname: str = ""
    raw: str = ""

@dataclass
class IPv4Snapshot:
    """Snapshot de rede retornado por RRF,16,6/9."""
    ip: str
    netmask: str
    gateway: str
    dns1: str
    dns2: str
    mac: str
    dhcp_flag: str  # "0"=DHCP; "1"=fixo
    hostname: str
    raw: str

    @property
    def dhcp(self) -> bool:
        return self.dhcp_flag == "0"

