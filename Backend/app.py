from flask import Flask, request, render_template, flash, redirect, url_for, session, Response
import pymysql
import os
import bcrypt
import json
import traceback
from datetime import datetime
from dotenv import load_dotenv

# Imports spécifiques WebAuthn (v2.7.1)
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

# Utilisation de la clé secrète du fichier .env
app.secret_key = os.getenv("SECRET_KEY", "436f9c8e7a1b5d3f2a8c6e4d9b7a1c3e5f8a2d4b6c0e9f7a3c1e5d8b2a4f6c0e")

# --- IMPORTS DES COLLÈGUES (TOTP) ---
try:
    from microsoft_authenticator import build_otpauth_uri, build_qr_code_url, generate_totp_secret, verify_totp
except ImportError:
    try:
        from Backend.microsoft_authenticator import build_otpauth_uri, build_qr_code_url, generate_totp_secret, verify_totp
    except ImportError:
        pass

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

        # Hachage du mot de passe
        hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

        try:
            conn = get_connection()
            with conn.cursor() as cursor:
                # Vérifier si l'email existe déjà
                cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
                if cursor.fetchone():
                    flash("Cet email est déjà utilisé.", "danger")
                    return render_template("register.html")
                
                # Insertion du nouvel utilisateur
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

# --- LOGIQUE DE SÉLECTION (UTILISÉE PAR LES COLLÈGUES) ---

@app.route("/select-auth-method", methods=["POST"])
def select_auth_method():
    method = request.form.get("auth_method")
    if method in ["microsoft", "google", "authy", "freeotp"]:
        # Redirection vers la route de setup correspondante
        return redirect(url_for(f"{method}_auth_setup"))
    return redirect(url_for("choose_auth"))

# --- TA PARTIE BIOMÉTRIE (RÉPARÉE POUR V2.7.1) ---

@app.route("/webauthn/register/options")
def webauthn_register_options():
    if "user_id" not in session:
        return {"error": "Session expirée"}, 401
    
    try:
        # 1. Préparation des données (ID en bytes obligatoire)
        user_id_bytes = str(session["user_id"]).encode('utf-8')
        user_name = session["user_name"]

        # 2. Appel au handler corrigé
        options = get_registration_options(user_id_bytes, user_name)
        
        # 3. Stockage du challenge en hexadécimal pour la vérification future
        session["webauthn_challenge"] = options.challenge.hex()
        
        # 4. Envoi de la réponse via Response + options_to_json (indispensable en v2.7.1)
        return Response(options_to_json(options), mimetype='application/json')
        
    except Exception as e:
        print("\n!!! ERREUR CRITIQUE DANS WEBAUTHN OPTIONS !!!")
        traceback.print_exc()
        return {"error": str(e)}, 500

@app.route("/webauthn/register/verify", methods=["POST"])
def webauthn_register_verify():
    challenge_hex = session.get("webauthn_challenge", "")
    if not challenge_hex:
        return {"status": "error", "message": "Challenge manquant"}, 400
    
    challenge = bytes.fromhex(challenge_hex)
    registration_data = request.get_json()
    
    try:
        # Vérification des données reçues du navigateur
        verification = verify_registration(registration_data, challenge)
        
        # Mise à jour de la base de données avec l'identifiant de l'empreinte
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
        
    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": str(e)}, 400

# --- FIN ET DÉCONNEXION ---

@app.route("/auth-success")
def auth_success():
    if "user_id" not in session:
        return redirect(url_for("login"))
    # On autorise l'accès si la biométrie OU le TOTP a réussi
    if not session.get("auth_verified") and not session.get("microsoft_auth_verified"):
        return redirect(url_for("choose_auth"))
    return render_template("auth_success.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    # Debug mode activé pour voir les erreurs dans le terminal
    app.run(debug=True, port=5000)