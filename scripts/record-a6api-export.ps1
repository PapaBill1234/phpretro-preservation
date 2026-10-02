param(
  [Parameter(Mandatory=$true)][string]$InputFile,
  [string]$Archive = "$PSScriptRoot\..\monitoring\a6api-requests.jsonl"
)

$ErrorActionPreference = 'Stop'
$archivePath = [IO.Path]::GetFullPath($Archive)
$parent = Split-Path -Parent $archivePath
New-Item -ItemType Directory -Force -Path $parent | Out-Null

Get-Content -LiteralPath $InputFile | Where-Object { $_.Trim() } | ForEach-Object {
  $row = $_ | ConvertFrom-Json
  if (-not $row.timestamp) { $row | Add-Member timestamp ([DateTime]::UtcNow.ToString('o')) }
  if (-not $row.request_id) { throw 'Each A6API row needs request_id.' }
  $row | ConvertTo-Json -Compress -Depth 8 | Add-Content -LiteralPath $archivePath -Encoding utf8
}

Write-Output "Archived A6API rows to $archivePath"
