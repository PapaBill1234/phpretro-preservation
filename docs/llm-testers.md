# A6API model testers

`scripts/llm-testers/run-llm-testers.py` runs six deterministic testers covering instruction following, logic, arithmetic, coding, and quoted-fact recall. It runs both `gpt-6.1-sol` and `gpt-6-luna` by default, records the server-reported model and latency, and writes raw answers to a timestamped JSON report under `monitoring/` (ignored by Git).

Set credentials in the process environment:

```powershell
$env:A6API_API_KEY = '...'
$env:A6API_BASE_URL = 'https://your-a6api-host/v1'
.\scripts\llm-testers\Run-LLMTesters.ps1 -Repeats 3
```

The same launcher accepts `-BaseUrl`, `-Models`, `-Repeats`, `-Timeout`, and `-Out`. A nonzero exit code means at least one request errored. A high score is behavioral evidence only; no black-box test can prove model identity. Check `reported_models`, latency, errors, and scores across repeated runs. Never pass the API key on the command line or commit it.
