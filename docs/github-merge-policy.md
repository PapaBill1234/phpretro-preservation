# GitHub merge policy

The repository uses pull requests for all changes entering `main`. The `foundation` status check, conversation resolution, administrator enforcement, and force-push/deletion protections remain enabled.

The repository owner has explicitly authorized the Sol coordinator to merge reviewed pull requests through the GitHub API. The `main` branch therefore requires zero approving reviews: the pull request boundary and required checks remain mandatory, while a second human approval is not required for this owner-authorized single-operator workflow. Sol must inspect the diff, required checks, scope, and secret scan before merging and record the merge in the run state.

Changing this policy requires a documented pull request under the repository's existing review and CI protections. The project is development-only with no production environment: authentication, sessions, cookies, CSRF, audit-event design, schema, migrations, and dependent units are open for development use under exact-unit briefs, independent review, and CI. Production enablement, real credentials, secrets or key material, real user data, live outside systems, and weakening review, CI, branch-protection, or approval gates remain closed.
