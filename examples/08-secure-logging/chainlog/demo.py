"""A chained, signed security log and three attacks on it: python -m chainlog.demo"""

import json
import os
import shutil
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from chainlog.log import Ed25519Signer, HmacSigner, SignedLog, read, verify

EVENTS = [
    dict(actor="hmi-line-2", action="login", target="operator session"),
    dict(actor="laptop-maintenance", action="config.write", target="spindle max speed 12000 -> 15000 rpm"),
    dict(actor="laptop-maintenance", action="firmware.update", target="1.0.0 -> 1.1.0"),
    dict(actor="hmi-line-2", action="access.denied", target="write single register"),
    dict(actor="hmi-line-2", action="logout", target="operator session"),
]


def rewrite(path: Path, records: list[dict]) -> None:
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in records))


def show(problem: str | None) -> str:
    return "OK" if problem is None else f"TAMPERING DETECTED, {problem}"


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        device_key = Ed25519PrivateKey.generate()
        device = Ed25519Signer(device_key)  # stays on the device
        auditor = Ed25519Signer(public_key=device_key.public_key())  # public key only

        print("1. The device logs 5 security events, each signed and chained to the previous one")
        log = tmp / "security.log"
        writer = SignedLog(log, device)
        for event in EVENTS:
            writer.append(**event)
        anchor = writer.anchor()  # published outside the device, e.g. to a log server
        print(f"   published anchor: {anchor.count} entries, last signature {anchor.last[:16]}...")
        print(f"   verify: {show(verify(log, auditor, anchor))}")

        print("2. Attacker edits entry 1 (hides who changed the spindle speed)")
        shutil.copy(log, tmp / "a.log")
        records = read(tmp / "a.log")
        records[1]["event"]["actor"] = "hmi-line-2"
        rewrite(tmp / "a.log", records)
        print(f"   verify: {show(verify(tmp / 'a.log', auditor, anchor))}")

        print("3. Attacker deletes entry 2 (hides the firmware update)")
        records = read(log)
        rewrite(tmp / "b.log", records[:2] + records[3:])
        print(f"   verify: {show(verify(tmp / 'b.log', auditor, anchor))}")

        print("4. Attacker cuts the last 2 entries")
        rewrite(tmp / "c.log", read(log)[:3])
        print(f"   chain alone: {show(verify(tmp / 'c.log', auditor))}")
        print(f"   with anchor: {show(verify(tmp / 'c.log', auditor, anchor))}")

        print("5. Non-repudiation: the auditor tries to add a fake entry")
        key = os.urandom(32)  # shared by device and auditor
        hlog = tmp / "hmac.log"
        hdevice = SignedLog(hlog, HmacSigner(key))
        for event in EVENTS[:2]:
            hdevice.append(**event)
        SignedLog(hlog, HmacSigner(key)).append(actor="hmi-line-2", action="alarm.disabled", target="all")
        print(f"   HMAC log, fake entry signed with the shared key: {show(verify(hlog, HmacSigner(key)))}")
        print("   -> the log cannot prove the device wrote it: the auditor could have")
        try:
            SignedLog(log, auditor).append(actor="hmi-line-2", action="alarm.disabled", target="all")
        except PermissionError as exc:
            print(f"   Ed25519 log, auditor holds the public key only: {exc}")

        print("6. The user turns monitoring off: the opt-out itself is the last signed entry")
        writer.append(actor="admin", action="logging.disabled", target="security log")
        last = read(log)[-1]
        print(f"   entry {last['seq']}: {last['event']['actor']} {last['event']['action']}"
              f" -> {show(verify(log, auditor))}")


if __name__ == "__main__":
    main()
