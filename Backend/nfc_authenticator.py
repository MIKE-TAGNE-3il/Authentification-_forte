"""
Authentification par carte NFC (lecture UID via pyscard).

Sécurité :
- L'UID de la carte est stocké en base de données, lié à l'utilisateur.
- Une date d'expiration est définie (NFC_CARD_VALIDITY_DAYS, défaut 30 jours).
- Lors de chaque authentification, l'UID lu est comparé à celui en base.
- Une carte inconnue ou expirée est rejetée.

Dépendance externe : pyscard  (pip install pyscard)
"""

from __future__ import annotations

import os
import pymysql
import pymysql.cursors
from datetime import datetime, timedelta

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

try:
    from smartcard.System import readers as get_readers
    PYSCARD_AVAILABLE = True
except ImportError:
    get_readers = None
    PYSCARD_AVAILABLE = False

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# Durée de validité d'une carte enregistrée (modifiable via .env)
NFC_CARD_VALIDITY_DAYS = int(os.getenv("NFC_CARD_VALIDITY_DAYS", "30"))

# ---------------------------------------------------------------------------
# Blueprint Flask
# ---------------------------------------------------------------------------
nfc_auth_bp = Blueprint("nfc_auth_bp", __name__)


# ---------------------------------------------------------------------------
# Connexion base de données (propre au module, identique à app.py)
# ---------------------------------------------------------------------------
def _get_connection():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "authentification"),
        port=int(os.getenv("DB_PORT", "3306")),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


