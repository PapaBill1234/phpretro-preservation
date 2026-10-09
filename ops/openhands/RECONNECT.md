# Provider recovery

The trusted runner retries a failed inference request inside the existing SDK
conversation. Previously completed tool actions and messages remain in memory;
reconnection does not send a new brief or create another builder attempt.

A6API remains first, followed by admitted Portdan routes. If all routes fail
with connection, timeout, rate-limit or server errors, the runner waits five
seconds and reconnects in primary-first order. A second reconnect waits fifteen
seconds. There are at most three rounds, each with one request per admitted
route. A successful fallback stays selected for that session. Authentication,
permission and missing-model errors may fall over once, but never reconnect.
Identity/usage integrity failures, cancellation, bugs and allowance exhaustion
never retry. The supervisor's original deadline and cancellation marker apply
throughout; waiting checks cancellation every second.

Each request is durably recorded before transport starts. The existing SDK
input limit is 65,536 tokens, its output limit is 4,096, and the runner rejects
context estimates above 60,000 before sending. New versioned checkpoints reserve
69,632 tokens for each request with unknown usage, plus all observed usage.
This is a conservative estimate under the enforced request limits, not a
provider invoice or a claim that usage is complete. Every retry consumes its
own reservation. Provider tokenization/billing anomalies can still exceed an
estimate; observed usage is never capped or discarded, and existing controller
guards stop on overspend. A6API account billing continues to govern spending.

The supervisor validates and preserves only typed accounting metadata. The
controller accepts the bounded estimate only when the schema, fixed ceiling,
started/completed/unknown counts, known usage count and total agree. Legacy,
missing or unusable checkpoints retain pessimistic accounting. Historical
charges are never recalculated, and token/cash caps are unchanged. An incomplete
usage record stays incomplete even when the resumed review succeeds.

This recovers temporary failures within one live worker. It does not revive an
exited worker, reopen an old review, reuse approval for another Git head, or
restart indefinitely during a long outage. Exhaustion leaves the controller to
settle the receipt and pause/defer under its existing rules. F61's old failed
review and allowance are unaffected by installing this change.

Offline regression tests inject failures after a completed tool action, fail
both providers, and finish on the recovered primary. The real SDK must preserve
the tool result and DeepSeek reasoning across that retry; exactly one tool
execution occurs. No paid availability probe is part of these tests.
