# GitHub merge policy

The repository uses pull requests for all changes entering `main`. The `foundation` status check, conversation resolution, administrator enforcement, and force-push/deletion protections remain enabled.

The repository owner has explicitly authorized the Sol coordinator to merge reviewed pull requests through the GitHub API. The `main` branch therefore requires zero approving reviews: the pull request boundary and required checks remain mandatory, while a second human approval is not required for this owner-authorized single-operator workflow. Sol must inspect the diff, required checks, scope, and secret scan before merging and record the merge in the run state.

Changing this policy requires an explicit owner instruction and a documented pull request. Product and production gates remain independent and closed unless separately decided.
