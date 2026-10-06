"""A chained, signed security log.

Each entry carries the signature of the previous entry, then is signed itself:

    entry n = { seq: n, time, event, prev: signature of entry n-1, sig }

Changing, inserting or deleting an entry breaks the chain from that point on.
Removing the last entries does not: the remaining chain is still valid. That is
why the writer publishes an anchor (entry count and last signature) somewhere the
attacker cannot rewrite, and the verifier checks the log against it.
"""

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

GENESIS = "00" * 64  # "previous signature" of the first entry


class Ed25519Signer:
    """Asymmetric: only the device signs; anyone with the public key verifies."""

    def __init__(self, private_key: Ed25519PrivateKey | None = None, public_key: Ed25519PublicKey | None = None):
        self.private_key = private_key
        self.public_key = public_key or private_key.public_key()

    def sign(self, data: bytes) -> bytes:
        if self.private_key is None:
            raise PermissionError("a public key cannot sign")
        return self.private_key.sign(data)

    def verify(self, data: bytes, signature: bytes) -> bool:
        try:
            self.public_key.verify(signature, data)
            return True
        except InvalidSignature:
            return False


class HmacSigner:
    """Symmetric: whoever can verify can also sign. No attribution to the device."""

    def __init__(self, key: bytes):
        self.key = key

    def sign(self, data: bytes) -> bytes:
        return hmac.new(self.key, data, hashlib.sha256).digest()

    def verify(self, data: bytes, signature: bytes) -> bool:
        return hmac.compare_digest(self.sign(data), signature)


def _signed_part(record: dict) -> bytes:
    """The bytes covered by the signature: everything but the signature itself."""
    return json.dumps({k: record[k] for k in ("seq", "time", "event", "prev")},
                      sort_keys=True, separators=(",", ":")).encode()


@dataclass(frozen=True)
class Anchor:
    """What the writer publishes outside the device: count and last signature."""

    count: int
    last: str


class SignedLog:
    """Append-only, one JSON record per line."""

    def __init__(self, path: Path, signer):
        self.path, self.signer = path, signer
        records = read(path)
        self.count = len(records)
        self.last = records[-1]["sig"] if records else GENESIS

    def append(self, **event) -> dict:
        record = {
            "seq": self.count,
            "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "event": event,
            "prev": self.last,
        }
        record["sig"] = self.signer.sign(_signed_part(record)).hex()
        with self.path.open("a") as f:
            f.write(json.dumps(record, sort_keys=True) + "\n")
        self.count, self.last = self.count + 1, record["sig"]
        return record

    def anchor(self) -> Anchor:
        return Anchor(self.count, self.last)


def read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def verify(path: Path, signer, anchor: Anchor | None = None) -> str | None:
    """Returns None if the log is intact, else the first problem found."""
    prev, records = GENESIS, read(path)
    for expected_seq, record in enumerate(records):
        if record["seq"] != expected_seq:
            return f"entry {expected_seq}: sequence jumps to {record['seq']} (entry removed or inserted)"
        if record["prev"] != prev:
            return f"entry {expected_seq}: does not chain to the previous entry"
        if not signer.verify(_signed_part(record), bytes.fromhex(record["sig"])):
            return f"entry {expected_seq}: bad signature (entry modified)"
        prev = record["sig"]
    if anchor is not None:
        if len(records) < anchor.count:
            return f"log ends at {len(records)} entries, the anchor says {anchor.count} (end truncated)"
        if records[anchor.count - 1]["sig"] != anchor.last:
            return f"entry {anchor.count - 1}: differs from the published anchor"
    return None
