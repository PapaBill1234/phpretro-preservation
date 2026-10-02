# F4 golden-harness evidence

Status: source-backed capture evidence using disposable synthetic data only.

The accepted Stage 3 capture is documented in `docs/golden-capture-evidence.md` and was rerun on 2026-10-02 from the pinned `stage3-original-phpretro/` checkout. Runtime digests were PHP `5.6-apache@sha256:0a40fd273961b99d8afe69a61a68c73c04bc0caa9de384d3b2dd9e7986eec86d` and MariaDB image ID `sha256:7f22313fc130a377a44999965bcb0a08dd5b21e8502824c1b864f792f9bc66ab`.

Stable hashes: public `/` `59f4ec34d6f77b0cdabdf589e6e1d92fc1bd336fceeaad7cf5f48bdad288a6f7`; login `500ebc46334b0c56b7947ee11fc63ce906b6e92f060fced732f12afef258d46d`; authenticated article `978c42d68043995c8c1bc850c5969c8f9948b91e4eca9e1e35d2a473f74f3475`; direct logout `0cb90dfb2de5dcbe9607988833dfa3d704793d11e565ca320ae4e6e39a17efec`; post-logout public page matches public `/`.

Failed login, successful-login redirect, authenticated profile, cookies, and logout completed with expected statuses. Host-port behavior remains UNKNOWN and out of scope. No production traffic, emulator writes, or client handoff is authorized.

Verification compares method, status, redirect, cookies, selected headers, body markers, normalized HTML, and stable hashes after verifying immutable runtime digests. Moving image tags, mismatches, non-synthetic data, or unreviewed runtime repairs fail the run.
