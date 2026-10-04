# F15 public GET / evidence

Status: source-backed evidence and synthetic test only. No production route is implemented here.

## Verified original source

The original Stage 3 checkout is outside the tracked Go product source and was read-only for this verification. Its bytes match `docs/stage3-original-phpretro-sha256.csv`:

| File | Manifest SHA-256 | Verified SHA-256 | Result |
| --- | --- | --- | --- |
| `stage3-original-phpretro/index.php` | `961e23e4e2ce4e8b367bb7ea4dddd672e334598f0f91701756cbfd80af74228b` | `961e23e4e2ce4e8b367bb7ea4dddd672e334598f0f91701756cbfd80af74228b` | match |
| `stage3-original-phpretro/landing.php` | `c40531f22d5287f6e7a4a4b6b45bcf4b7349f4b19600bda3745de84a6e1a7f5c` | `c40531f22d5287f6e7a4a4b6b45bcf4b7349f4b19600bda3745de84a6e1a7f5c` | match |

Relevant source citations, using the verified files and `nl -ba` line numbering:

- `index.php:18` requires `./includes/core.php`.
- `index.php:20` requires `./landing.php` and exits when `$settings->find("site_new_landing_page") == "1"`.
- `index.php:28` sends an authenticated user to `PATH . "/me"`.
- `landing.php:18` requires `./includes/core.php`.
- `landing.php:26` sends an authenticated user to `PATH . "/me"`.

These are source facts. They do not select a branch for the captured request because the captured setting value is not recorded here.

## Captured public-root provenance

The accepted disposable synthetic capture records:

- Request path: `/`
- Method: captured by `stage3-run/helper.sh` as a GET because `capture public_root /` supplies no `-X` or request body.
- Body SHA-256: `59f4ec34d6f77b0cdabdf589e6e1d92fc1bd336fceeaad7cf5f48bdad288a6f7`

The hash is recorded in `docs/golden-capture-evidence.md` and `docs/evidence/F4-golden-harness.md`. `stage3-run/helper.sh:18-22` shows that the capture follows redirects (`curl -L`), writes headers and body separately, and hashes the final body. `tests/golden/golden.go:21-42` is the comparator for method, status, redirect, cookies, selected headers, body markers, and optional body hash.

## Explicit unknowns

The tracked capture record does not preserve the raw response body. Therefore the following remain UNKNOWN for the captured public `/` response:

- final status code;
- redirect or `Location` value;
- cookies;
- selected headers;
- body markers or HTML contents;
- captured `site_new_landing_page` value and selected source branch;
- any runtime or schema characteristics implied by the body hash.

The accepted hash alone is not evidence for any of those values. The capture source is synthetic disposable data, not production traffic.

## Synthetic test boundary

`tests/golden/public_route_test.go` creates an independent, self-contained fixture with explicitly labeled synthetic status, headers, body, marker, and body hash. It checks that `golden.Compare` accepts the unchanged fixture and rejects a deliberate body mismatch. The accepted capture hash is retained as provenance metadata/value only; it is not supplied as the expected hash for the synthetic body. Consequently, this test does not reproduce or verify the unavailable capture bytes.
