Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repository = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$script = Join-Path $repository 'scripts/collect-a6api-dashboard.ps1'
$fixture = Join-Path $PSScriptRoot 'fixtures/a6api-dashboard-sample.jsonl'
. $script -Since '2026-10-01T00:00:00Z' -Until '2026-10-02T00:00:00Z'

function Assert($Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

$pages = @(Get-FixturePages $fixture 2)
Assert ($pages.Count -eq 2) 'Pagination: expected two pages.'
$sol = ConvertTo-A6ApiRow $pages[0].rows[0]
$luna = ConvertTo-A6ApiRow $pages[0].rows[1]
$missingWrite = ConvertTo-A6ApiRow $pages[1].rows[1]

Assert ($sol.input_price_per_million -eq [decimal]'0.0264') 'Sol input fallback price failed.'
Assert ($sol.cache_read_price_per_million -eq [decimal]'0.00132') 'Sol cache-read fallback price failed.'
Assert ($sol.output_price_per_million -eq [decimal]'0.132') 'Sol output fallback price failed.'
Assert ($sol.calculated_reference_cost_usd -eq [decimal]'0.000027984') 'Sol reference cost failed.'
Assert ($sol.displayed_cost_usd -eq [decimal]'0.000123') 'Displayed cost was not preserved.'
Assert ($sol.timestamp -ceq '2026-10-01 12:00:00') 'Dashboard timestamp changed.'
Assert ($sol.mode -ceq 'unknown') 'Mode was guessed.'
Assert ($null -eq $sol.cache_write_price_per_million) 'Sol cache-write price was inferred.'

Assert ($luna.input_price_per_million -eq [decimal]'0.0072') 'Luna input fallback price failed.'
Assert ($luna.cache_read_price_per_million -eq [decimal]'0.00072') 'Luna cache-read fallback price failed.'
Assert ($luna.cache_write_price_per_million -eq [decimal]'0.009') 'Luna cache-write fallback price failed.'
Assert ($luna.calculated_reference_cost_usd -eq [decimal]'0.000007236') 'Luna reference cost failed.'
Assert ($null -eq $luna.channel) 'Unknown channel was guessed.'
Assert ($missingWrite.input_price_per_million -eq [decimal]'0.03') 'Row price did not override profile.'
Assert ($null -eq $missingWrite.calculated_reference_cost_usd) 'Missing cache-write price produced a cost.'
$invalidPrice = ConvertTo-A6ApiRow ([pscustomobject]@{
    model = 'gpt-6.1-sol'; input_price_per_million = 'invalid'
    input_tokens = 1; cache_tokens = 0; output_tokens = 0; cache_write_tokens = 0
})
Assert ($null -eq $invalidPrice.input_price_per_million) 'An invalid dashboard price fell back to a reference rate.'

$temporary = Join-Path ([IO.Path]::GetTempPath()) ('a6api-collector-test-' + [guid]::NewGuid().ToString('N'))
[IO.Directory]::CreateDirectory($temporary) | Out-Null
try {
    $archive = Join-Path $temporary 'archive.jsonl'
    $diagnostics = Join-Path $temporary 'diagnostics.log'
    $start = [datetimeoffset]'2026-10-01T00:00:00Z'
    $end = [datetimeoffset]'2026-10-02T00:00:00Z'
    $dry = Invoke-Collector $pages $start $end $archive $true
    Assert ($dry.rows_seen -eq 4 -and $dry.rows_eligible -eq 3 -and $dry.duplicates_skipped -eq 1) 'Dry-run count or dedup failed.'
    Assert (-not [IO.File]::Exists($archive)) 'Dry run wrote an archive.'

    $first = Invoke-Collector $pages $start $end $archive $false
    Assert ($first.rows_written -eq 3) 'First archive write failed.'
    $second = Invoke-Collector $pages $start $end $archive $false
    Assert ($second.rows_written -eq 0 -and $second.duplicates_skipped -eq 4) 'Repeat run did not deduplicate.'
    Assert (@([IO.File]::ReadAllLines($archive)).Count -eq 3) 'Archive row count is wrong.'
    $backups = @([IO.Directory]::GetFiles($temporary, '.a6api-backup-*.jsonl'))
    Assert ($backups.Count -eq 0) 'No-change run rewrote the archive.'

    $newPage = [pscustomobject]@{ rows = @([pscustomobject]@{
        timestamp = '2026-10-01 12:03:00'; request_id = 'fixture-new-1'; model = 'gpt-6-luna'
        input_tokens = 10; cache_tokens = 0; output_tokens = 1; cache_write_tokens = 0
    }) }
    $third = Invoke-Collector @($newPage) $start $end $archive $false
    Assert ($third.rows_written -eq 1) 'Atomic archive update did not add the new row.'
    Assert (@([IO.File]::ReadAllLines($archive)).Count -eq 4) 'Archive update lost rows.'
    $backups = @([IO.Directory]::GetFiles($temporary, '.a6api-backup-*.jsonl'))
    Assert ($backups.Count -eq 1) 'Archive rewrite did not retain its backup.'
    Assert (@([IO.File]::ReadAllLines($backups[0])).Count -eq 3) 'Backup did not preserve the previous archive.'

    Write-Diagnostic 'OFFLINE_ARCHIVE_UPDATED' $first.rows_written $diagnostics
    $log = [IO.File]::ReadAllText($diagnostics)
    Assert (-not $log.Contains('FIXTURE_SECRET_NEVER_LOG')) 'Diagnostics leaked fixture secret.'
    Assert (-not ([IO.File]::ReadAllText($archive)).Contains('FIXTURE_SECRET_NEVER_LOG')) 'Archive leaked unrelated credential field.'

    $browserArgs = @{ Start = $start; End = $end; ArchivePath = $archive; Size = 2;
        Limit = 2; Continuous = $false; Interval = 60; Preview = $true }
    $generatedJs = Get-BrowserCode @browserArgs
    Assert ($generatedJs.Contains('/api/log/self/?')) 'Browser collector lacks the verified log endpoint.'
    Assert ($generatedJs.Contains('start_timestamp')) 'Browser collector lacks date filtering.'
    Assert ($generatedJs.Contains('maxPages: 2')) 'Browser collector did not apply MaxPages.'
    Assert (-not $generatedJs.Contains('FIXTURE_SECRET_NEVER_LOG')) 'Browser collector embedded fixture credentials.'
    if (Get-Command node -ErrorAction SilentlyContinue) {
        $browserCheck = Join-Path $temporary 'collector.js'
        [IO.File]::WriteAllText($browserCheck, $generatedJs)
        & node --check $browserCheck
        Assert ($LASTEXITCODE -eq 0) 'Generated browser code has a syntax error.'
    }

    $maxPagesStopped = $false
    try { Assert-WithinMaxPages $pages 1 } catch { $maxPagesStopped = $true }
    Assert $maxPagesStopped 'MaxPages did not stop incomplete pagination.'
    $pageSizeStopped = $false
    try { Get-FixturePages $fixture 1 | Out-Null } catch { $pageSizeStopped = $true }
    Assert $pageSizeStopped 'PageSize did not stop an oversized page.'
} finally {
    [IO.Directory]::Delete($temporary, $true)
}

'PASS: pricing, cache handling, pagination, normalization, deduplication, browser code, dry run, and secret redaction.'
