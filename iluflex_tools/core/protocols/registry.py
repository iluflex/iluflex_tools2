from __future__ import annotations
from typing import List, Any
from .base import BaseParser

class ParserRegistry:
    def __init__(self) -> None:
        self._parsers: list[BaseParser] = []

    def register(self, parser: BaseParser) -> "ParserRegistry":
        self._parsers.append(parser)
        return self

    def parse_lines(self, text: str) -> List[Any]:
        results: list[Any] = []
        if not text:
            return results
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            for p in self._parsers:
                if p.match(line):
                    obj = p.parse(line)
                    if obj is not None:
                        results.append(obj)
                    break
        return results
