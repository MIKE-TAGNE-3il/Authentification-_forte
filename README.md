# AuthForte — Plateforme d'authentification forte MFA

> Projet I2 2025-2026 — 3iL Ingénieurs | Superviseur : B. Chervy

Plateforme web Flask implémentant **8 méthodes d'authentification forte (MFA)** :
TOTP ×4 (Google, Microsoft, Authy, FreeOTP), OTP par e-mail, NFC, FIDO2/Cryptonox et WebAuthn (empreinte digitale).

---

## Table des matières

1. [Prérequis](#prérequis)
2. [Installation rapide (Docker)](#installation-rapide-docker)
3. [Installation manuelle (sans Docker)](#installation-manuelle-sans-docker)
4. [Configuration `.env`](#configuration-env)
5. [Lancer la plateforme](#lancer-la-plateforme)
6. [Accès aux services](#accès-aux-services)
7. [Méthodes d'authentification](#méthodes-dauthentification)
8. [Gestion des périphériques USB (NFC / Cryptonox / YubiKey)](#gestion-des-périphériques-usb)
9. [Architecture Docker](#architecture-docker)
10. [Commandes utiles (Makefile)](#commandes-utiles-makefile)
11. [Résolution de problèmes](#résolution-de-problèmes)

---

## Prérequis

### Méthode Docker (recommandée)

| Outil | Version minimale | Lien |
|-------|-----------------|------|
| Docker | 24+ | https://docs.docker.com/get-docker/ |
| Docker Compose | v2 (intégré à Docker Desktop) | — |
| Git | 2+ | https://git-scm.com/ |

> **Windows uniquement** : installez aussi [usbipd-win](https://github.com/dorssel/usbipd-win/releases) si vous utilisez NFC/Cryptonox/YubiKey.

### Méthode manuelle (sans Docker)

| Outil | Version minimale |
|-------|-----------------|
| Python | 3.11+ |
| MySQL | 8.0+ |
| Microsoft C++ Build Tools | 14.0+ (Windows uniquement, requis par `pyscard`) |

---

## Installation rapide (Docker)

### Linux / macOS

```bash
# 1. Cloner le dépôt
git clone https://github.com/MIKE-TAGNE-3il/Authentification-_forte.git
cd Authentification-_forte

# 2. Installer les dépendances système (pcscd, udev, Docker)
bash scripts/install.sh

# 3. Configurer l'environnement
cp .env.example .env
# Editez .env avec vos valeurs (voir section Configuration)

# 4. Vérifier les prérequis
bash scripts/check.sh

# 5. Démarrer la plateforme
make start-linux
```

### Windows (PowerShell en tant qu'Administrateur)

```powershell
# 1. Cloner le dépôt
git clone https://github.com/MIKE-TAGNE-3il/Authentification-_forte.git
cd Authentification-_forte

# 2. Installer les dépendances (Docker Desktop + usbipd-win)
powershell -ExecutionPolicy Bypass -File scripts\install.ps1

# 3. Configurer l'environnement
Copy-Item .env.example .env
# Editez .env avec vos valeurs

# 4. Vérifier les prérequis
powershell -ExecutionPolicy Bypass -File scripts\check.ps1

# 5. Démarrer la plateforme
make start-windows
# OU sans make :
powershell -ExecutionPolicy Bypass -File scripts\start.ps1
```

> **Problème PowerShell "scripts désactivés"** : exécutez `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` dans un PowerShell administrateur, ou utilisez `cmd.exe` avec les scripts `.bat`.

---

## Installation manuelle (sans Docker)

Cette méthode permet de lancer uniquement le backend Flask localement, sans conteneur.

### 1. Créer et activer un environnement virtuel

```bash
# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate

# Windows (cmd.exe)
python -m venv .venv
.venv\Scripts\activate.bat

# Windows (PowerShell — si l'activation échoue, voir note ci-dessus)
.venv\Scripts\Activate.ps1
```

### 2. Installer les dépendances Python

> **Windows** : `pyscard` (NFC) nécessite [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/). Si vous n'utilisez pas NFC, commentez la ligne `pyscard` dans `requirements.txt`.

```bash
pip install -r requirements.txt
```

### 3. Configurer la base de données

Créez une base MySQL et un utilisateur :

```sql
CREATE DATABASE authentification CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'authforte'@'localhost' IDENTIFIED BY 'votre_mot_de_passe';
GRANT ALL PRIVILEGES ON authentification.* TO 'authforte'@'localhost';
FLUSH PRIVILEGES;
```

### 4. Configurer l'environnement

```bash
cp .env.example .env
# Editez .env : DB_HOST=localhost, DB_PASSWORD=votre_mot_de_passe, etc.
```

### 5. Lancer le backend

```bash
cd Backend
python app.py
```

L'application est accessible sur http://localhost:5000.

---

## Configuration `.env`

Copiez `.env.example` en `.env` et renseignez les variables suivantes :

### Base obligatoire

| Variable | Description | Exemple |
|----------|-------------|---------|
| `SECRET_KEY` | Clé secrète Flask — **générez-en une unique** | voir commande ci-dessous |
| `DB_HOST` | Hôte MySQL (`db` en Docker, `localhost` en manuel) | `db` |
| `DB_USER` | Utilisateur MySQL | `authforte` |
| `DB_PASSWORD` | Mot de passe MySQL | `votre_mdp` |
| `DB_NAME` | Nom de la base | `authentification` |
| `MYSQL_ROOT_PASSWORD` | Mot de passe root MySQL (Docker uniquement) | `root_secure` |

Générer une SECRET_KEY sécurisée :
```bash
# Linux / macOS
openssl rand -hex 32

# PowerShell
[System.Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
```

### E-mail OTP (2FA par mail)

| Variable | Description | Dev (MailHog) | Prod (Gmail) |
|----------|-------------|---------------|--------------|
| `MAIL_SMTP_HOST` | Hôte SMTP | `mailhog` | `smtp.gmail.com` |
| `MAIL_SMTP_PORT` | Port SMTP | `1025` | `587` |
| `MAIL_SMTP_USER` | Compte expéditeur | *(vide)* | `votre@gmail.com` |
| `MAIL_SMTP_PASSWORD` | Mot de passe / App password | *(vide)* | mot de passe d'application |
| `MAIL_FROM` | Adresse expéditeur | `no-reply@authforte.local` | `no-reply@votre-domaine.com` |
| `MAIL_DEBUG` | `1` = affiche le code dans les logs | `0` | `0` |

> En développement, les e-mails sont capturés par **MailHog** — consultez-les sur http://localhost:8025, aucune configuration SMTP réelle n'est nécessaire.

### WebAuthn (empreinte digitale)

| Variable | Dev | Prod |
|----------|-----|------|
| `WEBAUTHN_RP_ID` | `localhost` | `votre-domaine.com` |
| `WEBAUTHN_ORIGIN` | `http://localhost:5000` | `https://votre-domaine.com` |

> WebAuthn requiert **HTTPS** en dehors de `localhost`. Utilisez un certificat TLS ou un tunnel (ngrok, Cloudflare Tunnel) en test.

### NFC

| Variable | Description | Défaut |
|----------|-------------|--------|
| `NFC_CARD_VALIDITY_DAYS` | Durée de validité d'une carte enregistrée (jours) | `30` |

---

## Lancer la plateforme

### Avec Make (recommandé)

```bash
make start-linux    # Linux
make start-windows  # Windows
```

### Avec Docker Compose directement

```bash
docker compose up -d
docker compose logs -f   # Suivre les logs
```

### Arrêter

```bash
make stop
# ou
docker compose down
```

---

## Accès aux services

| Service | URL | Description |
|---------|-----|-------------|
| Application principale | http://localhost | Via nginx (port 80) |
| Flask (direct) | http://localhost:5000 | Sans proxy |
| MailHog (e-mails dev) | http://localhost:8025 | Capture tous les e-mails |
| MySQL | `localhost:3306` | Accès via `make db-shell` |

---

## Méthodes d'authentification

| # | Méthode | Matériel requis | Configuration |
|---|---------|-----------------|---------------|
| 1 | **TOTP — Google Authenticator** | Smartphone | Scan QR au premier accès |
| 2 | **TOTP — Microsoft Authenticator** | Smartphone | Scan QR au premier accès |
| 3 | **TOTP — Authy** | Smartphone | Scan QR au premier accès |
| 4 | **TOTP — FreeOTP** | Smartphone | Scan QR au premier accès |
| 5 | **OTP par e-mail** | Aucun | Configuration SMTP dans `.env` |
| 6 | **NFC** | Lecteur NFC + carte | pcscd + USB passthrough |
| 7 | **FIDO2 / Cryptonox** | Carte Cryptonox | USB passthrough |
| 8 | **WebAuthn (empreinte)** | Capteur biométrique intégré | HTTPS requis hors localhost |

### Parcours utilisateur

1. Inscription avec e-mail + mot de passe
2. Choix de la méthode 2FA lors du premier accès
3. À chaque connexion : e-mail/mot de passe → validation 2FA

---

## Gestion des périphériques USB

Nécessaire pour **NFC**, **Cryptonox**, **YubiKey** et **lecteur d'empreinte externe**.

### Windows — usbipd-win

```powershell
# Lister les périphériques USB
usbipd list

# Partager un périphérique avec Docker/WSL2
usbipd bind --busid 2-3        # remplacez 2-3 par votre BUSID
usbipd attach --wsl --busid 2-3

# Script automatique inclus
powershell -ExecutionPolicy Bypass -File scripts\usb-passthrough.ps1
```

### Linux — pcscd + udev

```bash
# Démarrer le démon PC/SC (requis pour NFC)
sudo systemctl start pcscd
sudo systemctl enable pcscd  # démarrage automatique

# Les règles udev sont installées par scripts/install.sh
```

---

## Architecture Docker

```
┌─────────────────────────────────────────────────────────────────┐
│                       HOST (Windows/Linux)                       │
│                                                                  │
│  ┌─── authforte-network ──────────────────────────────────────┐ │
│  │                                                             │ │
│  │  ┌──────────┐    ┌──────────────┐    ┌──────────────────┐ │ │
│  │  │  nginx   │───▶│   backend    │───▶│       db         │ │ │
│  │  │  :80     │    │  Flask :5000 │    │   MySQL :3306    │ │ │
│  │  └──────────┘    └──────────────┘    └──────────────────┘ │ │
│  │                         │                                  │ │
│  │                  ┌──────────────┐                          │ │
│  │                  │   mailhog    │                          │ │
│  │                  │ SMTP :1025   │                          │ │
│  │                  │ UI   :8025   │                          │ │
│  │                  └──────────────┘                          │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  Périphériques USB ───(passthrough)──▶ backend (privileged)     │
│  [NFC, Cryptonox, YubiKey, Empreinte]                           │
└─────────────────────────────────────────────────────────────────┘
```

| Fonctionnalité | Windows | Linux |
|----------------|---------|-------|
| Docker | Docker Desktop | Docker Engine |
| USB passthrough | usbipd-win + WSL2 | udev rules + `/dev/bus/usb` |
| PC/SC (NFC) | pcscd dans le conteneur | pcscd sur l'hôte + socket partagée |
| Mode conteneur | `privileged: true` | montage socket |

---

## Commandes utiles (Makefile)

```
make help              Afficher l'aide
make start-linux       Démarrer sur Linux
make start-windows     Démarrer sur Windows
make stop              Arrêter tous les conteneurs
make restart           Redémarrer
make build             Reconstruire l'image backend
make logs              Logs en temps réel (tous les services)
make logs-backend      Logs Flask uniquement
make shell             Shell dans le conteneur backend
make db-shell          MySQL CLI dans le conteneur db
make check-linux       Vérifier les prérequis Linux
make check-windows     Vérifier les prérequis Windows
make clean             Arrêter + supprimer les conteneurs
make reset             Reset complet (supprime les volumes — ⚠ efface la BDD)
make usb-windows       Passthrough USB (Windows)
```

---

## Résolution de problèmes

### PowerShell — "l'exécution de scripts est désactivée"

```powershell
# Dans PowerShell administrateur
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Ou utilisez `cmd.exe` avec `.venv\Scripts\activate.bat`.

---

### `ModuleNotFoundError: No module named 'flask'`

Le venv est activé mais les dépendances ne sont pas installées :

```bash
pip install -r requirements.txt
```

---

### `Failed to build wheel for pyscard` (Windows)

`pyscard` nécessite les outils de compilation C++.

**Option 1** — Installer [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) (cochez "Desktop development with C++").

**Option 2** — Commenter `pyscard` dans `requirements.txt` si vous n'utilisez pas le NFC.

---

### L'application ne démarre pas — "waiting for db"

MySQL prend 20-30 secondes à initialiser. Le backend attend automatiquement. Si le problème persiste :

```bash
docker compose logs db
```

---

### Les e-mails ne sont pas reçus

En développement, les e-mails sont capturés par **MailHog** : http://localhost:8025.  
Vérifiez que `MAIL_SMTP_HOST=mailhog` et `MAIL_SMTP_PORT=1025` dans votre `.env`.

---

### NFC / pcscd — périphérique non détecté

- **Linux** : `systemctl status pcscd` — le démon doit être actif.
- **Windows** : vérifiez `usbipd list` et relancez `scripts\usb-passthrough.ps1`.

---

### WebAuthn (empreinte) ne fonctionne pas

WebAuthn requiert **HTTPS** hors `localhost`. Options :
- Tunnel local : `ngrok http 5000`
- Cloudflare Tunnel
- Certificat TLS auto-signé sur le serveur nginx

---

## Checklist de démo

- [ ] Page de connexion accessible sur http://localhost
- [ ] Inscription d'un nouveau compte
- [ ] Connexion e-mail + mot de passe
- [ ] Choix de la méthode 2FA
- [ ] TOTP Google Authenticator — scan QR + code valide
- [ ] TOTP Microsoft Authenticator — scan QR + code valide
- [ ] TOTP Authy — scan QR + code valide
- [ ] TOTP FreeOTP — scan QR + code valide
- [ ] OTP e-mail — réception sur MailHog (http://localhost:8025)
- [ ] NFC — enregistrement carte + vérification + révocation
- [ ] Cryptonox — enregistrement FIDO2 + authentification
- [ ] WebAuthn — enregistrement biométrique + authentification
- [ ] Page `auth_success` accessible après 2FA validé
- [ ] Déconnexion fonctionnelle

---

*AuthForte — Projet I2 2025-2026 — 3iL Ingénieurs*
