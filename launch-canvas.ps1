param(
  [switch]$OpenWhenReady
)

$ErrorActionPreference = "Stop"

function Test-CanvasServer {
  try {
    $Response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:3001/" -TimeoutSec 2
    return $Response.StatusCode -eq 200
  } catch {
    return $false
  }
}

$PhysicalAppDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not (Test-Path -LiteralPath (Join-Path $PhysicalAppDir "main.py"))) {
  throw "Cannot find main.py: $PhysicalAppDir"
}

$AppDir = $PhysicalAppDir
$PythonExe = Join-Path $AppDir "python\python.exe"
$Url = "http://127.0.0.1:3001/"
$LogDir = Join-Path $AppDir "output"
$OutLog = Join-Path $LogDir "launcher-server.out.log"
$ErrLog = Join-Path $LogDir "launcher-server.err.log"

if (Test-CanvasServer) {
  if ($OpenWhenReady) {
    Start-Process $Url | Out-Null
  }
  exit 0
}

if (-not (Test-Path -LiteralPath $PythonExe)) {
  throw "Cannot find bundled Python: $PythonExe"
}

if (-not (Test-Path -LiteralPath $LogDir)) {
  New-Item -ItemType Directory -Path $LogDir | Out-Null
}

$UvicornArgs = @(
  "-m", "uvicorn", "main:app",
  "--app-dir", "`"$AppDir`"",
  "--host", "127.0.0.1",
  "--port", "3001"
)

Start-Process -FilePath $PythonExe `
  -ArgumentList $UvicornArgs `
  -WorkingDirectory $AppDir `
  -WindowStyle Hidden `
  -RedirectStandardOutput $OutLog `
  -RedirectStandardError $ErrLog | Out-Null

if ($OpenWhenReady) {
  $Deadline = (Get-Date).AddSeconds(60)
  while ((Get-Date) -lt $Deadline) {
    if (Test-CanvasServer) {
      Start-Process $Url | Out-Null
      exit 0
    }
    Start-Sleep -Milliseconds 700
  }
  throw "Canvas did not become ready within 60 seconds. Check: $ErrLog"
}

exit 0
