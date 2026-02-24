# Authentification-_forte
Application des différents types d'authentifications sur un site web comme OTP, Notification par mail,..

## Envoi d'e‑mails (2FA par mail)

Pour que l'envoi du code de vérification fonctionne, il faut configurer un
serveur SMTP. L'application lit les valeurs suivantes dans l'environnement
avant d'envoyer un message :

| Variable | Valeur attendue | Exemple |
|----------|-----------------|---------|
| `MAIL_SMTP_HOST` | nom de l'hôte SMTP | `smtp.gmail.com`, `smtp.office365.com` |
| `MAIL_SMTP_PORT` | port TCP (par défaut 587) | `587` ou `465` |
| `MAIL_SMTP_USER` | nom d'utilisateur pour l'authentification | adresse mail |
| `MAIL_SMTP_PASSWORD` | mot de passe ou mot de passe d'application | |
| `MAIL_FROM` | expéditeur affiché (optionnel) | `no-reply@monapp.local` |
| `MAIL_DEBUG` | actif (`1` ou `true`) pour imprimer le code au lieu d'envoyer | utile en dev |

**Développement local**

Vous pouvez exécuter un serveur SMTP de débogage qui affiche les messages dans
la console :

```powershell
python -m smtpd -c DebuggingServer -n localhost:1025
```

puis démarrer l'application ainsi :

```powershell
$env:MAIL_SMTP_HOST="localhost"
$env:MAIL_SMTP_PORT="1025"
python Backend/app.py
```

ou simplement activer le mode debug pour afficher le code dans le terminal :

```powershell
$env:MAIL_DEBUG=1
python Backend/app.py
```

**Production**

Définissez les variables d'environnement sur le serveur avant de lancer
l'application. Exemple pour un compte Gmail :

```powershell
$env:MAIL_SMTP_HOST="smtp.gmail.com"
$env:MAIL_SMTP_PORT="587"
$env:MAIL_SMTP_USER="moncompte@gmail.com"
$env:MAIL_SMTP_PASSWORD="motdepasse"
$env:MAIL_FROM="no-reply@monapp.local"
python Backend/app.py
```

Puisque Gmail impose des restrictions, utilisez un mot de passe d'application
et activez l'accès sécurisé (voir documentation Google).
