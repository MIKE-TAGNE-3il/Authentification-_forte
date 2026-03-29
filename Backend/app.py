from flask import Flask, request, render_template, flash, redirect, url_for, session, json, Response
from dotenv import load_dotenv
load_dotenv()
import pymysql
import os
import bcrypt
import logging


try:
    from totp_core import TOTP_CONFIGS, generate_totp_secret, build_otpauth_uri, build_qr_code_url, verify_totp
except ImportError:
    from Backend.totp_core import TOTP_CONFIGS, generate_totp_secret, build_otpauth_uri, build_qr_code_url, verify_totp

# Configuration du logger applicatif
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("app")

# --- IMPORTS BLUEPRINTS (Cryptonox, NFC) ---
try:
    from cryptonox_authenticator import cryptonox_auth_bp, init_webauthn_table
except ImportError:
    from Backend.cryptonox_authenticator import cryptonox_auth_bp, init_webauthn_table

try:
    from nfc_authenticator import nfc_auth_bp, init_nfc_table
except ImportError:
    from Backend.nfc_authenticator import nfc_auth_bp, init_nfc_table

try:
    from mail_authenticator import email_auth_bp
except ImportError:
    from Backend.mail_authenticator import email_auth_bp

from webauthn_handler import get_registration_options, verify_registration
from webauthn.helpers import options_to_json

try:
    from yubikey_authenticator import (
        begin_registration,
        complete_registration,
        begin_authentication,
        complete_authentication,
        b64url_encode,
    )
except ImportError:
    from Backend.yubikey_authenticator import (
        begin_registration,
        complete_registration,
        begin_authentication,
        complete_authentication,
        b64url_encode,
    )


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)

app = Flask(
    __name__,
    template_folder=os.path.join(PROJECT_DIR, "Frontend"),
    static_folder=os.path.join(PROJECT_DIR, "static"),
    static_url_path="/static",
)

app.register_blueprint(cryptonox_auth_bp)
app.register_blueprint(nfc_auth_bp)
app.register_blueprint(email_auth_bp)

# Clé secrète depuis le fichier .env
app.secret_key = os.getenv("SECRET_KEY", "436f9c8e7a1b5d3f2a8c6e4d9b7a1c3e5f8a2d4b6c0e9f7a3c1e5d8b2a4f6c0e")

# --- CONNEXION BASE DE DONNÉES ---
def get_connection():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "authentification"),
        port=int(os.getenv("DB_PORT", "3306")),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )


