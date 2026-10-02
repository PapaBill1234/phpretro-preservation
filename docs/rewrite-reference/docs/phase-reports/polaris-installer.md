# Polaris installer

`install/polaris.php` is the fresh-environment installer for this project.

It requires `DB_DSN`, `DB_USER`, and `DB_PASS` to be configured for the Polaris database.
It verifies the real Polaris `users` table, creates only the PHPRetro-owned
`phpretro_schema_migrations` ledger, then applies each committed `migrations/*.sql` file in
filename order. A migration is recorded only after all of its SQL statements succeed.

The installer never creates, alters, or deletes Polaris tables. New project schema files,
including the Phase 5b `002_admin_features.sql` migration once merged, are automatically
included on fresh installs.

The legacy `install/install.php` remains in the repository for historical reference but is
not the default install route because it targets Holograph and can modify hotel tables.
