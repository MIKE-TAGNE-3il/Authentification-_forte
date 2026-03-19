"""
Authentification par carte NFC (lecture UID via pyscard).

Ce module fournit :
- la lecture de l'UID d'une carte NFC via un lecteur PC/SC
- un Blueprint Flask avec les routes correspondantes

Dependance externe : pyscard  (pip install pyscard)
"""

from __future__ import annotations

import os
from datetime import datetime

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
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
# Blueprint Flask
# ---------------------------------------------------------------------------
nfc_auth_bp = Blueprint("nfc_auth_bp", __name__)


@nfc_auth_bp.route("/nfc-auth/setup")
def nfc_auth_setup():
    if "user_id" not in session:
        return redirect(url_for("login"))
    session.pop("nfc_uid_verified", None)
    session.pop("nfc_uid", None)
    return render_template("nfc_auth_setup.html")


@nfc_auth_bp.route("/read-nfc")
def read_nfc():
    if "user_id" not in session:
        return jsonify({"error": "Non authentifie"}), 401

    if not PYSCARD_AVAILABLE:
        return jsonify({"error": "pyscard non installe. Lancez : pip install pyscard"}), 500

    try:
        r = get_readers()
        if not r:
            return jsonify({"error": "Aucun lecteur NFC detecte. Verifiez la connexion USB."}), 500

        reader = r[0]
        connection = reader.createConnection()
        connection.connect()

        GET_UID = [0xFF, 0xCA, 0x00, 0x00, 0x00]
        data, sw1, sw2 = connection.transmit(GET_UID)

        if sw1 == 0x90:
            uid = "".join([f"{b:02X}" for b in data])
            session["nfc_uid_verified"] = True
            session["nfc_uid"] = uid
            return jsonify({"uid": uid})

        return jsonify({"error": f"Lecture echouee (SW={sw1:02X}{sw2:02X}). Repositionnez la carte."}), 500

    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@nfc_auth_bp.route("/nfc-auth/report")
def nfc_auth_report():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if not session.get("nfc_uid_verified"):
        flash("Veuillez lire votre carte NFC.", "error")
        return redirect(url_for("nfc_auth_bp.nfc_auth_setup"))
    return render_template(
        "nfc_auth_report.html",
        uid=session.get("nfc_uid"),
        now=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
