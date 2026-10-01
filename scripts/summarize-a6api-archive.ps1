param(
  [string]$Archive = "$PSScriptRoot\..\monitoring\a6api-requests.jsonl",
  [string]$Output = "$PSScriptRoot\..\monitoring\a6api-summary.json"
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Archive)) { throw "Archive not found: $Archive" }
$rows = @(Get-Content -LiteralPath $Archive | Where-Object { $_.Trim() } | ForEach-Object { $_ | ConvertFrom-Json })
function Cost($r) {
  $input = [double]($r.input_tokens ?? $r.inputTokens)
  $cache = [double]($r.cache_tokens ?? $r.cacheTokens)
  $output = [double]($r.output_tokens ?? $r.outputTokens)
  $ip = [double]($r.input_price_per_million ?? $r.inputPricePerMillion)
  $cp = [double]($r.cache_price_per_million ?? $r.cachePricePerMillion)
  $op = [double]($r.output_price_per_million ?? $r.outputPricePerMillion)
  return ($input*$ip + $cache*$cp + $output*$op) / 1000000
}
$items = @($rows | ForEach-Object { [pscustomobject]@{ timestamp=$_.timestamp; request_id=$_.request_id; model=$_.model; cost_usd=(Cost $_); accepted=$_.accepted; mode=$_.mode } })
$sum = [double](($items | Measure-Object cost_usd -Sum).Sum)
$out = [pscustomobject]@{ generated_at=[DateTime]::UtcNow.ToString('o'); request_count=$items.Count; total_usd=[math]::Round($sum,8); cost_per_request_usd=if($items.Count){[math]::Round($sum/$items.Count,8)}else{0}; requests=$items }
$out | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Output -Encoding utf8
$out | ConvertTo-Json -Depth 8
