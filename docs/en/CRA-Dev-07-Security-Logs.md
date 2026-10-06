---
description: >-
  The minimum the CRA asks for logging (Annex I, Part I, 2(l)): record who accessed or changed what, monitor those events, let the user opt out. In Python, with the standard library only.
---

# Who did what, and when? Logging security activity

> **CRA & Dev #7** · ["CRA & Dev" series](index.md) · Reading time: about 5 min · Cross-platform ·
> Example: Python (standard library)

## What the CRA requires

The [Cyber Resilience Act][cra] requires, on the basis of the risk assessment and
where applicable, to "provide security related information by recording and
monitoring relevant internal activity, including the access to or modification of
data, services or functions, with an opt-out mechanism for the user" (Annex I,
Part I, point 2, l).

Three verbs: record, monitor, opt out. For this point, the text asks for these three
actions.

## The classic trap

The log exists, but it is the debug log: `connection reset`, `value=15000`, stack
traces. The day you need to know who changed a setpoint, the answer is not there.
The opposite trap, logging everything, fills it with passwords and personal data,
and buries the event that matters.

## The technique: a closed list, one line per event

First, the list of security events. It is short and closed: everything that says
who accessed what, or who changed what.

| Event | Example |
| --- | --- |
| `login` | successful or refused login |
| `access.denied` | command refused for lack of rights |
| `config.change` | setpoint or setting changed |
| `firmware.update` | update installed |
| `logging.off`, `logging.on` | logging turned off or back on |

Then, one JSON line per event, always with the same fields: when (in UTC), what,
who, on what, with which outcome. Python's `logging` module is enough (simplified
excerpt from `seclog/log.py`):

```python
def record(self, event, actor, target, outcome="ok"):
    if event not in EVENTS:
        raise ValueError(f"unknown security event: {event}")
    if not self.enabled:
        return
    line = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "event": event, "actor": actor, "target": target, "outcome": outcome}
    self.logger.info(json.dumps(line))
```

A `RotatingFileHandler` bounds the size on disk: a full log must not fill the
device. Rotation deletes the oldest files: whatever must be kept longer has to be
exported first (point 2 below).

Monitoring means doing something with those lines. One simple rule is enough to
start: five refused logins for the same actor raise an alert.

Finally, the opt-out. The text does not say how; we recommend recording the opt-out
itself, with its author, as the last line. You then know when and by whom logging
was turned off.

The [demo][example] does all three (raw program output):

```
1. The device records who accessed or changed what
   login            operator        hmi
   config.change    operator        spindle speed 12000 -> 15000 rpm
   firmware.update  update-service  1.0.0 -> 1.1.0
2. Monitoring: someone guesses the password
   ALERT: 5 failed logins from laptop-unknown
3. The user turns logging off
   last line: logging.off by admin, nothing recorded after it
```

## On embedded targets

The same building blocks exist on each target:

| Target | Record, with a bounded size | Export |
| --- | --- | --- |
| Microcontroller, C or C++ | [Zephyr logging][zephyr-log]: file backend `CONFIG_LOG_BACKEND_FS`, bounded file size and count | `CONFIG_LOG_BACKEND_NET` backend: syslog over UDP or TCP, no TLS |
| Microcontroller, Rust | the [`log`][log-rs] facade (`no_std`) and the [`sequential-storage`][seqstor] flash FIFO queue, which can overwrite the oldest entry | yours to write |
| Embedded Linux, C or C++ | `syslog(3)` or `sd_journal_send(3)`; in C++, [spdlog][spdlog] (rotating files, syslog sink) | the system daemon, for example [rsyslog over TLS][rsyslog-tls] |
| Embedded Linux, Rust | [`log`][log-rs] with [`systemd-journal-logger`][sdjl] or [`syslog`][syslog-rs] | same |

## Three things to know

1. No secret and no needless data in the log: an operator id, not their password or
   their address. That is also what point 2, (g) asks for (data minimisation).
2. An attacker who takes over the device often starts by erasing the logs. Hence a
   copy off the device, to a log server, with a defined retention period. The
   transfer must be authenticated, encrypted (for example syslog over TLS,
   [RFC 5425][rfc5425]) and survive network outages. Python's `SysLogHandler`
   provides none of this ([documentation][syslogh]).
3. Point 2, (l) does not require a tamper-proof log. If your risk assessment calls for
   one, the tool exists on Linux: systemd-journald's
   [Forward Secure Sealing][journalctl].

## Takeaway

A closed list of events, one structured line per event, one monitoring rule, an
opt-out that leaves a trace: that is the minimum the CRA asks for on this point, and it fits in a
few dozen lines.

---

*Previous episode: [A thousand fragments, one signature, updating firmware over
LoRaWAN](CRA-Dev-06-FUOTA-LoRaWAN.md).*

*Companion code, in [`examples/07-security-logging`][example]: the log, the
monitoring rule, the demo and its tests.*

[cra]: https://eur-lex.europa.eu/eli/reg/2024/2847/oj?locale=en
[rfc5425]: https://www.rfc-editor.org/rfc/rfc5425
[syslogh]: https://docs.python.org/3/library/logging.handlers.html#sysloghandler
[zephyr-log]: https://docs.zephyrproject.org/latest/services/logging/index.html
[log-rs]: https://docs.rs/log/latest/log/
[seqstor]: https://docs.rs/sequential-storage/latest/sequential_storage/
[spdlog]: https://github.com/gabime/spdlog
[rsyslog-tls]: https://docs.rsyslog.com/doc/tutorials/tls_cert_summary.html
[sdjl]: https://docs.rs/systemd-journal-logger/latest/systemd_journal_logger/
[syslog-rs]: https://docs.rs/syslog/latest/syslog/
[journalctl]: https://www.freedesktop.org/software/systemd/man/latest/journalctl.html
[example]: https://github.com/ADNTIO/cra-dev-wiki/tree/main/examples/07-security-logging
