# Golden capture evidence

The disposable Stage 3 harness is in `stage3-run/`. The original source checkout used for the capture is present locally in `stage3-original-phpretro/` and is intentionally not treated as a product source or automatically redistributed. Its file hashes are recorded in `stage3-original-phpretro-sha256.csv`.

Source authority: original Quackster/PHPRetro behavior and routes. The recovered Stage 3 summary records public, login, failed-login, successful-login, profile, article, cookie, redirect, response-hash, and logout captures using synthetic data. The host port remained unverified; internal disposable-container capture is the accepted evidence.

Before F4 acceptance, rerun the harness from a clean checkout, record the resolved immutable runtime image digest, and compare route/method/status/redirect/cookies/selected headers/body markers/normalized HTML and stable hashes. Do not use a moving image tag or production data.

## Clean readiness rerun (2026-10-02)

The disposable stack was recreated from the pinned `stage3-original-phpretro/` checkout with Docker Compose. The PHP runtime resolved to `php:5.6-apache@sha256:0a40fd273961b99d8afe69a61a68c73c04bc0caa9de384d3b2dd9e7986eec86d`; MariaDB resolved locally as `mariadb:10.11` image ID `sha256:7f22313fc130a377a44999965bcb0a08dd5b21e8502824c1b864f792f9bc66ab`.

The clean helper rerun reproduced the recorded stable hashes: public `/` `59f4ec34d6f77b0cdabdf589e6e1d92fc1bd336fceeaad7cf5f48bdad288a6f7`, login page `500ebc46334b0c56b7947ee11fc63ce906b6e92f060fced732f12afef258d46d`, authenticated article `978c42d68043995c8c1bc850c5969c8f9948b91e4eca9e1e35d2a473f74f3475`, direct logout `0cb90dfb2de5dcbe9607988833dfa3d704793d11e565ca320ae4e6e39a17efec`, and post-logout public page `59f4ec34d6f77b0cdabdf589e6e1d92fc1bd336fceeaad7cf5f48bdad288a6f7`. Failed login, successful login redirect, profile, and authenticated content all completed with the expected statuses. The helper emitted a final CRLF shell warning after the captures; it did not affect the captured responses.
