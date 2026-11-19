# Pokreće aplikaciju i javni Cloudflare link (radi s bilo koje mreže).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# --- cloudflared ---
$cf = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
if (-not $cf) { $cf = Get-ChildItem "C:\Program Files*\cloudflared\cloudflared.exe" -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName }
if (-not $cf) {
    Write-Host "cloudflared nije instaliran. Pokrenite u terminalu:  winget install Cloudflare.cloudflared" -ForegroundColor Red
    Read-Host "Enter za izlaz"; exit 1
}

# --- Python okruženje ---
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Prvo pokretanje: stvaram .venv i instaliram pakete..."
    & "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m venv .venv
    & ".venv\Scripts\python.exe" -m pip install -r requirements.txt
}

# --- aplikacija (ako već ne radi) ---
$radi = Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue
if (-not $radi) {
    Write-Host "Pokrećem aplikaciju..."
    $app = Start-Process ".venv\Scripts\python.exe" -ArgumentList "-m", "streamlit", "run", "app.py" -PassThru -WindowStyle Minimized
    Start-Sleep 5
}

# --- tunel ---
$log = Join-Path $env:TEMP "ores_cloudflared.log"
Remove-Item $log -ErrorAction SilentlyContinue
Write-Host "Otvaram javni link (10-20 sekundi)..."
$tun = Start-Process $cf -ArgumentList "tunnel", "--url", "http://localhost:8501" -PassThru -WindowStyle Hidden -RedirectStandardError $log

$url = $null
for ($i = 0; $i -lt 45 -and -not $url; $i++) {
    Start-Sleep 1
    $m = Select-String -Path $log -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($m) { $url = $m.Matches[0].Value }
}

if ($url) {
    # Pričekaj da adresa postoji u DNS-u. Provjera ide preko 1.1.1.1 (ne preko routera), jer
    # router/preglednik koji prerano pita zapamti "ne postoji" i link mu ne radi i do pola sata.
    Write-Host "Čekam da link postane dostupan (do 1 min)..."
    $h = ([uri]$url).Host
    for ($i = 0; $i -lt 60; $i++) {
        try { Resolve-DnsName $h -Server 1.1.1.1 -DnsOnly -ErrorAction Stop | Out-Null; break } catch { Start-Sleep 1 }
    }
    Start-Sleep 10
}

if (-not $url) {
    Write-Host "Link se nije uspio otvoriti. Zapis greške: $log" -ForegroundColor Red
} else {
    Set-Clipboard $url
    Write-Host ""
    Write-Host "  ============================================================" -ForegroundColor Green
    Write-Host "   LINK ZA STUDENTE I PROFESORA (radi s bilo koje mreže):" -ForegroundColor Green
    Write-Host ""
    Write-Host "     $url" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "   (link je već kopiran - samo zalijepite Ctrl+V)" -ForegroundColor Green
    Write-Host "  ============================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Ako netko dobije 'Server nije pronađen': pričekati minutu, pa osvježiti (F5)"
    Write-Host "  ili otvoriti link u drugom pregledniku / privatnom prozoru."
    Start-Process $url
}

Write-Host "  NE ZATVARAJTE OVAJ PROZOR dok traje vježba. Za kraj pritisnite Enter."
Read-Host | Out-Null
Stop-Process -Id $tun.Id -Force -ErrorAction SilentlyContinue
if ($app) { Stop-Process -Id $app.Id -Force -ErrorAction SilentlyContinue }
