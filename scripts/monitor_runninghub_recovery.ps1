param(
    [Parameter(Mandatory = $true)][string]$TaskId,
    [Parameter(Mandatory = $true)][string]$CanvasId,
    [Parameter(Mandatory = $true)][string]$NodeId,
    [Parameter(Mandatory = $true)][string]$OutputId,
    [string]$BaseUrl = 'http://127.0.0.1:3001',
    [int]$PollSeconds = 15,
    [int]$MaxHours = 6
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$logPath = Join-Path $root ("output\runninghub-recovery-{0}.log" -f $TaskId)
$deadline = (Get-Date).AddHours([Math]::Max(1, $MaxHours))

function Write-RecoveryLog([string]$Message) {
    $line = "{0} {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    Add-Content -LiteralPath $logPath -Value $line -Encoding UTF8
}

function Ensure-Property($Object, [string]$Name, $Value) {
    if ($Object.PSObject.Properties.Name -contains $Name) {
        $Object.$Name = $Value
    } else {
        Add-Member -InputObject $Object -NotePropertyName $Name -NotePropertyValue $Value
    }
}

function Restore-Outputs([array]$Urls) {
    for ($attempt = 1; $attempt -le 20; $attempt++) {
        $response = Invoke-RestMethod "$BaseUrl/api/canvases/$CanvasId" -TimeoutSec 30
        $canvas = $response.canvas
        $output = @($canvas.nodes | Where-Object { $_.id -eq $OutputId })[0]
        $node = @($canvas.nodes | Where-Object { $_.id -eq $NodeId })[0]
        if ($null -eq $output -or $null -eq $node) {
            throw "找不到目标节点：node=$NodeId output=$OutputId"
        }

        $existing = @($output.images | ForEach-Object {
            if ($_ -is [string]) { $_ } else { $_.url }
        } | Where-Object { $_ })
        $newItems = @()
        foreach ($url in $Urls) {
            if (-not $url -or $existing -contains $url) { continue }
            $newItems += [pscustomobject]@{
                url = $url
                viewed = $false
                runMs = 0
                kind = 'video'
                run = [pscustomobject]@{
                    nodeType = 'rh'
                    node = [pscustomobject]@{ id = $NodeId; type = 'rh' }
                    prompt = 'RunningHub'
                    refs = @()
                    request = [pscustomobject]@{
                        task_id = $TaskId
                        backend = 'runninghub'
                        mode = 'app'
                    }
                }
            }
        }
        Ensure-Property $output 'images' (@($output.images) + $newItems)
        if ($output.PSObject.Properties.Name -contains '_pending') {
            $output.PSObject.Properties.Remove('_pending')
        }

        Ensure-Property $node 'generatedOutputs' (@($node.generatedOutputs) + @($Urls) | Select-Object -Unique)
        Ensure-Property $node 'runStatus' 'done'
        Ensure-Property $node 'runError' ''
        Ensure-Property $node 'rhPendingTask' $null

        $successLog = [pscustomobject]@{
            id = "log_rh_recovery_$TaskId"
            createdAt = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
            status = 'success'
            platform = 'rh'
            nodeType = 'rh'
            model = 'RunningHub'
            request = [pscustomobject]@{ task_id = $TaskId; backend = 'runninghub'; mode = 'app' }
            prompt = 'RunningHub'
            outputs = @($Urls)
            refs = @()
            runMs = 0
            error = ''
        }

        $payload = [ordered]@{
            title = $canvas.title
            icon = $canvas.icon
            nodes = @($canvas.nodes)
            connections = @($canvas.connections)
            viewport = if ($canvas.viewport) { $canvas.viewport } else { @{} }
            logs = @($canvas.logs) + @($successLog)
            settings = if ($canvas.settings) { $canvas.settings } else { @{} }
            client_id = "runninghub-recovery-$TaskId"
            base_updated_at = [long]$canvas.updated_at
        }

        try {
            Invoke-RestMethod "$BaseUrl/api/canvases/$CanvasId" -Method Put -ContentType 'application/json; charset=utf-8' -Body ($payload | ConvertTo-Json -Depth 100) -TimeoutSec 60 | Out-Null
            return $true
        } catch {
            $status = $_.Exception.Response.StatusCode.value__
            if ($status -eq 409 -and $attempt -lt 20) {
                Start-Sleep -Milliseconds 500
                continue
            }
            throw
        }
    }
    return $false
}

Write-RecoveryLog "开始监控任务，最长 ${MaxHours} 小时。"
while ((Get-Date) -lt $deadline) {
    try {
        $query = Invoke-RestMethod "$BaseUrl/api/runninghub/query?taskId=$TaskId" -TimeoutSec 60
        $data = $query.data
        Write-RecoveryLog ("状态={0} code={1} outputs={2}" -f $data.status, $data.code, @($data.urls).Count)
        if ($data.status -eq 'SUCCESS') {
            $urls = @($data.urls | Where-Object { $_ })
            if (-not $urls.Count) { throw 'RunningHub 返回成功但没有输出地址。' }
            if (Restore-Outputs $urls) {
                Write-RecoveryLog ("恢复成功，已写回画布，输出数量={0}" -f $urls.Count)
                exit 0
            }
        }
        if ($data.status -eq 'FAILED') {
            Write-RecoveryLog ("云端任务失败：{0}" -f $data.failReason)
            exit 2
        }
    } catch {
        Write-RecoveryLog ("查询或恢复异常：{0}" -f $_.Exception.Message)
    }
    Start-Sleep -Seconds ([Math]::Max(5, $PollSeconds))
}

Write-RecoveryLog '监控达到最长时间，任务仍未完成。'
exit 3
