"""
Authentification FIDO2/WebAuthn avec carte Cryptonox.

Ce module fournit :
- les helpers d'enregistrement (registration) WebAuthn
- la gestion des credentials en base de donnees
- un Blueprint Flask avec les routes correspondantes

Dependance externe : fido2  (pip install fido2)
"""

from __future__ import annotations

import base64
import os

import pymysql
import pymysql.cursors
from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from fido2.server import Fido2Server
from fido2.webauthn import (
    AttestationObject,
    AttestedCredentialData,
    AuthenticatorAttestationResponse,
    CollectedClientData,
    PublicKeyCredentialRpEntity,
    PublicKeyCredentialUserEntity,
    RegistrationResponse,
    UserVerificationRequirement,
)


# ---------------------------------------------------------------------------
# Configuration Relying Party
# Doit correspondre exactement au domaine servi en HTTPS.
# Exemple : WEBAUTHN_RP_ID=monserveur.local python Backend/app.py
# ---------------------------------------------------------------------------
RP_ID   = os.getenv("WEBAUTHN_RP_ID", "localhost")
RP_NAME = "AuthentificationForte"

_server = Fido2Server(PublicKeyCredentialRpEntity(id=RP_ID, name=RP_NAME))


# ---------------------------------------------------------------------------
# Helpers base64url (RFC 4648 §5, sans padding)
# ---------------------------------------------------------------------------
def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


# ---------------------------------------------------------------------------
# Serialisation du state fido2 pour la session Flask (JSON uniquement)
# Les bytes sont convertis en base64url pour pouvoir etre stockes en cookie.
# ---------------------------------------------------------------------------
def _state_encode(state: dict) -> dict:
    out = {}
    for k, v in state.items():
        if isinstance(v, (bytes, bytearray)):
            out[k] = {"__b64__": _b64url_encode(bytes(v))}
        else:
            out[k] = v
    return out


def _state_decode(raw: dict) -> dict:
    out = {}
    for k, v in raw.items():
        if isinstance(v, dict) and "__b64__" in v:
            out[k] = _b64url_decode(v["__b64__"])
        else:
            out[k] = v
    return out


# ---------------------------------------------------------------------------
# Base de donnees
# ---------------------------------------------------------------------------
def _get_connection():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "authentification"),
        port=int(os.getenv("DB_PORT", "3306")),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def init_webauthn_table() -> None:
    """Cree la table webauthn_credentials si elle n'existe pas."""
    conn = None
    cursor = None
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS webauthn_credentials (
                id              INT AUTO_INCREMENT PRIMARY KEY,
                user_id         INT NOT NULL,
                credential_id   VARBINARY(256) NOT NULL,
                credential_data BLOB NOT NULL,
                sign_count      INT DEFAULT 0,
                created_at      DATETIME NOT NULL,
                UNIQUE KEY uq_cred_id (credential_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci
            """
        )
        conn.commit()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def _save_credential(user_id: int, credential_data: AttestedCredentialData) -> None:
    """Stocke la credential FIDO2 en base de donnees."""
    credential_id_bytes   = bytes(credential_data.credential_id)
    credential_data_bytes = bytes(credential_data)

    conn = None
    cursor = None
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO webauthn_credentials
                (user_id, credential_id, credential_data, sign_count, created_at)
            VALUES (%s, %s, %s, 0, NOW())
            ON DUPLICATE KEY UPDATE
                credential_data = VALUES(credential_data),
                sign_count      = 0
            """,
            (user_id, credential_id_bytes, credential_data_bytes),
        )
        conn.commit()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def _load_credentials(user_id: int) -> list:
    """Charge les credentials FIDO2 d'un utilisateur depuis la base."""
    conn = None
    cursor = None
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT credential_data FROM webauthn_credentials WHERE user_id = %s",
            (user_id,),
        )
        rows = cursor.fetchall()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return [AttestedCredentialData(bytes(row["credential_data"])) for row in rows]


