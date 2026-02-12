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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)

app = Flask(
    __name__,
    template_folder=os.path.join(PROJECT_DIR, "Frontend"),
    static_folder=os.path.join(PROJECT_DIR, "static"),
    static_url_path="/static",
)

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
        except pymysql.err.IntegrityError:
            if conn:
                conn.rollback()
            flash("Cet email est deja utilise.", "error")
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


if __name__ == "__main__":
    app.run(debug=True)
