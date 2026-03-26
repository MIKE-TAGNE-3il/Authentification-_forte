"""
Moteur TOTP générique (RFC 6238).

Les quatre applications TOTP (Microsoft Authenticator, Google Authenticator,
Authy, FreeOTP) utilisent exactement le même algorithme HMAC-SHA1.
Seul le label dans l'URI otpauth:// varie.

Ce module centralise toute la logique pour éviter la duplication.
Les anciens modules (microsoft_authenticator.py, etc.) restent présents
comme stubs de compatibilité qui importent depuis ici.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import struct
import time
import urllib.parse
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration des 4 applications TOTP supportées
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TOTPConfig:
    """Décrit une application TOTP : son identifiant URL et son nom d'affichage."""
    key: str    # Utilisé dans les URLs et les clés de session  (ex: "microsoft")
    label: str  # Nom affiché à l'utilisateur                  (ex: "Microsoft Authenticator")
    issuer: str = "AuthentificationForte"


TOTP_CONFIGS: dict[str, TOTPConfig] = {
    "microsoft": TOTPConfig("microsoft", "Microsoft Authenticator"),
    "google":    TOTPConfig("google",    "Google Authenticator"),
    "authy":     TOTPConfig("authy",     "Authy"),
    "freeotp":   TOTPConfig("freeotp",   "FreeOTP"),
}


# ---------------------------------------------------------------------------
# Fonctions TOTP (RFC 6238 / HOTP RFC 4226)
# ---------------------------------------------------------------------------

def generate_totp_secret(num_bytes: int = 20) -> str:
    """Génère un secret aléatoire encodé en base32 (160 bits par défaut)."""
    raw = os.urandom(num_bytes)
    return base64.b32encode(raw).decode("ascii").replace("=", "")


def build_otpauth_uri(secret: str, account_name: str, issuer: str) -> str:
    """Construit l'URI otpauth:// scannable par toute application TOTP."""
    label = urllib.parse.quote(f"{issuer}:{account_name}")
    issuer_enc = urllib.parse.quote(issuer)
    return (
        f"otpauth://totp/{label}"
        f"?secret={secret}&issuer={issuer_enc}&algorithm=SHA1&digits=6&period=30"
    )


def build_qr_code_url(otpauth_uri: str, size: str = "250x250") -> str:
    """Retourne une URL d'image QR utilisable dans un <img src=...>."""
    payload = urllib.parse.quote(otpauth_uri, safe="")
    return f"https://quickchart.io/qr?size={size}&text={payload}"


def _totp_at(secret: str, for_time: int, period: int = 30, digits: int = 6) -> str:
    """Calcule le code TOTP pour un instant donné (usage interne)."""
    normalized = secret.upper()
    padding = "=" * ((8 - len(normalized) % 8) % 8)
    key = base64.b32decode(normalized + padding, casefold=True)

    counter = int(for_time // period)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()

    offset = digest[-1] & 0x0F
    code_int = struct.unpack(">I", digest[offset: offset + 4])[0] & 0x7FFFFFFF
    return str(code_int % (10 ** digits)).zfill(digits)


def get_current_totp(secret: str, period: int = 30, digits: int = 6) -> str:
    """Retourne le code TOTP valide à cet instant."""
    return _totp_at(secret, int(time.time()), period, digits)


def verify_totp(
    secret: str,
    user_code: str,
    period: int = 30,
    digits: int = 6,
    valid_window: int = 1,
) -> bool:
    """
    Vérifie un code TOTP saisi par l'utilisateur.

    valid_window=1 accepte la fenêtre précédente, courante et suivante
    pour tolérer un léger décalage d'horloge (~30 s de marge).
    Utilise hmac.compare_digest pour résister aux attaques temporelles.
    """
    cleaned = (user_code or "").strip().replace(" ", "")
    if not cleaned.isdigit() or len(cleaned) != digits:
        return False

    now = int(time.time())
    for step in range(-valid_window, valid_window + 1):
        expected = _totp_at(secret, now + step * period, period, digits)
        if hmac.compare_digest(expected, cleaned):
            return True

    logger.debug("Échec TOTP : code incorrect ou fenêtre dépassée.")
    return False
