---
description: >-
  Modbus/TCP accepts any command from the network. Modbus/TCP Security (mutual TLS, port 802, roles in the certificate), or failing that a service disabled by default and isolated: the protection from unauthorised access the CRA requires (Annex I, Part I, 2(d)).
---

# Modbus never asks "who is there?": mutual TLS and roles

> **CRA & Dev #7** · ["CRA & Dev" series](index.md) · Reading time: about 7 min · Industrial, Modbus ·
> Example: Python (pymodbus)

## What the CRA requires

The [Cyber Resilience Act][cra] requires a product to ensure protection from
unauthorised access by appropriate control mechanisms, such as authentication or
identity and access management systems, and to report on possible unauthorised
access (Annex I, Part I, point 2, d). It also requires a secure by default
configuration (point b), limited attack surfaces, including external interfaces
(point j), and protection of the data and commands transmitted (points e and f).

For a PLC, a drive or a motion controller that speaks Modbus, the question is simple:
when a command arrives on the network port, does the product know who sent it, and
is it able to refuse it?

## The classic trap

Modbus/TCP has no password and no notion of a user. Any client that reaches port 502
can read and write whatever the device exposes. This is not an implementation bug:
the protocol is designed that way, and gateways that carry serial Modbus over
Ethernet inherit the same behaviour.

The consequences are documented. The FrostyGoop malware, analysed by
[Dragos][dragos], acts on industrial equipment over Modbus TCP on port 502; used
against a district heating company in Ukraine, it left customers without heating for
two days. Security advisories follow the same pattern, for example
[CVE-2025-48466][cve-advantech]: an unauthenticated remote attacker sends Modbus TCP
frames and drives the outputs of an I/O module.

The "our network is isolated" reflex does not last: a maintenance laptop, a remote
access router or a compromised supervision PC is enough to reach port 502 from the
inside.

## The technique: Modbus/TCP Security

Modbus.org has specified a secure version of the protocol, [Modbus/TCP
Security][mbsec] ("mbaps"), on port 802, [registered with IANA][iana] as `mbap-s`.
Modbus frames do not change: they travel inside a TLS session. The key requirements:

- TLS 1.2 or newer, with no fallback to an older version (R-01, R-34);
- mutual authentication: the client presents an X.509 certificate too, and the device
  closes the session if it does not (R-02, R-10);
- one role per certificate, in the extension `1.3.6.1.4.1.50316.802.1` (R-21, R-65);
- role-based authorisation, with rules the user can configure and no fixed default
  role (R-27, R-28); a refused request gets Modbus exception 01, *Illegal function*
  (R-31).

![A client without a certificate, or with a certificate from another authority, is cut off at the TLS handshake; a recognised client is authorised or not request by request, according to the role written in its certificate.](images/modbus-tls.svg)

On the device side, in Python with [pymodbus][pymodbus], the core fits in a few
lines. First the TLS session, which requires a client certificate signed by the
plant's authority:

```python
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.minimum_version = ssl.TLSVersion.TLSv1_2   # R-01, R-34
ctx.verify_mode = ssl.CERT_REQUIRED            # R-02, R-10
ctx.load_cert_chain("plc.crt", "plc.key")
ctx.load_verify_locations("ca.crt")            # only our clients get in
```

Then authorisation: the role is read once, when the session opens, and every request
is checked against the rules (simplified excerpt from `mbsec/plc.py`):

```python
def callback_connected(self):
    der = self.transport.get_extra_info("ssl_object").getpeercert(binary_form=True)
    self.role = role_from_certificate(der)     # None if the certificate has none

async def handle_request(self):
    pdu = self.last_pdu
    if not self.server.rules.authorise(self.role, pdu.function_code):
        log.warning("DENIED %s from %s (role %s)", ...)    # report (CRA 2 d)
        self.server_send(ExceptionResponse(pdu.function_code, ExcCodes.ILLEGAL_FUNCTION), ...)
        return
    await super().handle_request()
```

