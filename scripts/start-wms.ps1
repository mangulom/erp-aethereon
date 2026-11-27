$ErrorActionPreference = 'Stop'
$erpRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $erpRoot 'backend'
$logisticsRoot = Join-Path $backendRoot 'services\logistics'
$financeEnv = Join-Path $erpRoot 'backend\services\finance\.env'
$py = Join-Path $logisticsRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { $py = (Get-Command python).Source }

if (-not (Test-Path $financeEnv)) { throw 'Finance private .env not found; WMS requires shared ERP DB/JWT settings.' }
if (-not (Test-Path $logisticsRoot)) { throw 'Integrated logistics backend sources not found.' }

$envContent = Get-Content $financeEnv
$dbLine = $envContent | Where-Object { $_ -match '^DATABASE_URL=' } | Select-Object -First 1
$jwtLine = $envContent | Where-Object { $_ -match '^JWT_SECRET_KEY=' } | Select-Object -First 1
if (-not $dbLine -or -not $jwtLine) { throw 'Finance .env must provide DATABASE_URL and JWT_SECRET_KEY.' }
$env:DATABASE_URL = $dbLine.Substring('DATABASE_URL='.Length)
$env:JWT_SECRET = $jwtLine.Substring('JWT_SECRET_KEY='.Length)
$env:JWT_ISSUER = 'aethereon-identity'
$env:JWT_AUDIENCE = 'aethereon-erp'
$env:JWT_ALGORITHM = 'HS256'
$env:DB_SCHEMA = 'public'
$env:PORT = '18005'
$env:ENV = 'development'
$env:FORCE_HTTPS = 'false'
$env:TRUSTED_HOSTS = '*'
$env:CORS_ALLOWED_ORIGINS = 'http://localhost:42000,http://127.0.0.1:42000'
Set-Location $backendRoot
& $py run_logistics.py