# ---------------------------------------------------------------------------
# Initialisation de la table nfc_cards (appelée depuis app.py au démarrage)
# ---------------------------------------------------------------------------
def init_nfc_table():
    """Crée la table nfc_cards si elle n'existe pas."""
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS nfc_cards (
                    id           INT AUTO_INCREMENT PRIMARY KEY,
                    user_id      INT NOT NULL,
                    uid          VARCHAR(64) NOT NULL,
                    registered_at DATETIME NOT NULL,
                    expires_at   DATETIME NOT NULL,
                    INDEX idx_user_id (user_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Helpers BDD
# ---------------------------------------------------------------------------
def _get_active_card(user_id: int) -> dict | None:
    """
    Retourne la ligne nfc_cards active (non expirée) pour cet utilisateur,
    ou None s'il n'en a pas.
    """
    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT uid, registered_at, expires_at
                FROM nfc_cards
                WHERE user_id = %s AND expires_at > NOW()
                ORDER BY registered_at DESC
                LIMIT 1
                """,
                (user_id,),
            )
            return cursor.fetchone()
    finally:
        conn.close()


def _register_card(user_id: int, uid: str) -> datetime:
    """
    Enregistre (ou renouvelle) l'association carte ↔ utilisateur en base.
    Retourne la date d'expiration calculée.
    """
    now = datetime.now()
    expires_at = now + timedelta(days=NFC_CARD_VALIDITY_DAYS)

    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            # Supprime les anciennes entrées de cet utilisateur avant d'insérer
            cursor.execute("DELETE FROM nfc_cards WHERE user_id = %s", (user_id,))
            cursor.execute(
                """
                INSERT INTO nfc_cards (user_id, uid, registered_at, expires_at)
                VALUES (%s, %s, %s, %s)
                """,
                (user_id, uid, now, expires_at),
            )
    finally:
        conn.close()

    return expires_at


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@nfc_auth_bp.route("/nfc-auth/setup")
def nfc_auth_setup():
    """
    Page de configuration / vérification NFC.
    Passe au template l'état actuel de la carte de l'utilisateur.
    """
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Réinitialise l'état NFC de la session à chaque visite de cette page
    session.pop("nfc_uid_verified", None)
    session.pop("nfc_uid", None)

    active_card = _get_active_card(session["user_id"])
    return render_template(
        "nfc_auth_setup.html",
        active_card=active_card,
        validity_days=NFC_CARD_VALIDITY_DAYS,
    )


@nfc_auth_bp.route("/read-nfc")
def read_nfc():
    """
    Lit l'UID de la carte NFC posée sur le lecteur, puis :
    - Si l'utilisateur n'a pas de carte active → enregistre la carte en BDD.
    - Si l'utilisateur a déjà une carte active → compare l'UID.
      • Même UID  → authentification validée.
      • UID différent → rejetée (carte non associée au compte).
    """
    if "user_id" not in session:
        return jsonify({"error": "Non authentifié"}), 401

    if not PYSCARD_AVAILABLE:
        return jsonify({
            "error": "pyscard non installé. Lancez : pip install pyscard"
        }), 500

    # --- 1. Lecture physique de la carte ---
    try:
        readers_list = get_readers()
        if not readers_list:
            return jsonify({
                "error": "Aucun lecteur NFC détecté. Vérifiez la connexion USB."
            }), 500

        connection = readers_list[0].createConnection()
        connection.connect()

        GET_UID = [0xFF, 0xCA, 0x00, 0x00, 0x00]
        data, sw1, sw2 = connection.transmit(GET_UID)

        if sw1 != 0x90:
            return jsonify({
                "error": f"Lecture échouée (SW={sw1:02X}{sw2:02X}). Repositionnez la carte."
            }), 500

        uid_scanned = "".join(f"{b:02X}" for b in data)

    except Exception as exc:
        return jsonify({"error": f"Erreur lecteur : {exc}"}), 500

    # --- 2. Logique BDD ---
    user_id = session["user_id"]
    active_card = _get_active_card(user_id)

    if active_card is None:
        # Aucune carte enregistrée (ou expirée) → on enregistre cette carte
        expires_at = _register_card(user_id, uid_scanned)

        session["nfc_uid_verified"] = True
        session["nfc_uid"] = uid_scanned
        session["nfc_auth_verified"] = True

        return jsonify({
            "status": "registered",
            "uid": uid_scanned,
            "expires_at": expires_at.strftime("%d/%m/%Y à %H:%M"),
            "message": (
                f"Carte enregistrée avec succès. "
                f"Elle sera valide jusqu'au {expires_at.strftime('%d/%m/%Y à %H:%M')}."
            ),
        })

    # Une carte active existe → on vérifie que c'est la bonne
    if uid_scanned != active_card["uid"]:
        return jsonify({
            "status": "rejected",
            "error": (
                "Cette carte n'est pas associée à votre compte. "
                "Utilisez la carte enregistrée ou contactez un administrateur."
            ),
        }), 403

    # Bonne carte, non expirée → authentification validée
    session["nfc_uid_verified"] = True
    session["nfc_uid"] = uid_scanned
    session["nfc_auth_verified"] = True

    expires_at = active_card["expires_at"]
    return jsonify({
        "status": "verified",
        "uid": uid_scanned,
        "expires_at": expires_at.strftime("%d/%m/%Y à %H:%M"),
        "message": (
            f"Carte reconnue. Authentification validée. "
            f"Validité : jusqu'au {expires_at.strftime('%d/%m/%Y à %H:%M')}."
        ),
    })


@nfc_auth_bp.route("/nfc-auth/revoke", methods=["POST"])
def nfc_auth_revoke():
    """
    Révoque (supprime) la carte NFC associée au compte.
    Utile en cas de perte ou de vol de la carte.
    """
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = _get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "DELETE FROM nfc_cards WHERE user_id = %s", (session["user_id"],)
            )
    finally:
        conn.close()

    session.pop("nfc_uid_verified", None)
    session.pop("nfc_uid", None)
    session.pop("nfc_auth_verified", None)

    flash("Votre carte NFC a été révoquée. Vous pouvez en enregistrer une nouvelle.", "success")
    return redirect(url_for("nfc_auth_bp.nfc_auth_setup"))


@nfc_auth_bp.route("/nfc-auth/report")
def nfc_auth_report():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if not session.get("nfc_uid_verified"):
        flash("Veuillez lire votre carte NFC.", "error")
        return redirect(url_for("nfc_auth_bp.nfc_auth_setup"))

    # Récupère les infos de la carte depuis la BDD pour les afficher
    active_card = _get_active_card(session["user_id"])

    return render_template(
        "nfc_auth_report.html",
        uid=session.get("nfc_uid"),
        now=datetime.now().strftime("%d/%m/%Y à %H:%M"),
        expires_at=active_card["expires_at"].strftime("%d/%m/%Y à %H:%M") if active_card else "—",
        validity_days=NFC_CARD_VALIDITY_DAYS,
    )
