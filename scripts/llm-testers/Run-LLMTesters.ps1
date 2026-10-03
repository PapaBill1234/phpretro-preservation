param(
  [string]$BaseUrl = $env:A6API_BASE_URL,
  [string[]]$Models = @('gpt-6.1-sol', 'gpt-6-luna'),
  [ValidateRange(1,20)][int]$Repeats = 1,
  [int]$Timeout = 90,
  [string]$Out
)

$ErrorActionPreference = 'Stop'
if (-not $BaseUrl) { throw 'Set A6API_BASE_URL or pass -BaseUrl (for example https://your-a6api-host/v1).' }
if (-not $env:A6API_API_KEY) { throw 'Set A6API_API_KEY in the environment. The key is never saved by this script.' }
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$runner = Join-Path $PSScriptRoot 'run-llm-testers.py'
$args = @($runner, '--base-url', $BaseUrl, '--models') + $Models + @('--repeats', $Repeats, '--timeout', $Timeout)
if ($Out) { $args += @('--out', $Out) }
python @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
