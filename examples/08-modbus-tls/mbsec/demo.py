"""Plain Modbus/TCP versus Modbus/TCP Security, on your machine: python -m mbsec.demo

The demo uses ports 5020 and 8020 instead of 502 and 802, which need root.
"""

import asyncio
import logging
import ssl
import sys
import tempfile
from pathlib import Path

from pymodbus.client import AsyncModbusTcpClient, AsyncModbusTlsClient
from pymodbus.exceptions import ModbusException

from mbsec.authz import Rules
from mbsec.pki import make_pki
from mbsec.plc import SPINDLE_SPEED, AuthorisingTlsServer, client_tls_context, make_context, plain_server, server_tls_context

PLAIN_PORT, SECURE_PORT = 5020, 8020
RULES = Path(__file__).resolve().parent.parent / "rules.toml"


# With TLS 1.3, the client may only learn that its certificate was rejected after
# the handshake: the PLC then sends a fatal alert and closes the session (R-10).
REJECTED = "rejected, the PLC closed the TLS session"


async def write_speed(client, value: int) -> str:
    """Writes the spindle speed setpoint; returns what happened, in a few words."""
    try:
        if not await client.connect():
            return REJECTED
        reply = await client.write_register(SPINDLE_SPEED, value)
    except ModbusException:
        return REJECTED
    finally:
        client.close()
    if reply.isError():
        return f"refused, Modbus exception {reply.exception_code} (Illegal function)"
    return "accepted"


async def read_speed(client) -> str:
    try:
        if not await client.connect():
            return REJECTED
        reply = await client.read_holding_registers(SPINDLE_SPEED)
    except ModbusException:
        return REJECTED
    finally:
        client.close()
    if reply.isError():
        return f"refused, Modbus exception {reply.exception_code} (Illegal function)"
    return f"{reply.registers[0]} rpm"


def tls_client(identity, ca, port: int = SECURE_PORT):
    ctx = client_tls_context(identity, ca)
    return AsyncModbusTlsClient("127.0.0.1", port=port, sslctx=ctx, retries=0, timeout=2)


async def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="   plc log: %(message)s", stream=sys.stdout)
    logging.getLogger("pymodbus").setLevel(logging.CRITICAL)

    with tempfile.TemporaryDirectory() as tmp:
        pki = make_pki(Path(tmp))
        # Two PLCs: a legacy one, and one that only speaks Modbus/TCP Security
        plain = plain_server(PLAIN_PORT, make_context())
        secure = AuthorisingTlsServer(SECURE_PORT, make_context(), server_tls_context(pki["plc"], pki["ca"]),
                                      Rules.load(RULES))
        await plain.serve_forever(background=True)
        await secure.serve_forever(background=True)
        try:
            print("1. Legacy PLC, plain Modbus/TCP: anyone on the network sets the spindle to 60000 rpm")
            attacker = AsyncModbusTcpClient("127.0.0.1", port=PLAIN_PORT, retries=0, timeout=2)
            print(f"   write: {await write_speed(attacker, 60000)}")
            check = AsyncModbusTcpClient("127.0.0.1", port=PLAIN_PORT, retries=0, timeout=2)
            print(f"   spindle speed now: {await read_speed(check)}")

            print("2. Secure PLC, Modbus/TCP Security only. Client without a certificate")
            print(f"   write: {await write_speed(tls_client(None, pki['ca']), 60000)}")

            print("3. Client with an Engineer role, signed by its own CA")
            print(f"   write: {await write_speed(tls_client(pki['rogue'], pki['ca']), 60000)}")

            print("4. Operator (HMI): may read, may not write")
            print(f"   read:  {await read_speed(tls_client(pki['operator'], pki['ca']))}")
            print(f"   write: {await write_speed(tls_client(pki['operator'], pki['ca']), 60000)}")

            print("5. Certificate from our CA, but without a role")
            print(f"   read:  {await read_speed(tls_client(pki['no-role'], pki['ca']))}")

            print("6. Engineer (maintenance laptop): may write")
            print(f"   write: {await write_speed(tls_client(pki['engineer'], pki['ca']), 15000)}")
            print(f"   spindle speed now: {await read_speed(tls_client(pki['operator'], pki['ca']))}")

            print(f"7. Modbus requests refused and logged by the PLC: {len(secure.denials)}")
            print("   (rejected TLS sessions never reach Modbus: log them in the TLS layer)")
        finally:
            await secure.shutdown()
            await plain.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except ssl.SSLError as exc:
        raise SystemExit(f"TLS error: {exc}")
