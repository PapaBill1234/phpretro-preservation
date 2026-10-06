#!/usr/bin/env bash
# ops/setup/configure-profiles.sh
#
# Configure the headless builder/reviewer/planner/auditor profiles so no run can
# ever wait on a prompt. Idempotent; run as the repo user.
#
#   approvals.single_query_mode deny   headless -z runs can never hang: a
#                                      dangerous command is refused instantly
#                                      instead of waiting for an answer.
#   approvals.deny                     destructive globs. These fire BEFORE
#                                      --yolo and before approvals.mode=off, so
#                                      they are the one approval control a
#                                      headless agent cannot dodge.
#   command_allowlist                  git/go/gh/make so ordinary work never
#                                      prompts.
#   security.protected_instruction_files true (AGENTS.md and skills stay
#                                      guarded while they are edited by hand).
#
# The real boundaries remain outside the model:
#   * ops/hooks/pre-push rejects pushes to main and any force push;
#   * builders run with their worktree as cwd only;
#   * the GitHub token is scoped to this repository;
#   * branch protection forbids force-push and deletion of main;
#   * secrets live in ~/.hermes/.env, outside every worktree.
set -euo pipefail

PROFILES=(builder reviewer planner auditor)
REPO="${PHPRETRO_REPO:-$HOME/phpretro-preservation}"

DENY='["git push --force*", "git push -f *", "git push --delete*", "git push *refs/heads/main*", "git reset --hard*", "git checkout main*", "git update-ref -d*", "git filter-branch*", "git branch -D main*", "rm -rf /*", "rm -rf ~*", "rm -rf $HOME*", "rm -rf ..*", "rm -rf /home/ubuntu*", "gh auth*", "gh repo delete*", "gh api *-X DELETE*", "sudo*", "dd *of=/dev/*", "chmod -R 777*"]'

ALLOW='["git status", "git fetch", "git add", "git commit", "git diff", "git rebase", "git log", "git worktree list", "go build", "go vet", "go test", "gofmt", "staticcheck", "gosec", "govulncheck", "gh pr", "make", "bash scripts/check.sh"]'

for p in "${PROFILES[@]}"; do
  home="$HOME/.hermes/profiles/$p"
  [ -d "$home" ] || { echo "no such profile: $p" >&2; continue; }
  HERMES_HOME="$home" hermes config set approvals.mode smart >/dev/null
  HERMES_HOME="$home" hermes config set approvals.single_query_mode deny >/dev/null
  HERMES_HOME="$home" hermes config set approvals.cron_mode deny >/dev/null
  HERMES_HOME="$home" hermes config set approvals.unattended_mode deny >/dev/null
  HERMES_HOME="$home" hermes config set approvals.timeout 10 >/dev/null
  HERMES_HOME="$home" hermes config set approvals.deny "$DENY" >/dev/null
  HERMES_HOME="$home" hermes config set command_allowlist "$ALLOW" >/dev/null
  HERMES_HOME="$home" hermes config set security.protected_instruction_files true >/dev/null
  HERMES_HOME="$home" hermes config set security.redact_secrets true >/dev/null
  HERMES_HOME="$home" hermes config set display.streaming false >/dev/null
  echo "configured $p"
done

# Hermes resolves `-s <name>` in the active profile's skills dir, so each role
# skill is installed there under its registered name.
install -d "$HOME/.hermes/profiles/builder/skills/unit-builder"
install -d "$HOME/.hermes/profiles/reviewer/skills/unit-reviewer"
install -d "$HOME/.hermes/profiles/planner/skills/unit-planner"
install -d "$HOME/.hermes/profiles/auditor/skills/unit-auditor"
install -m 0644 "$REPO/ops/skills/builder/SKILL.md" \
  "$HOME/.hermes/profiles/builder/skills/unit-builder/SKILL.md"
install -m 0644 "$REPO/ops/skills/reviewer/SKILL.md" \
  "$HOME/.hermes/profiles/reviewer/skills/unit-reviewer/SKILL.md"
install -m 0644 "$REPO/ops/skills/planner/SKILL.md" \
  "$HOME/.hermes/profiles/planner/skills/unit-planner/SKILL.md"
install -m 0644 "$REPO/ops/skills/auditor/SKILL.md" \
  "$HOME/.hermes/profiles/auditor/skills/unit-auditor/SKILL.md"
echo "role skills installed"

echo "profiles configured: ${PROFILES[*]}"
