"""
Helpers TOTP compatibles Google Authenticator.

Ce module implemente:
- la generation d'un secret base32
- la construction d'une URI otpauth:// (scan QR)
- la generation d'un code TOTP (6 chiffres)
- la verification d'un code saisi par l'utilisateur

Aucune dependance externe n'est requise.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import struct
import time
import urllib.parse


def generate_totp_secret(num_bytes: int = 20) -> str:
    """Genere un secret base32 aleatoire (RFC 6238)."""
    raw = os.urandom(num_bytes)
    return base64.b32encode(raw).decode("ascii").replace("=", "")


def build_otpauth_uri(secret: str, account_name: str, issuer: str = "AuthentificationForte") -> str:
    """Construit une URI otpauth scanable par Google Authenticator."""
    label = f"{issuer}:{account_name}"
    label_encoded = urllib.parse.quote(label)
    issuer_encoded = urllib.parse.quote(issuer)
    return (
        f"otpauth://totp/{label_encoded}"
        f"?secret={secret}&issuer={issuer_encoded}&algorithm=SHA1&digits=6&period=30"
    )


def build_qr_code_url(otpauth_uri: str, size: str = "250x250") -> str:
    """Retourne une URL d'image QR a utiliser dans un <img src=\"...\">."""
    payload = urllib.parse.quote(otpauth_uri, safe="")
    return f"https://quickchart.io/qr?size={size}&text={payload}"


def _totp_at(secret: str, for_time: int, period: int = 30, digits: int = 6) -> str:
    normalized = secret.upper()
    padding = "=" * ((8 - len(normalized) % 8) % 8)
    key = base64.b32decode(normalized + padding, casefold=True)

    counter = int(for_time // period)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()

    offset = digest[-1] & 0x0F
    code_int = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    code = code_int % (10 ** digits)
    return str(code).zfill(digits)


def get_current_totp(secret: str, period: int = 30, digits: int = 6) -> str:
    """Genere le code TOTP courant."""
    return _totp_at(secret=secret, for_time=int(time.time()), period=period, digits=digits)


def verify_totp(
    secret: str,
    user_code: str,
    period: int = 30,
    digits: int = 6,
    valid_window: int = 1,
) -> bool:
    """
    Verifie un code TOTP saisi par l'utilisateur.

    valid_window=1 accepte la fenetre precedente, courante et suivante
    pour tolerer un leger decalage d'horloge.
    """
    cleaned = (user_code or "").strip().replace(" ", "")
    if not cleaned.isdigit() or len(cleaned) != digits:
        return False

    now = int(time.time())
    for step_offset in range(-valid_window, valid_window + 1):
        step_time = now + step_offset * period
        expected = _totp_at(secret=secret, for_time=step_time, period=period, digits=digits)
        if hmac.compare_digest(expected, cleaned):
            return True
    return False


if __name__ == "__main__":
    # Demo locale rapide.
    demo_secret = generate_totp_secret()
    demo_uri = build_otpauth_uri(
        secret=demo_secret,
        account_name="user@example.com",
        issuer="AuthentificationForte",
    )
    print("SECRET:", demo_secret)
    print("OTPAuth URI:", demo_uri)
    print("QR URL:", build_qr_code_url(demo_uri))
    print("Code actuel:", get_current_totp(demo_secret))
