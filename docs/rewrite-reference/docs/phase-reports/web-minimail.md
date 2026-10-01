# Website minimail (PHP CMS mailbox)

## Result

Branch: `feature/web-minimail`. Base: `096a47d` (`feature/phase6-habblet-batch3`, PR #21 still open). This PR is stacked on batch 3 and is not merged or deployed.

Minimail is restored as a **website-owned** mailbox. PolarIS `messenger_messages` / `messenger_members` / `messenger_offline` are chat, not mail, and are never read or written. Live-game notify is a separate no-op hook.

## Schema (project-owned)

| Table | Source | Columns used |
| --- | --- | --- |
| `phpretro_emulator_outbox` | `migrations/003_web_minimail.sql` | `id`, `event_type`, `payload_json`, `status`, `created_at`, `processed_at` |
| `phpretro_minimail` | `migrations/003_web_minimail.sql` | `id`, `sender_id`, `recipient_id`, `subject`, `body`, `conversation_id`, `sent_at`, `read_at`, `deleted`, `deleted_at`, `synced_at` |
| `phpretro_user_reports` | `migrations/002_admin_features.sql` | reporter/reported/reason/evidence for minimail reports |
| `users` | `CleanDB.sql:55189` | `id`, `username`, `look`, `online` |
| `messenger_friendships` | `CleanDB.sql:52763` | `user_one_id`, `user_two_id` (send allowlist; report unfriends both directions) |
| `messenger_friendrequests` | `CleanDB.sql:52750` | cleared on report |

Verified absent (not invented, not queried):

```sh
grep -n "CREATE TABLE IF NOT EXISTS \`messenger_" references/schema/CleanDB.sql
# messenger_conversations 52734, messenger_members 52780, messenger_messages 52801,
# messenger_offline 52818 — no subject, trash, or conversation mailbox columns.
```

`synced_at` is NULL on every website write. Outbox rows stay `pending` because `PhpretroLiveSync::notifyLiveGame()` is empty.

## Behaviour

| File | Result |
| --- | --- |
| `minimail_loadMessages.php` | Inbox / sent / trash / conversation lists. Bound paging. Escaped subjects/names. Original folder DOM and compose control. |
| `minimail_loadMessage.php` | Owner-or-recipient only. Inbox open sets `read_at` and records `minimail.read`. |
| `minimail_sendMessage.php` | Friends only, one row per recipient, subject+body, reply allocates `conversation_id`. Records `minimail.sent`. No email (`email_minimail` is not a PolarIS column). |
| `minimail_deleteMessage.php` | Recipient-only. First delete sets `deleted=1`; second purge. |
| `minimail_undeleteMessage.php` | Recipient trash only. |
| `minimail_emptyTrash.php` | Recipient-scoped purge. |
| `minimail_confirmReport.php` | Blocks reporting your own copy; escapes names. |
| `minimail_report.php` | Writes `phpretro_user_reports`, removes both friendship directions, deletes the recipient copy. |
| `minimail_preview.php` | Escaped BBCode preview. No SQL. |
| `minimail_recipients.php` | Unchanged (already PolarIS friendships). |
| `me.php` | Restores the `#minimail` widget and compose form the legacy JS already loads for `page['id']=me`. |

Record vs notify: every write calls `record()` then `notifyLiveGame()`. Step 2 is a no-op today.

## Gaps still 501 / not invented

- PolarIS messenger is not a mailbox and is not used.
- No website email notifications (no `email_minimail` column on `users`).
- Custom packets / Java consumer are out of scope.

## Validation

```sh
php tests/web_minimail_test.php
php tests/phase6_habblet_batch1_test.php
```
