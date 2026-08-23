"""position-guard — DeFi health monitor with AI alerts.

Tracks Aave v3 / Compound v3 positions via The Graph public subgraphs,
computes health factors, and pushes plain-English alerts (LLM-written with a
deterministic template fallback). Telegram optional; keyless web-preview demo
by default.
"""

__version__ = "0.1.0"

# The bundled demo identity. All zeros-padded hex, obviously synthetic — it is
# only ever paired with the bundled fixture payloads, never queried live.
DEMO_ADDRESS = "0x" + "d3" * 20

PROTOCOL_AAVE_V3 = "aave-v3"
PROTOCOL_COMPOUND_V3 = "compound-v3"
SUPPORTED_PROTOCOLS = (PROTOCOL_AAVE_V3, PROTOCOL_COMPOUND_V3)