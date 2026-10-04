[CmdletBinding()]
param(
    [string]$Board = "phpretro-preservation",
    [int]$IntervalSeconds = 5,
    [switch]$Watch,
    [switch]$Json,
    [switch]$IncludeArchived
)

$ErrorActionPreference = "Stop"

function Invoke-Kanban {
    param([string[]]$Arguments)
    $output = & hermes @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw (($output | Out-String).Trim())
    }
    return ($output | Out-String)
}

function Get-KanbanCards {
    $args = @("kanban", "--board", $Board, "list", "--json", "--sort", "updated")
    if ($IncludeArchived) { $args += "--archived" }
    $raw = Invoke-Kanban $args
    if ([string]::IsNullOrWhiteSpace($raw)) { return @() }
    $parsed = $raw | ConvertFrom-Json
    if ($null -eq $parsed) { return @() }
    return @($parsed)
}

function Get-CardAge {
    param($Card)
    if ($Card.status -eq "running" -and $Card.started_at) {
        return (([DateTimeOffset]::UtcNow - [DateTimeOffset]::FromUnixTimeSeconds([int64]$Card.started_at)).TotalMinutes)
    }
    if ($Card.completed_at -and $Card.started_at) {
        return (([DateTimeOffset]::FromUnixTimeSeconds([int64]$Card.completed_at) - [DateTimeOffset]::FromUnixTimeSeconds([int64]$Card.started_at)).TotalMinutes)
    }
    return $null
}

function Get-StatusColor {
    param([string]$Status)
    switch ($Status) {
        "running" { return "Green" }
        "ready" { return "Cyan" }
        "todo" { return "Yellow" }
        "triage" { return "DarkYellow" }
        "blocked" { return "Red" }
        "done" { return "DarkGreen" }
        default { return "Gray" }
    }
}

function Show-Progress {
    $cards = Get-KanbanCards
    $groups = @($cards | Group-Object status | Sort-Object Name)
    $running = @($cards | Where-Object status -eq "running")
    $timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")

    if ($Json) {
        $summary = [ordered]@{
            board = $Board
            timestamp = $timestamp
            total = $cards.Count
            byStatus = [ordered]@{}
            cards = @($cards | ForEach-Object {
                [ordered]@{
                    id = $_.id
                    title = $_.title
                    assignee = $_.assignee
                    status = $_.status
                    priority = $_.priority
                    branch = $_.branch_name
                    started = $_.started_at
                    completed = $_.completed_at
                    ageMinutes = Get-CardAge $_
                    result = $_.result
                }
            })
        }
        foreach ($group in $groups) { $summary.byStatus[$group.Name] = $group.Count }
        $summary | ConvertTo-Json -Depth 6
        return
    }

    Clear-Host
    Write-Host "PHPRetro Kanban Progress" -ForegroundColor Cyan
    Write-Host ("Board: {0}    Updated: {1}" -f $Board, $timestamp) -ForegroundColor DarkGray
    Write-Host ""

    $statusOrder = @("running", "ready", "todo", "blocked", "triage", "done")
    $counts = @{}
    foreach ($group in $groups) { $counts[$group.Name] = $group.Count }
    $countLine = foreach ($status in $statusOrder) {
        $count = if ($counts.ContainsKey($status)) { $counts[$status] } else { 0 }
        "{0}: {1}" -f $status, $count
    }
    Write-Host ($countLine -join "  ")
    Write-Host "Total cards: $($cards.Count)"
    Write-Host ""

    if ($running.Count -gt 0) {
        Write-Host "ACTIVE AGENTS" -ForegroundColor Green
        foreach ($card in ($running | Sort-Object assignee)) {
            $age = Get-CardAge $card
            $ageText = if ($null -eq $age) { "n/a" } else { "{0:N1} min" -f $age }
            Write-Host ("  {0,-12} {1,-32} {2} (age {3})" -f $card.assignee, $card.id, $card.title, $ageText) -ForegroundColor Green
        }
    } else {
        Write-Host "ACTIVE AGENTS: none" -ForegroundColor Yellow
    }
    Write-Host ""

    Write-Host "CARDS" -ForegroundColor Cyan
    foreach ($card in ($cards | Sort-Object @{Expression={
        switch ($_.status) { "running" { 0 } "ready" { 1 } "todo" { 2 } "blocked" { 3 } "triage" { 4 } "done" { 5 } default { 6 } }
    }}, assignee, title)) {
        $age = Get-CardAge $card
        $ageText = if ($null -eq $age) { "" } else { " | {0:N1}m" -f $age }
        $line = "  [{0,-7}] {1,-12} {2} - {3}{4}" -f $card.status, $card.assignee, $card.id, $card.title, $ageText
        Write-Host $line -ForegroundColor (Get-StatusColor $card.status)
        if ($card.result) { Write-Host ("             Result: " + $card.result) -ForegroundColor DarkGray }
    }

    if ($Watch) {
        Write-Host ""
        Write-Host ("Refreshing every {0} seconds. Press Ctrl+C to stop." -f $IntervalSeconds) -ForegroundColor DarkGray
    }
}

if ($IntervalSeconds -lt 1) { throw "IntervalSeconds must be at least 1." }

do {
    try {
        Show-Progress
    } catch {
        Write-Error $_
        if (-not $Watch) { exit 1 }
    }
    if ($Watch) { Start-Sleep -Seconds $IntervalSeconds }
} while ($Watch)
