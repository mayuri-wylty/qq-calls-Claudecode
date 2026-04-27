$OutputEncoding = [System.Text.UTF8Encoding]::new()
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new()
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
chcp.com 65001 | Out-Null

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$logDir = Join-Path $root "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
try {
    Start-Transcript -Path (Join-Path $logDir "napcat-console.log") -Append | Out-Null
} catch {
}
$napcatDir = Join-Path $root "NapCatCompat\NapCat.41785.Shell"
Set-Location $napcatDir
$quickLogin = $env:A5_QQ
if ($quickLogin) {
    & ".\NapCatWinBootMain.exe" $quickLogin
} else {
    & ".\NapCatWinBootMain.exe"
}
