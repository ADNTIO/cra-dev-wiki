import tempfile
from pathlib import Path

from seclog.log import SecurityLog, alerts


def main():
    with tempfile.TemporaryDirectory() as tmp:
        log = SecurityLog(Path(tmp) / "security.log")

        print("1. The device records who accessed or changed what")
        log.record("login", "operator", "hmi")
        log.record("config.change", "operator", "spindle speed 12000 -> 15000 rpm")
        log.record("firmware.update", "update-service", "1.0.0 -> 1.1.0")
        for e in log.entries():
            print(f"   {e['event']:<16} {e['actor']:<15} {e['target']}")

        print("2. Monitoring: someone guesses the password")
        for _ in range(5):
            log.record("login", "laptop-unknown", "hmi", outcome="failed")
        for alert in alerts(log.entries()):
            print(f"   ALERT: {alert}")

        print("3. The user turns logging off")
        log.set_enabled(False, "admin")
        log.record("config.change", "operator", "spindle speed 15000 -> 9000 rpm")
        last = log.entries()[-1]
        print(f"   last line: {last['event']} by {last['actor']}, nothing recorded after it")


if __name__ == "__main__":
    main()
