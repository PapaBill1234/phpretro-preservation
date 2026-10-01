# Golden capture evidence

The disposable Stage 3 harness is in `stage3-run/`. The original source checkout used for the capture is present locally in `stage3-original-phpretro/` and is intentionally not treated as a product source or automatically redistributed. Its file hashes are recorded in `stage3-original-phpretro-sha256.csv`.

Source authority: original Quackster/PHPRetro behavior and routes. The recovered Stage 3 summary records public, login, failed-login, successful-login, profile, article, cookie, redirect, response-hash, and logout captures using synthetic data. The host port remained unverified; internal disposable-container capture is the accepted evidence.

Before F4 acceptance, rerun the harness from a clean checkout, record the resolved immutable runtime image digest, and compare route/method/status/redirect/cookies/selected headers/body markers/normalized HTML and stable hashes. Do not use a moving image tag or production data.
