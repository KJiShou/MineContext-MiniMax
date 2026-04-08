# MineContext Build Script for Windows
# Packages the Python backend into a single executable using PyInstaller.

param(
    [switch]$SkipDependencies
)

$ErrorActionPreference = "Stop"

Write-Host "=== MineContext Build Script (Windows) ===" -ForegroundColor Cyan

# 1. Dependency Check
Write-Host "--> Checking for Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "    Found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "    Error: Python is not found. Please install Python 3." -ForegroundColor Red
    exit 1
}

# 2. Check for uv
$USE_UV = $false
if (Get-Command uv -ErrorAction SilentlyContinue) {
    Write-Host "--> uv found, will use for PyInstaller..." -ForegroundColor Yellow
    $USE_UV = $true
} else {
    Write-Host "--> uv not found, will use pip for PyInstaller..." -ForegroundColor Yellow
}

# 3. Install PyInstaller if not present
if ($USE_UV) {
    $hasPyInstaller = $false
    try { $result = uv run python -c "import PyInstaller" 2>$null; $hasPyInstaller = $true } catch {}
    if (-not $hasPyInstaller) {
        Write-Host "--> PyInstaller not found (uv env). Installing..." -ForegroundColor Yellow
        uv pip install pyinstaller
    }
} else {
    $hasPyInstaller = $false
    try { $result = python -c "import PyInstaller" 2>$null; $hasPyInstaller = $true } catch {}
    if (-not $hasPyInstaller) {
        Write-Host "--> PyInstaller not found. Installing..." -ForegroundColor Yellow
        python -m pip install pyinstaller
    }
}

# 4. Clean up previous builds
Write-Host "--> Cleaning up previous build directories..." -ForegroundColor Yellow
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }

# 5. Run PyInstaller build
Write-Host "--> Starting application build with PyInstaller..." -ForegroundColor Yellow
if ($USE_UV) {
    uv run pyinstaller --clean --noconfirm --log-level INFO opencontext.spec
} else {
    pyinstaller --clean --noconfirm --log-level INFO opencontext.spec
}

# 6. Verify build and package
Write-Host "--> Verifying build output..." -ForegroundColor Yellow
$EXECUTABLE_NAME = "main"
$ONEDIR_EXECUTABLE_WIN = "dist\$EXECUTABLE_NAME\$EXECUTABLE_NAME.exe"

if (Test-Path $ONEDIR_EXECUTABLE_WIN) {
    $BUILT_EXECUTABLE = $ONEDIR_EXECUTABLE_WIN
    Write-Host "    Build successful!" -ForegroundColor Green

    # Copy config directory
    if (Test-Path "config") {
        Write-Host "--> Copying 'config' directory to 'dist/'..." -ForegroundColor Yellow
        Copy-Item -Recurse "config" "dist\"
        Write-Host "    Config directory copied." -ForegroundColor Green
    } else {
        Write-Host "    Warning: 'config' directory not found." -ForegroundColor Yellow
    }

    Write-Host ""
    Write-Host "=== Build complete! ===" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Executable location: $ONEDIR_EXECUTABLE_WIN" -ForegroundColor White
    Write-Host ""
    Write-Host "To run the backend:" -ForegroundColor White
    Write-Host "  .\dist\main\main.exe start" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Options: --port 9000 | --host 0.0.0.0 | --config config\config.yaml" -ForegroundColor Gray
    Write-Host ""
} else {
    Write-Host "Build failed. Check the PyInstaller logs above for errors." -ForegroundColor Red
    exit 1
}
