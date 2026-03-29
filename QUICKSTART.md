# AuthForte — Guide de démarrage rapide

> Plateforme d'authentification forte MFA — 3iL Ingénieurs 2025-2026
> Superviseur : B. Chervy

---

## 5 commandes pour démarrer

### Linux / macOS

```bash
# 1. Cloner et se placer dans le projet
git clone <url-du-repo> && cd Authentification-_forte

# 2. Installer les dépendances système (pcscd, Docker, udev)
bash scripts/install.sh

# 3. Configurer l'environnement
cp .env.example .env
# Editez .env avec vos valeurs (mots de passe, clés)

# 4. Vérifier les prérequis
bash scripts/check.sh

# 5. Démarrer la plateforme
make start-linux
```

### Windows (PowerShell en tant qu'Administrateur)

```powershell
# 1. Cloner et se placer dans le projet
git clone <url-du-repo>; cd Authentification-_forte

# 2. Installer Docker Desktop + usbipd-win
powershell -ExecutionPolicy Bypass -File scripts\install.ps1

# 3. Configurer l'environnement
Copy-Item .env.example .env
# Editez .env avec vos valeurs

# 4. Vérifier les prérequis
powershell -ExecutionPolicy Bypass -File scripts\check.ps1

# 5. Démarrer la plateforme
make start-windows
# OU : powershell -ExecutionPolicy Bypass -File scripts\start.ps1
```

---

## Accès après démarrage

| Service | URL |
|---------|-----|
| Application | http://localhost |
| Flask (direct) | http://localhost:5000 |
| MailHog (e-mails) | http://localhost:8025 |
| MySQL | localhost:3306 |

---

## Architecture Docker

```
┌─────────────────────────────────────────────────────────────────┐
│                        HOST (Windows/Linux)                      │
│                                                                  │
│  ┌─── authforte-network ──────────────────────────────────────┐ │
│  │                                                             │ │
│  │  ┌──────────┐    ┌──────────────┐    ┌──────────────────┐ │ │
│  │  │  nginx   │───▶│   backend    │───▶│       db         │ │ │
│  │  │ :80      │    │  Flask :5000 │    │   MySQL :3306    │ │ │
│  │  └──────────┘    └──────────────┘    └──────────────────┘ │ │
│  │                         │                                  │ │
│  │                  ┌──────────────┐                          │ │
│  │                  │   mailhog    │                          │ │
│  │                  │ SMTP :1025   │                          │ │
│  │                  │ UI   :8025   │                          │ │
│  │                  └──────────────┘                          │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  Périphériques USB  ──(passthrough)──▶ backend (privileged)     │
│  [NFC, Cryptonox, YubiKey, Fingerprint]                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Compatibilité Windows / Linux

| Fonctionnalité | Windows | Linux |
|----------------|---------|-------|
| Démarrage Docker | Docker Desktop | Docker Engine |
| USB passthrough | usbipd-win + WSL2 | udev rules + `/dev/bus/usb` |
| PC/SC (NFC) | pcscd dans le conteneur (privileged) | pcscd sur l'hôte + socket partagée |
| Mode privilégié | Requis (`privileged: true`) | Non requis (montage socket) |
| Règles udev | N/A | `/etc/udev/rules.d/99-authforte.rules` |
| Script démarrage | `scripts/start.ps1` | `scripts/start.sh` |
| Makefile | `make start-windows` | `make start-linux` |

---

## Gestion des périphériques USB (NFC, Cryptonox, YubiKey)

### Windows

```powershell
# Lister les périphériques USB
usbipd list

# Partager un périphérique avec Docker (remplacez 2-3 par votre BUSID)
usbipd bind --busid 2-3
usbipd attach --wsl --busid 2-3

