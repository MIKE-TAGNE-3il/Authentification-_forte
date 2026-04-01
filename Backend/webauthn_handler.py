import base64
from webauthn import (
    generate_registration_options, verify_registration_response
)
# Objets de configuration obligatoires pour la version 2.7.1
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    UserVerificationRequirement,
    AttestationConveyancePreference,
    RegistrationCredential,
    AuthenticatorAttachment,
    AuthenticatorAttestationResponse
)

RP_ID = "localhost"
RP_NAME = "AuthentificationForte"
ORIGIN = "http://localhost:5000"

def get_registration_options(user_id_bytes, username):
    auth_selection = AuthenticatorSelectionCriteria(
        user_verification=UserVerificationRequirement.PREFERRED,
        authenticator_attachment=AuthenticatorAttachment.PLATFORM
    )

    return generate_registration_options(
        rp_id=RP_ID,
        rp_name=RP_NAME,
        user_id=user_id_bytes, 
        user_name=username,
        attestation=AttestationConveyancePreference.NONE,
        authenticator_selection=auth_selection
    )

def _b64url_decode(value: str) -> bytes:
    padding = 4 - len(value) % 4
    if padding != 4:
        value += "=" * padding
    return base64.urlsafe_b64decode(value)

def verify_registration(token_data, expected_challenge):
    credential = RegistrationCredential(
        id=token_data["id"],
        raw_id=_b64url_decode(token_data["rawId"]),
        response=AuthenticatorAttestationResponse(
            client_data_json=_b64url_decode(token_data["response"]["clientDataJSON"]),
            attestation_object=_b64url_decode(token_data["response"]["attestationObject"]),
        ),
    )
    return verify_registration_response(
        credential=credential,
        expected_challenge=expected_challenge,
        expected_origin=ORIGIN,
        expected_rp_id=RP_ID
    )