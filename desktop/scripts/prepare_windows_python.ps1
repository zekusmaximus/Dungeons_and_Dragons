param(
  [string]$PythonVersion = "3.11.8"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot ".." "..")
$desktopRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$pythonRoot = Join-Path $desktopRoot "python"
$embedZip = Join-Path $desktopRoot ("python-embed-" + $PythonVersion + ".zip")
$embedUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
$getPipUrl = "https://bootstrap.pypa.io/get-pip.py"
$getPipPath = Join-Path $desktopRoot "get-pip.py"
$requirementsPath = Join-Path $repoRoot "service" "requirements.txt"

Write-Host "Preparing embedded Python $PythonVersion..."
Write-Host "Downloading $embedUrl"
Invoke-WebRequest -Uri $embedUrl -OutFile $embedZip

if (Test-Path $pythonRoot) {
  Remove-Item -Recurse -Force $pythonRoot
}
New-Item -ItemType Directory -Path $pythonRoot | Out-Null
Expand-Archive -Path $embedZip -DestinationPath $pythonRoot -Force

Write-Host "Downloading get-pip.py"
Invoke-WebRequest -Uri $getPipUrl -OutFile $getPipPath

$pythonExe = Join-Path $pythonRoot "python.exe"
Write-Host "Installing pip into embedded Python..."
& $pythonExe $getPipPath

Write-Host "Ensuring site-packages is enabled..."
$pth = Get-ChildItem -Path $pythonRoot -Filter "python*._pth" | Select-Object -First 1
if ($null -ne $pth) {
  $lines = Get-Content $pth.FullName
  $updated = @()
  $hasSite = $false
  $hasImportSite = $false
  foreach ($line in $lines) {
    if ($line -match "Lib\\site-packages") { $hasSite = $true }
    if ($line -match "^import site") { $hasImportSite = $true }
    $updated += $line
  }
  if (-not $hasSite) { $updated += "Lib\\site-packages" }
  if (-not $hasImportSite) { $updated += "import site" }
  Set-Content -Path $pth.FullName -Value $updated
}

Write-Host "Installing backend dependencies..."
& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install --no-warn-script-location -r $requirementsPath

Write-Host "Embedded Python ready at $pythonRoot"
