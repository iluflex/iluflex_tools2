from __future__ import annotations
from dataclasses import replace
import ipaddress, re
from .types import IPv4Config

_HOST_RE = re.compile(r"^(?=.{1,253}$)(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")

class IPv4ConfigValidator:
    """Validador/normalizador stdlib. Uso: ok, err, cfg_norm = IPv4ConfigValidator.validate(cfg)"""

    @staticmethod
    def validate(cfg: IPv4Config) -> tuple[bool, str|None, IPv4Config]:
        # hostname opcional
        if cfg.hostname and not _HOST_RE.match(cfg.hostname):
            return False, "Hostname inválido (RFC-1123).", cfg

        # DHCP: só valida formatos de DNS se vierem
        if cfg.dhcp:
            for label, val in (("DNS1", cfg.dns1), ("DNS2", cfg.dns2)):
                if val:
                    try: ipaddress.IPv4Address(val)
                    except Exception: return False, f"{label} inválido.", cfg
            return True, None, replace(cfg)

        # IP fixo: IP/máscara/gateway obrigatórios
        if not (cfg.ip and cfg.netmask and cfg.gateway):
            return False, "IP, máscara e gateway são obrigatórios para IP fixo.", cfg

        try:
            ip_addr = ipaddress.IPv4Address(cfg.ip)
        except Exception as e:
            return False, f"IP inválido: {e}", cfg

        # aceita "/24" ou "255.255.255.0"
        try:
            if cfg.netmask.isdigit():
                pref = int(cfg.netmask)
                if not 0 <= pref <= 32:
                    return False, "Prefixo fora de 0..32.", cfg
                net = ipaddress.IPv4Network(f"{cfg.ip}/{pref}", strict=False)
            else:
                net = ipaddress.IPv4Network(f"{cfg.ip}/{cfg.netmask}", strict=False)
                pref = net.prefixlen
        except Exception as e:
            return False, f"Máscara inválida: {e}", cfg

        try:
            gw_addr = ipaddress.IPv4Address(cfg.gateway)
        except Exception as e:
            return False, f"Gateway inválido: {e}", cfg

        if pref >= 31:
            return False, "Prefixo /31 ou /32 não possui hosts utilizáveis.", cfg
        if ip_addr not in net:
            return False, "IP não pertence à rede calculada.", cfg
        if gw_addr not in net:
            return False, "Gateway não pertence à mesma rede do IP.", cfg
        if ip_addr in (net.network_address, net.broadcast_address):
            return False, "IP não pode ser rede/broadcast.", cfg
        if gw_addr in (net.network_address, net.broadcast_address):
            return False, "Gateway não pode ser rede/broadcast.", cfg
        if gw_addr == ip_addr:
            return False, "Gateway não pode ser igual ao IP.", cfg

        for label, val in (("DNS1", cfg.dns1), ("DNS2", cfg.dns2)):
            if val:
                try: ipaddress.IPv4Address(val)
                except Exception: return False, f"{label} inválido.", cfg

        # normaliza netmask para dotted
        cfg_norm = replace(cfg,
            ip=str(ip_addr),
            netmask=str(net.netmask),
            gateway=str(gw_addr),
            dns1=cfg.dns1.strip(),
            dns2=cfg.dns2.strip(),
            hostname=cfg.hostname.strip()
        )
        return True, None, cfg_norm
