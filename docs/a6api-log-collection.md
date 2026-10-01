# A6API log collection

The A6API console is the billing authority. The collector does not log in, scrape cookies, or store dashboard credentials. Export request rows from `https://a6api.com/console/log` and save them as JSONL, then archive them:

```powershell
pwsh scripts/record-a6api-export.ps1 -InputFile .\a6api-export.jsonl
```

The archive is append-only at `monitoring/a6api-requests.jsonl`. Generate a summary at any time:

```powershell
pwsh scripts/summarize-a6api-archive.ps1
```

Each row should include `timestamp`, `request_id`, `model`, `input_tokens`, `cache_tokens`, `output_tokens`, and the three per-million prices. Optional fields are `accepted` and `mode` (`ungated`, `gated`, or `escalated`). Do not store API keys, cookies, authorization headers, or private dashboard HTML.

For the supplied merchant row, use input `$0.0264/M`, output `$0.1320/M`, and cache read `$0.001320/M`. Cache-write pricing was not supplied; record it when the dashboard/export provides it, and do not infer it. Actual deduction remains authoritative.

