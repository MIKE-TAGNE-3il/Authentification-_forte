"""
Authentification WebAuthn / FIDO2 avec YubiKey.
Compatible fido2 >= 1.0 (API CredentialCreationOptions).

pip install fido2
"""

from __future__ import annotations

import base64
from fido2 import cbor
from fido2.server import Fido2Server
from fido2.webauthn import (
    AttestationObject,
    AuthenticatorData,
    CollectedClientData,
    PublicKeyCredentialRpEntity,
    PublicKeyCredentialUserEntity,
    UserVerificationRequirement,
    RegistrationResponse, 
    AuthenticationResponse,
    AuthenticatorAttestationResponse
)

# ---------------------------------------------------------------------------
# Relying Party
# ---------------------------------------------------------------------------
RP_ID   = "localhost"
RP_NAME = "AuthentificationForte"

_rp     = PublicKeyCredentialRpEntity(id=RP_ID, name=RP_NAME)
_server = Fido2Server(_rp)


# ---------------------------------------------------------------------------
# Helpers Base64URL
# ---------------------------------------------------------------------------

def b64url_encode(data) -> str:
    """Encode en Base64URL de manière robuste."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(value: str) -> bytes:
    padding = 4 - len(value) % 4
    if padding != 4:
        value += "=" * padding
    return base64.urlsafe_b64decode(value)


# ---------------------------------------------------------------------------
# Enregistrement
# ---------------------------------------------------------------------------

def begin_registration(user_id: int, user_name: str, user_email: str) -> tuple[dict, dict]:
    """
    Retourne (options_json, state).
    state est un dict avec 'challenge' en bytes.
    """
    user = PublicKeyCredentialUserEntity(
        id=str(user_id).encode("utf-8"),
        name=user_email,
        display_name=user_name,
    )

    options, state = _server.register_begin(
        user=user,
        user_verification=UserVerificationRequirement.PREFERRED,
    )

    # fido2 >= 1.0 : les options sont dans options.public_key
    pk = options.public_key if hasattr(options, "public_key") else options

    options_json = {
        "challenge": b64url_encode(pk.challenge),
        "rp": {
            "id":   pk.rp.id,
            "name": pk.rp.name,
        },
        "user": {
            "id":          b64url_encode(pk.user.id),
            "name":        pk.user.name,
            "displayName": pk.user.display_name,
        },
        "pubKeyCredParams": [
            {"type": "public-key", "alg": p.alg}
            for p in pk.pub_key_cred_params
        ],
        "timeout": pk.timeout or 60000,
        "excludeCredentials": [
            {
                "type":       "public-key",
                "id":         b64url_encode(c.id),
                "transports": list(c.transports) if c.transports else [],
            }
            for c in (pk.exclude_credentials or [])
        ],
        "authenticatorSelection": {
            "userVerification": (
                pk.authenticator_selection.user_verification.value
                if pk.authenticator_selection
                else "preferred"
            ),
        },
        "attestation": pk.attestation.value if pk.attestation else "none",
    }

    # Normalise state en dict simple sérialisable
    if isinstance(state, dict):
        uv = state.get("user_verification", "preferred")
        normalized_state = {
            "challenge":         state.get("challenge") or pk.challenge,
            "user_verification": uv.value if hasattr(uv, "value") else uv,
        }
    else:
        normalized_state = {
            "challenge":         pk.challenge,
            "user_verification": "preferred",
        }

    return options_json, normalized_state


def complete_registration(
    state: dict,
    client_data_json_b64: str,
    attestation_object_b64: str,
) -> dict:
    """
    Vérifie l'attestation. Retourne credential_id, public_key, sign_count.
    """
    client_data_bytes = b64url_decode(client_data_json_b64)
    att_obj_bytes     = b64url_decode(attestation_object_b64)

    # 1. On crée la réponse d'attestation
    attestation_response = AuthenticatorAttestationResponse(
        client_data=CollectedClientData(client_data_bytes),
        attestation_object=AttestationObject(att_obj_bytes),
    )

    # 2. On crée l'objet RegistrationResponse (avec un raw_id factice ou extrait si disponible)
    # Note: Dans ton flux JS, tu devrais aussi envoyer le "rawId" pour être 100% propre
    registration_response = RegistrationResponse(
        raw_id=b"", # Ou extrait de la requête si tu l'as ajouté au JSON envoyé par le JS
        response=attestation_response,
    )

    fido_state = {
        "challenge":         state["challenge"],
        "user_verification": state.get("user_verification", "preferred"),
    }

    # 3. APPEL CORRIGÉ : Seulement 2 arguments (le state et la réponse)
    auth_data = _server.register_complete(fido_state, registration_response)

    credential_id: bytes = auth_data.credential_data.credential_id
    public_key:    bytes = cbor.encode(dict(auth_data.credential_data.public_key))
    sign_count:    int   = auth_data.counter

    return {
        "credential_id": credential_id,
        "public_key":    public_key,
        "sign_count":    sign_count,
    }

# ---------------------------------------------------------------------------
# Authentification
# ---------------------------------------------------------------------------

def begin_authentication(credentials: list[dict]) -> tuple[dict, dict]:
    """
    Retourne (options_json, state).
    """
    from fido2.webauthn import AttestedCredentialData

    fido_credentials = [
        AttestedCredentialData.create(
            aaguid=b"\x00" * 16,
            credential_id=c["credential_id"],
            public_key=cbor.decode(c["public_key"]),
        )
        for c in credentials
    ]

    options, state = _server.authenticate_begin(
        credentials=fido_credentials,
        user_verification=UserVerificationRequirement.PREFERRED,
    )

    pk = options.public_key if hasattr(options, "public_key") else options

    options_json = {
        "challenge": b64url_encode(pk.challenge),
        "timeout":   pk.timeout or 60000,
        "rpId":      pk.rp_id,
        "allowCredentials": [
            {
                "type":       "public-key",
                "id":         b64url_encode(c.id),
                "transports": list(c.transports) if c.transports else ["usb", "nfc"],
            }
            for c in (pk.allow_credentials or [])
        ],
        "userVerification": (
            pk.user_verification.value if pk.user_verification else "preferred"
        ),
    }

    if isinstance(state, dict):
        uv = state.get("user_verification", "preferred")
        normalized_state = {
            "challenge":         state.get("challenge") or pk.challenge,
            "user_verification": uv.value if hasattr(uv, "value") else uv,
        }
    else:
        normalized_state = {
            "challenge":         pk.challenge,
            "user_verification": "preferred",
        }

    return options_json, normalized_state


def complete_authentication(
    state: dict,
    credentials: list[dict],
    credential_id_b64: str,
    client_data_json_b64: str,
    authenticator_data_b64: str,
    signature_b64: str,
) -> dict:
    """
    Vérifie la signature. Retourne credential_id et new_sign_count.
    """
    from fido2.webauthn import AttestedCredentialData

    fido_credentials = [
        AttestedCredentialData.create(
            aaguid=b"\x00" * 16,
            credential_id=c["credential_id"],
            public_key=cbor.decode(c["public_key"]),
        )
        for c in credentials
    ]

    auth_response = AuthenticationResponse(
        raw_id=b64url_decode(credential_id_b64),
        response={
            "clientDataJSON": b64url_decode(client_data_json_b64),
            "authenticatorData": b64url_decode(authenticator_data_b64),
            "signature": b64url_decode(signature_b64),
        }
    )

    fido_state = {
        "challenge": state["challenge"],
        "user_verification": state.get("user_verification", "preferred"),
    }

    auth_result = _server.authenticate_complete(
        state=fido_state,
        credentials=fido_credentials,
        response=auth_response  
    )

    cred_id = getattr(auth_result, 'credential_id', None)
    if not cred_id and hasattr(auth_result, 'credential'):
        cred_id = auth_result.credential.credential_id

    new_sign_count = getattr(auth_result, 'sign_count', getattr(auth_result, 'counter', 0))

    return {
        "credential_id": cred_id,
        "new_sign_count": new_sign_count,
    }