The rules live in a file the operator can edit:

```toml
[roles.Operator]
functions = [1, 2, 3, 4]               # reads only

[roles.Engineer]
functions = [1, 2, 3, 4, 5, 6, 15, 16] # reads and writes
```

The [demo][example] runs two simulated PLCs on your machine, driving the spindle of a
machine tool: one speaking plain Modbus/TCP, the other only Modbus/TCP Security. The
first case replays on a spindle what FrostyGoop did to heating controllers: any
client on the network rewrites the setpoint, here from 12,000 to 60,000 rpm, and the
PLC applies it. Run it with
`uv run python -m mbsec.demo`; an excerpt of the output:

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
6. Engineer (maintenance laptop): may write
   write: accepted
   spindle speed now: 15000 rpm
```

The third case matters: anyone can mint a certificate carrying the `Engineer` role.
It is the signature of the plant's authority that gives it value.

## When the device cannot do TLS

Not every product has the memory or the CPU for TLS, and many installed clients only
speak Modbus/TCP. The CRA does not require a given protocol; it requires that
unauthorised access be controlled and that the default configuration be secure.
Without Modbus/TCP Security:

- ship the Modbus/TCP service disabled, to be enabled explicitly by the operator
  (point b);
- limit it to what is needed: read-only by default, a dedicated network interface,
  an allowlist of client addresses (point j);
- document that it must live in an isolated network zone, never exposed to the
  Internet, and say why: the protocol authenticates no one.

An IP address allowlist reduces exposure, but does not authenticate: on the same
network, an address can be spoofed. It is a complement, not an equivalent of mutual
TLS.

## Three things to know

1. The real work is the key infrastructure. You need a certificate authority per
   plant or per customer, certificates with an expiry date and a way to withdraw one,
   and the authority's key offline or in an HSM, like the signing key of
   [episode 6](CRA-Dev-06-FUOTA-LoRaWAN.md). The specification leaves that management
   to the plant's PKI.
2. The specification provides for a suite without encryption. A server should be
   able to enable `TLS_RSA_WITH_NULL_SHA256` (R-67), which authenticates and protects
   integrity without encrypting. If you enable it, data travels in the clear: the
   confidentiality required by point e is no longer provided.
3. TLS does not protect against a compromised legitimate client. A hacked maintenance
   laptop presents a valid certificate with the `Engineer` role, and its writes will
   be accepted. Roles limit the damage, all the more if they also restrict address
   ranges, and the log of refusals (CRA, point d) helps spot a client going beyond
   its role. A refused TLS session never reaches Modbus: the product's TLS layer has
   to log it.

## Takeaway

Modbus/TCP executes what it is sent, without asking who sent it. Modbus/TCP Security
asks the question in the right place: a certificate signed by the plant to get in, a
role in that certificate to decide on each request, a logged refusal when the role
is not enough. When the device cannot do TLS, the service must at least be off by
default, restricted and isolated. That is what meets the CRA's requirement of
protection from unauthorised access.

---

*Previous episode: [A thousand fragments, one signature, updating firmware over
LoRaWAN](CRA-Dev-06-FUOTA-LoRaWAN.md).*

*Companion code, in [`examples/07-modbus-tls`][example]: the two simulated PLCs, the
demo and its tests.*

[cra]: https://eur-lex.europa.eu/eli/reg/2024/2847/oj?locale=en
[mbsec]: https://www.modbus.org/file/secure/modbussecurityprotocol.pdf
[iana]: https://www.iana.org/assignments/service-names-port-numbers/service-names-port-numbers.xhtml?search=mbap-s
[dragos]: https://www.dragos.com/blog/protect-against-frostygoop-ics-malware-targeting-operational-technology/
[cve-advantech]: https://www.cve.org/CVERecord?id=CVE-2025-48466
[pymodbus]: https://pymodbus.readthedocs.io/
[example]: https://github.com/ADNTIO/cra-dev-wiki/tree/main/examples/07-modbus-tls
