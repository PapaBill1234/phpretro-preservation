# PHP 8.5 compatibility verification

**Branch:** `fix/php85-compatibility`  
**Runtime verified:** PHP 8.5.10 (XAMPP CLI and CGI)  
**Scope:** every tracked PHP source file in the repository.

## Result

PHP 8.5 lint passed for all 261 PHP files with `E_ALL` enabled. The pass initially
reported three PHP 8.5 compatibility warnings in three files. All are fixed and the
repeat pass emitted zero warnings, deprecations, or syntax errors.

```powershell
$files = Get-ChildItem -Recurse -File -Filter *.php
foreach ($file in $files) {
    C:\xampp\php\php.exe -d error_reporting=E_ALL -d display_errors=1 -l $file.FullName
}
```

Final result: `FILES=261`, `LINT_FAILURES=0`, `WARNINGS_OR_DEPRECATIONS=0`.

## Files changed

| File | Before | After | Reason |
| --- | --- | --- | --- |
| `habblet/mytagslist.php` | `(double) microtime()` | `(float) microtime()` | PHP 8.5 deprecates non-canonical casts. |
| `includes/languages/en.php` | 11 `case "value";` labels | 11 `case "value":` labels | PHP 8.5 deprecates a semicolon after a `case` label. |
| `install/migrate_functions.php` | `default: continue; break;` inside `switch` | `default: break;` | Removed the warning that `continue` in a `switch` is equivalent to `break`; behavior is unchanged. |
| `PHPRetro-Modernization-Plan.md` | PHP 8.3 target labels | PHP 8.5 target labels | Synchronizes the tracked plan with the supplied PHP 8.5 plan. |

The XAMPP runtime configuration also contained `E_STRICT` in `error_reporting`. PHP 8.4
deprecated that constant, so the local `C:\xampp\php\php.ini` now uses
`E_ALL & ~E_DEPRECATED`. This server configuration file is intentionally outside this PR.

## Compatibility checklist

Reviewed against the official PHP migration references for [PHP 8.4 deprecations](https://www.php.net/manual/en/migration84.deprecated.php), [PHP 8.4 incompatible changes](https://www.php.net/manual/en/migration84.incompatible.php), [PHP 8.5 deprecations](https://www.php.net/manual/en/migration85.deprecated.php), and [PHP 8.5 incompatible changes](https://www.php.net/manual/en/migration85.incompatible.php).

Static searches found no remaining use of the removed or deprecated APIs relevant to this
application, including `CURLOPT_BINARYTRANSFER`, `mysqli_ping`/`kill`/`refresh`,
`lcg_value`, `curl_close`, `curl_share_close`, `finfo_close`, `date_sunrise`,
`date_sunset`, `imap_*`, `oci_*`, `pspell_*`, `E_STRICT`, `trigger_error(...,
E_USER_ERROR)`, legacy session SID INI settings, `DatePeriod`'s string constructor,
`__sleep`, `__wakeup`, `__debugInfo`, `disable_classes`, and `report_memleaks`.

The audit also checked for non-canonical casts and semicolon-form `case` labels. The
only findings were the fixed entries above. Regular `case value:` labels remain valid.

## Live environment

The XAMPP CGI server was verified with PHP 8.5.10 and active `curl`, `mbstring`,
`mysqli`, `openssl`, and `pdo_mysql` extensions. The application home route returns
HTTP 200. Full authenticated and database-backed flow testing remains dependent on the
deployment's application configuration and test database.
