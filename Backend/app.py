from flask import Flask, request, render_template, flash, redirect, url_for, session, json
from dotenv import load_dotenv
load_dotenv()
import pymysql
import os
import time
import bcrypt
try:
    from microsoft_authenticator import (
        build_otpauth_uri,
        build_qr_code_url,
        generate_totp_secret,
        verify_totp,
    )
except ImportError:
    from Backend.microsoft_authenticator import (
        build_otpauth_uri,
        build_qr_code_url,
        generate_totp_secret,
        verify_totp,
    )
try:
    from google_authenticator import (
        build_otpauth_uri as build_google_otpauth_uri,
        build_qr_code_url as build_google_qr_code_url,
        generate_totp_secret as generate_google_totp_secret,
        verify_totp as verify_google_totp,
    )
except ImportError:
    from Backend.google_authenticator import (
        build_otpauth_uri as build_google_otpauth_uri,
        build_qr_code_url as build_google_qr_code_url,
        generate_totp_secret as generate_google_totp_secret,
        verify_totp as verify_google_totp,
    )
try:
    from authy_authenticator import (
        build_otpauth_uri as build_authy_otpauth_uri,
        build_qr_code_url as build_authy_qr_code_url,
        generate_totp_secret as generate_authy_totp_secret,
        verify_totp as verify_authy_totp,
    )
except ImportError:
    from Backend.authy_authenticator import (
        build_otpauth_uri as build_authy_otpauth_uri,
        build_qr_code_url as build_authy_qr_code_url,
        generate_totp_secret as generate_authy_totp_secret,
        verify_totp as verify_authy_totp,
    )
try:
    from freeotp_authenticator import (
        build_otpauth_uri as build_freeotp_otpauth_uri,
        build_qr_code_url as build_freeotp_qr_code_url,
        generate_totp_secret as generate_freeotp_totp_secret,
        verify_totp as verify_freeotp_totp,
    )
except ImportError:
    from Backend.freeotp_authenticator import (
        build_otpauth_uri as build_freeotp_otpauth_uri,
        build_qr_code_url as build_freeotp_qr_code_url,
        generate_totp_secret as generate_freeotp_totp_secret,
        verify_totp as verify_freeotp_totp,
    )

# email authentication blueprint (moved out of app)
try:
    from mail_authenticator import email_auth_bp
except ImportError:
    from Backend.mail_authenticator import email_auth_bp


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

# register blueprints imported earlier
app.register_blueprint(email_auth_bp)

app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-this-in-production")


def get_connection():
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
        # Corrige les anciennes bases ou id n'etait pas AUTO_INCREMENT.
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


@app.route("/")
def home():
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        nom = request.form.get("nom", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm", "")

        if not nom or not email or not password or not confirm_password:
            flash("Tous les champs sont requis.", "error")
            return render_template("register.html")

        if password != confirm_password:
            flash("Les mots de passe ne correspondent pas.", "error")
            return render_template("register.html")

        hashed_password = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO users (nom, email, password, createdAt)
                VALUES (%s, %s, %s, NOW())
                """,
                (nom, email, hashed_password),
            )
            conn.commit()
            flash("Inscription reussie. Vous pouvez vous connecter.", "success")
            return redirect(url_for("login"))
        except pymysql.err.IntegrityError as exc:
            if conn:
                conn.rollback()
            mysql_error_code = exc.args[0] if exc.args else None
            if mysql_error_code == 1062:
                flash("Cet email est deja utilise.", "error")
            else:
                flash("Erreur d'integrite de la base de donnees.", "error")
            return render_template("register.html")
        except Exception:
            if conn:
                conn.rollback()
            flash("Erreur serveur pendant l'inscription.", "error")
            return render_template("register.html")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Email et mot de passe requis.", "error")
            return render_template("login.html")

        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, nom, email, password FROM users WHERE email = %s",
                (email,),
            )
            user = cursor.fetchone()
        except Exception:
            flash("Erreur serveur pendant la connexion.", "error")
            return render_template("login.html")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

        if not user:
            flash("Identifiants invalides.", "error")
            return render_template("login.html")

        if not bcrypt.checkpw(password.encode("utf-8"), user["password"].encode("utf-8")):
            flash("Identifiants invalides.", "error")
            return render_template("login.html")

        session["user_id"] = user["id"]
        session["user_name"] = user["nom"]
        session["user_email"] = user.get("email")  # nécessaire pour la 2FA par e-mail
        return redirect(url_for("choose_auth"))

    return render_template("login.html")


@app.route("/choose-auth")
def choose_auth():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("choosAuth.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/select-auth-method", methods=["POST"])
def select_auth_method():
    if "user_id" not in session:
        return redirect(url_for("login"))

    selected_method = request.form.get("auth_method", "").strip()
    if not selected_method:
        flash("Veuillez choisir une methode d'authentification.", "error")
        return redirect(url_for("choose_auth"))

    session["selected_auth_method"] = selected_method

    if selected_method == "microsoft":
        return redirect(url_for("microsoft_auth_setup"))
    if selected_method == "google":
        return redirect(url_for("google_auth_setup"))
    if selected_method == "authy":
        return redirect(url_for("authy_auth_setup"))
    if selected_method == "freeotp":
        return redirect(url_for("freeotp_auth_setup"))
    if selected_method == "email":
        return redirect(url_for("email_auth_bp.email_auth_setup"))
    if selected_method == "yubikey":
        return redirect(url_for("yubikey_setup"))

    flash(f"Methode {selected_method} non implementee pour le moment.", "error")
    return redirect(url_for("choose_auth"))


@app.route("/microsoft-auth/setup", methods=["GET", "POST"])
def microsoft_auth_setup():
    if "user_id" not in session:
        return redirect(url_for("login"))

    secret = session.get("microsoft_totp_secret")
    if not secret:
        secret = generate_totp_secret()
        session["microsoft_totp_secret"] = secret
        session["microsoft_auth_verified"] = False

    account_name = session.get("user_name", "utilisateur")
    issuer = "AuthentificationForte"
    otpauth_uri = build_otpauth_uri(secret=secret, account_name=account_name, issuer=issuer)
    qr_url = build_qr_code_url(otpauth_uri)

    if request.method == "POST":
        otp_code = request.form.get("otp_code", "").strip()
        if verify_totp(secret=secret, user_code=otp_code):
            session["microsoft_auth_verified"] = True
            flash("Microsoft Authenticator configure avec succes.", "success")
            return redirect(url_for("microsoft_auth_report"))
        flash("Code invalide. Verifiez l'application puis reessayez.", "error")

    return render_template(
        "microsoft_auth_setup.html",
        qr_url=qr_url,
        secret=secret,
        issuer=issuer,
        account_name=account_name,
    )


@app.route("/microsoft-auth/report")
def microsoft_auth_report():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if not session.get("microsoft_auth_verified"):
        flash("Veuillez finaliser la verification Microsoft Authenticator.", "error")
        return redirect(url_for("microsoft_auth_setup"))
    return render_template("microsoft_auth_report.html")


@app.route("/google-auth/setup", methods=["GET", "POST"])
def google_auth_setup():
    if "user_id" not in session:
        return redirect(url_for("login"))

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
    app.run(debug=True)
