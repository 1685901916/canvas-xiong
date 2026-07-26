param(
    [Parameter(Mandatory = $true)][string]$TaskId,
    [string]$BaseUrl = 'http://127.0.0.1:3001',
    [int]$PollSeconds = 15,
    [int]$MaxHours = 6
)

$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$log = Join-Path $root ("output\runninghub-status-{0}.log" -f $TaskId)
$deadline = (Get-Date).AddHours([Math]::Max(1, $MaxHours))
$lastStatus = ''

function Write-Status([string]$Message) {
    Add-Content -LiteralPath $log -Value ("{0} {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message) -Encoding UTF8
}

Write-Status "开始监控任务，最长 ${MaxHours} 小时。"
while ((Get-Date) -lt $deadline) {
    try {
        $response = Invoke-RestMethod "$BaseUrl/api/runninghub/query?taskId=$TaskId" -TimeoutSec 90
        $data = $response.data
        if ($data.status -ne $lastStatus -or $data.status -in @('SUCCESS', 'FAILED')) {
            Write-Status ("状态={0} code={1} outputs={2} reason={3}" -f $data.status, $data.code, @($data.urls).Count, $data.failReason)
            $lastStatus = $data.status
        }
        if ($data.status -eq 'SUCCESS') {
            foreach ($url in @($data.urls)) { Write-Status "输出=$url" }
            exit 0
        }
        if ($data.status -eq 'FAILED') { exit 2 }
    } catch {
        Write-Status ("查询异常：{0}" -f $_.Exception.Message)
    }
    Start-Sleep -Seconds ([Math]::Max(5, $PollSeconds))
}
Write-Status '达到最长监控时间，任务仍未结束。'
exit 3
