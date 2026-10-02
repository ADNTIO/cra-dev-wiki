"""A simulated PLC, served over plain Modbus/TCP and over Modbus/TCP Security.

Holding register 0 is a temperature setpoint, in tenths of a degree.

The secure server follows MB-TCP-Security-v36: TLS 1.2 or newer (R-01, R-34),
mutual authentication with a fatal alert when the client sends no certificate
(R-02, R-10), the role read from the client certificate at the handshake (R-30),
and every request checked against the rules, a refusal being answered with
exception code 01, Illegal function (R-31). Each refusal is logged: the CRA asks
products to report on possible unauthorised access (Annex I, Part I, 2 (d)).
"""

import logging
import ssl
from dataclasses import dataclass, field

from pymodbus.constants import ExcCodes
from pymodbus.datastore import ModbusDeviceContext, ModbusSequentialDataBlock, ModbusServerContext
from pymodbus.pdu import ExceptionResponse
from pymodbus.server import ModbusTcpServer, ModbusTlsServer
from pymodbus.server.requesthandler import ServerRequestHandler

from mbsec.authz import FUNCTIONS, Rules, role_from_certificate
from mbsec.pki import Identity

log = logging.getLogger("plc")

SETPOINT = 0  # holding register address
INITIAL_SETPOINT = 215  # 21.5 °C


def make_context() -> ModbusServerContext:
    # pymodbus data blocks start at 1: block address 1 is Modbus address 0
    device = ModbusDeviceContext(hr=ModbusSequentialDataBlock(1, [INITIAL_SETPOINT] * 10))
    return ModbusServerContext(devices=device, single=True)


def plain_server(port: int, context: ModbusServerContext) -> ModbusTcpServer:
    """Plain Modbus/TCP, as most devices ship it: any client may do anything."""
    return ModbusTcpServer(context, address=("127.0.0.1", port))


def server_tls_context(plc: Identity, ca: Identity) -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2  # R-01, R-34
    ctx.verify_mode = ssl.CERT_REQUIRED  # R-02, R-07, R-10
    ctx.load_cert_chain(plc.cert, plc.key)
    ctx.load_verify_locations(ca.cert)  # only our CA's clients get in
    return ctx


def client_tls_context(me: Identity | None, ca: Identity) -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_verify_locations(ca.cert)  # the client checks the PLC too
    if me is not None:
        ctx.load_cert_chain(me.cert, me.key)
    return ctx


@dataclass
class Denial:
    peer: str
    role: str | None
    function_code: int


@dataclass
class AuthorisingTlsServer(ModbusTlsServer):
    """ModbusTlsServer whose connections check every request against the rules."""

    rules: Rules = field(default=None)
    denials: list[Denial] = field(default_factory=list)

    def __init__(self, port: int, context: ModbusServerContext, sslctx: ssl.SSLContext, rules: Rules):
        self.rules = rules
        self.denials = []
        super().__init__(context, address=("127.0.0.1", port), sslctx=sslctx)

    def callback_new_connection(self):
        return AuthorisingHandler(self, self.trace_packet, self.trace_pdu, self.trace_connect)


class AuthorisingHandler(ServerRequestHandler):
    """One per TLS connection: caches the client role, then filters each request."""

    role: str | None = None
    peer: str = "?"

    def callback_connected(self) -> None:
        super().callback_connected()
        tls = self.transport.get_extra_info("ssl_object")
        self.peer = "%s:%s" % (self.transport.get_extra_info("peername") or ("?", "?"))[:2]
        der = tls.getpeercert(binary_form=True) if tls else None
        self.role = role_from_certificate(der) if der else None
        log.info("TLS session from %s, role %s", self.peer, self.role or "none")

    async def handle_request(self):
        pdu = self.last_pdu
        if pdu and not self.server.rules.authorise(self.role, pdu.function_code):
            name = FUNCTIONS.get(pdu.function_code, f"function {pdu.function_code}")
            log.warning("DENIED %s from %s (role %s)", name, self.peer, self.role or "none")
            self.server.denials.append(Denial(self.peer, self.role, pdu.function_code))
            response = ExceptionResponse(pdu.function_code, ExcCodes.ILLEGAL_FUNCTION)  # R-31
            response.transaction_id = pdu.transaction_id
            response.dev_id = pdu.dev_id
            self.server_send(response, self.last_addr)
            return
        await super().handle_request()
