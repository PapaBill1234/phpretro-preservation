# A6API and Jev cost monitoring

The A6API console is the billing authority. Export request rows from `https://a6api.com/console/log` or create a JSONL file with one object per request:

```json
{"timestamp":"2026-10-01T11:31:12Z","request_id":"...","model":"gpt-6.1-sol","input_tokens":13059,"cache_tokens":161536,"output_tokens":799,"input_price_per_million":0.0264,"cache_price_per_million":0.00132,"output_price_per_million":0.132,"accepted":true}
```

The example row calculates approximately `$0.000663`, matching the console's reference calculation. Actual deduction remains authoritative.

Run the read-only report:

```powershell
pwsh scripts/a6api-cost-report.ps1 -A6ApiJsonl .\a6api-export.jsonl -OutJson .\a6api-cost-report.json
```

The report includes request count, accepted units, total A6API cost, local Jev calls and estimated Jev fee from `~/.codex/jev/usage.jsonl`, Jev share of A6API cost, and cost per accepted unit. Do not put API keys, cookies, or dashboard session data in the export.

For a fair gate experiment, label runs `ungated`, `gated`, or `escalated`, keep the task set and model settings fixed, and compare matched accepted units. Track false denies, false allows, escalations, gate latency, retries, total A6API cost, Jev cost, and time. Global `jev_gate` is enabled for monitoring; it is not evidence of savings until the report shows lower matched cost per accepted unit without unacceptable decisions.