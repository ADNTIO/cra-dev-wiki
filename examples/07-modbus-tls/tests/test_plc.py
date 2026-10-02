"""End to end: real TLS sessions against the simulated PLCs, on free local ports."""

import asyncio
import socket
import ssl
from pathlib import Path

import pytest
from pymodbus.client import AsyncModbusTcpClient, AsyncModbusTlsClient

from mbsec.authz import Rules
from mbsec.demo import RULES, read_setpoint, tls_client, write_setpoint
from mbsec.pki import make_pki
from mbsec.plc import AuthorisingTlsServer, make_context, plain_server, server_tls_context


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def pki(tmp_path_factory):
    return make_pki(tmp_path_factory.mktemp("pki"))


def run(pki, scenario):
    """Starts a secure PLC, runs scenario(port, server), stops the PLC."""

    async def main():
        port = free_port()
        server = AuthorisingTlsServer(port, make_context(), server_tls_context(pki["plc"], pki["ca"]),
                                      Rules.load(RULES))
        await server.serve_forever(background=True)
        try:
            return await scenario(port, server)
        finally:
            await server.shutdown()

    return asyncio.run(main())


def test_plain_modbus_accepts_anyone():
    async def main():
        port = free_port()
        server = plain_server(port, make_context())
        await server.serve_forever(background=True)
        try:
            client = lambda: AsyncModbusTcpClient("127.0.0.1", port=port, retries=0, timeout=2)
            assert await write_setpoint(client(), 999) == "accepted"
            return await read_setpoint(client())
        finally:
            await server.shutdown()

    assert asyncio.run(main()) == "99.9 °C"


def test_client_without_certificate_is_rejected(pki):
    async def scenario(port, server):
        return await write_setpoint(tls_client(None, pki["ca"], port), 999)

    assert run(pki, scenario).startswith("rejected")


def test_certificate_from_another_ca_is_rejected(pki):
    async def scenario(port, server):
        return await write_setpoint(tls_client(pki["rogue"], pki["ca"], port), 999)

    assert run(pki, scenario).startswith("rejected")


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_tls_older_than_1_2_is_rejected(pki):
    # R-34: no fallback to TLS 1.1 or older
    async def scenario(port, server):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.load_verify_locations(pki["ca"].cert)
        ctx.load_cert_chain(pki["engineer"].cert, pki["engineer"].key)
        try:
            ctx.minimum_version = ssl.TLSVersion.TLSv1
            ctx.maximum_version = ssl.TLSVersion.TLSv1_1
        except (ValueError, ssl.SSLError):
            pytest.skip("this OpenSSL build cannot even offer TLS 1.1")
        client = AsyncModbusTlsClient("127.0.0.1", port=port, sslctx=ctx, retries=0, timeout=2)
        return await write_setpoint(client, 999)

    assert run(pki, scenario).startswith("rejected")


def test_operator_reads_but_cannot_write(pki):
    async def scenario(port, server):
        read = await read_setpoint(tls_client(pki["operator"], pki["ca"], port))
        write = await write_setpoint(tls_client(pki["operator"], pki["ca"], port), 999)
        return read, write, server.denials

    read, write, denials = run(pki, scenario)
    assert read == "21.5 °C"
    assert "exception 1" in write  # R-31: Illegal function
    assert [(d.role, d.function_code) for d in denials] == [("Operator", 6)]


def test_certificate_without_role_gets_nothing(pki):
    async def scenario(port, server):
        return await read_setpoint(tls_client(pki["no-role"], pki["ca"], port))

    assert "exception 1" in run(pki, scenario)


def test_engineer_can_write(pki):
    async def scenario(port, server):
        write = await write_setpoint(tls_client(pki["engineer"], pki["ca"], port), 230)
        read = await read_setpoint(tls_client(pki["operator"], pki["ca"], port))
        return write, read

    assert run(pki, scenario) == ("accepted", "23.0 °C")
