# CAMR Personal installer for Windows (PowerShell).
#   irm https://raw.githubusercontent.com/Satasdin/CAMR/main/install/install.ps1 | iex
# Installs CAMR into its own virtual environment (%USERPROFILE%\.camr\venv) and adds a `camr` command.
$ErrorActionPreference = "Stop"
$Ref = if ($env:CAMR_REF) { $env:CAMR_REF } else { "main" }
$HomeDir = if ($env:CAMR_HOME) { $env:CAMR_HOME } else { Join-Path $env:USERPROFILE ".camr" }

$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) { $Python = "py"; $PyArgs = @("-3") } else { $Python = "python"; $PyArgs = @() }
& $Python @PyArgs -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if ($LASTEXITCODE -ne 0) { throw "Python 3.10 or newer is required: https://www.python.org/downloads/" }

New-Item -ItemType Directory -Force -Path $HomeDir | Out-Null
& $Python @PyArgs -m venv (Join-Path $HomeDir "venv")
$VenvPy = Join-Path $HomeDir "venv\Scripts\python.exe"
& $VenvPy -m pip install --quiet --upgrade pip
Write-Host "==> Installing CAMR ($Ref). The first install downloads PyTorch; this can take a few minutes."
& $VenvPy -m pip install --quiet "camr[app] @ git+https://github.com/Satasdin/CAMR.git@$Ref"

$Scripts = Join-Path $HomeDir "venv\Scripts"
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -notlike "*$Scripts*") {
  [Environment]::SetEnvironmentVariable("Path", "$UserPath;$Scripts", "User")
  Write-Host "==> Added $Scripts to your PATH (open a new terminal)."
}
if (Get-Command ollama -ErrorAction SilentlyContinue) { ollama list }
else { Write-Host "==> Install Ollama from https://ollama.com/download, then: ollama pull qwen2.5:1.5b" }
Write-Host "==> Done. Start CAMR Personal with:   camr app"
