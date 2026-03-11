from flask import Flask, request, render_template, flash, redirect, url_for, session
import pymysql
import os
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
try:
    from cryptonox_authenticator import cryptonox_auth_bp, init_webauthn_table
except ImportError:
    from Backend.cryptonox_authenticator import cryptonox_auth_bp, init_webauthn_table

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)

app = Flask(
    __name__,
    template_folder=os.path.join(PROJECT_DIR, "Frontend"),
    static_folder=os.path.join(PROJECT_DIR, "static"),
    static_url_path="/static",
)

app.register_blueprint(cryptonox_auth_bp)

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
init_webauthn_table()


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
    if selected_method == "yubikey":
        return redirect(url_for("cryptonox_auth_bp.cryptonox_auth_setup"))

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


if __name__ == "__main__":
    app.run(debug=True)
