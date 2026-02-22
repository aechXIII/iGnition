param(
  [Parameter(Mandatory = $false)]
  [switch]$Clean,
  [Parameter(Mandatory = $false)]
  [switch]$Installer
)

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
  Write-Error "Virtual environment not found. Run scripts\\setup.ps1 first."
  exit 1
}

& .\.venv\Scripts\python.exe -m pip install pyinstaller

# Generate .ico from PNG if missing or older than source
$png = "src\ignition\gui\assets\ignition_logo.png"
$ico = "src\ignition\gui\assets\ignition_logo.ico"
if (-not (Test-Path $ico) -or (Get-Item $png).LastWriteTime -gt (Get-Item $ico).LastWriteTime) {
  Write-Host "Generating $ico from $png..."
  $pngAbs = (Resolve-Path $png).Path
  $icoAbs = Join-Path (Get-Location) $ico
  & .\.venv\Scripts\python.exe -c "from PIL import Image; img=Image.open(r'$pngAbs').convert('RGBA'); img.save(r'$icoAbs', format='ICO', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)]); print('ICO generated.')"
}

if ($Clean) {
  if (Test-Path ".\build") { Remove-Item -Recurse -Force ".\build" }
  if (Test-Path ".\dist") { Remove-Item -Recurse -Force ".\dist" }
}

& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm iGnition.spec

if ($LASTEXITCODE -ne 0) {
  Write-Error "PyInstaller failed."
  exit 1
}

Write-Host "OK: dist\iGnition.exe" -ForegroundColor Green

if ($Installer) {
  # Look for Inno Setup compiler in default install locations
  $iscc = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
  ) | Where-Object { Test-Path $_ } | Select-Object -First 1

  if (-not $iscc) {
    Write-Warning "Inno Setup 6 nie znaleziony. Pobierz z https://jrsoftware.org/isdl.php"
    exit 1
  }

  Write-Host "Compiling installer..." -ForegroundColor Cyan
  & $iscc "installer\iGnition.iss"

  if ($LASTEXITCODE -ne 0) {
    Write-Error "Inno Setup failed."
    exit 1
  }

  Write-Host "OK: installer\Output\iGnition-Setup-$((Select-String -Path installer\iGnition.iss -Pattern '#define AppVersion').Line -replace '.*\"(.+)\".*','$1').exe" -ForegroundColor Green
}
