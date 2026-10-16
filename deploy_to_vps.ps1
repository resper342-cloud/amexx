<#
.SYNOPSIS
    Clears remote VPS data and deploys the American Express Personal Loans platform.
#>

param(
    [string]$VpsHost = "89.125.43.3",
    [string]$VpsUser = "root",
    [string]$RemoteDir = "/var/www/amex",
    [string]$Domain = "amexloans.online"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$ArchiveName = "amex_deploy.tar.gz"
$ArchivePath = Join-Path $ScriptDir $ArchiveName

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " AMERICAN EXPRESS PERSONAL LOANS VPS DEPLOYMENT TOOL" -ForegroundColor Yellow
Write-Host " Target VPS: $VpsUser@$VpsHost" -ForegroundColor Cyan
Write-Host " Remote Directory: $RemoteDir" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Package files
Write-Host "`n[1/3] Packing project files into $ArchiveName..." -ForegroundColor Green
if (Test-Path $ArchivePath) { Remove-Item -Force $ArchivePath }
& tar --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' --exclude='*.sqlite3' --exclude='*.sqlite' --exclude='paypal_deploy.tar.gz' -czf $ArchiveName *

if (-not (Test-Path $ArchivePath)) {
    Write-Error "Failed to generate $ArchiveName"
    exit 1
}

# 2. Upload archive and deployment script
Write-Host "`n[2/3] Uploading archive and deploy_vps.sh to VPS via SCP..." -ForegroundColor Green
& scp -o StrictHostKeyChecking=accept-new $ArchivePath "deploy_vps.sh" "${VpsUser}@${VpsHost}:/tmp/"

if ($LASTEXITCODE -ne 0) {
    Write-Error "SCP upload failed. Please verify credentials."
    exit $LASTEXITCODE
}

# 3. Execute setup on VPS with interactive TTY
Write-Host "`n[3/3] Running remote wipe & deployment on VPS..." -ForegroundColor Green
$RemoteCmd = "sed -i 's/\r$//' /tmp/deploy_vps.sh && chmod +x /tmp/deploy_vps.sh && bash /tmp/deploy_vps.sh"
& ssh -tt -o StrictHostKeyChecking=accept-new "${VpsUser}@${VpsHost}" $RemoteCmd

# Cleanup local archive
if (Test-Path $ArchivePath) { Remove-Item -Force $ArchivePath }

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host " DEPLOYMENT FINISHED!" -ForegroundColor Green
Write-Host " Check your portals:" -ForegroundColor Yellow
Write-Host " - Domain (HTTPS):     https://$Domain/" -ForegroundColor Green
Write-Host " - Admin Dashboard:    https://$Domain/admin" -ForegroundColor Green
Write-Host " - Partner Portal:     https://$Domain/agent" -ForegroundColor Green
Write-Host " - Direct IP Backup:   http://$VpsHost/" -ForegroundColor White
Write-Host "==========================================================" -ForegroundColor Cyan
