# GitHub merge policy

The repository uses pull requests for all changes entering `main`. The `foundation` status check, conversation resolution, administrator enforcement, and force-push/deletion protections remain enabled.

The Luna coordinator may merge a reviewed pull request through the GitHub API under the repository's existing authority. The `main` branch therefore requires zero approving reviews: the pull request boundary, independent review, delegated development-scope approval where applicable, and required checks remain mandatory. The coordinator must inspect the diff, required checks, scope, and secret scan before merging and record the merge in the run state; review and delegated approval do not grant merge authority.

Changing this policy requires a documented pull request under the repository's existing review and CI protections. The project is development-only with no production environment or production gate: authentication, sessions, cookies, CSRF, audit-event design, schema, migrations, and dependent units are open for development use under exact-unit briefs, independent review, and CI. Real credentials, secrets or key material, real user data, live outside systems, and weakening review, CI, branch-protection, or approval gates remain closed.
