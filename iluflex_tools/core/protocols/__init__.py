# iluflex_tools.core.protocols
# iluflex_tools.core.protocols
from .registry import ParserRegistry
from .discovery import DiscoveryFoundParser
from .rrf10 import RRF10Parser
from .rrf16 import RRF16_6Parser, RRF16_9Parser, build_srf16_sequence
from .types import IPv4Config, IPv4Snapshot
from .ipvalidator import IPv4ConfigValidator

def make_default_registry() -> ParserRegistry:
    return (
        ParserRegistry()
        .register(DiscoveryFoundParser())
        .register(RRF10Parser())
        .register(RRF16_6Parser())
        .register(RRF16_9Parser())
    )