def init_database_schema():
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INT(100) NOT NULL AUTO_INCREMENT,
                nom VARCHAR(500) NOT NULL,
                email VARCHAR(500) NOT NULL,
                password VARCHAR(1000) NOT NULL,
                createdAt DATETIME NOT NULL,
                PRIMARY KEY (id),
                UNIQUE KEY email (email)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci
            """
        )
        cursor.execute(
            """
            ALTER TABLE users
            MODIFY COLUMN id INT(100) NOT NULL AUTO_INCREMENT
            """
        )
        conn.commit()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


init_database_schema()
init_webauthn_table()
init_nfc_table()


@app.route("/")
def home():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
        conn.close()

        if user and bcrypt.checkpw(password.encode("utf-8"), user["password"].encode("utf-8")):
            session["user_id"] = user["id"]
            session["user_name"] = user["nom"]
            return redirect(url_for("choose_auth"))

        flash("Identifiants incorrects.", "danger")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        nom = request.form.get("nom")
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password")

        hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

        try:
            conn = get_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
                if cursor.fetchone():
                    flash("Cet email est déjà utilisé.", "danger")
                    return render_template("register.html")

                cursor.execute(
                    "INSERT INTO users (nom, email, password, createdAt) VALUES (%s, %s, %s, NOW())",
                    (nom, email, hashed_pw.decode("utf-8"))
                )
            conn.close()
            flash("Compte créé avec succès ! Connectez-vous.", "success")
            return redirect(url_for("login"))

        except Exception as e:
            flash(f"Erreur lors de l'inscription : {e}", "danger")

    return render_template("register.html")

@app.route("/choose-auth")
def choose_auth():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("choosAuth.html")

@app.route("/select-auth-method", methods=["POST"])
def select_auth_method():
    if "user_id" not in session:
        return redirect(url_for("login"))

    selected_method = request.form.get("auth_method", "").strip()
    if not selected_method:
        flash("Veuillez choisir une methode d'authentification.", "error")
        return redirect(url_for("choose_auth"))

    session["selected_auth_method"] = selected_method

    if selected_method in TOTP_CONFIGS:
        return redirect(url_for("totp_auth_setup", method=selected_method))
    if selected_method == "cryptonox":
        return redirect(url_for("cryptonox_auth_bp.cryptonox_auth_setup"))
    if selected_method == "nfc":
        return redirect(url_for("nfc_auth_bp.nfc_auth_setup"))
    if selected_method == "email":
        return redirect(url_for("email_auth_bp.email_auth_setup"))
    if selected_method == "yubikey":
        return redirect(url_for("yubikey_setup"))

    flash(f"Methode {selected_method} non implementee pour le moment.", "error")
    return redirect(url_for("choose_auth"))


@app.route("/webauthn/register/options")
def webauthn_register_options():
    if "user_id" not in session:
        return {"error": "Session expirée"}, 401

    try:
        user_id_bytes = str(session["user_id"]).encode('utf-8')
        user_name = session["user_name"]

        options = get_registration_options(user_id_bytes, user_name)

        session["webauthn_challenge"] = options.challenge.hex()

        return Response(options_to_json(options), mimetype='application/json')

    except Exception:
        logger.exception("Erreur WebAuthn options (user_id=%s)", session.get("user_id"))
        return {"error": "Erreur interne lors de la génération des options WebAuthn."}, 500

@app.route("/webauthn/register/verify", methods=["POST"])
def webauthn_register_verify():
    challenge_hex = session.get("webauthn_challenge", "")
    if not challenge_hex:
        return {"status": "error", "message": "Challenge manquant"}, 400

    challenge = bytes.fromhex(challenge_hex)
    registration_data = request.get_json()

    try:
        verification = verify_registration(registration_data, challenge)

        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(
                """UPDATE users SET
                   webauthn_credential_id=%s,
                   webauthn_public_key=%s
                   WHERE id=%s""",
                (verification.credential_id, verification.credential_public_key, session["user_id"])
            )
        conn.close()

        session["auth_verified"] = True
        return {"status": "ok"}

    except Exception:
        logger.exception("Échec vérification WebAuthn (user_id=%s)", session.get("user_id"))
        return {"status": "error", "message": "Échec de la vérification biométrique."}, 400


@app.route("/auth-success")
def auth_success():
    if "user_id" not in session:
        return redirect(url_for("login"))
    totp_verified = any(session.get(f"{m}_auth_verified") for m in TOTP_CONFIGS)
    if not session.get("auth_verified") and not session.get("nfc_auth_verified") and not totp_verified:
        return redirect(url_for("choose_auth"))
    return render_template("auth_success.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# --- AUTHENTICATEURS TOTP GÉNÉRIQUES ---
# Une seule paire de routes remplace les 4×2 = 8 routes précédentes.
# <method> accepte : microsoft | google | authy | freeotp

@app.route("/<method>-auth/setup", methods=["GET", "POST"])
def totp_auth_setup(method: str):
    if method not in TOTP_CONFIGS:
        return redirect(url_for("choose_auth"))
    if "user_id" not in session:
        return redirect(url_for("login"))

    cfg = TOTP_CONFIGS[method]
    secret_key = f"{method}_totp_secret"
    verified_key = f"{method}_auth_verified"

    secret = session.get(secret_key)
    if not secret:
        secret = generate_totp_secret()
        session[secret_key] = secret
        session[verified_key] = False

    account_name = session.get("user_name", "utilisateur")
    otpauth_uri = build_otpauth_uri(secret=secret, account_name=account_name, issuer=cfg.issuer)
    qr_url = build_qr_code_url(otpauth_uri)

    if request.method == "POST":
        otp_code = request.form.get("otp_code", "").strip()
        if verify_totp(secret=secret, user_code=otp_code):
            session[verified_key] = True
            logger.info("TOTP validé : user_id=%s méthode=%s", session["user_id"], method)
            flash(f"{cfg.label} configuré avec succès.", "success")
            return redirect(url_for("totp_auth_report", method=method))
        logger.warning("Code TOTP invalide : user_id=%s méthode=%s", session["user_id"], method)
        flash("Code invalide. Vérifiez l'application puis réessayez.", "error")

    return render_template(
        f"{method}_auth_setup.html",
        qr_url=qr_url,
        secret=secret,
        issuer=cfg.issuer,
        account_name=account_name,
        app_label=cfg.label,
    )


@app.route("/<method>-auth/report")
def totp_auth_report(method: str):
    if method not in TOTP_CONFIGS:
        return redirect(url_for("choose_auth"))
    if "user_id" not in session:
        return redirect(url_for("login"))
    if not session.get(f"{method}_auth_verified"):
        flash(f"Veuillez finaliser la vérification {TOTP_CONFIGS[method].label}.", "error")
        return redirect(url_for("totp_auth_setup", method=method))
    return render_template(f"{method}_auth_report.html")


# --- AUTHENTIFICATION PAR E-MAIL (blueprint) ---

    secret = session.get("google_totp_secret")
    if not secret:
        secret = generate_google_totp_secret()
        session["google_totp_secret"] = secret
        session["google_auth_verified"] = False

    account_name = session.get("user_name", "utilisateur")
    issuer = "AuthentificationForte"
    otpauth_uri = build_google_otpauth_uri(
        secret=secret, account_name=account_name, issuer=issuer
    )
    qr_url = build_google_qr_code_url(otpauth_uri)

    if request.method == "POST":
        otp_code = request.form.get("otp_code", "").strip()
        if verify_google_totp(secret=secret, user_code=otp_code):
            session["google_auth_verified"] = True
            flash("Google Authenticator configure avec succes.", "success")
            return redirect(url_for("google_auth_report"))
        flash("Code invalide. Verifiez l'application puis reessayez.", "error")

    return render_template(
        "google_auth_setup.html",
        qr_url=qr_url,
        secret=secret,
        issuer=issuer,
        account_name=account_name,
    )


@app.route("/google-auth/report")
def google_auth_report():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if not session.get("google_auth_verified"):
        flash("Veuillez finaliser la verification Google Authenticator.", "error")
        return redirect(url_for("google_auth_setup"))
    return render_template("google_auth_report.html")


@app.route("/authy-auth/setup", methods=["GET", "POST"])
def authy_auth_setup():
    if "user_id" not in session:
        return redirect(url_for("login"))

    secret = session.get("authy_totp_secret")
    if not secret:
        secret = generate_authy_totp_secret()
        session["authy_totp_secret"] = secret
        session["authy_auth_verified"] = False

    account_name = session.get("user_name", "utilisateur")
    issuer = "AuthentificationForte"
    otpauth_uri = build_authy_otpauth_uri(
        secret=secret, account_name=account_name, issuer=issuer
    )
    qr_url = build_authy_qr_code_url(otpauth_uri)

    if request.method == "POST":
        otp_code = request.form.get("otp_code", "").strip()
        if verify_authy_totp(secret=secret, user_code=otp_code):
            session["authy_auth_verified"] = True
            flash("Authy est configure avec succes.", "success")
            return redirect(url_for("authy_auth_report"))
        flash("Code invalide. Verifiez l'application puis reessayez.", "error")

    return render_template(
        "authy_auth_setup.html",
        qr_url=qr_url,
        secret=secret,
        issuer=issuer,
        account_name=account_name,
    )


@app.route("/authy-auth/report")
def authy_auth_report():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if not session.get("authy_auth_verified"):
        flash("Veuillez finaliser la verification Authy.", "error")
        return redirect(url_for("authy_auth_setup"))
    return render_template("authy_auth_report.html")


@app.route("/freeotp-auth/setup", methods=["GET", "POST"])
def freeotp_auth_setup():
    if "user_id" not in session:
        return redirect(url_for("login"))

    secret = session.get("freeotp_totp_secret")
    if not secret:
        secret = generate_freeotp_totp_secret()
        session["freeotp_totp_secret"] = secret
        session["freeotp_auth_verified"] = False

    account_name = session.get("user_name", "utilisateur")
    issuer = "AuthentificationForte"
    otpauth_uri = build_freeotp_otpauth_uri(
        secret=secret, account_name=account_name, issuer=issuer
    )
    qr_url = build_freeotp_qr_code_url(otpauth_uri)

    if request.method == "POST":
        otp_code = request.form.get("otp_code", "").strip()
        if verify_freeotp_totp(secret=secret, user_code=otp_code):
            session["freeotp_auth_verified"] = True
            flash("FreeOTP est configure avec succes.", "success")
            return redirect(url_for("freeotp_auth_report"))
        flash("Code invalide. Verifiez l'application puis reessayez.", "error")

    return render_template(
        "freeotp_auth_setup.html",
        qr_url=qr_url,
        secret=secret,
        issuer=issuer,
        account_name=account_name,
    )


@app.route("/freeotp-auth/report")
def freeotp_auth_report():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if not session.get("freeotp_auth_verified"):
        flash("Veuillez finaliser la verification FreeOTP.", "error")
        return redirect(url_for("freeotp_auth_setup"))
    return render_template("freeotp_auth_report.html")


def _get_yubikey_credentials(user_id: int) -> list[dict]:
    """Retourne la liste des credentials enregistrées pour cet utilisateur."""
    conn = cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT credentialId, publicKey, signCount FROM yubikey WHERE userId = %s",
            (user_id,),
        )
        rows = cursor.fetchall()
        return [
            {
                "credential_id": bytes(row["credentialId"]),
                "public_key": bytes(row["publicKey"]),
                "sign_count": row["signCount"],
            }
            for row in rows
        ]
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# ─────────────────────────────────────────────────────────────────────────────
#  PAGE D'ACCUEIL  —  choix enregistrement vs authentification
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/yubikey/setup")
def yubikey_setup():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("yubikey_setup.html")


# ─────────────────────────────────────────────────────────────────────────────
#  ENREGISTREMENT  —  begin  (renvoie le challenge JSON au navigateur)
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/yubikey/register/begin", methods=["POST"])
def yubikey_register_begin():
    """
    Étape 1 : génère et stocke un challenge d'enregistrement.
    Le frontend appelle cette route en AJAX (fetch POST).
    """
    if "user_id" not in session:
        return {"error": "Non authentifié"}, 401

    options_json, state = begin_registration(
        user_id=session["user_id"],
        user_name=session.get("user_name", "utilisateur"),
        user_email=session.get("user_email", ""),
    )

    # Le state contient le challenge ; on le sérialise en session Flask.
    # fido2 renvoie un dict avec une clé "challenge" en bytes → on encode.
    session["yubikey_register_state"] = {
        "challenge": b64url_encode(state["challenge"]),
        # fido2 >= 1.x stocke aussi user_verification dans state
        "user_verification": state.get("user_verification", "preferred"),
    }

    return options_json  # Flask sérialise automatiquement le dict en JSON


# ─────────────────────────────────────────────────────────────────────────────
#  ENREGISTREMENT  —  complete  (vérifie la réponse de la YubiKey)
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/yubikey/register/complete", methods=["POST"])
def yubikey_register_complete():
    """
    Étape 2 : vérifie l'attestation et persiste la credential en base.
    """
    if "user_id" not in session:
        return {"error": "Non authentifié"}, 401

    state = session.pop("yubikey_register_state", None)
    if not state:
        return {"error": "Pas de challenge d'enregistrement actif"}, 400

    # Restaure le state au format attendu par fido2
    from yubikey_authenticator import b64url_decode  # noqa: local import ok ici
    state["challenge"] = b64url_decode(state["challenge"])

    data = request.get_json(force=True)
    try:
        result = complete_registration(
            state=state,
            client_data_json_b64=data["clientDataJSON"],
            attestation_object_b64=data["attestationObject"],
        )
    except Exception as exc:
        return {"error": f"Échec de l'enregistrement : {exc}"}, 400

    # Persiste la credential en base de données
    conn = cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO yubikey (userId, credentialId, publicKey, signCount, createdAt)
            VALUES (%s, %s, %s, %s, NOW())
            """,
            (
                session["user_id"],
                result["credential_id"],   # bytes → BLOB
                result["public_key"],      # bytes → BLOB
                result["sign_count"],
            ),
        )
        conn.commit()
    except Exception as exc:
        if conn:
            conn.rollback()
        return {"error": f"Erreur base de données : {exc}"}, 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    session["yubikey_registered"] = True
    return {"status": "ok", "message": "YubiKey enregistrée avec succès"}


