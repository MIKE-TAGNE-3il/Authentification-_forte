from webauthn import (
    generate_registration_options, verify_registration_response
)
# Objets de configuration obligatoires pour la version 2.7.1
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria, 
    UserVerificationRequirement,
    AttestationConveyancePreference,
    RegistrationCredential,
    AuthenticatorAttachment
)

RP_ID = "localhost"
RP_NAME = "AuthentificationForte"
ORIGIN = "http://localhost:5000"

def get_registration_options(user_id_bytes, username):
    auth_selection = AuthenticatorSelectionCriteria(
        user_verification=UserVerificationRequirement.PREFERRED,
        authenticator_attachment=AuthenticatorAttachment.CROSS_PLATFORM
    )

    return generate_registration_options(
        rp_id=RP_ID,
        rp_name=RP_NAME,
        user_id=user_id_bytes, 
        user_name=username,
        attestation=AttestationConveyancePreference.NONE,
        authenticator_selection=auth_selection
    )

def verify_registration(token_data, expected_challenge):
    return verify_registration_response(
        credential=token_data,
        expected_challenge=expected_challenge,
        expected_origin=ORIGIN,
        expected_rp_id=RP_ID
    )