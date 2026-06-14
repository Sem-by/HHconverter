# Build a standalone Windows app (no Python install required on target PCs).
# Output: dist\HHConverter\HHConverter.exe
#
# Usage: .\build.ps1
#
# Optional code signing:
#   $env:HHCONVERTER_SIGN_PFX = "C:\path\to\cert.pfx"
#   $env:HHCONVERTER_SIGN_PASSWORD = "secret"
#   .\build.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

python -m pip install --upgrade pip pyinstaller tzdata | Out-Host
python -m PyInstaller --noconfirm --clean HHConverter.spec | Out-Host

$dist = Join-Path $PSScriptRoot "dist\HHConverter"
$exe = Join-Path $dist "HHConverter.exe"
if (-not (Test-Path $exe)) {
    throw "Build failed: $exe not found"
}

function Find-SignTool {
    $cmd = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $kits = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin\*\x64\signtool.exe" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending
    if ($kits) { return $kits[0].FullName }
    return $null
}

function Try-SignExecutable([string]$Path) {
    $pfx = $env:HHCONVERTER_SIGN_PFX
    if (-not $pfx -or -not (Test-Path $pfx)) {
        return
    }
    $signtool = Find-SignTool
    if (-not $signtool) {
        Write-Host "Signing skipped: signtool.exe not found (install Windows SDK)"
        return
    }
    $args = @(
        "sign", "/fd", "SHA256", "/f", $pfx,
        "/tr", "http://timestamp.digicert.com", "/td", "SHA256",
        $Path
    )
    if ($env:HHCONVERTER_SIGN_PASSWORD) {
        $args += @("/p", $env:HHCONVERTER_SIGN_PASSWORD)
    }
    & $signtool @args
    if ($LASTEXITCODE -ne 0) {
        throw "signtool failed with exit code $LASTEXITCODE"
    }
    Write-Host "Signed: $Path"
}

Try-SignExecutable $exe

Copy-Item -Force "config.example.json" $dist
@"
Run HHConverter.exe from this folder.
Keep the _internal folder next to the exe.
Do not run the copy under build\ — that folder is incomplete.
"@ | Set-Content -Path (Join-Path $dist "README.txt") -Encoding UTF8

$zip = Join-Path $PSScriptRoot "dist\HHConverter-portable.zip"
if (Test-Path $zip) {
    Remove-Item $zip -Force
}
try {
    Compress-Archive -Path $dist -DestinationPath $zip -Force
} catch {
    Write-Host "Zip skipped (files in use): $zip"
    $zip = ""
}

Write-Host ""
Write-Host "Built: $exe"
Write-Host "Share the folder: $dist"
if ($zip) {
    Write-Host "Or zip:         $zip"
}
Write-Host ""
Write-Host "Do NOT run HHConverter.exe from build\HHConverter\"