# Script automatique inclus :
powershell -ExecutionPolicy Bypass -File scripts\usb-passthrough.ps1
```

### Linux

Les règles udev sont installées automatiquement par `scripts/install.sh`.
Le démon pcscd doit tourner sur l'hôte :

```bash
sudo systemctl start pcscd
sudo systemctl enable pcscd
```

---

## Référence Makefile

```
make help            Afficher cette aide
make start-linux     Démarrer sur Linux
make start-windows   Démarrer sur Windows
make stop            Arrêter tous les conteneurs
make restart         Redémarrer
make build           Reconstruire l'image backend
make check-linux     Vérifier les prérequis Linux
make check-windows   Vérifier les prérequis Windows
make install-linux   Installer dépendances Linux
make install-windows Installer dépendances Windows
make logs            Logs en temps réel (tous les services)
make logs-backend    Logs Flask uniquement
make shell           Shell dans le conteneur backend
make db-shell        MySQL CLI dans le conteneur db
make usb-windows     Passthrough USB (Windows)
make clean           Arrêter + supprimer conteneurs
make reset           Reset complet avec suppression des volumes
```

---

## Variables d'environnement (.env)

Copiez `.env.example` en `.env` et renseignez :

| Variable | Description | Exemple |
|----------|-------------|---------|
| `SECRET_KEY` | Clé secrète Flask (64 chars aléatoires) | `openssl rand -hex 32` |
| `DB_PASSWORD` | Mot de passe MySQL utilisateur `authforte` | `votre_mdp` |
| `MYSQL_ROOT_PASSWORD` | Mot de passe root MySQL | `root_secure` |
| `MAIL_SMTP_HOST` | Hôte SMTP (MailHog en dev) | `mailhog` |
| `MAIL_SMTP_PORT` | Port SMTP | `1025` (MailHog) / `587` (Gmail) |
| `NFC_CARD_VALIDITY_DAYS` | Durée de validité des cartes NFC | `30` |

---

## FAQ

**Q : L'application ne démarre pas — "waiting for db"**
R : MySQL prend 20-30s à démarrer. Le conteneur backend attend automatiquement via `healthcheck`. Patientez ou vérifiez : `docker compose logs db`

**Q : pyscard / NFC ne détecte pas le lecteur**
→ Linux : Vérifiez que `pcscd` tourne (`systemctl status pcscd`) et que la socket est montée.
→ Windows : Vérifiez que le périphérique est partagé via `usbipd list` et relancez `usb-passthrough.ps1`.

**Q : Les e-mails ne sont pas reçus**
R : En développement, consultez MailHog sur http://localhost:8025. Les e-mails y sont capturés sans être envoyés réellement.

**Q : WebAuthn (empreinte) ne fonctionne pas en production**
R : WebAuthn nécessite HTTPS hors `localhost`. Configurez un certificat TLS ou un tunnel (ngrok, Cloudflare Tunnel).

**Q : Comment générer une SECRET_KEY sécurisée ?**
```bash
# Linux/macOS
openssl rand -hex 32
# PowerShell
[System.Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
```

---

## Démo — Checklist complète

- [ ] Page de connexion accessible sur http://localhost
- [ ] Inscription d'un nouveau compte
- [ ] Connexion email + mot de passe
- [ ] Choix de la méthode 2FA
- [ ] TOTP Microsoft Authenticator — scan QR + code valide
- [ ] TOTP Google Authenticator — scan QR + code valide
- [ ] TOTP Authy — scan QR + code valide
- [ ] TOTP FreeOTP — scan QR + code valide
- [ ] E-mail OTP — réception sur MailHog (http://localhost:8025)
- [ ] NFC — enregistrement carte + vérification + révocation
- [ ] Cryptonox — enregistrement FIDO2 + authentification
- [ ] WebAuthn — enregistrement biométrique + authentification
- [ ] Page auth_success accessible après 2FA validé
- [ ] Déconnexion fonctionnelle

---

*AuthForte — Projet I2 2025-2026 — 3iL Ingénieurs*
