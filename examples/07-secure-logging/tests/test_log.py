import json
import os

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from chainlog.log import Ed25519Signer, HmacSigner, SignedLog, read, verify


def rewrite(path, records):
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in records))


@pytest.fixture
def key():
    return Ed25519PrivateKey.generate()


@pytest.fixture
def log(tmp_path, key):
    path = tmp_path / "security.log"
    writer = SignedLog(path, Ed25519Signer(key))
    for i in range(5):
        writer.append(actor="hmi", action="event", target=str(i))
    return path, writer.anchor()


def auditor(key):
    return Ed25519Signer(public_key=key.public_key())


def test_intact_log_verifies(log, key):
    path, anchor = log
    assert verify(path, auditor(key), anchor) is None


def test_each_entry_carries_the_previous_signature(log):
    path, _ = log
    records = read(path)
    assert all(b["prev"] == a["sig"] for a, b in zip(records, records[1:]))


def test_modified_entry_is_detected(log, key):
    path, anchor = log
    records = read(path)
    records[1]["event"]["actor"] = "someone-else"
    rewrite(path, records)
    assert "bad signature" in verify(path, auditor(key), anchor)


def test_deleted_entry_is_detected_even_after_renumbering(log, key):
    path, anchor = log
    records = read(path)
    del records[2]
    for seq, record in enumerate(records):
        record["seq"] = seq
    rewrite(path, records)
    assert verify(path, auditor(key), anchor) is not None


def test_inserted_entry_signed_with_another_key_is_detected(log, key):
    path, anchor = log
    records = read(path)
    forged = SignedLog(path.with_name("x.log"), Ed25519Signer(Ed25519PrivateKey.generate()))
    fake = forged.append(actor="intruder", action="event", target="fake")
    rewrite(path, records[:2] + [fake] + records[2:])
    assert verify(path, auditor(key), anchor) is not None


def test_truncation_needs_the_anchor(log, key):
    path, anchor = log
    rewrite(path, read(path)[:3])
    assert verify(path, auditor(key)) is None  # the shorter chain is still valid
    assert "truncated" in verify(path, auditor(key), anchor)


def test_hmac_holder_can_forge_entries(tmp_path):
    secret = os.urandom(32)
    path = tmp_path / "hmac.log"
    SignedLog(path, HmacSigner(secret)).append(actor="device", action="event", target="real")
    SignedLog(path, HmacSigner(secret)).append(actor="device", action="event", target="forged by the verifier")
    assert verify(path, HmacSigner(secret)) is None  # no way to tell who wrote what


def test_public_key_holder_cannot_sign(log, key):
    path, _ = log
    with pytest.raises(PermissionError):
        SignedLog(path, auditor(key)).append(actor="auditor", action="event", target="fake")


def test_opt_out_is_itself_logged(log, key):
    path, _ = log
    writer = SignedLog(path, Ed25519Signer(key))
    writer.append(actor="admin", action="logging.disabled", target="security log")
    assert read(path)[-1]["event"]["action"] == "logging.disabled"
    assert verify(path, auditor(key), writer.anchor()) is None
