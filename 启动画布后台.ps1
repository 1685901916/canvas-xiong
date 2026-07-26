param(
  [switch]$OpenWhenReady
)

$ErrorActionPreference = "Stop"

function Get-DosDeviceTarget {
  param([Parameter(Mandatory = $true)][string]$DriveName)

  if (-not ("CanvasDosDevice" -as [type])) {
    Add-Type -TypeDefinition @'
using System.Text;
using System.Runtime.InteropServices;
public static class CanvasDosDevice {
  [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
  public static extern uint QueryDosDevice(string lpDeviceName, StringBuilder lpTargetPath, int ucchMax);
}
'@
  }

  $Buffer = [Text.StringBuilder]::new(32768)
  $Length = [CanvasDosDevice]::QueryDosDevice($DriveName, $Buffer, $Buffer.Capacity)
  if ($Length -eq 0) {
    return ""
  }

  $Target = $Buffer.ToString()
  if ($Target.StartsWith("\??\")) {
    return $Target.Substring(4).TrimEnd("\")
  }
  return $Target
}

function Ensure-CanvasAppDrive {
  param([Parameter(Mandatory = $true)][string]$PhysicalAppDir)

  $Expected = [IO.Path]::GetFullPath($PhysicalAppDir).TrimEnd("\")
  $Current = Get-DosDeviceTarget -DriveName "R:"
  if (-not $Current) {
    & "$env:SystemRoot\System32\subst.exe" "R:" $Expected
    if ($LASTEXITCODE -ne 0) {
      throw "无法创建 R: 本地映射，退出码 $LASTEXITCODE。"
    }
    $Current = Get-DosDeviceTarget -DriveName "R:"
  }

  if (-not [string]::Equals($Current, $Expected, [StringComparison]::OrdinalIgnoreCase)) {
    throw "R: 已被其他磁盘或目录占用：$Current。为避免覆盖，画布服务未启动。"
  }

  $MappedAppDir = "R:\"
  if (-not (Test-Path -LiteralPath (Join-Path $MappedAppDir "main.py"))) {
    throw "R: 映射完成，但找不到 main.py：$MappedAppDir"
  }
  return $MappedAppDir
}

function Test-CanvasServer {
  try {
    return [bool](Get-NetTCPConnection -LocalPort 3001 -State Listen -ErrorAction SilentlyContinue)
  } catch {
    return $false
  }
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (Test-Path -LiteralPath (Join-Path $ScriptDir "main.py")) {
  $PhysicalAppDir = $ScriptDir
} else {
  $PhysicalAppDir = Join-Path $ScriptDir "Infinite-Canvas-main"
}

if (-not (Test-Path -LiteralPath (Join-Path $PhysicalAppDir "main.py"))) {
  throw "Cannot find main.py: $PhysicalAppDir"
}

$AppDir = Ensure-CanvasAppDrive -PhysicalAppDir $PhysicalAppDir
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
  "--app-dir", $AppDir,
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
  throw "画布服务在 60 秒内未就绪，请检查日志：$ErrLog"
}

exit 0
