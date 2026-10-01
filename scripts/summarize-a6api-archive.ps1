param(
  [string]$Archive = "$PSScriptRoot\..\monitoring\a6api-requests.jsonl",
  [string]$Output = "$PSScriptRoot\..\monitoring\a6api-summary.json",
  [string]$Rates = "$PSScriptRoot\..\config\a6api-rates.json"
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Archive)) { throw "Archive not found: $Archive" }
$rows = @(Get-Content -LiteralPath $Archive | Where-Object { $_.Trim() } | ForEach-Object { $_ | ConvertFrom-Json })
$rateTable = Get-Content -LiteralPath $Rates -Raw | ConvertFrom-Json
function ValueOr($r, [string]$primary, [string]$secondary, $fallback = $null) {
  $value = $r.PSObject.Properties[$primary]
  if ($value -and $null -ne $value.Value) { return $value.Value }
  $value = $r.PSObject.Properties[$secondary]
  if ($value -and $null -ne $value.Value) { return $value.Value }
  return $fallback
}
function Cost($r) {
  $input = [double](ValueOr $r 'input_tokens' 'inputTokens' 0)
  $cache = [double](ValueOr $r 'cache_tokens' 'cacheTokens' 0)
  $output = [double](ValueOr $r 'output_tokens' 'outputTokens' 0)
  $profile = $rateTable.($r.model)
  $ip = [double](ValueOr $r 'input_price_per_million' 'inputPricePerMillion' $profile.input_price_per_million)
  $cp = [double](ValueOr $r 'cache_price_per_million' 'cachePricePerMillion' $profile.cache_read_price_per_million)
  $op = [double](ValueOr $r 'output_price_per_million' 'outputPricePerMillion' $profile.output_price_per_million)
  return ($input*$ip + $cache*$cp + $output*$op) / 1000000
}
$items = @($rows | ForEach-Object { [pscustomobject]@{ timestamp=$_.timestamp; request_id=$_.request_id; model=$_.model; cost_usd=(Cost $_); accepted=$_.accepted; mode=$_.mode } })
$sum = [double](($items | Measure-Object cost_usd -Sum).Sum)
$byModel = @($items | Group-Object model | ForEach-Object { [pscustomobject]@{ model=$_.Name; request_count=$_.Count; total_usd=[math]::Round([double](($_.Group | Measure-Object cost_usd -Sum).Sum),8) } })
$out = [pscustomobject]@{ generated_at=[DateTime]::UtcNow.ToString('o'); request_count=$items.Count; total_usd=[math]::Round($sum,8); cost_per_request_usd=if($items.Count){[math]::Round($sum/$items.Count,8)}else{0}; by_model=$byModel; requests=$items }
$out | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Output -Encoding utf8
$out | ConvertTo-Json -Depth 8
