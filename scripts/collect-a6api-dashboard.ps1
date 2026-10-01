param(
    [Parameter(Mandatory)][string]$Since,
    [string]$Until,
    [string]$Output = '.\monitoring\a6api-dashboard-export.jsonl',
    [switch]$DryRun,
    [ValidateRange(1, 1000)][int]$PageSize = 100,
    [ValidateRange(1, 100000)][int]$MaxPages = 1000,
    [switch]$Watch,
    [ValidateRange(30, 3600)][int]$PollSeconds = 60,
    [switch]$BrowserCode,
    [string]$FixturePath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$RepoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$MonitoringRoot = [IO.Path]::GetFullPath((Join-Path $RepoRoot 'monitoring'))
$DiagnosticsPath = Join-Path $MonitoringRoot 'a6api-dashboard-collector.log'

function Get-Field($Object, [string]$Name) {
    if ($null -eq $Object) { return $null }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
}

function Get-DecimalOrNull($Value) {
    if ($null -eq $Value -or [string]::IsNullOrWhiteSpace([string]$Value)) { return $null }
    $text = ([string]$Value).Trim() -replace '^\$', '' -replace '\s*/\s*M(?:illion)?$', ''
    $number = [decimal]0
    if (-not [decimal]::TryParse($text, [Globalization.NumberStyles]::Number,
        [Globalization.CultureInfo]::InvariantCulture, [ref]$number)) { return $null }
    return $number
}

function Get-LongOrNull($Value) {
    $number = Get-DecimalOrNull $Value
    if ($null -eq $number -or $number -lt 0 -or $number -ne [decimal]::Truncate($number) -or
        $number -gt [long]::MaxValue) { return $null }
    return [long]$number
}

function Get-Price($Raw, [string]$Field, [string]$Model) {
    $dashboardValue = Get-Field $Raw $Field
    if ($null -ne $dashboardValue -and -not [string]::IsNullOrWhiteSpace([string]$dashboardValue)) {
        $rowPrice = Get-DecimalOrNull $dashboardValue
        if ($null -ne $rowPrice -and $rowPrice -ge 0) { return $rowPrice }
        return $null
    }
    # These are reference prices, used only for exact model IDs.
    $rates = @{
        'gpt-6.1-sol' = @{
            input_price_per_million = [decimal]'0.0264'
            cache_read_price_per_million = [decimal]'0.001320'
            output_price_per_million = [decimal]'0.1320'
            cache_write_price_per_million = $null
        }
        'gpt-6-luna' = @{
            input_price_per_million = [decimal]'0.007200'
            cache_read_price_per_million = [decimal]'0.000720'
            output_price_per_million = [decimal]'0.0360'
            cache_write_price_per_million = [decimal]'0.009000'
        }
    }
    if ($null -ne $Model -and $rates.ContainsKey([string]$Model)) { return $rates[[string]$Model][$Field] }
    return $null
}

function ConvertTo-A6ApiRow($Raw) {
    $model = Get-Field $Raw 'model'
    $metadata = Get-Field $Raw 'metadata'
    $mode = Get-Field $metadata 'gating_mode'
    if ($mode -cnotin @('gated', 'ungated', 'escalated')) { $mode = 'unknown' }

    $row = [ordered]@{
        timestamp = Get-Field $Raw 'timestamp'
        request_id = Get-Field $Raw 'request_id'
        model = $model
        channel = Get-Field $Raw 'channel'
        reasoning_effort = Get-Field $Raw 'reasoning_effort'
        request_path = Get-Field $Raw 'request_path'
        input_tokens = Get-LongOrNull (Get-Field $Raw 'input_tokens')
        cache_tokens = Get-LongOrNull (Get-Field $Raw 'cache_tokens')
        output_tokens = Get-LongOrNull (Get-Field $Raw 'output_tokens')
        cache_write_tokens = Get-LongOrNull (Get-Field $Raw 'cache_write_tokens')
        input_price_per_million = Get-Price $Raw 'input_price_per_million' $model
        cache_read_price_per_million = Get-Price $Raw 'cache_read_price_per_million' $model
        output_price_per_million = Get-Price $Raw 'output_price_per_million' $model
        cache_write_price_per_million = Get-Price $Raw 'cache_write_price_per_million' $model
        displayed_cost_usd = Get-DecimalOrNull (Get-Field $Raw 'displayed_cost_usd')
        calculated_reference_cost_usd = $null
        mode = $mode
        source = 'a6api-console'
    }

    $required = @('input_tokens', 'cache_tokens', 'output_tokens', 'cache_write_tokens',
        'input_price_per_million', 'cache_read_price_per_million', 'output_price_per_million')
    $complete = $true
    foreach ($field in $required) {
        if ($null -eq $row[$field]) { $complete = $false; break }
    }
    if ($complete -and $row.cache_write_tokens -gt 0 -and $null -eq $row.cache_write_price_per_million) {
        $complete = $false
    }
    if ($complete) {
        $uncached = $row.input_tokens - $row.cache_tokens - $row.cache_write_tokens
        if ($uncached -ge 0) {
            $writeCost = [decimal]0
            if ($row.cache_write_tokens -gt 0) {
                $writeCost = [decimal]$row.cache_write_tokens * $row.cache_write_price_per_million
            }
            $row.calculated_reference_cost_usd = (
                [decimal]$uncached * $row.input_price_per_million +
                [decimal]$row.cache_tokens * $row.cache_read_price_per_million +
                [decimal]$row.output_tokens * $row.output_price_per_million + $writeCost
            ) / [decimal]1000000
        }
    }
    return [pscustomobject]$row
}

function Get-FixturePages([string]$Path, [int]$Limit) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw 'Fixture file was not found.'
    }
    $pages = New-Object 'System.Collections.Generic.List[object]'
    $lineNumber = 0
    foreach ($line in [IO.File]::ReadAllLines([IO.Path]::GetFullPath($Path))) {
        $lineNumber++
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        try {
            # Windows PowerShell 5.1 has no -Depth parameter; fixture rows are
            # shallow enough for its parser while PowerShell 7 keeps the bound.
            if ($PSVersionTable.PSVersion.Major -ge 6) {
                $page = $line | ConvertFrom-Json -Depth 30
            } else {
                $page = $line | ConvertFrom-Json
            }
        } catch {
            throw "Invalid fixture JSON at line $lineNumber."
        }
        if ((Get-Field $page 'page') -ne ($pages.Count + 1) -or
            $null -eq (Get-Field $page 'rows') -or
            @((Get-Field $page 'rows')).Count -gt $Limit) {
            throw "Invalid fixture page at line $lineNumber."
        }
        $pages.Add($page)
    }
    if ($pages.Count -eq 0 -or (Get-Field $pages[$pages.Count - 1] 'has_more') -ne $false) {
        throw 'Fixture pagination is incomplete.'
    }
    for ($index = 0; $index -lt $pages.Count - 1; $index++) {
        if ((Get-Field $pages[$index] 'has_more') -ne $true) {
            throw 'Fixture pagination ended before the last page.'
        }
    }
    return $pages.ToArray()
}

