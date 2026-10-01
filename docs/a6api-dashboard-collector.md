# A6API browser collector

## Automatic collection with Tampermonkey

The ongoing collector is [a6api-dashboard-auto.user.js](../scripts/a6api-dashboard-auto.user.js). Install Tampermonkey from its official Chrome or Edge extension store, create a new script in its dashboard, replace the template with this file's contents, and save it. The extension also needs browser permission to execute userscripts: in Chrome, turn on **Allow User Scripts** in Tampermonkey's extension details; in Edge, open `edge://extensions` and turn on **Developer mode** if Edge does not offer the Allow User Scripts toggle. See [Tampermonkey's FAQ](https://www.tampermonkey.net/faq.php?q=Q209). Then open or reload `https://a6api.com/console/log` while signed in. Click **Choose monitoring folder** in the small A6API collector panel and select this repository's exact `monitoring` folder. This initial choice is required by the browser. If you installed an older copy, replace its contents with the current file in Tampermonkey and save; editing the local file does not update a pasted copy automatically.

After that, the script starts on each log-page visit when Chrome or Edge still grants folder access. It checks A6API's own log endpoint every 60 seconds, fetches all pages within the needed time window, and adds only unseen `request_id` values to `a6api-dashboard-export.jsonl`. The first run looks back 24 hours; later runs resume from the last successful check with a two-minute overlap, including after a closed tab or browser restart. A backup is made before each archive rewrite. When it saves new rows, it reloads the dashboard at most once every five minutes so the visible list updates. Keep the tab open and the browser running for ongoing collection. The panel shows checked and saved counts, the archived row count, the authoritative displayed-cost sum, and the last check time. **Pause** stops this tab's timer. On an API, archive, or permission error, collection stops and shows the reason; it does not silently retry.

Chrome or Edge can require a new click on **Restore folder access** after a reload or browser restart. A userscript cannot bypass that browser permission prompt. The script never asks for or records an A6API API key, cookie, or session token. It reads the page's numeric user ID only to make the same authenticated, same-origin request as the dashboard. It saves the chosen directory handle, last successful check time, and numeric account ID in IndexedDB under the `a6api.com` origin so it can resume and detect an account switch. **Other scripts served by that origin could access the saved directory handle.** Choose only the intended `monitoring` folder, and remove that site's stored data or revoke its file permission if you stop using the collector. It sends no logs to a third party or local server.

Do not run the one-shot console collector and Tampermonkey collector against the same archive at the same time. The userscript uses a browser lock to prevent two log tabs from writing concurrently; it stops if the browser lacks that lock API. It preserves the existing archive's row format and does not alter its current contents until it finds a new request ID. Its first-run 24-hour lookback is intentionally bounded; use the one-shot command below for older history. To test the userscript's parsing, pagination, deduplication, backup, and failure behavior without A6API access, run `node .\tests\test-a6api-dashboard-auto.js`. A real browser run is still required to verify Tampermonkey injection and file permission on this machine.

The A6API log page uses `GET /api/log/self/` with `p`, `page_size`, `type`, `start_timestamp`, `end_timestamp`, and optional filters. Its response contains `success` and `data.items`, `data.page`, `data.page_size`, and `data.total`. These details come from the log page's loaded JavaScript. The page has no visible export control.

A standalone PowerShell process cannot use the signed-in browser session without moving session credentials. This collector therefore runs the read-only request **inside the signed-in A6API tab**. PowerShell prepares the browser code and copies it to the clipboard; the browser writes normalized JSONL into the local `monitoring/` folder you select. The code sends requests only to A6API's own log endpoint and writes local files. It does not use an A6API API key or export cookies, passwords, session tokens, or the page's local-storage user record. It reads the numeric user ID inside the page to set the same `New-API-User` header that A6API's page uses, then discards it.

## Run once

In PowerShell, change to this repository and run:

```powershell
pwsh .\scripts\collect-a6api-dashboard.ps1 `
  -Since '2026-10-01T00:00:00Z' `
  -Until '2026-10-02T00:00:00Z' `
  -Output '.\monitoring\a6api-dashboard-export.jsonl'
```

The command creates the `monitoring` directory if needed and copies browser code to the clipboard. In a signed-in **Chrome or Edge** tab at `https://a6api.com/console/log`, open Developer Tools (F12), choose Console, paste the code, and press Enter. Click the **Start capture** button that appears on the page. When the browser asks for a directory, select this repository's exact `monitoring` folder shown in the button's message. The collector reads all matching pages and writes `a6api-dashboard-export.jsonl` there. It shows rows checked, rows saved, and duplicates in the page. If the browser refuses pasted code, review the browser's warning and perform its steps yourself; the tool cannot bypass it.

The one-shot command uses `[Since, Until)`, capped at the current time. For ongoing collection, omit `-Until` and add `-Watch -PollSeconds 60`. Keep the tab open. Each successful poll resumes with a 60-second overlap, deduplicates by `request_id`, and stops on a failed request or unexpected page response. Click **Stop** in the page or close the tab to stop it. `-PageSize` defaults to 100; `-MaxPages` defaults to 1000 and stops instead of silently archiving a partial result. `-DryRun` checks rows but does not request folder access or write files. `-BrowserCode` prints the generated JavaScript instead of copying it.

Chrome or Edge is required for the local directory picker. The Codex in-app browser may not expose this feature or Developer Tools; signing in normally in Chrome or Edge is acceptable. The collector does not automate login. It never sends dashboard data to a third-party service or a local server.

## Data and costs

Only normalized request rows are written. The archive, `a6api-dashboard-collector.log`, and uniquely named backups stay in the selected `monitoring/` directory. Diagnostics contain only a timestamp, fixed status code, and row count. The collector validates existing JSONL before a rewrite, deduplicates by request ID, writes a backup before replacing the archive, and never deletes old archives or backups. The browser's file writer commits on close; exact replacement guarantees depend on the browser's File System Access implementation. Run only one collector against an archive at a time.

The dashboard's `quota` is divided by the page's `quota_per_unit` to reproduce its six-decimal USD display. Explicit row prices and the page's token-price ratios take precedence; missing prices use the reference rates only for exact `gpt-6.1-sol` and `gpt-6-luna` model IDs. Cache-write price is not inferred from a missing ratio. Unknown prices and fields remain null. A reference cost is calculated only when required token counts and prices are present; `/v1/messages` is excluded because A6API's UI says its prompt token count excludes cached tokens. `mode` stays `unknown` unless explicit metadata says otherwise. **A6API's actual deduction remains authoritative.** A displayed cost and calculated reference cost can differ.

## Test and rotate

Run the offline fixture test without network access:

```powershell
pwsh -NoProfile -File .\tests\test-collect-a6api-dashboard.ps1
```

The fixture is synthetic and cannot be written into the real archive through the command; `-FixturePath` requires `-DryRun`. To archive old logs, move the JSONL and its backups into a dated subfolder **within** `monitoring/`, then run a new capture. No scheduler, extension, browser permission change, or background service is installed.

The browser-side request path and pagination are verified against the page's code, and the offline tests pass. A live capture on 2026-10-01 wrote 558 rows with 558 unique request IDs and a displayed-cost sum of $0.270732; the prior 221-row archive was backed up. A subsequent poll should report zero new rows when no new request IDs exist. When the dashboard's visible time window and empty filters exactly match the collector's request, it compares the first returned row with the first visible row and stops if they differ. The code stops on a mismatch rather than guessing.
