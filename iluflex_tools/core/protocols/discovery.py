from __future__ import annotations
from typing import Optional
from .base import BaseParser
from .types import DiscoveryFoundRaw

class DiscoveryFoundParser(BaseParser):
    """Aceita SOMENTE linhas que começam com 'Found:' ou 'FOUND:'."""
    def match(self, line: str) -> bool:
        s = line.lstrip()
        return s.startswith("Found:") or s.startswith("FOUND:")

    def parse(self, line: str) -> Optional[DiscoveryFoundRaw]:
        return DiscoveryFoundRaw(raw=line.strip())