function Assert-WithinMaxPages([object[]]$Pages, [int]$Limit) {
    if ($Pages.Count -gt $Limit) { throw 'MaxPages stopped collection before the final fixture page.' }
}

function Get-ArchivePath([string]$Requested) {
    $resolved = [IO.Path]::GetFullPath((Join-Path $RepoRoot $Requested))
    $prefix = $MonitoringRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
    if (-not $resolved.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase) -or
        [IO.Path]::GetExtension($resolved) -ne '.jsonl') {
        throw 'Output must be a JSONL file beneath this repository monitoring directory.'
    }
    return $resolved
}

function Read-Archive([string]$Path) {
    $rows = New-Object 'System.Collections.Generic.List[object]'
    if (-not [IO.File]::Exists($Path)) { return $rows.ToArray() }
    $lineNumber = 0
    foreach ($line in [IO.File]::ReadLines($Path)) {
        $lineNumber++
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        try {
            if ($PSVersionTable.PSVersion.Major -ge 6) {
                $row = $line | ConvertFrom-Json -Depth 30
            } else {
                $row = $line | ConvertFrom-Json
            }
        } catch {
            throw "Existing archive has invalid JSON at line $lineNumber; it was not changed."
        }
        if ([string]::IsNullOrWhiteSpace([string](Get-Field $row 'request_id'))) {
            throw "Existing archive has no request_id at line $lineNumber; it was not changed."
        }
        $rows.Add($row)
    }
    return $rows.ToArray()
}

