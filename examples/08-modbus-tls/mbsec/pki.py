"""A throwaway PKI for the demo: a CA, a server certificate, client certificates.

Client certificates carry their Modbus role in the extension defined by the
Modbus/TCP Security specification (MB-TCP-Security-v36, R-21, R-22): OID
1.3.6.1.4.1.50316.802.1, value encoded as an ASN.1 UTF8String.

In production the CA key lives offline or in an HSM, and certificates come from
your PKI, not from a script.
"""

import datetime
import ipaddress
from dataclasses import dataclass
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

ROLE_OID = x509.ObjectIdentifier("1.3.6.1.4.1.50316.802.1")


def utf8string(text: str) -> bytes:
    """DER encoding of an ASN.1 UTF8String (tag 0x0C)."""
    raw = text.encode()
    if len(raw) < 0x80:
        return bytes([0x0C, len(raw)]) + raw
    length = len(raw).to_bytes((len(raw).bit_length() + 7) // 8, "big")
    return bytes([0x0C, 0x80 | len(length)]) + length + raw


@dataclass
class Identity:
    cert: Path
    key: Path


def _name(common_name: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])


def _write(directory: Path, stem: str, cert: x509.Certificate, key) -> Identity:
    cert_path, key_path = directory / f"{stem}.crt", directory / f"{stem}.key"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    key_path.chmod(0o600)
    return Identity(cert_path, key_path)


def _issue(subject: str, issuer_name, issuer_key, *, ca=False, server=False, role=None, key=None):
    key = key or ec.generate_private_key(ec.SECP256R1())
    now = datetime.datetime.now(datetime.timezone.utc)
    builder = (
        x509.CertificateBuilder()
        .subject_name(_name(subject))
        .issuer_name(issuer_name or _name(subject))
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
    )
    if ca:
        builder = builder.add_extension(
            x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True
        )
    else:
        usage = ExtendedKeyUsageOID.SERVER_AUTH if server else ExtendedKeyUsageOID.CLIENT_AUTH
        builder = builder.add_extension(x509.ExtendedKeyUsage([usage]), critical=False)
    if server:
        builder = builder.add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
            ),
            critical=False,
        )
    if role is not None:
        builder = builder.add_extension(
            x509.UnrecognizedExtension(ROLE_OID, utf8string(role)), critical=False
        )
    return builder.sign(issuer_key or key, hashes.SHA256()), key


def make_pki(directory: Path) -> dict[str, Identity]:
    """Creates every identity the demo needs, in directory."""
    directory.mkdir(parents=True, exist_ok=True)
    ca_cert, ca_key = _issue("Demo plant CA", None, None, ca=True)
    out = {"ca": _write(directory, "ca", ca_cert, ca_key)}

    def issue(stem, subject, **kwargs):
        cert, key = _issue(subject, ca_cert.subject, ca_key, **kwargs)
        out[stem] = _write(directory, stem, cert, key)

    issue("plc", "plc-01", server=True)
    issue("operator", "hmi-line-2", role="Operator")
    issue("engineer", "laptop-maintenance", role="Engineer")
    issue("no-role", "old-scada")

    # An attacker can mint a certificate with any role, but not with our CA
    rogue_ca, rogue_key = _issue("Rogue CA", None, None, ca=True)
    cert, key = _issue("attacker", rogue_ca.subject, rogue_key, role="Engineer")
    out["rogue"] = _write(directory, "rogue", cert, key)
    return out
