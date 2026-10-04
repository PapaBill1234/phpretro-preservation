# F16 public login route evidence

Status: source-backed evidence and synthetic golden test only. No product route, authentication, or session behavior is implemented here.

## Scope

This unit records the original public `GET /login_popup.php` source and one retained disposable capture. The capture is synthetic disposable environment evidence, not production traffic. Its raw body and headers remain local and are not committed.

## Source verification

Read-only original source: `stage3-original-phpretro/login_popup.php`, SHA-256 `c813f9634aab1f82be117b0e13465d1916d944fa6efdbe624032875e82799f7c`; it matches the corresponding entry in `docs/stage3-original-phpretro-sha256.csv`. The manifest's CRLF-byte SHA-256 is `aa72ca4d73794df6d17e704d532c8efb6330bfbfdb727ad85ec748b28dc75081`; the same tracked Git blob checked out with LF line endings has SHA-256 `2a995ca39bb10c37d0e9ea4349f072382dce9e476f01acf0027eb93b6fc215eb`. These hashes differ only because of CRLF/LF line endings; the tracked blob and source entry are unchanged. Relevant source lines:

- Line 18 requires `./includes/core.php`.
- Lines 24-27 initialize `$_SESSION['login']['enabled']` and `tries` only when `$_SESSION['login']` is unset.
- Line 32 sends users with `$user->id > 0` to `PATH . "/client"` via `Location`.
- Lines 68-78 define a POST form targeting `PATH . "/account/submit"`, with `username` text and `password` password fields.
- Line 79 gates the CAPTCHA markup on `tries > 4` and `site_capcha == "1"`.
- Line 114 defines the `login-submit-button`; line 127 defines `forgot-password`.
- Line 34 requires `./templates/login_header.php`; line 160 requires `./templates/login_footer.php`.

These are source facts only. They do not establish a production authentication, session, or CAPTCHA contract.

## Capture provenance and observed response

The local, credential-free manifest is `C:\Users\Karim\AppData\Local\hermes-phpretro\capture-evidence\F16-login-20261004\capture-manifest.json` (SHA-256 `c175ad01dfd5a7cd2ca1c91b6a296c7188edd86b396cb59ae9a583c8195f770e`). Its recorded source hash matches the verified source above. The local body `login_page.body` is 7,940 bytes with SHA-256 `500ebc46334b0c56b7947ee11fc63ce906b6e92f060fced732f12afef258d46d`, matching the accepted F4 login digest. The local response headers file `login_page.headers` has SHA-256 `a5d58f29017c1b62f794ef885b4eb77d6bba6caae648bc2dccb15e0c7151e6de`.

The `stage3-run/helper.sh` sequence initializes the disposable install, then calls `capture public_root /` followed by `capture login_page /login_popup.php`. `capture` invokes curl with the same cookie jar for both `-c` and `-b`, uses `-L` to follow redirects, records headers with `-D`, and writes the response body separately. Thus the login capture is a GET after install and the public-root request, using the same cookie jar; its recorded headers/body and status describe the final response after redirects.

Observed final response: `200 OK`, no `Location`, no `Set-Cookie` header, `Content-Type: text/html; charset=UTF-8`, and `Cache-Control: no-store, no-cache, must-revalidate, post-check=0, pre-check=0`. The body includes `login-habblet`, `login-username`, `login-password`, `login-submit-button`, `forgot-password`, and `account/submit`. Runtime image identifiers are recorded in the local manifest. Absence of `Set-Cookie` in this response does not establish whether a fresh session was absent; cookie-jar contents and session internals are not asserted here.

## Synthetic test boundary

`tests/golden/login_route_test.go` uses a clearly synthetic body and synthetic response expectations modeled on the observed status, selected headers, and markers. It checks comparator acceptance and rejection of changed status, redirect, selected header, missing marker, and synthetic body hash. The real capture digest is provenance only and is never used as the expected hash of synthetic bytes. The test does not read local capture files and requires no Docker in CI.

## Explicit unknowns

- Whether this request began with a fresh session, and the session/cookie state before or after the request.
- Runtime values of `$user->id`, session `tries`, and `site_capcha`; therefore whether the authenticated redirect or CAPTCHA branch was active in the capture.
- The behavior of `/account/submit`, authentication outcomes, and production behavior.
- Any production database, schema, user, credential, or traffic characteristics; none are inferred from this disposable capture.