function Write-ArchiveAtomically([string]$Path, [object[]]$Rows) {
    $directory = [IO.Path]::GetDirectoryName($Path)
    [IO.Directory]::CreateDirectory($directory) | Out-Null
    $temporary = Join-Path $directory ('.a6api-' + [guid]::NewGuid().ToString('N') + '.tmp')
    $backup = Join-Path $directory ('.a6api-backup-' + (Get-Date -Format 'yyyyMMddTHHmmssfffffff') +
        '-' + [guid]::NewGuid().ToString('N') + '.jsonl')
    try {
        $stream = [IO.FileStream]::new($temporary, [IO.FileMode]::CreateNew,
            [IO.FileAccess]::Write, [IO.FileShare]::None, 4096, [IO.FileOptions]::WriteThrough)
        try {
            $writer = [IO.StreamWriter]::new($stream, [Text.UTF8Encoding]::new($false))
            try {
                foreach ($row in $Rows) { $writer.WriteLine(($row | ConvertTo-Json -Depth 30 -Compress)) }
                $writer.Flush()
                $stream.Flush($true)
            } finally { $writer.Dispose() }
        } finally { $stream.Dispose() }
        if ([IO.File]::Exists($Path)) {
            [IO.File]::Replace($temporary, $Path, $backup, $true)
        } else {
            [IO.File]::Move($temporary, $Path)
        }
    } finally {
        if ([IO.File]::Exists($temporary)) { [IO.File]::Delete($temporary) }
    }
}

