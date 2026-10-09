# PHPRetro OpenHands migration

Implementation is staged under STOP. A source commit is not a validation result.
The live controller, timers, dashboard and interactive Hermes/RDP sessions are
not activated by this change. Merge and resume only after the checks below pass.

## Runtime policy

Subscription Codex prepares bounded briefs; `python3 ops/import_brief.py brief.json`
imports them once under STOP and the controller lock. The current `origin/main`
commit must match `base_commit`. Dependencies must exist and be acyclic; active
or delivered units cannot be replaced, protected paths are forbidden, and
attempt/token counters survive re-import. Unclear/split/nightly/audit work becomes
a durable `state/planning-needed/<ID>.json` handoff. Other ready work can proceed.

Haiku is retired from automatic builders, reviewers and fallbacks. At the user's
request, Sol 6.1 fills its model slot: Luna, DeepSeek, Sol, then DeepSeek; four
attempts remain the ceiling. Review prefers Sol, then DeepSeek, then Luna, subject
to author-family independence. Sol and Luna are both GPT-family models, so only
two independent families are configured. The user has explicitly authorized a
temporary two-family review policy for ordinary and sensitive work. Provider
activation still requires every configured model's capability checks to pass.
Step through OpenCode was tested but every inference request returned HTTP 403,
including both official clients. There is no paid planner or paid weekly audit.

