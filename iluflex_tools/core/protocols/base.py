from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, Any

class BaseParser(ABC):
    @abstractmethod
    def match(self, line: str) -> bool: ...
    @abstractmethod
    def parse(self, line: str) -> Optional[Any]: ...
