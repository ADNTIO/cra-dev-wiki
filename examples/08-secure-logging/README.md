# Example: a chained, signed security log

Companion code for episode 8 of the "CRA & Dev" series,
[A log that cannot lie](../../docs/en/CRA-Dev-08-Signed-Logs.md).

Each entry carries the signature of the previous entry, then is signed itself with
Ed25519. Changing, deleting or inserting an entry breaks the chain; cutting the end
is caught by an anchor (entry count and last signature) published outside the
device.

## Run

This project uses [uv](https://docs.astral.sh/uv/).

```bash
uv run python -m chainlog.demo   # the scenarios, step by step
uv run pytest                    # the tests
```

Output (signatures are random, so the anchor changes from one run to the next):

```
1. The device logs 5 security events, each signed and chained to the previous one
   published anchor: 5 entries, last signature d1e0ae6c5bf747d1...
   verify: OK
2. Attacker edits entry 1 (hides who changed the spindle speed)
   verify: TAMPERING DETECTED, entry 1: bad signature (entry modified)
3. Attacker deletes entry 2 (hides the firmware update)
   verify: TAMPERING DETECTED, entry 2: sequence jumps to 3 (entry removed or inserted)
4. Attacker cuts the last 2 entries
   chain alone: OK
   with anchor: TAMPERING DETECTED, log ends at 3 entries, the anchor says 5 (end truncated)
5. Non-repudiation: the auditor tries to add a fake entry
   HMAC log, fake entry signed with the shared key: OK
   -> the log cannot prove the device wrote it: the auditor could have
   Ed25519 log, auditor holds the public key only: a public key cannot sign
6. The user turns monitoring off: the opt-out itself is the last signed entry
   entry 5: admin logging.disabled -> OK
```

## What is inside

| File | Role |
| --- | --- |
| `chainlog/log.py` | The log: append, anchor, verify; an Ed25519 signer and an HMAC signer |
| `chainlog/demo.py` | The scenarios |
| `tests/test_log.py` | Modification, deletion (even renumbered), insertion, truncation, HMAC forgery, opt-out |

One entry, one JSON line:

```json
{"event": {"action": "config.write", "actor": "laptop-maintenance", "target": "..."},
 "prev": "<signature of the previous entry>", "seq": 1, "sig": "<Ed25519 signature>",
 "time": "2026-10-02T12:00:00+00:00"}
```

The signature covers `seq`, `time`, `event` and `prev`.

## What it does not do

- Protect the signing key. Here it lives in memory; on a device it belongs in a
  secure element, a TPM or at least a file only the logging service can read.
- Rotate the key over time. An attacker who steals today's key can rewrite the whole
  past. Forward-secure schemes, such as systemd-journald's Forward Secure Sealing,
  evolve the key so that a stolen key cannot reseal older entries.
- Ship the anchor anywhere. In a product, publish it regularly to a log server or a
  remote store the device cannot rewrite.
