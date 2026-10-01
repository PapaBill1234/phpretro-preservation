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

Reference merchant rates are stored in `config/a6api-rates.json`:

| Model | Input/M | Output/M | Cache read/M | Cache write/M |
|---|---:|---:|---:|---:|
| `gpt-6.1-sol` | `$0.0264` | `$0.1320` | `$0.001320` | unknown |
| `gpt-6-luna` | `$0.007200` | `$0.0360` | `$0.000720` | `$0.009000` |

The collector prefers prices displayed on each dashboard row. The rate table is used only when a row omits prices and its model matches exactly. Actual deduction remains authoritative.

