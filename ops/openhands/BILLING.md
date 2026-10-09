# Provider billing

A6API collection uses the console's read-only `/api/user/self`, `/api/log/self`
and `/api/log/self/stat` endpoints, with `/api/status` supplying the USD quota
conversion. The approved System Access Token is stored outside Git at
`~/phpretro-openhands/secrets/a6api-billing.json` (owner-only mode 0600):

```json
{"user_id": 123, "access_token": "replace-with-private-console-token"}
```

This account token may grant broader access than billing. The collector only
makes GET requests to four fixed A6API paths, does not follow redirects, and
never logs credentials or raw account responses. It publishes allowlisted
token counts, request IDs, charges, balance and timestamps to the private
`~/phpretro-ops/state/a6api-billing.json` snapshot. No email, IP, prompts or
account profile fields are retained. Collection is bounded to 20 pages of
100 coding consumption records for the current UTC day. Duplicate IDs,
changing pagination, invalid currency/account and failed requests reject the
new snapshot and retain the last good one with a failure marker.

The paused installer enables the read-only **user** `phpretro-billing.timer`
when the credential exists. It refreshes two minutes after each collection.
It does not activate coding timers or remove STOP. Run manually with:

```sh
python3 ~/phpretro-preservation/ops/billing.py
systemctl --user status phpretro-billing.timer
```

The dashboard's OpenHands page displays the provider-reported account daily
charge and balance separately from uncalibrated gateway estimates. Snapshots
older than five minutes, future timestamps and failed collection are stale.

A current same-day observation permits conservative cash admission for an
unknown A6API run using its retained pessimistic token charge and the existing
quote. The cash guard uses the larger of the ledger estimate and provider's
whole-account daily charge, and checks reservations against observed balance.
This neither claims bill settlement nor makes incomplete SDK usage complete.
Token caps, failed receipts, run charges, exact-head reviews and canary scope
remain in force. Stale or absent billing cannot reconcile a new unknown run.
Reported charges may lag and price quotes are not guarantees of final bills.

`portdan_cost_check: user-disabled` records the user's explicit fallback trial:
priced and unknown Portdan ledger rows are excluded from cash admission. They
remain in history with their original cost/usage status and token charges.
Admission still reserves an A6API primary-route quote before dispatch;
fallback transport does not add a Portdan cash check. A6API remains first and
Portdan second. Model/usage checks, tokens and runtime limits still apply.
Restore the Portdan cash guard by removing this policy setting and validating
the runtime again. Remove the billing credential and disable its user timer
to stop collection; revoke the account token in A6API when no longer needed.
