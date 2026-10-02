"""Signing and verifying an MCUboot image, with imgtool.

These are the commands from the article, called as they are: the check made here is
the one MCUboot makes at boot.
"""

import subprocess
import sys
from pathlib import Path


def _imgtool(*args: str | Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "imgtool.main", *map(str, args)],
        capture_output=True,
        text=True,
    )


def keygen(private_key: Path, public_key: Path, key_type: str = "ecdsa-p256") -> None:
    """Creates the key pair. Only the public key goes into the device."""
    _imgtool("keygen", "-k", private_key, "-t", key_type).check_returncode()
    _imgtool("getpub", "-k", private_key, "-e", "pem", "-o", public_key).check_returncode()


def sign(private_key: Path, firmware: Path, signed: Path, version: str) -> None:
    """Manufacturer side: produces the signed image the FUOTA server will fragment."""
    _imgtool(
        "sign", "-k", private_key, "-v", version,
        "--header-size", "0x200", "--pad-header", "--slot-size", "0x20000", "--align", "4",
        firmware, signed,
    ).check_returncode()  # fmt: skip


def verify(public_key: Path, image: Path) -> bool:
    """Device side: does the image carry a valid signature for this key?"""
    return _imgtool("verify", "-k", public_key, image).returncode == 0


def hash_is_valid(image: Path) -> bool:
    """The insufficient check: without a key, imgtool only checks the image hash."""
    return _imgtool("verify", image).returncode == 0
