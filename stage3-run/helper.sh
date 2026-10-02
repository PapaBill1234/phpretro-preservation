#!/bin/sh
set -eu
jar=/tmp/stage3.cookies
base=http://web
install() {
  curl -sS -c "$jar" -b "$jar" "$base/install/index.php" -o /dev/null
  curl -sS -c "$jar" -b "$jar" "$base/install/install.php" -o /dev/null
  curl -sS -c "$jar" -b "$jar" -d 'page=1&s_site_language=en&submit=Continue' "$base/install/install.php" -o /dev/null
  curl -sS -c "$jar" -b "$jar" -d 'page=2&submit=Continue' "$base/install/install.php" -o /dev/null
  curl -sS -c "$jar" -b "$jar" --data-urlencode 'page=3' --data-urlencode 'db_prefix=cms_' --data-urlencode 'db_server=mysql' --data-urlencode 'db_host=db' --data-urlencode 'db_port=3306' --data-urlencode 'db_username=phpretro' --data-urlencode 'db_password=stage3pass' --data-urlencode 'db_name=phpretro' --data-urlencode 'submit=Continue' "$base/install/install.php" -o /dev/null
  curl -sS -c "$jar" -b "$jar" --data-urlencode 'page=4' --data-urlencode 's_site_name=Stage3 Hotel' --data-urlencode 's_site_shortname=Stage3' --data-urlencode 's_site_path=http://web' --data-urlencode 's_hotel_server=holograph' --data-urlencode 'submit=Continue' "$base/install/install.php" -o /dev/null
  curl -sS -c "$jar" -b "$jar" --data-urlencode 'page=5' --data-urlencode 'admin_username=stage3admin' --data-urlencode 'admin_password=Stage3Pass!' --data-urlencode 'admin_email=stage3@example.invalid' --data-urlencode 'submit=Continue' "$base/install/install.php" -o /dev/null
  curl -sS -c "$jar" -b "$jar" -d 'page=6&submit=Continue' "$base/install/install.php" -o /dev/null
  cp /var/www/html/install/config.php /var/www/html/includes/config.php
}
capture() {
  name=$1; url=$2; shift 2
  curl -sS -L -c "$jar" -b "$jar" -D "/tmp/$name.headers" "$@" "$base$url" -o "/tmp/$name.body"
  status=$(awk 'toupper($1) ~ /^HTTP\// {code=$2} END {print code}' "/tmp/$name.headers")
  location=$(awk 'tolower($1)=="location:" {print $2}' "/tmp/$name.headers" | tail -1 | tr -d '\r')
  hash=$(sha256sum "/tmp/$name.body" | cut -d' ' -f1)
  printf '%s status=%s location=%s sha256=%s bytes=%s\n' "$name" "$status" "${location:-}" "$hash" "$(wc -c < /tmp/$name.body)"
}
capture_raw() {
  name=$1; url=$2; shift 2
  curl -sS -c "$jar" -b "$jar" -D "/tmp/$name.headers" "$@" "$base$url" -o "/tmp/$name.body"
  status=$(awk 'toupper($1) ~ /^HTTP\// {code=$2} END {print code}' "/tmp/$name.headers")
  location=$(awk 'tolower($1)=="location:" {print $2}' "/tmp/$name.headers" | tail -1 | tr -d '\r')
  hash=$(sha256sum "/tmp/$name.body" | cut -d' ' -f1)
  printf '%s status=%s location=%s sha256=%s bytes=%s\n' "$name" "$status" "${location:-}" "$hash" "$(wc -c < /tmp/$name.body)"
}
install
capture public_root /
capture login_page /login_popup.php
capture content_read /articles/archive
capture_raw login_failed /account/submit -X POST --data 'username=stage3admin&password=wrong-stage3-password&page=0&_login_remember_me=0'
capture_raw login_submit /account/submit -X POST --data 'username=stage3admin&password=Stage3Pass!&page=0&_login_remember_me=0'
capture profile_read /profile
capture authenticated_content /articles/archive
capture logout /logout.php
capture post_logout /
