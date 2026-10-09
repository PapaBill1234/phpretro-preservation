# Builder activity

The Builders page monitors automated OpenHands SDK workers independently of
interactive OpenHands chats. Verified worker PID/process identities and
supervisor receipts supply live role, model, provider, elapsed time, attempt,
reported token count and API-call count. Receipts checkpoint every five seconds;
the browser polls every ten seconds. Unfinished calls may not yet report usage.

The server projects only allowlisted metadata into builder history and the
timeline. It does not serve raw SDK logs, prompts, tool output or credential
fields. Observed SDK totals and conservative ledger charges are shown separately.
An exit code of zero means completed, not an independent review pass. Controller
review-verdict events are labeled generically without inferring their verdict.

Bounded allowances include ledger charges even when the roadmap's token counter
has not caught up. The current paused state explains F61's exhausted allowance.
Intentional STOP suppresses stale-dispatch/no-merge alarms but retains actual
nightly check failures. No control behavior, quota, dispatch scope or ledger is
changed by this view. Workers are not launched as part of dashboard installation.

The visual refresh retains existing unit/parity/analytics/operations tools,
authenticated access, light/dark themes and assistant embeds. Wide screens use
a sidebar; smaller screens use horizontally scrollable navigation. Automated
Builders and Interactive OpenHands have separate navigation entries.

Validation includes metadata privacy, dead/prepared worker exclusion, conservative
allowance accounting, nested SDK usage and bounded history tests. Active-worker
rendering uses synthetic metadata; production is intentionally paused, so no real
active-worker update is claimed during installation. Desktop and mobile browser
previews and the repository merge gate are checked before publication.
