from flask import Flask, request, render_template, flash, redirect, url_for, session, Response
import pymysql
import os
import bcrypt
import logging
from dotenv import load_dotenv

# --- IMPORT TOTP GÉNÉRIQUE (remplace les 4 imports redondants) ---
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

# --- IMPORTS WEBAUTHN (v2.7.1) ---
from webauthn_handler import get_registration_options, verify_registration
from webauthn.helpers import options_to_json

load_dotenv()

# Configuration des chemins pour le Frontend et le Static
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
        # Corrige les anciennes bases où id n'était pas AUTO_INCREMENT
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

# --- ROUTES D'AUTHENTIFICATION CLASSIQUE ---

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
                    "INSERT INTO users (nom, email, password) VALUES (%s, %s, %s)",
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

    flash(f"Methode {selected_method} non implementee pour le moment.", "error")
    return redirect(url_for("choose_auth"))

# --- BIOMÉTRIE WEBAUTHN (v2.7.1) ---

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

# --- FIN ET DÉCONNEXION ---

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


if __name__ == "__main__":
    app.run(debug=True, port=5000)
