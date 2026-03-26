# Stub de compatibilité — toute la logique est dans totp_core.py
from totp_core import (  # noqa: F401
    generate_totp_secret,
    build_otpauth_uri,
    build_qr_code_url,
    get_current_totp,
    verify_totp,
)
