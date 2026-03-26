# ═══════════════════════════════════════════════════════════════════════════════
#  AuthForte — Partage USB Windows → Docker via usbipd-win
#  Requis pour : NFC, Cryptonox, YubiKey, lecteur d'empreintes
#
#  Prérequis : usbipd-win installé (winget install dorssel.usbipd-win)
#  Exécutez en tant qu'Administrateur
# ═══════════════════════════════════════════════════════════════════════════════
#Requires -Version 5.1

function info { param($msg) Write-Host "[->] $msg" -ForegroundColor Cyan }
function ok   { param($msg) Write-Host "[OK] $msg" -ForegroundColor Green }
function warn { param($msg) Write-Host "[!!] $msg" -ForegroundColor Yellow }
function fail { param($msg) Write-Host "[XX] $msg" -ForegroundColor Red }

Write-Host ""
Write-Host "AuthForte — Passthrough USB (usbipd-win)" -ForegroundColor White
Write-Host "══════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Vérifier usbipd
if (-not (Get-Command usbipd -ErrorAction SilentlyContinue)) {
    fail "usbipd-win non trouvé."
    Write-Host "Installez avec : winget install dorssel.usbipd-win" -ForegroundColor Yellow
    exit 1
}

# ── Lister les périphériques USB disponibles ──────────────────────────────────
info "Périphériques USB disponibles :"
Write-Host ""
usbipd list
Write-Host ""

# ── Sélection interactive ─────────────────────────────────────────────────────
Write-Host "Entrez le BUSID du périphérique à partager (ex: 2-3)," -ForegroundColor White
Write-Host "ou appuyez sur Entrée pour partager tous les périphériques détectés :" -ForegroundColor White
$busid = Read-Host "BUSID"

if ([string]::IsNullOrWhiteSpace($busid)) {
    # ── Partage automatique des périphériques NFC/Smart Card connus ───────────
    info "Tentative de partage automatique des périphériques smart card / NFC..."

    $devices = usbipd list 2>&1 | Where-Object { $_ -match "Smart|NFC|RFID|Yubi|Kensington|CCID|Reader|ACR" }
    if ($devices) {
        foreach ($device in $devices) {
            if ($device -match "^(\d+-\d+)") {
                $id = $Matches[1]
                info "Partage du périphérique $id : $device"
                usbipd bind --busid $id 2>&1 | Out-Null
                usbipd attach --wsl --busid $id
                ok "Périphérique $id partagé avec WSL/Docker"
            }
        }
    } else {
        warn "Aucun périphérique NFC/Smart Card détecté automatiquement."
        warn "Branchez votre lecteur NFC ou clé FIDO2 et relancez ce script."
    }
} else {
    # ── Partage d'un périphérique spécifique ──────────────────────────────────
    info "Partage du périphérique $busid..."
    usbipd bind --busid $busid
    usbipd attach --wsl --busid $busid
    ok "Périphérique $busid partagé avec WSL/Docker"
}

Write-Host ""
Write-Host "État après partage :" -ForegroundColor Cyan
usbipd list
Write-Host ""
Write-Host "Note : Le partage USB est temporaire (session WSL uniquement)." -ForegroundColor Yellow
Write-Host "       Relancez ce script après chaque redémarrage du PC." -ForegroundColor Yellow
Write-Host ""
Write-Host "Pour détacher : usbipd detach --busid <BUSID>" -ForegroundColor Gray
Write-Host ""