# ---------------------------------------------------------------------------
# Blueprint Flask
# ---------------------------------------------------------------------------
cryptonox_auth_bp = Blueprint("cryptonox_auth_bp", __name__)


@cryptonox_auth_bp.route("/cryptonox-auth/setup")
def cryptonox_auth_setup():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("cryptonox_auth_setup.html")


@cryptonox_auth_bp.route("/webauthn/register/begin", methods=["POST"])
def webauthn_register_begin():
    """Genere le challenge d'enregistrement et renvoie les options en JSON."""
    if "user_id" not in session:
        return jsonify({"error": "non authentifie"}), 401

    user = PublicKeyCredentialUserEntity(
        id=str(session["user_id"]).encode(),
        name=session.get("user_name", "utilisateur"),
        display_name=session.get("user_name", "utilisateur"),
    )

    options, state = _server.register_begin(
        user,
        user_verification=UserVerificationRequirement.PREFERRED,
    )

    session["webauthn_register_state"]    = _state_encode(dict(state))
    session["cryptonox_auth_verified"]    = False

    pk = options.public_key
    options_json = {
        "challenge": _b64url_encode(bytes(pk.challenge)),
        "rp": {
            "id":   pk.rp.id,
            "name": pk.rp.name,
        },
        "user": {
            "id":          _b64url_encode(bytes(pk.user.id)),
            "name":        pk.user.name,
            "displayName": pk.user.display_name,
        },
        "pubKeyCredParams": [
            {"type": p.type.value, "alg": int(p.alg)}
            for p in pk.pub_key_cred_params
        ],
        "timeout":            pk.timeout or 60000,
        "attestation":        (pk.attestation.value
                               if pk.attestation else "none"),
        "excludeCredentials": [],
        "authenticatorSelection": {
            "userVerification": "preferred",
            "authenticatorAttachment": "cross-platform",
        },
    }
    return jsonify(options_json)


@cryptonox_auth_bp.route("/webauthn/register/complete", methods=["POST"])
def webauthn_register_complete():
    """Verifie l'attestation de la carte et stocke la credential en base."""
    if "user_id" not in session:
        return jsonify({"error": "non authentifie"}), 401

    raw_state = session.pop("webauthn_register_state", None)
    if not raw_state:
        return jsonify({"error": "Aucune session d'enregistrement active"}), 400

    state = _state_decode(raw_state)
    data  = request.get_json(force=True)
    if not data:
        return jsonify({"error": "Corps JSON manquant"}), 400

    try:
        raw_id_bytes      = _b64url_decode(data["rawId"])
        client_data_bytes = _b64url_decode(data["response"]["clientDataJSON"])
        attestation_bytes = _b64url_decode(data["response"]["attestationObject"])

        attestation_response = AuthenticatorAttestationResponse(
            client_data=CollectedClientData(client_data_bytes),
            attestation_object=AttestationObject(attestation_bytes),
        )
        registration_response = RegistrationResponse(
            raw_id=raw_id_bytes,
            response=attestation_response,
        )
        auth_data = _server.register_complete(state, registration_response)
        _save_credential(session["user_id"], auth_data.credential_data)
        session["cryptonox_auth_verified"] = True
        return jsonify({"status": "ok"})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@cryptonox_auth_bp.route("/webauthn/report")
def cryptonox_auth_report():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if not session.get("cryptonox_auth_verified"):
        flash("Veuillez finaliser l'enregistrement de votre carte.", "error")
        return redirect(url_for("cryptonox_auth_bp.cryptonox_auth_setup"))
    return render_template("cryptonox_auth_report.html")


if __name__ == "__main__":
    print("RP_ID  :", RP_ID)
    print("RP_NAME:", RP_NAME)
    print("Configurez WEBAUTHN_RP_ID pour correspondre a votre domaine HTTPS.")
    print("Exemple : $env:WEBAUTHN_RP_ID='localhost' ; python Backend/app.py")
