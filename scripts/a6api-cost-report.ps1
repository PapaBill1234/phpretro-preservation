param(
  [Parameter(Mandatory=$true)][string]$A6ApiJsonl,
  [string]$JevUsageJsonl = "$env:USERPROFILE\.codex\jev\usage.jsonl",
  [string]$OutJson = "a6api-cost-report.json"
)

# A6API export format: one JSON object per request with timestamp, request_id,
# input_tokens, cache_tokens, output_tokens, input_price_per_million,
# cache_price_per_million, output_price_per_million, and optional accepted=true.
$rows = Get-Content -LiteralPath $A6ApiJsonl | Where-Object { $_.Trim() } | ForEach-Object { $_ | ConvertFrom-Json }
$jevs = if (Test-Path -LiteralPath $JevUsageJsonl) { Get-Content -LiteralPath $JevUsageJsonl | Where-Object { $_.Trim() } | ForEach-Object { $_ | ConvertFrom-Json } } else { @() }

function Cost($r) {
  $input = [double]($r.input_tokens ?? $r.inputTokens)
  $cache = [double]($r.cache_tokens ?? $r.cacheTokens)
  $output = [double]($r.output_tokens ?? $r.outputTokens)
  $ip = [double]($r.input_price_per_million ?? $r.inputPricePerMillion)
  $cp = [double]($r.cache_price_per_million ?? $r.cachePricePerMillion)
  $op = [double]($r.output_price_per_million ?? $r.outputPricePerMillion)
  return ($input*$ip + $cache*$cp + $output*$op) / 1000000
}

$costs = @($rows | ForEach-Object { [pscustomobject]@{ request_id=$_.request_id; timestamp=$_.timestamp; model=$_.model; accepted=[bool]$_.accepted; cost_usd=(Cost $_) } })
$jevCost = [double](($jevs | Measure-Object -Property estimatedUsd -Sum).Sum)
$total = [double](($costs | Measure-Object -Property cost_usd -Sum).Sum)
$accepted = @($costs | Where-Object accepted).Count
$report = [pscustomobject]@{
  generated_at=(Get-Date).ToUniversalTime().ToString('o')
  request_count=$costs.Count
  accepted_count=$accepted
  total_a6api_usd=[math]::Round($total,8)
  jev_call_count=$jevs.Count
  jev_estimated_usd=[math]::Round($jevCost,8)
  jev_share_of_a6api_percent=if($total -gt 0){[math]::Round(100*$jevCost/$total,4)}else{0}
  cost_per_accepted_unit_usd=if($accepted -gt 0){[math]::Round($total/$accepted,8)}else{$null}
  requests=$costs
}
$report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $OutJson -Encoding utf8
$report | ConvertTo-Json -Depth 6