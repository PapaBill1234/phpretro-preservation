#!/bin/sh
set -eu
for path in / /install/index.php /login_popup.php /articles/archive /profile.php /logout.php; do
  echo "--- $path ---"
  curl -sS -D - "http://web$path" -o /tmp/body
  head -c 700 /tmp/body | tr '\r\n' ' '
  echo
 done