# ─────────────────────────────────────────────────────────────────────────────
#  AUTHENTIFICATION  —  begin
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/yubikey/login/begin", methods=["POST"])
def yubikey_login_begin():
    """
    Étape 1 : génère un challenge d'authentification pour les credentials
    connues de l'utilisateur connecté (session intermédiaire après login).
    """
    if "user_id" not in session:
        return {"error": "Non authentifié"}, 401

    credentials = _get_yubikey_credentials(session["user_id"])
    if not credentials:
        return {"error": "Aucune YubiKey enregistrée pour ce compte"}, 404

    options_json, state = begin_authentication(credentials)

    session["yubikey_auth_state"] = {
        "challenge": b64url_encode(state["challenge"]),
        "user_verification": state.get("user_verification", "preferred"),
    }

    return options_json


# ─────────────────────────────────────────────────────────────────────────────
#  AUTHENTIFICATION  —  complete
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/yubikey/login/complete", methods=["POST"])
def yubikey_login_complete():
    """
    Étape 2 : vérifie la signature et met à jour le signCount.
    """
    if "user_id" not in session:
        return {"error": "Non authentifié"}, 401

    state = session.pop("yubikey_auth_state", None)
    if not state:
        return {"error": "Pas de challenge d'authentification actif"}, 400

    from yubikey_authenticator import b64url_decode  # noqa
    state["challenge"] = b64url_decode(state["challenge"])

    credentials = _get_yubikey_credentials(session["user_id"])
    if not credentials:
        return {"error": "Aucune YubiKey enregistrée"}, 404

    data = request.get_json(force=True)
    try:
        result = complete_authentication(
            state=state,
            credentials=credentials,
            credential_id_b64=data["id"],
            client_data_json_b64=data["clientDataJSON"],
            authenticator_data_b64=data["authenticatorData"],
            signature_b64=data["signature"],
        )
    except Exception as exc:
        return {"error": f"Échec de l'authentification : {exc}"}, 401

    # Met à jour le signCount en base (protection contre le clonage)
    conn = cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE yubikey SET signCount = %s
            WHERE userId = %s AND credentialId = %s
            """,
            (
                result["new_sign_count"],
                session["user_id"],
                result["credential_id"],
            ),
        )
        conn.commit()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    session["yubikey_auth_verified"] = True
    return {"status": "ok", "redirect": "/yubikey/report"}


# ─────────────────────────────────────────────────────────────────────────────
#  RAPPORT  (page de confirmation, même pattern que les autres modules)
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/yubikey/report")
def yubikey_report():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if not session.get("yubikey_registered") and not session.get("yubikey_auth_verified"):
        flash("Veuillez d'abord enregistrer ou authentifier votre YubiKey.", "error")
        return redirect(url_for("yubikey_setup"))
    return render_template("yubikey_report.html")
# --- authentification par e-mail ------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True, port=5000)
