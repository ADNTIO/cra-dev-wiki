"""The minimum the CRA asks for: record, monitor, let the user opt out."""
import json
import logging
import logging.handlers
from collections import Counter
from datetime import datetime, timezone

# A closed list: the events that say who accessed or changed what.
EVENTS = {"login", "access.denied", "config.change", "firmware.update", "logging.off", "logging.on"}


class SecurityLog:
    def __init__(self, path):
        self.path = path
        self.enabled = True
        self.logger = logging.getLogger(f"security.{path}")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        # Bounded on disk: a full log must not fill the device.
        self.logger.addHandler(logging.handlers.RotatingFileHandler(path, maxBytes=64_000, backupCount=2))

    def record(self, event, actor, target, outcome="ok"):
        if event not in EVENTS:
            raise ValueError(f"unknown security event: {event}")
        if not self.enabled:
            return
        line = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "event": event, "actor": actor, "target": target, "outcome": outcome}
        self.logger.info(json.dumps(line))

    def set_enabled(self, on, actor):
        """The user's opt-out. The switch itself is the last line recorded."""
        if not on:
            self.record("logging.off", actor, "security log")
        self.enabled = on
        if on:
            self.record("logging.on", actor, "security log")

    def entries(self):
        with open(self.path) as f:
            return [json.loads(line) for line in f]


def alerts(entries, limit=5):
    """Monitoring: one simple rule, too many failed logins from one actor."""
    failures = Counter(e["actor"] for e in entries if e["event"] == "login" and e["outcome"] == "failed")
    return [f"{n} failed logins from {actor}" for actor, n in failures.items() if n >= limit]