function Write-Diagnostic([string]$Code, [int]$Count = 0, [string]$Path = $DiagnosticsPath) {
    $allowed = @('LIVE_AUTH_UNAVAILABLE', 'OFFLINE_DRY_RUN', 'OFFLINE_ARCHIVE_UPDATED', 'OFFLINE_NO_CHANGE')
    if ($Code -cnotin $allowed) { throw 'Invalid diagnostic code.' }
    [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($Path)) | Out-Null
    $entry = '{0} {1} count={2}' -f (Get-Date).ToUniversalTime().ToString('o'), $Code, $Count
    [IO.File]::AppendAllText($Path, $entry + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
}

function Invoke-Collector([object[]]$Pages, [datetimeoffset]$Start, [datetimeoffset]$End,
    [string]$ArchivePath, [bool]$IsDryRun) {
    $seen = 0; $duplicates = 0
    $missing = [ordered]@{}
    $incoming = New-Object 'System.Collections.Generic.List[object]'
    $existing = @(Read-Archive $ArchivePath)
    $retained = New-Object 'System.Collections.Generic.List[object]'
    $ids = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    foreach ($row in $existing) {
        if ($ids.Add([string]$row.request_id)) { $retained.Add($row) }
        else { $duplicates++ }
    }
    $earliest = $null; $latest = $null
    foreach ($page in $Pages) {
        foreach ($raw in @(Get-Field $page 'rows')) {
            $seen++
            $row = ConvertTo-A6ApiRow $raw
            foreach ($field in $row.PSObject.Properties) {
                if ($null -eq $field.Value) {
                    if (-not $missing.Contains($field.Name)) { $missing[$field.Name] = 0 }
                    $missing[$field.Name]++
                }
            }
            $parsed = [datetimeoffset]::MinValue
            if (-not [datetimeoffset]::TryParse([string]$row.timestamp,
                [Globalization.CultureInfo]::InvariantCulture,
                [Globalization.DateTimeStyles]::AssumeUniversal, [ref]$parsed)) { continue }
            if ($parsed -lt $Start -or $parsed -ge $End) { continue }
            if ([string]::IsNullOrWhiteSpace([string]$row.request_id)) { continue }
            if ($null -eq $earliest -or $parsed -lt $earliest) { $earliest = $parsed }
            if ($null -eq $latest -or $parsed -gt $latest) { $latest = $parsed }
            if (-not $ids.Add([string]$row.request_id)) { $duplicates++; continue }
            $incoming.Add($row)
        }
    }
    if (-not $IsDryRun -and ($incoming.Count -gt 0 -or $retained.Count -lt $existing.Count)) {
        Write-ArchiveAtomically $ArchivePath @($retained.ToArray() + $incoming.ToArray())
    }
    return [pscustomobject]@{
        rows_seen = $seen
        rows_written = $(if ($IsDryRun) { 0 } else { $incoming.Count })
        rows_eligible = $incoming.Count
        duplicates_skipped = $duplicates
        earliest_timestamp = $(if ($null -eq $earliest) { $null } else { $earliest.ToString('o') })
        latest_timestamp = $(if ($null -eq $latest) { $null } else { $latest.ToString('o') })
        missing_fields = [pscustomobject]$missing
        dry_run = $IsDryRun
    }
}

function Get-BrowserCode([datetimeoffset]$Start, $End, [string]$ArchivePath,
    [int]$Size, [int]$Limit, [bool]$Continuous, [int]$Interval, [bool]$Preview) {
    # This code runs only when the user pastes it into the signed-in A6API page.
    # It sends requests to A6API's own read-only log endpoint and writes local files.
    $code = @'
(() => {
  'use strict';
  if (location.origin !== 'https://a6api.com' || location.pathname !== '/console/log') {
    throw new Error('Open the signed-in https://a6api.com/console/log page first.');
  }
  if (window.__a6apiCollector) throw new Error('A6API collector is already installed in this tab.');
  const cfg = {
    since: __SINCE__, until: __UNTIL__, file: __FILE__, folder: __FOLDER__,
    pageSize: __PAGE_SIZE__, maxPages: __MAX_PAGES__,
    watch: __WATCH__, pollMs: __POLL_MS__, dryRun: __DRY_RUN__
  };
  const rates = {
    'gpt-6.1-sol': {input:0.0264, cache:0.00132, output:0.132, write:null},
    'gpt-6-luna': {input:0.0072, cache:0.00072, output:0.036, write:0.009}
  };
  const box = document.createElement('div');
  box.style.cssText = 'position:fixed;right:16px;bottom:16px;z-index:2147483647;background:#17212b;color:#fff;padding:12px;border-radius:8px;font:13px sans-serif;max-width:340px;box-shadow:0 3px 18px #0008';
  const status = document.createElement('div');
  status.textContent = `A6API collector ready. Select ${cfg.folder}`;
  const startButton = document.createElement('button');
  startButton.textContent = 'Start capture';
  const stopButton = document.createElement('button');
  stopButton.textContent = 'Stop';
  stopButton.disabled = true;
  for (const button of [startButton, stopButton]) {
    button.style.cssText = 'margin:8px 8px 0 0;padding:5px 8px;cursor:pointer';
    box.append(button);
  }
  box.prepend(status);
  document.body.append(box);
  const state = {stopped:false, timer:null, directory:null, lastSecond:null};
  window.__a6apiCollector = {stop:() => {state.stopped=true; clearTimeout(state.timer); status.textContent='A6API collector stopped.'; stopButton.disabled=true;}};
  stopButton.onclick = window.__a6apiCollector.stop;
  const number = value => {
    if (value === null || value === undefined || value === '') return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
  };
  const integer = value => { const n=number(value); return n !== null && Number.isSafeInteger(n) ? n : null; };
  const formatTime = seconds => {
    const d = new Date(seconds * 1000);
    if (!Number.isFinite(d.getTime())) return null;
    const two = n => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${two(d.getMonth()+1)}-${two(d.getDate())} ${two(d.getHours())}:${two(d.getMinutes())}:${two(d.getSeconds())}`;
  };
  const getOther = raw => {
    if (raw.other && typeof raw.other === 'object') return raw.other;
    if (typeof raw.other === 'string') {
      try { const value=JSON.parse(raw.other); return value && typeof value==='object' ? value : {}; }
      catch { return {}; }
    }
    return {};
  };
  const selectPrice = (raw, other, field, profile) => {
    const direct = raw[field] ?? other[field];
    if (direct !== null && direct !== undefined && direct !== '') return number(direct);
    const ratio=number(other.model_ratio);
    const fixed=number(other.model_price);
    if (fixed!==null) return null;
    if (ratio!==null) {
      const long=other.long_context_applied===true;
      const factor=name=>long ? (number(other[name]) || 1) : 1;
      if (field==='input_price_per_million')
        return ratio*2*factor('long_context_in_multiplier');
      if (field==='output_price_per_million' && number(other.completion_ratio)!==null)
        return ratio*2*number(other.completion_ratio)*factor('long_context_out_multiplier');
      if (field==='cache_read_price_per_million' && number(other.cache_ratio)!==null)
        return ratio*2*number(other.cache_ratio)*factor('long_context_cache_read_multiplier');
    }
    return profile;
  };
  const normalize = (raw, quotaPerUnit) => {
    const other = getOther(raw);
    const model = raw.model_name ?? raw.model ?? null;
    const profile = rates[model] ?? {input:null,cache:null,output:null,write:null};
    const five = integer(other.cache_creation_tokens_5m);
    const hour = integer(other.cache_creation_tokens_1h);
    let write = integer(other.cache_creation_tokens ?? raw.cache_creation_tokens);
    if (write === null && (five !== null || hour !== null)) write = (five ?? 0) + (hour ?? 0);
    const cache = integer(raw.cache_tokens ?? other.cache_tokens);
    const input = integer(raw.prompt_tokens ?? raw.input_tokens);
    const output = integer(raw.completion_tokens ?? raw.output_tokens);
    const path = raw.request_path ?? other.request_path ?? null;
    const quota = number(raw.quota);
    const displayed = quota !== null && quotaPerUnit !== null && quotaPerUnit > 0
      ? Number((quota / quotaPerUnit).toFixed(6)) : null;
    const metadataMode = raw.gating_mode ?? other.gating_mode;
    const row = {
      timestamp: typeof raw.timestamp2string === 'string' ? raw.timestamp2string : formatTime(Number(raw.created_at)),
      request_id: raw.request_id ?? null,
      model, channel: raw.channel ? `${raw.channel} - ${raw.channel_name ?? '[unknown]'}` : null,
      reasoning_effort: raw.reasoning_effort ?? null,
      request_path: path,
      input_tokens: input, cache_tokens: cache, output_tokens: output, cache_write_tokens: write,
      input_price_per_million: selectPrice(raw,other,'input_price_per_million',profile.input),
      cache_read_price_per_million: selectPrice(raw,other,'cache_read_price_per_million',profile.cache),
      output_price_per_million: selectPrice(raw,other,'output_price_per_million',profile.output),
      cache_write_price_per_million: selectPrice(raw,other,'cache_write_price_per_million',profile.write),
      displayed_cost_usd: displayed, calculated_reference_cost_usd: null,
      mode: ['gated','ungated','escalated'].includes(metadataMode) ? metadataMode : 'unknown',
      source: 'a6api-console'
    };
    // The dashboard says /v1/messages prompt_tokens excludes cached tokens.
    const inclusiveInput = path !== '/v1/messages';
    const required = [input,cache,output,write,row.input_price_per_million,
      row.cache_read_price_per_million,row.output_price_per_million];
    if (inclusiveInput && required.every(v => v !== null) &&
        (write === 0 || row.cache_write_price_per_million !== null) && input >= cache + write) {
      row.calculated_reference_cost_usd = ((input-cache-write)*row.input_price_per_million +
        cache*row.cache_read_price_per_million + output*row.output_price_per_million +
        write*(row.cache_write_price_per_million ?? 0)) / 1e6;
    }
    return row;
  };
  const readArchive = async directory => {
    let handle;
    try { handle = await directory.getFileHandle(cfg.file); }
    catch (error) { if (error.name === 'NotFoundError') return {text:'',rows:[]}; throw error; }
    const text = await (await handle.getFile()).text();
    const rows = [];
    for (const line of text.split(/\r?\n/)) {
      if (!line.trim()) continue;
      let row;
      try { row=JSON.parse(line); } catch { throw new Error('Existing archive has invalid JSON; no files were changed.'); }
      if (!row.request_id) throw new Error('Existing archive lacks a request_id; no files were changed.');
      rows.push(row);
    }
    return {text,rows};
  };
  const writeFile = async (directory, name, content) => {
    const handle = await directory.getFileHandle(name,{create:true});
    const stream = await handle.createWritable();
    try { await stream.write(content); await stream.close(); }
    catch (error) { try { await stream.abort(); } catch {} throw error; }
  };
  const diagnostic = async (code,count=0) => {
    if (!state.directory) return;
    const allowed = ['CAPTURE_OK','CAPTURE_NO_CHANGE','CAPTURE_FAILED'];
    if (!allowed.includes(code)) return;
    const name='a6api-dashboard-collector.log';
    let previous='';
    try { previous=await (await (await state.directory.getFileHandle(name)).getFile()).text(); }
    catch (error) { if (error.name!=='NotFoundError') throw error; }
    await writeFile(state.directory,name,previous+`${new Date().toISOString()} ${code} count=${count}\n`);
  };
  const collect = async () => {
    const start = Math.max(Date.parse(cfg.since)/1000,
      state.lastSecond === null ? 0 : state.lastSecond - 60);
    const fixedEnd = cfg.until === null ? Infinity : Date.parse(cfg.until)/1000;
    const end = Math.min(Date.now()/1000, fixedEnd);
    if (!Number.isFinite(start) || !Number.isFinite(end) || start >= end) {
      throw new Error('The capture window is empty or invalid.');
    }
    let userId;
    try { userId=JSON.parse(localStorage.getItem('user') ?? 'null')?.id; } catch {}
    if (!Number.isSafeInteger(Number(userId)) || Number(userId) < 0) {
      throw new Error('The browser page has no signed-in user ID. Sign in normally and try again.');
    }
    const quotaPerUnit = number(localStorage.getItem('quota_per_unit'));
    const rows=[];
    let total=null;
    let dashboard_match=null;
    for (let page=1; page<=cfg.maxPages; page++) {
      const params = new URLSearchParams({p:String(page),page_size:String(cfg.pageSize),type:'0',
        token_name:'',model_name:'',start_timestamp:String(Math.floor(start)),
        end_timestamp:String(Math.ceil(end)),group:'',request_id:''});
      const response = await fetch(`/api/log/self/?${params}`, {method:'GET',credentials:'same-origin',
        headers:{'New-API-User':String(userId),'Cache-Control':'no-store'}});
      if (!response.ok) throw new Error(`Dashboard log request failed (HTTP ${response.status}).`);
      const result=await response.json();
      if (result?.success !== true || !Array.isArray(result?.data?.items)) {
        throw new Error('Dashboard log response did not match the page API; capture stopped.');
      }
      const data=result.data;
      if (Number(data.page)!==page || Number(data.page_size)!==cfg.pageSize ||
          !Number.isSafeInteger(Number(data.total))) {
        throw new Error('Dashboard pagination changed; capture stopped.');
      }
      total=Number(data.total);
      if (page===1 && typeof document.querySelector==='function') {
        const startInput=document.querySelector('input[placeholder="start time"]');
        const endInput=document.querySelector('input[placeholder="End Time"]');
        const filters=['Token Name','Model Name','Group','Request ID'];
        const emptyFilters=filters.every(name=>!document.querySelector(`input[placeholder="${name}"]`)?.value);
        const sameWindow=startInput && endInput &&
          Math.abs(Date.parse(startInput.value)/1000-start)<1 &&
          Math.abs(Date.parse(endInput.value)/1000-end)<1;
        if (emptyFilters && sameWindow) {
          const visible=document.querySelector('tr.semi-table-row[data-row-key]:not([data-row-key$="-expanded-row"])');
          const first=data.items[0];
          dashboard_match=(!first && !visible) ||
            (!!first && !!visible && String(first.id)===visible.getAttribute('data-row-key'));
          if (!dashboard_match) throw new Error('The API first row differs from the visible dashboard row.');
        }
      }
      rows.push(...data.items);
      if (rows.length>=total) break;
      if (page===cfg.maxPages) throw new Error('MaxPages reached before all dashboard rows were read.');
    }
    const archive = cfg.dryRun ? {text:'',rows:[]} : await readArchive(state.directory);
    const seenIds = new Set(archive.rows.map(row=>String(row.request_id)));
    const novel=[];
    let duplicates=0, latest=state.lastSecond;
    const missing={};
    let earliestTimestamp=null, latestTimestamp=null;
    for (const raw of rows) {
      const row=normalize(raw,quotaPerUnit);
      for (const [key,value] of Object.entries(row)) {
        if (value===null) missing[key]=(missing[key]??0)+1;
      }
      const id=row.request_id;
      if (!id || !row.timestamp) continue;
      if (earliestTimestamp===null || row.timestamp<earliestTimestamp) earliestTimestamp=row.timestamp;
      if (latestTimestamp===null || row.timestamp>latestTimestamp) latestTimestamp=row.timestamp;
      const second=number(raw.created_at);
      if (second!==null && (latest===null || second>latest)) latest=second;
      if (seenIds.has(String(id))) {duplicates++;continue;}
      seenIds.add(String(id)); novel.push(row);
    }
    if (!cfg.dryRun && novel.length) {
      if (archive.text) {
        const stamp=new Date().toISOString().replace(/[:.]/g,'-');
        await writeFile(state.directory,`.a6api-backup-${stamp}.jsonl`,archive.text);
      }
      const merged=archive.rows.concat(novel).map(row=>JSON.stringify(row)).join('\n')+'\n';
      await writeFile(state.directory,cfg.file,merged);
    }
    state.lastSecond=latest;
    if (!cfg.dryRun) await diagnostic(novel.length?'CAPTURE_OK':'CAPTURE_NO_CHANGE',novel.length);
    const summary={rows_seen:rows.length,rows_written:cfg.dryRun?0:novel.length,
      rows_eligible:novel.length,duplicates_skipped:duplicates,
      earliest_timestamp:earliestTimestamp,latest_timestamp:latestTimestamp,
      dashboard_match,missing_fields:missing};
    window.__a6apiCollector.lastSummary=summary;
    console.info('A6API collector summary',summary);
    status.textContent=`A6API: ${rows.length}/${total} rows checked; ${novel.length} ${cfg.dryRun?'eligible':'saved'}; ${duplicates} duplicates. ${cfg.watch?'Watching':'Done'}.`;
    return summary;
  };
  const run = async () => {
    if (state.stopped) return;
    try {
      status.textContent='A6API: reading request-log pages…';
      await collect();
      if (cfg.watch && !state.stopped && (cfg.until===null || Date.now()<Date.parse(cfg.until)))
        state.timer=setTimeout(run,cfg.pollMs);
      else stopButton.disabled=true;
    } catch (error) {
      state.stopped=true; clearTimeout(state.timer); stopButton.disabled=true;
      status.textContent=`A6API capture stopped: ${error.message}`;
      try { await diagnostic('CAPTURE_FAILED'); } catch {}
    }
  };
  startButton.onclick=async () => {
    startButton.disabled=true;
    try {
      if (!cfg.dryRun) {
        if (typeof showDirectoryPicker!=='function') throw new Error('This browser needs directory access (Chrome or Edge).');
        state.directory=await showDirectoryPicker({id:'a6api-monitoring',mode:'readwrite'});
        if (state.directory.name!=='monitoring') throw new Error('Select this repository’s monitoring folder.');
      }
      stopButton.disabled=false;
      await run();
    } catch (error) {
      status.textContent=`A6API capture did not start: ${error.message}`;
      startButton.disabled=false;
    }
  };
})();
'@
    $sinceLiteral = ConvertTo-Json -InputObject $Start.ToUniversalTime().ToString('o') -Compress
    $untilLiteral = if ($null -eq $End) { 'null' } else {
        ConvertTo-Json -InputObject $End.ToUniversalTime().ToString('o') -Compress
    }
    $fileLiteral = ConvertTo-Json -InputObject ([IO.Path]::GetFileName($ArchivePath)) -Compress
    $code = $code.Replace('__SINCE__', $sinceLiteral)
    $code = $code.Replace('__UNTIL__', $untilLiteral)
    $code = $code.Replace('__FILE__', $fileLiteral)
    $code = $code.Replace('__FOLDER__', (ConvertTo-Json -InputObject $MonitoringRoot -Compress))
    $code = $code.Replace('__PAGE_SIZE__', [string]$Size)
    $code = $code.Replace('__MAX_PAGES__', [string]$Limit)
    $code = $code.Replace('__WATCH__', $Continuous.ToString().ToLowerInvariant())
    $code = $code.Replace('__POLL_MS__', [string]($Interval * 1000))
    $code = $code.Replace('__DRY_RUN__', $Preview.ToString().ToLowerInvariant())
    return $code
}

function Main {
    $start = [datetimeoffset]::MinValue
    if (-not [datetimeoffset]::TryParse($Since, [Globalization.CultureInfo]::InvariantCulture,
        [Globalization.DateTimeStyles]::AssumeUniversal, [ref]$start)) {
        throw 'Since must be a valid timestamp.'
    }
    $end = $null
    if (-not [string]::IsNullOrWhiteSpace($Until)) {
        $parsedEnd = [datetimeoffset]::MinValue
        if (-not [datetimeoffset]::TryParse($Until, [Globalization.CultureInfo]::InvariantCulture,
            [Globalization.DateTimeStyles]::AssumeUniversal, [ref]$parsedEnd) -or $start -ge $parsedEnd) {
            throw 'Until must be later than Since.'
        }
        $end = $parsedEnd
    } elseif (-not $Watch) {
        throw 'Until is required unless Watch is selected.'
    }
    $archivePath = Get-ArchivePath $Output
    if ([string]::IsNullOrWhiteSpace($FixturePath)) {
        $code = Get-BrowserCode -Start $start -End $end -ArchivePath $archivePath -Size $PageSize `
            -Limit $MaxPages -Continuous:([bool]$Watch) -Interval $PollSeconds -Preview:([bool]$DryRun)
        if ($BrowserCode) { return $code }
        [IO.Directory]::CreateDirectory($MonitoringRoot) | Out-Null
        Set-Clipboard -Value $code
        Write-Output 'Browser collector copied to the clipboard. Open the signed-in A6API log page in Chrome or Edge, paste the code into DevTools Console, click Start capture, and select this repository monitoring folder. Keep that tab open for Watch mode.'
        return
    }
    if ($null -eq $end) { throw 'Fixture mode requires Until.' }
    if (-not $DryRun) {
        throw 'FixturePath requires DryRun so synthetic rows cannot enter the monitoring archive.'
    }
    $pages = @(Get-FixturePages $FixturePath $PageSize)
    Assert-WithinMaxPages $pages $MaxPages
    $summary = Invoke-Collector $pages $start $end $archivePath ([bool]$DryRun)
    if ($DryRun) { Write-Diagnostic 'OFFLINE_DRY_RUN' $summary.rows_eligible }
    elseif ($summary.rows_written -gt 0) { Write-Diagnostic 'OFFLINE_ARCHIVE_UPDATED' $summary.rows_written }
    else { Write-Diagnostic 'OFFLINE_NO_CHANGE' }
    return $summary
}

if ($MyInvocation.InvocationName -ne '.') { Main }
