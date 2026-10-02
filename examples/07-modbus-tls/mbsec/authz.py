"""Role-based authorisation, as in Modbus/TCP Security (MB-TCP-Security-v36, 8.4).

The server reads the role from the client certificate once, at the handshake, then
checks every request against a roles-to-rights rules database. The specification
leaves that database to the vendor, but requires it to be configurable by the end
user, with no hard-coded, unchangeable default roles (R-26 to R-28): here it is a
TOML file.
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path

from cryptography import x509

from mbsec.pki import ROLE_OID

# Modbus function codes used in the rules, for readable logs
FUNCTIONS = {
    1: "read coils",
    2: "read discrete inputs",
    3: "read holding registers",
    4: "read input registers",
    5: "write single coil",
    6: "write single register",
    15: "write multiple coils",
    16: "write multiple registers",
}


def role_from_certificate(der: bytes) -> str | None:
    """The role carried by a client certificate, or None (the spec's NULL role, R-23)."""
    cert = x509.load_der_x509_certificate(der)
    try:
        value = cert.extensions.get_extension_for_oid(ROLE_OID).value.value
    except x509.ExtensionNotFound:
        return None
    # ASN.1 UTF8String (R-22): tag 0x0C, then a short or long form length
    if len(value) < 2 or value[0] != 0x0C:
        return None
    length, offset = value[1], 2
    if length & 0x80:
        size = length & 0x7F
        length, offset = int.from_bytes(value[2 : 2 + size], "big"), 2 + size
    raw = value[offset : offset + length]
    if len(raw) != length:
        return None
    return raw.decode("utf-8", "replace")  # one role per certificate (R-65)


@dataclass(frozen=True)
class Rules:
    """Roles-to-rights rules: which function codes each role may use."""

    allowed: dict[str, frozenset[int]]

    @classmethod
    def load(cls, path: Path) -> "Rules":
        data = tomllib.loads(path.read_text())
        return cls({role: frozenset(spec["functions"]) for role, spec in data.get("roles", {}).items()})

    def authorise(self, role: str | None, function_code: int) -> bool:
        # No role, or a role the rules do not know: nothing is allowed
        return role is not None and function_code in self.allowed.get(role, frozenset())
