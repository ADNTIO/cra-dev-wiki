import pytest

from seclog.log import SecurityLog, alerts


@pytest.fixture
def log(tmp_path):
    return SecurityLog(tmp_path / "security.log")


def test_records_who_did_what(log):
    log.record("config.change", "operator", "spindle speed", outcome="ok")
    (e,) = log.entries()
    assert (e["event"], e["actor"], e["target"], e["outcome"]) == ("config.change", "operator", "spindle speed", "ok")
    assert e["time"].endswith("+00:00")


def test_rejects_unknown_events(log):
    with pytest.raises(ValueError):
        log.record("debug", "operator", "anything")


def test_alert_only_from_the_limit(log):
    for _ in range(4):
        log.record("login", "laptop", "hmi", outcome="failed")
    assert alerts(log.entries()) == []
    log.record("login", "laptop", "hmi", outcome="failed")
    assert alerts(log.entries()) == ["5 failed logins from laptop"]


def test_opt_out_is_recorded_then_nothing(log):
    log.set_enabled(False, "admin")
    log.record("config.change", "operator", "spindle speed")
    assert [e["event"] for e in log.entries()] == ["logging.off"]


def test_opt_in_is_recorded(log):
    log.set_enabled(False, "admin")
    log.set_enabled(True, "admin")
    assert [e["event"] for e in log.entries()] == ["logging.off", "logging.on"]
