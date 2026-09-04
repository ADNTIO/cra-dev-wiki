---
description: >-
  Versioning conventions to apply: SemVer, pre-releases (alpha, beta, release candidate) and choosing between PATCH, MINOR and MAJOR.
---

# Versions

| Example | Status | Usage |
|---|---|---|
| `v0.x.y` | Pre-release | Initial development, unstable API |
| `v1.0.0-alpha.1` | Alpha | Incomplete features |
| `v1.0.0-beta.1` | Beta | Feature-complete, testing and fixes |
| `v1.0.0-rc.1` | Release candidate | Stable version awaiting validation |
| `v1.0.0` | Release | First stable public version |
| `v1.0.1` | Patch | Backward-compatible bug fix |
| `v1.1.0` | Minor | New backward-compatible feature |
| `v2.0.0` | Major | Breaking change |

| Change | Version |
|---|---|
| Compatible bug fix | `PATCH`: `v1.0.1` |
| Compatible feature | `MINOR`: `v1.1.0` |
| Code, configuration, or usage must change | `MAJOR`: `v2.0.0` |

Before `v1.0.0`, use `PATCH` for fixes and `MINOR` for features or breaking changes.

## Full example

| Version | Bootloader evolution |
|---|---|
| `v0.1.0` | Experimental USB prototype |
| `v1.0.0-alpha.1` | Incomplete USB update support |
| `v1.0.0-beta.1` | All features implemented, testing begins |
| `v1.0.0-rc.1` | Release candidate ready for validation |
| `v1.0.0` | First stable public release |
| `v1.0.1` | USB bug fix, usage unchanged |
| `v1.1.0` | Optional signature verification added |
| `v2.0.0` | New protocol incompatible with `v1.x.x` |
