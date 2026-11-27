import pytest

from mbsec.authz import Rules, role_from_certificate
from mbsec.pki import make_pki, utf8string


@pytest.fixture(scope="module")
def pki(tmp_path_factory):
    return make_pki(tmp_path_factory.mktemp("pki"))


def der(identity):
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization

    cert = x509.load_pem_x509_certificate(identity.cert.read_bytes())
    return cert.public_bytes(serialization.Encoding.DER)


def test_role_is_read_from_the_modbus_extension(pki):
    assert role_from_certificate(der(pki["operator"])) == "Operator"
    assert role_from_certificate(der(pki["engineer"])) == "Engineer"


def test_certificate_without_role_gives_the_null_role(pki):
    # R-23: no role in the certificate, a NULL role for the authorisation function
    assert role_from_certificate(der(pki["no-role"])) is None


def test_utf8string_encoding_matches_the_specification():
    # R-22: ASN.1 UTF8String, tag 0x0C, here for the specification's own example
    assert utf8string("Operator") == b"\x0c\x08Operator"
    long_role = "x" * 200
    assert utf8string(long_role)[:3] == b"\x0c\x81\xc8"


@pytest.fixture
def rules(tmp_path):
    path = tmp_path / "rules.toml"
    path.write_text('[roles.Operator]\nfunctions = [3]\n[roles.Engineer]\nfunctions = [3, 6]\n')
    return Rules.load(path)


def test_rules_follow_the_configuration_file(rules):
    assert rules.authorise("Operator", 3)
    assert not rules.authorise("Operator", 6)
    assert rules.authorise("Engineer", 6)


def test_null_or_unknown_role_gets_nothing(rules):
    assert not rules.authorise(None, 3)
    assert not rules.authorise("Admin", 3)
