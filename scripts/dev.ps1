[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateSet('database', 'backend', 'frontend', 'catalog')]
    [string]$Service,
    [string]$EnvFile,
    [string]$FrontendDirectory,
    [string]$ReviewDirectory
)

$ErrorActionPreference = 'Stop'
$backendDirectory = Split-Path -Parent $PSScriptRoot
if (-not $EnvFile) { $EnvFile = Join-Path $backendDirectory '.env.local' }
if (-not $FrontendDirectory) { $FrontendDirectory = Join-Path $backendDirectory '../blue_archive_music/client' }
if (-not $ReviewDirectory) { $ReviewDirectory = Join-Path $backendDirectory 'tools/catalog-import/data' }

# Read literal KEY=value lines, without evaluating their contents or printing secrets.
if ($Service -ne 'frontend') {
    $EnvFile = (Resolve-Path -LiteralPath $EnvFile).Path
    $settings = @{}
    foreach ($line in Get-Content -LiteralPath $EnvFile) {
        if ([string]::IsNullOrWhiteSpace($line) -or $line.TrimStart().StartsWith('#')) { continue }
        if ($line -notmatch '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$') {
            throw 'Invalid environment file: use one KEY=value setting per line.'
        }
        $key = $Matches[1]
        $value = $Matches[2].Trim()
        if ($value.Length -ge 2 -and (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'")))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        $settings[$key] = $value
    }
    $required = @('POSTGRES_DB', 'POSTGRES_DATASOURCE_URL', 'POSTGRES_USER', 'POSTGRES_PASSWORD')
    if ($Service -ne 'database') { $required += @('ADMIN_API_KEY', 'R2_ENDPOINT', 'R2_BUCKET', 'R2_ACCESS_KEY', 'R2_SECRET_KEY') }
    foreach ($key in $required) {
        if ([string]::IsNullOrWhiteSpace($settings[$key])) { throw "Missing required setting: $key" }
    }
    if ($settings.POSTGRES_DB -ne 'blue_archive_api' -or $settings.POSTGRES_DATASOURCE_URL -ne 'jdbc:postgresql://localhost:5433/blue_archive_api') {
        throw 'Everyday development requires blue_archive_api at localhost:5433.'
    }
    if ($Service -ne 'database' -and $settings.R2_BUCKET -ne 'bluearchive-music-dev') {
        throw 'Everyday development requires the bluearchive-music-dev R2 bucket.'
    }
    foreach ($key in $settings.Keys) { [Environment]::SetEnvironmentVariable($key, $settings[$key], 'Process') }
}

Push-Location $backendDirectory
try {
    switch ($Service) {
        'database' {
            & docker --host npipe:////./pipe/docker_engine compose --project-name bluearchivemusicapi --env-file $EnvFile --file (Join-Path $backendDirectory 'compose.yaml') up -d postgres
        }
        'backend' {
            $env:SPRING_PROFILES_ACTIVE = 'dev'
            $env:PORT = '8080'
            $env:SPRING_DOCKER_COMPOSE_ENABLED = 'false'
            $env:SPRING_DATASOURCE_URL = $settings.POSTGRES_DATASOURCE_URL
            $env:SPRING_DATASOURCE_USERNAME = $settings.POSTGRES_USER
            $env:SPRING_DATASOURCE_PASSWORD = $settings.POSTGRES_PASSWORD
            $env:CLOUDFLARE_R2_ENDPOINT = $settings.R2_ENDPOINT
            $env:CLOUDFLARE_R2_BUCKET = $settings.R2_BUCKET
            $env:CLOUDFLARE_R2_ACCESSKEY = $settings.R2_ACCESS_KEY
            $env:CLOUDFLARE_R2_SECRETKEY = $settings.R2_SECRET_KEY
            $env:CORS_ALLOWED_ORIGINS = 'http://localhost:5173'
            $maven = Get-Command mvn.cmd -ErrorAction SilentlyContinue
            if ($maven) { $mavenCommand = $maven.Source } else { $mavenCommand = Join-Path $backendDirectory 'mvnw.cmd' }
            & $mavenCommand spring-boot:run '-Dspring-boot.run.arguments=--server.port=8080'
        }
        'frontend' {
            Set-Location -LiteralPath $FrontendDirectory
            $env:VITE_API_BASE_URL = 'http://localhost:8080'
            & npm.cmd run dev -- --host localhost --port 5173 --strictPort
        }
        'catalog' {
            $env:CATALOG_IMPORT_API_KEY = $settings.ADMIN_API_KEY
            & python (Join-Path $backendDirectory 'tools/catalog-import/app.py') --backend-url http://127.0.0.1:8080 --port 8765 --data-dir $ReviewDirectory
        }
    }
    if ($LASTEXITCODE -ne 0) { throw "$Service exited with code $LASTEXITCODE." }
}
finally { Pop-Location }
