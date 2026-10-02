"""Signature et vérification d'une image MCUboot, avec imgtool.

Ce sont les commandes de l'article, appelées telles quelles : la vérification
faite ici est celle que MCUboot fait au démarrage.
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
    """Crée la paire de clés. Seule la clé publique ira dans l'appareil."""
    _imgtool("keygen", "-k", private_key, "-t", key_type).check_returncode()
    _imgtool("getpub", "-k", private_key, "-e", "pem", "-o", public_key).check_returncode()


def sign(private_key: Path, firmware: Path, signed: Path, version: str) -> None:
    """Côté fabricant : produit l'image signée que le serveur FUOTA fragmentera."""
    _imgtool(
        "sign", "-k", private_key, "-v", version,
        "--header-size", "0x200", "--pad-header", "--slot-size", "0x20000", "--align", "4",
        firmware, signed,
    ).check_returncode()  # fmt: skip


def verify(public_key: Path, image: Path) -> bool:
    """Côté appareil : l'image porte-t-elle une signature valide pour cette clé ?"""
    return _imgtool("verify", "-k", public_key, image).returncode == 0


def hash_is_valid(image: Path) -> bool:
    """Le contrôle insuffisant : sans clé, imgtool ne vérifie que le hash de l'image."""
    return _imgtool("verify", image).returncode == 0
