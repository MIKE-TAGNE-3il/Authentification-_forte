"""
Simple backend pour la 2FA par code envoyé par e-mail.

Ce module fournit :

- la génération d'un code numérique aléatoire (6 chiffres par défaut)
- l'envoi d'un message via SMTP (paramètres configurables par variables
denvironnement)
- une fonction de vérification du code avec durée de validité

Aucune dépendance externe n'est requise (seule la librairie standard).
"""

from __future__ import annotations

import hmac
import os
import random
import smtplib
import time
from email.message import EmailMessage


def generate_code(digits: int = 6) -> str:
    """Retourne un code numérique aléatoire de la longueur spécifiée.

    Le résultat est renvoyé sous forme de chaîne zéro‑padding (ex. "004321").
    """
    if digits <= 0:
        raise ValueError("digits doit être un entier positif")
    value = random.randint(0, 10**digits - 1)
    return str(value).zfill(digits)


def send_email_code(to_address: str, code: str, subject: str | None = None) -> None:
    host = os.getenv("MAIL_SMTP_HOST")
    if not host:
        # during development it can be useful to simply dump the code to the console
        # instead of raising an error. set MAIL_DEBUG=1 to enable this behaviour
        if os.getenv("MAIL_DEBUG"):
            print(f"[mail_authenticator] DEBUG - code for {to_address}: {code}")
            return
        raise RuntimeError("MAIL_SMTP_HOST n'est pas défini")

    port = int(os.getenv("MAIL_SMTP_PORT", "587"))
    user = os.getenv("MAIL_SMTP_USER")
    password = os.getenv("MAIL_SMTP_PASSWORD")
    sender = os.getenv("MAIL_FROM", "no-reply@example.com")

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to_address
    msg["Subject"] = subject or "Votre code d'accès"
    msg.set_content(
        f"Bonjour,\n\nVotre code de connexion est : {code}\n"
        "Il est valide pendant quelques minutes.\n\n"
        "Si vous n'avez pas demandé ce code, ignorez ce message."
    )

    try:
        with smtplib.SMTP(host, port) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            if user and password:
                smtp.login(user, password)
            smtp.send_message(msg)
    except Exception as e:
        # re-raise so caller can handle/log, but include some context
        raise RuntimeError(f"échec envoi SMTP: {e}") from e


def verify_code(expected: str, user_code: str, expiry: float, digits: int = 6) -> bool:
    """Vérifie que le code utilisateur correspond et n'est pas expiré.

    - `expected` : code enregistré (généralement en session)
    - `user_code` : code saisi par l'utilisateur
    - `expiry` : timestamp UNIX après lequel le code n'est plus valable
    - `digits` : longueur attendue du code

    ``False`` est retourné en cas de non correspondance ou expiration.
    """
    if not expected:
        return False
    if time.time() > expiry:
        return False
    cleaned = (user_code or "").strip()
    if not cleaned.isdigit() or len(cleaned) != digits:
        return False
    # utilisez compare_digest pour éviter les attaques par timing
    return hmac.compare_digest(expected, cleaned)


# ---------------------------------------------------------------------------
# Flask helpers / blueprint for routing logic
# ---------------------------------------------------------------------------
from flask import Blueprint, session, request, flash, redirect, url_for, render_template

email_auth_bp = Blueprint("email_auth_bp", __name__)


@email_auth_bp.route("/email-auth/setup", methods=["GET", "POST"])
def email_auth_setup():
    """Identique à la logique précédente déplacée depuis app.py."""
    print(f"DEBUG SESSION: {session.get('user_id')}")
    if "user_id" not in session:
        return redirect(url_for("login"))

    email = session.get("user_email")
    if not email:
        flash("Adresse e-mail introuvable.", "error")
        return redirect(url_for("login"))

    # toujours générer un code à chaque GET pour limiter la durée de vie
    if request.method == "GET" or "email_otp_code" not in session or time.time() > session.get("email_otp_expiry", 0):
        code = generate_code()
        session["email_otp_code"] = code
        session["email_otp_expiry"] = time.time() + 300  # 5 minutes
        try:
            send_email_code(to_address=email, code=code)
            flash("Un code a été envoyé par e-mail.", "info")
        except Exception:
            flash("Impossible d'envoyer l'e-mail. Réessayez plus tard.", "error")

    if request.method == "POST":
        otp_code = request.form.get("otp_code", "").strip()
        expected = session.get("email_otp_code")
        expiry = session.get("email_otp_expiry", 0)
        if verify_code(expected=expected, user_code=otp_code, expiry=expiry):
            session["email_auth_verified"] = True
            # code consommé
            session.pop("email_otp_code", None)
            session.pop("email_otp_expiry", None)
            flash("Authentification par e-mail configurée avec succès.", "success")
            return redirect(url_for("email_auth_bp.email_auth_report"))
        flash("Code invalide ou expiré.", "error")

    return render_template("email_auth_setup.html", email=email)


@email_auth_bp.route("/email-auth/report")
def email_auth_report():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if not session.get("email_auth_verified"):
        flash("Veuillez finaliser la vérification par e-mail.", "error")
        return redirect(url_for("email_auth_bp.email_auth_setup"))
    return render_template("email_auth_report.html")


if __name__ == "__main__":
    test_code = generate_code()
    print("Code généré :", test_code)

    print("HOST =", os.getenv("MAIL_SMTP_HOST"))
    print("USER =", os.getenv("MAIL_SMTP_USER"))

    try:
        send_email_code("tonmail@gmail.com", test_code)
        print("Email envoyé")
    except Exception as e:
        print("Erreur SMTP :", e)