Sol uses Responses for tool calling, as required by the
[official model documentation](https://developers.openai.com/api/docs/models/gpt-6.1-sol).
Its user-supplied merchant quote per million tokens is $0.09 input, $0.45 output,
$0.0045 cache reads and $0 cache writes. Prices remain uncalibrated; no provider
identity, tool capability or actual billing acceptance is implied by this quote.
The unchanged conservative 3M-token reservation is $1.35 at the highest configured
automatic output rate, within the $5 daily quote ceiling before other spending.
Independent review always runs, including for sensitive work: the reviewer must
be a different family from the author, including cached receipts and fallbacks.
The temporary policy waives the third independent-family review; telemetry records
the active family requirement. Set `required_review_families` back to 3 when a
verified third family is configured to restore sensitive-path second review.
F38 remains parked until its original durable replay requirements are delivered.

The installed OpenHands SDK runs trusted inference on the host. Its only agent
tool runs in a disposable Docker container: no network, provider credentials,
host home, Git publication credentials or Docker socket; unprivileged UID,
read-only root, no capabilities, bounded memory/PIDs and build slice. The source
mount is disposable, read-only for reviewers. Tool commands share one heavy
lane and restart their namespace before releasing it. Accepted builder edits
are copied out only after draining the namespace and validating every changed
path. Git commit/push/merge belongs to the trusted controller.

Foundation, quality and nightly synthetic integration run in the same isolated
environment. The worker image preloads pinned Go, Node, lockfile dependencies,
static-analysis tools and a Go vulnerability snapshot. The foundation command
keeps the same checks. Go is pinned to patched 1.26.9, Staticcheck to v0.7.0, Gosec to v2.28.0 and govulncheck to v1.7.0
(the previous Go pin has seven reachable standard-library advisories); CI uses the same
govulncheck version. The database uses the official bulk download and `file://` API:
https://go.dev/doc/security/vuln/database . Rebuild within 48 hours; unknown new
dependencies fail offline rather than enabling tool network access.

Two builder inference sessions are allowed; tool work stays serialized. Aggregate
build limits are CPU 150%, memory high 2200M/max 2800M; inference limits are CPU
50%, memory high 768M/max 1024M, with 512M per worker. Host admission defers below
1.5GiB available, reduces width after sustained CPU/memory pressure, and restores
two after five stable minutes. It never terminates an in-flight paid call simply
to reduce concurrency.

Every paid run has a UUID receipt, reservation, cancellation marker and systemd
unit. The supervisor/recovery drain that unit and its UUID-labelled container
before settlement. Usage is checkpointed after each inference/tool event;
automatic SDK retries and model substitutions are disabled. Each model uses
A6API first and Portdan second among fresh verified routes. A typed transport,
auth, rate-limit or server failure suppresses that provider for the rest of the
session; integrity failures and cancellation never trigger paid fallback. Both
routes preserve the same model and tool API. Each request stays inside the
original receipt deadline and reservation. Each unreported call keeps its own
conservative 1M-token allowance. Provider labels distinguish A6API, Portdan and
mixed sessions. Portdan Luna/DeepSeek costs stay unknown until its prices are
verified; Sol uses the supplied merchant quote. Unknown charges still block later
cash-spend admission. Model identity and
provider usage must be present. Cache buckets are normalized once and reasoning
is not double-counted. Partial/unknown usage keeps the existing conservative
1M-token floor and blocks cash-spend admission until reconciled. Original 3M/unit
and 60M/day token caps and all roadmap/delivery history are retained.

The 5/day spending guard is an estimate in uncalibrated gateway quote units.
It reserves the worst automatic token rate before launch and includes other
reservations. It is not a verified USD ceiling or an account deduction. Provider
balance/price-unit calibration is required before claiming either. The dashboard
uses the same run reader, charged tokens and recorded cost estimates; reservation
and outcome rows are excluded, outcomes are overlaid, and unknown costs stay
unknown. No raw model/tool output is exposed as a live tail.

## Deployment and validation

Keep `/home/ubuntu/phpretro-ops/STOP` present and all three system timers disabled.
The existing secret is loaded by trusted SDK code only; its owner must be ubuntu
and its mode 600. Supported JSON provisioning keys are `a6api_api_key`,
`A6API_API_KEY`, or `a6api.api_key`/`a6api.key`. Portdan keys are private `portdan.openai` and `portdan.deepseek` fields in the
same owned mode-600 file. Never print credentials or put them in the repository.
The SDK environment is pinned by `requirements.lock`; no agent-server or remote
DockerWorkspace is used.

1. Inspect the source diff and complete migration regression coverage, especially
   approval-cache family separation, budget/receipt crash windows, SDK tool round
   trips, timeout/reboot/container cleanup, scope export and adaptive admission.
2. Install resource slices under STOP using `python3 ops/openhands/install_paused.py
   --resources-only` on one line, then build the worker image from this repo
   using `python3 ops/openhands/build_image.py`.
   Run image building with bounded resources; never mount secrets in its context.
3. Run the explicit small paid probes with the existing SDK Python:
   `/home/ubuntu/phpretro-openhands/venv/bin/python ops/openhands/probe_models.py --paid-probes`.
   Use `--provider a6api|portdan` and optional repeated `--model` selectors to check
   only changed routes. Without selectors, all three models and both providers
   are checked independently. At least one fresh passing route per model is
   required for migration readiness; unverified routes are skipped. They use
   durable supervised receipts, record actual usage in the controller
   ledger and preserve reservations on interruption. A failed model is not
   declared capable. Explicit paid probes now include the configured Sol route.
4. Run `python3 ops/openhands/validate.py --provider-evidence
   /home/ubuntu/phpretro-ops/state/openhands-provider-evidence.json` on one line.
   It runs ops, foundation, frontend and container isolation/resource/lifecycle
   checks and writes a pass stamp only for the exact source and Docker image.
   The controller refuses admission if evidence is absent, failed, stale, source
   changes, or the image tag is retargeted.
5. Merge the reviewed migration PR through required GitHub foundation checks,
   update the live checkout, and repeat validation for that exact source. Under
   STOP, run `python3 ops/openhands/install_paused.py`. It backs up source/config,
   installs the dashboard and slices, reloads managers and keeps timers disabled.
   Restart the protected loopback dashboard only after validating its API/auth,
   escaping and telemetry. Alert credentials use a dedicated service environment;
   interactive Hermes `.env` is never loaded.
6. Resume with F39b and F61 as the disjoint two-builder canary, while keeping
   F38 parked. Require exact-head local gates, independent reviews, protected
   GitHub foundation and sequential gated merges. Observe CPU, memory, receipt
   settlement and account balance before continuing F62/F63. Preserve RDP and
   the existing protected HTTPS front door.

## Bounded subscription brief

```json
{
  "schema": "phpretro.brief.v1",
  "planning_source": "subscription-codex",
  "base_commit": "<current 40-character origin/main SHA>",
  "units": [{
    "id": "F61",
    "title": "<bounded behavior and original evidence>",
    "size": "S",
    "depends_on": ["F18"],
    "paths": ["<owned implementation path>", "<owned test path>", "docs/units/F61.md"],
    "acceptance": ["<observable original behavior with source citation>"],
    "tests": ["<independent acceptance command>"],
    "fixtures": ["<synthetic or disposable evidence>"],
    "allowed_models": ["gpt-6-luna", "deepseek-v4.1-flash", "gpt-6.1-sol"],
    "token_cap": 3000000
  }]
}
```

Rollback: create STOP, disable timers, drain supervised workers and UUID
containers, and settle receipts before replacing source/config from the recorded
backup. Retain ledger, reservations, counters, board/delivery history and provider
secrets. Never resume the old paid-planning policy implicitly.

## Provider acceptance finding — 2026-10-09

The explicit probes returned tool calls and counters for DeepSeek. Luna passed
one probe and failed a later call; it needs a fresh successful probe after the
endpoint failure is understood. The requested `claude-haiku-5-5` route returned
`cb/deepseek-v4.1-flash`. It therefore fails model identity and cannot provide an
independent Claude review. The runtime deliberately rejects this response.
Haiku has now been retired; historical receipts and charges remain unchanged.
Keep STOP and disabled timers until a verified third-family replacement passes
the exact identity, tool-call and usage checks. Do not weaken family checks or
count Sol and Luna as distinct families. Provider evidence currently records failure, so no
passing validation stamp or coding canary has been established.

Failed or interrupted probes retain conservative ledger charges and unknown
costs. The daily spending guard blocks days containing unresolved unknown usage;
do not reset counters or edit historical ledger lines to clear that condition.
Quoted rates are uncalibrated and are not proof of a five-dollar account limit.

The refreshed foundation scanner requires HTTPS-only session cookies. Its sole
synthetic caller was updated, and normalized port values are logged numerically.
These security changes do not establish durable storage or product completion.
