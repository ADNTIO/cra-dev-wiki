# Example: plain Modbus/TCP versus Modbus/TCP Security

Companion code for episode 7 of the "CRA & Dev" series,
[Modbus never asks who is there](../../docs/en/CRA-Dev-07-Modbus-TLS.md).

Two simulated PLCs, driving the spindle of a machine tool, run on your machine; no
hardware needed:

- a legacy PLC speaking plain Modbus/TCP, which accepts any command from anyone;
- a PLC speaking only Modbus/TCP Security ("mbaps"): mutual TLS, a role carried by
  each client certificate, and a roles-to-rights check on every request.

## Run

This project uses [uv](https://docs.astral.sh/uv/).

```bash
uv run python -m mbsec.demo   # the scenarios, step by step
uv run pytest                 # the tests
```

Output:

```
1. Legacy PLC, plain Modbus/TCP: anyone on the network sets the spindle to 60000 rpm
   write: accepted
   spindle speed now: 60000 rpm
2. Secure PLC, Modbus/TCP Security only. Client without a certificate
   write: rejected, the PLC closed the TLS session
3. Client with an Engineer role, signed by its own CA
   write: rejected, the PLC closed the TLS session
4. Operator (HMI): may read, may not write
   read:  12000 rpm
   plc log: DENIED write single register from 127.0.0.1:36604 (role Operator)
   write: refused, Modbus exception 1 (Illegal function)
5. Certificate from our CA, but without a role
   plc log: DENIED read holding registers from 127.0.0.1:36610 (role none)
   read:  refused, Modbus exception 1 (Illegal function)
6. Engineer (maintenance laptop): may write
   write: accepted
   spindle speed now: 15000 rpm
7. Modbus requests refused and logged by the PLC: 2
   (rejected TLS sessions never reach Modbus: log them in the TLS layer)
```

The demo listens on ports 5020 and 8020; the real ports, 502 for Modbus/TCP and 802
for Modbus/TCP Security, need root.

## What is inside

| File | Role |
| --- | --- |
| `mbsec/pki.py` | A throwaway CA, the PLC certificate, client certificates with their role |
| `mbsec/authz.py` | Reads the role from a certificate; checks a request against the rules |
| `rules.toml` | The roles-to-rights rules, editable by the end user |
| `mbsec/plc.py` | The two PLCs; the secure one filters every request and logs refusals |
| `mbsec/demo.py` | The scenarios |
| `tests/` | The same scenarios as tests, plus TLS 1.1 rejected and the role encoding |

## How it maps to the specification

Modbus/TCP Security is specified by Modbus.org in
[MB-TCP-Security-v36_2021-07-30][mbsec].

| Requirement | Where |
| --- | --- |
| R-01, R-34: TLS 1.2 or newer, no fallback | `server_tls_context()`, `test_tls_older_than_1_2_is_rejected` |
| R-02, R-07, R-10: mutual authentication, fatal alert without a client certificate | `ssl.CERT_REQUIRED`, scenarios 2 and 3 |
| R-21, R-22, R-65: role in extension `1.3.6.1.4.1.50316.802.1`, one UTF8String | `pki.py`, `role_from_certificate()` |
| R-23: no role gives a NULL role | `role_from_certificate()` returns `None`, scenario 5 |
| R-27, R-28: rules configurable, no fixed default role | `rules.toml` |
| R-30: role extracted from the certificate | `AuthorisingHandler.callback_connected()` |
| R-31: a refused request gets exception 01, Illegal function | `AuthorisingHandler.handle_request()` |

The role is read once per TLS session and cached, as section 8.4 of the
specification describes. The rules here only look at the function code; a real
product would usually also restrict address ranges.

## What was checked, and what was not

Checked: the 12 tests pass with pymodbus 3.15 and Python 3.12, and
`openssl asn1parse` shows the role extension encoded as in the specification's own
example (`0C 08 "Operator"`).

Not checked: interoperability with a commercial Modbus/TCP Security device or client.
The PLC side hooks into pymodbus internals (`ServerRequestHandler`), which may change
between pymodbus versions; the version is pinned by `uv.lock`.

[mbsec]: https://www.modbus.org/file/secure/modbussecurityprotocol.pdf
