# Example: recording and monitoring security events

Companion code for episode 7 of the "CRA & Dev" series,
[Who did what, and when?](../../docs/en/CRA-Dev-07-Security-Logs.md).

The minimum asked by the CRA (Annex I, Part I, point 2 (l)): record the relevant
internal activity, monitor it, and let the user opt out. Standard library only.

## Run

This project uses [uv](https://docs.astral.sh/uv/).

```bash
uv run python -m seclog.demo   # the scenario
uv run pytest                  # the tests
```

Output:

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

One event, one JSON line:

```json
{"time": "2026-10-06T12:00:00+00:00", "event": "config.change", "actor": "operator", "target": "spindle speed 12000 -> 15000 rpm", "outcome": "ok"}
```

## What it does not do

- Send a copy off the device. In a product, add a handler to a log server, for
  example `logging.handlers.SysLogHandler`, so that an attacker who takes over the
  device cannot erase the history.
- Make the log tamper-evident. The CRA does not require it; if the risk assessment
  calls for it, see systemd-journald's Forward Secure Sealing.
