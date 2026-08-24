# GitHub App GitOps Automation

## Purpose

This document is the **reproducible implementation guide** for the GitHub App used by the AI Platform source repository to update the separate GitOps repository and open deployment pull requests as:

```text
ai-platform-gitops-bot[bot]
```

This guide covers the full lifecycle:

```text
create GitHub App
    ↓
configure least-privilege permissions
    ↓
install App on ai-platform-gitops
    ↓
generate private key
    ↓
store GitHub Actions credentials
    ↓
generate short-lived installation token
    ↓
clone GitOps repository
    ↓
create automation branch
    ↓
update immutable image digests
    ↓
commit as GitHub App bot
    ↓
push branch
    ↓
open pull request
    ↓
GitOps validation
    ↓
human merge
```

A new engineer should be able to rebuild this automation from zero using this document.

---

# 1. Implementation Context

## Source Repository

Local:

```text
/mnt/data/ai-platform-operator
```

Remote:

```text
git@github.com:anselem-okeke/ai-platform-operator.git
```

The GitHub Actions release workflow runs from this repository.

## GitOps Repository

Local:

```text
/mnt/data/ai-platform-gitops
```

Remote:

```text
https://github.com/anselem-okeke/ai-platform-gitops.git
```

The GitHub App receives access to this repository.

## GitHub App

Expected GitHub App / bot identity:

```text
ai-platform-gitops-bot
```

GitHub renders installation actions from the App as:

```text
ai-platform-gitops-bot[bot]
```

## Current Release Workflow

Expected source workflow:

```text
.github/workflows/release-images.yml
```

Before rebuilding or changing credentials, inspect the actual workflow:

```bash
cd /mnt/data/ai-platform-operator

grep -n -A40 -B10 \
  'create-github-app-token' \
  .github/workflows/release-images.yml
```

Also inspect every App-related variable/secret reference:

```bash
grep -nE \
  'app-id|client-id|private-key|APP_|GITOPS_|create-github-app-token|GH_TOKEN|GITHUB_TOKEN' \
  .github/workflows/release-images.yml
```

**Important:** use the exact secret/variable names already referenced by the workflow unless intentionally migrating them.

---

# 2. Why the Platform Uses a GitHub App

The release workflow needs to modify a **different repository**:

```text
ai-platform-operator
        |
        | release workflow
        v
ai-platform-gitops
```

The default source-repository `GITHUB_TOKEN` is not a general-purpose credential for modifying another repository.

The platform therefore uses a GitHub App installation token.

Benefits:

```text
short-lived credential
repository-scoped installation
machine identity
least-privilege permissions
independent revocation
no dependency on a human PAT
auditable bot commits and pull requests
```

This is an important software supply-chain boundary.

---

# 3. Required Permissions

The App only needs to:

1. clone/read the GitOps repository
2. create a branch
3. commit/push changed manifests
4. create a pull request

Use the minimum repository permissions:

| GitHub App repository permission | Access | Why |
|---|---|---|
| **Contents** | **Read & write** | Clone repository, create commits, push branch |
| **Pull requests** | **Read & write** | Create and inspect GitOps PR |
| **Metadata** | Read | Automatically available/required for repository metadata |

Do **not** grant these unless the implementation later needs them:

```text
Administration
Actions
Workflows
Secrets
Environments
Deployments
Issues
Checks
Packages
Members
Organization administration
```

The current bot updates Kustomize files, not GitHub Actions workflow files, so it should not require `Workflows: write`.

---

# 4. Create the GitHub App

GitHub UI navigation for a personal-account-owned App:

```text
GitHub
  → profile picture
  → Settings
  → Developer settings
  → GitHub Apps
  → New GitHub App
```

For an organization-owned App:

```text
GitHub
  → Your organizations
  → <organization>
  → Settings
  → Developer settings / GitHub Apps
```

## 4.1 GitHub App Name

Set:

```text
ai-platform-gitops-bot
```

GitHub App names must be globally unique. If the exact name is unavailable, use a clearly related unique name and update the documentation/workflow expectations.

## 4.2 Homepage URL

Use a stable project URL.

Recommended:

```text
https://github.com/anselem-okeke/ai-platform-gitops
```

or the source repository URL if that is the project landing page.

## 4.3 User Authorization

This App acts as itself through an **installation access token**.

It does not need user OAuth authorization for this workflow.

Leave user-authorization/callback settings unused unless a future feature explicitly requires them.

## 4.4 Setup URL

Not required for this bot.

Leave blank unless you later build an installation setup application.

## 4.5 Webhooks

The current bot is invoked by GitHub Actions and does not need an inbound webhook service.

Recommended:

```text
Webhook: inactive
```

This avoids creating an unused webhook endpoint and secret.

If webhooks are enabled in the current real App, document the reason and endpoint separately.

## 4.6 Repository Permissions

Under **Permissions → Repository permissions** configure:

```text
Contents       Read & write
Pull requests  Read & write
```

Leave everything else at:

```text
No access
```

unless explicitly required.

## 4.7 Installation Scope

For a private/internal project App owned by the same account, choose:

```text
Only on this account
```

Then create the App.

---

# 5. Record the App Identity

After creation, open the GitHub App settings page.

Record the non-secret identifiers required by the workflow.

Depending on the version/configuration of `actions/create-github-app-token`, the workflow may use either:

```text
Client ID
```

or the legacy:

```text
App ID
```

The project pinned `actions/create-github-app-token` to:

```text
bcd2ba49218906704ab6c1aa796996da409d3eb1
```

which corresponds to the v3.2.0 line used during implementation.

Current v3 documentation recommends `client-id`; `app-id` remains supported for compatibility.

## Verify What the Project Workflow Uses

```bash
cd /mnt/data/ai-platform-operator

grep -nE \
  'client-id:|app-id:|private-key:' \
  .github/workflows/release-images.yml
```

Do not guess. Match the repository workflow.

---

# 6. Generate the GitHub App Private Key

Navigate:

```text
GitHub App
  → General
  → Private keys
  → Generate a private key
```

GitHub downloads a PEM file.

Example local filename:

```text
ai-platform-gitops-bot.<date>.private-key.pem
```

## Security Rules

The PEM file is a private credential.

Never:

```text
git add <private-key>.pem
paste it into documentation
paste it into a GitHub issue
print it in CI logs
store it in the GitOps repository
store it in a Kubernetes manifest
```

Verify repository ignore rules:

```bash
cd /mnt/data/ai-platform-operator

git check-ignore -v /path/to/private-key.pem || true
```

The source and GitOps repositories should ignore:

```text
*.pem
*.key
.local/
.env
```

Store the key only long enough to place it into the approved secret store.

---

# 7. Install the GitHub App on the GitOps Repository

Creating a GitHub App does **not** install it.

Navigate from the App settings:

```text
GitHub App
  → Install App
```

Choose the owning account:

```text
anselem-okeke
```

Select:

```text
Only select repositories
```

Select:

```text
ai-platform-gitops
```

Complete installation.

## Why Only the GitOps Repository

The bot's purpose is:

```text
source CI
  → update GitOps desired state
```

It does not need write access to every repository on the account.

---

# 8. Validate the Installation in the GitHub UI

Open:

```text
GitHub
  → Settings
  → Applications
  → Installed GitHub Apps
```

Select:

```text
ai-platform-gitops-bot
```

Verify repository access includes:

```text
ai-platform-gitops
```

Verify permissions include:

```text
Contents: Read and write
Pull requests: Read and write
```

This exact check is critical.

A real implementation failure occurred because token creation could not find a valid repository installation.

---

# 9. Configure Source Repository Variables and Secrets

The source workflow runs in:

```text
anselem-okeke/ai-platform-operator
```

Navigate:

```text
ai-platform-operator
  → Settings
  → Secrets and variables
  → Actions
```

## 9.1 App Identifier

If the workflow uses a GitHub Actions **variable**, store the Client ID/App ID under the exact name referenced in `release-images.yml`.

Example canonical naming:

```text
Variable:
GITOPS_APP_CLIENT_ID
```

or, if the workflow uses legacy App ID:

```text
Variable:
GITOPS_APP_ID
```

## 9.2 Private Key

Create a repository **secret** containing the entire PEM file contents.

Example canonical name:

```text
GITOPS_APP_PRIVATE_KEY
```

Value shape:

```text
-----BEGIN RSA PRIVATE KEY-----
...
-----END RSA PRIVATE KEY-----
```

or the key format GitHub generated.

Do not remove newlines unless the workflow/action intentionally supports escaped newline handling.

## Verify Exact Existing Names

```bash
cd /mnt/data/ai-platform-operator

grep -nE \
  '\$\{\{ *(secrets|vars)\.[A-Za-z0-9_]+' \
  .github/workflows/release-images.yml
```

Use the names shown there.

---

# 10. Generate a Short-Lived Installation Token in GitHub Actions

The project uses:

```text
actions/create-github-app-token
```

Pinned commit:

```text
bcd2ba49218906704ab6c1aa796996da409d3eb1
```

A canonical project step using the current v3-style `client-id` input is:

```yaml
- name: Create GitOps GitHub App token
  id: gitops-app-token
  uses: actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1
  with:
    client-id: ${{ vars.GITOPS_APP_CLIENT_ID }}
    private-key: ${{ secrets.GITOPS_APP_PRIVATE_KEY }}
    owner: anselem-okeke
    repositories: ai-platform-gitops
    permission-contents: write
    permission-pull-requests: write
```

If the real repository workflow uses `app-id`, preserve it unless intentionally migrating:

```yaml
- name: Create GitOps GitHub App token
  id: gitops-app-token
  uses: actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1
  with:
    app-id: ${{ vars.GITOPS_APP_ID }}
    private-key: ${{ secrets.GITOPS_APP_PRIVATE_KEY }}
    owner: anselem-okeke
    repositories: ai-platform-gitops
    permission-contents: write
    permission-pull-requests: write
```

## Output

The installation token is:

```yaml
${{ steps.gitops-app-token.outputs.token }}
```

The App slug is:

```yaml
${{ steps.gitops-app-token.outputs.app-slug }}
```

Never echo the token.

---

# 11. Test Token Creation Before Using It for Deployment Automation

Before coupling the App to digest updates, create a temporary manual workflow or temporary diagnostic step that performs a read-only API request.

Example:

```yaml
- name: Verify GitHub App installation token
  env:
    GH_TOKEN: ${{ steps.gitops-app-token.outputs.token }}
  run: |
    gh api \
      /repos/anselem-okeke/ai-platform-gitops \
      --jq '{full_name, default_branch, private}'
```

Expected:

```json
{
  "full_name": "anselem-okeke/ai-platform-gitops",
  "default_branch": "main",
  ...
}
```

If this fails, do not proceed to branch/PR automation.

---

# 12. Validate the Token's Repository Installation

Use:

```yaml
- name: Verify GitOps repository is available to installation
  env:
    GH_TOKEN: ${{ steps.gitops-app-token.outputs.token }}
  run: |
    gh api /installation/repositories \
      --jq '.repositories[].full_name'
```

Expected output contains:

```text
anselem-okeke/ai-platform-gitops
```

If it does not appear, the App is not installed on the correct repository.

---

# 13. Clone the GitOps Repository Using the Installation Token

A secure pattern is:

```bash
git clone \
  "https://x-access-token:${GH_TOKEN}@github.com/anselem-okeke/ai-platform-gitops.git" \
  ai-platform-gitops
```

In GitHub Actions:

```yaml
- name: Clone GitOps repository
  env:
    GH_TOKEN: ${{ steps.gitops-app-token.outputs.token }}
  run: |
    git clone \
      "https://x-access-token:${GH_TOKEN}@github.com/anselem-okeke/ai-platform-gitops.git" \
      ai-platform-gitops
```

GitHub masks registered secrets/tokens, but do not run shell tracing such as:

```bash
set -x
```

around credential-bearing commands.

Alternative: use `actions/checkout` with the App token and explicit target repository.

---

# 14. Configure the Commit Identity as the GitHub App Bot

GitHub App commits should show the App bot identity rather than a developer identity.

The action exposes:

```yaml
${{ steps.gitops-app-token.outputs.app-slug }}
```

Expected slug:

```text
ai-platform-gitops-bot
```

GitHub's official pattern obtains the bot user ID through the API.

Example:

```yaml
- name: Get GitHub App bot user ID
  id: gitops-bot-user
  env:
    GH_TOKEN: ${{ steps.gitops-app-token.outputs.token }}
    APP_SLUG: ${{ steps.gitops-app-token.outputs.app-slug }}
  run: |
    USER_ID="$(
      gh api \
        "/users/${APP_SLUG}[bot]" \
        --jq '.id'
    )"

    echo "user-id=${USER_ID}" >> "$GITHUB_OUTPUT"
```

Configure Git:

```yaml
- name: Configure Git bot identity
  working-directory: ai-platform-gitops
  env:
    APP_SLUG: ${{ steps.gitops-app-token.outputs.app-slug }}
    APP_USER_ID: ${{ steps.gitops-bot-user.outputs.user-id }}
  run: |
    git config \
      user.name \
      "${APP_SLUG}[bot]"

    git config \
      user.email \
      "${APP_USER_ID}+${APP_SLUG}[bot]@users.noreply.github.com"
```

Expected GitHub author:

```text
ai-platform-gitops-bot[bot]
```

## Validate Locally in the Workflow

```bash
git config user.name
git config user.email
```

Never substitute a personal email address for the automation identity.

---

# 15. Create the Automation Branch

The implemented branch convention is:

```text
automation/image-<source-sha>
```

In Actions:

```bash
SOURCE_SHA="${GITHUB_SHA}"
BRANCH="automation/image-${SOURCE_SHA}"

git switch -c "${BRANCH}"
```

Validate:

```bash
git branch --show-current
```

Expected:

```text
automation/image/<...>
```

or the repository's exact convention:

```text
automation/image-<source-sha>
```

Use the convention actually implemented in the release workflow.

---

# 16. Inputs from the Image Build Jobs

The GitOps update must only run after both images are successfully built.

Expected dependency:

```yaml
update-gitops:
  needs:
    - build-operator
    - build-api
```

Inputs:

```text
source commit SHA
operator image digest
API image digest
```

Expected image identities:

```text
ghcr.io/anselem-okeke/ai-platform-operator@sha256:<digest>
ghcr.io/anselem-okeke/ai-platform-api@sha256:<digest>
```

If either build fails:

```text
no GitOps PR
```

---

# 17. Update the GitOps Development Overlay

The automation modifies exactly:

```text
platform/operator/overlays/dev/kustomization.yaml
platform/api/overlays/dev/kustomization.yaml
```

It should not modify unrelated resources.

The final rendered image must be immutable:

```text
@sha256:<64 hex characters>
```

## Verify Changed Files

```bash
git status --short
```

Expected only the intended Kustomize files.

Check:

```bash
git diff -- \
  platform/operator/overlays/dev/kustomization.yaml \
  platform/api/overlays/dev/kustomization.yaml
```

---

# 18. Validate Kustomize Before Committing

Operator:

```bash
kubectl kustomize \
  platform/operator/overlays/dev \
  >/tmp/operator-rendered.yaml
```

API:

```bash
kubectl kustomize \
  platform/api/overlays/dev \
  >/tmp/api-rendered.yaml
```

Inspect images:

```bash
grep -n 'image:' \
  /tmp/operator-rendered.yaml \
  /tmp/api-rendered.yaml
```

Expected:

```text
ghcr.io/anselem-okeke/...@sha256:<64-hex-digest>
```

Whitespace validation:

```bash
git diff --check
```

Expected:

```text
no output
```

---

# 19. Commit as the Bot

Expected commit convention:

```text
chore(dev): deploy images from <source-sha>
```

Example:

```bash
git add \
  platform/operator/overlays/dev/kustomization.yaml \
  platform/api/overlays/dev/kustomization.yaml

git diff --cached --check

git commit \
  -m "chore(dev): deploy images from ${GITHUB_SHA}"
```

Validate:

```bash
git log -1 \
  --format='author=%an <%ae>%nsubject=%s'
```

Expected author:

```text
ai-platform-gitops-bot[bot]
```

Expected subject:

```text
chore(dev): deploy images from <source-sha>
```

---

# 20. Push the Bot Branch

```bash
git push \
  -u origin \
  "${BRANCH}"
```

Expected:

```text
new remote branch created successfully
```

The App requires:

```text
Contents: Read & write
```

for this step.

---

# 21. Open the GitOps Pull Request

Use the installation token:

```bash
GH_TOKEN="${APP_TOKEN}" \
gh pr create \
  --repo anselem-okeke/ai-platform-gitops \
  --base main \
  --head "${BRANCH}" \
  --title "chore(dev): deploy images from ${GITHUB_SHA}" \
  --body "Automated immutable image digest update from source commit ${GITHUB_SHA}."
```

In GitHub Actions:

```yaml
- name: Open GitOps pull request
  working-directory: ai-platform-gitops
  env:
    GH_TOKEN: ${{ steps.gitops-app-token.outputs.token }}
    SOURCE_SHA: ${{ github.sha }}
  run: |
    BRANCH="automation/image-${SOURCE_SHA}"

    gh pr create \
      --repo anselem-okeke/ai-platform-gitops \
      --base main \
      --head "${BRANCH}" \
      --title "chore(dev): deploy images from ${SOURCE_SHA}" \
      --body "Automated immutable image digest update from source commit ${SOURCE_SHA}."
```

The App requires:

```text
Pull requests: Read & write
```

for this step.

---

# 22. Expected GitHub Result

After a successful release:

```text
PR author:
ai-platform-gitops-bot[bot]

branch:
automation/image-<source-sha>

files:
platform/operator/overlays/dev/kustomization.yaml
platform/api/overlays/dev/kustomization.yaml

title:
chore(dev): deploy images from <source-sha>
```

The PR should then run:

```text
Validate GitOps Manifests
```

It must remain unmerged until:

```text
GitOps validation passes
human review/merge occurs
```

The bot must **not** bypass this promotion boundary.

---

# 23. End-to-End Validation

## 23.1 Trigger a Real Source Release

Merge an approved source PR into:

```text
main
```

Verify release workflow:

```bash
gh run list \
  --workflow release-images.yml \
  --limit 5
```

Inspect:

```bash
gh run view <RUN_ID>
```

## 23.2 Confirm Build Jobs

Expected:

```text
build-operator  success
build-api       success
update-gitops   success
```

## 23.3 Confirm Bot PR

In the GitOps repository:

```bash
gh pr list \
  --repo anselem-okeke/ai-platform-gitops
```

Expected author:

```text
ai-platform-gitops-bot[bot]
```

## 23.4 Inspect PR

```bash
gh pr view <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-gitops
```

## 23.5 Confirm Changed Files

```bash
gh pr diff <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-gitops \
  --name-only
```

Expected:

```text
platform/operator/overlays/dev/kustomization.yaml
platform/api/overlays/dev/kustomization.yaml
```

## 23.6 Confirm GitOps Validation

```bash
gh pr checks <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-gitops
```

Expected:

```text
Validate GitOps Manifests  pass
```

## 23.7 Merge Manually

Merge only after review.

Then Argo CD reconciles the approved Git state.

---

# 24. Failure Scenario: Repository Installation Lookup `Not Found`

## Symptom

The token-generation step reports an error equivalent to:

```text
Not Found
```

while trying to resolve the installation/repository.

## Root Cause

A GitHub App registration and a GitHub App installation are different things.

Common causes:

```text
App exists but is not installed
App installed on wrong account
ai-platform-gitops not selected
wrong owner
wrong repository name
wrong App/Client ID
wrong private key
installation has old permissions
```

## Diagnosis Step 1 — Verify App Installation

GitHub UI:

```text
Settings
  → Applications
  → Installed GitHub Apps
  → ai-platform-gitops-bot
```

Confirm:

```text
ai-platform-gitops
```

is selected.

## Diagnosis Step 2 — Verify Workflow Owner/Repository

Expected:

```text
owner: anselem-okeke
repositories: ai-platform-gitops
```

Inspect:

```bash
grep -n -A20 -B5 \
  'create-github-app-token' \
  .github/workflows/release-images.yml
```

## Diagnosis Step 3 — Verify App Identifier

Check GitHub App settings and compare to the Actions variable.

## Diagnosis Step 4 — Regenerate Token

Re-run a manual diagnostic workflow and call:

```bash
gh api /installation/repositories
```

Expected:

```text
anselem-okeke/ai-platform-gitops
```

## Fix

Correct the App installation so the GitOps repository is included.

Then re-run the workflow.

---

# 25. Failure Scenario: `403 Resource not accessible by integration`

## Meaning

The App installation exists, but the token lacks a required permission.

## For Push Failures

Check:

```text
Contents: Read & write
```

## For PR Creation Failures

Check:

```text
Pull requests: Read & write
```

After changing App permissions, GitHub may require the installation owner to approve the updated permissions.

Do not keep adding broad permissions until the error disappears.

---

# 26. Failure Scenario: Clone Succeeds, Push Fails

Inspect:

```bash
git remote -v
git status
git branch --show-current
```

Confirm the Git remote is authenticated with the installation token.

Confirm `Contents: write`.

Confirm branch rules do not forbid creation of the automation branch.

---

# 27. Failure Scenario: Bot Can Push but Cannot Create PR

Verify:

```text
Pull requests: Read & write
```

Then test:

```bash
GH_TOKEN="<installation-token>" \
gh api \
  /repos/anselem-okeke/ai-platform-gitops/pulls
```

Do not print the token in shell history on a shared host.

---

# 28. Failure Scenario: Wrong Commit Author

If GitHub displays a human user instead of:

```text
ai-platform-gitops-bot[bot]
```

inspect:

```bash
git config user.name
git config user.email
```

Expected pattern:

```text
<app-slug>[bot]
<bot-user-id>+<app-slug>[bot]@users.noreply.github.com
```

Obtain ID:

```bash
gh api \
  '/users/ai-platform-gitops-bot[bot]' \
  --jq '.id'
```

---

# 29. Failure Scenario: Automation Modifies Unexpected Files

Before commit:

```bash
git status --short
git diff --name-only
```

Expected exactly:

```text
platform/operator/overlays/dev/kustomization.yaml
platform/api/overlays/dev/kustomization.yaml
```

If anything else appears:

```text
FAIL the workflow
```

Do not commit unrelated changes.

A useful guard is:

```bash
EXPECTED="$(
  printf '%s\n' \
    platform/api/overlays/dev/kustomization.yaml \
    platform/operator/overlays/dev/kustomization.yaml
)"

ACTUAL="$(
  git diff --name-only |
  sort
)"

test "${ACTUAL}" = "${EXPECTED}"
```

Adapt sorting consistently.

---

# 30. Private Key Rotation

GitHub App private keys do not automatically expire, so rotation is an operational responsibility.

Safe rotation:

```text
1. generate new GitHub App private key
2. update GitHub Actions secret with new key
3. trigger diagnostic token workflow
4. verify repository access
5. trigger one real/controlled automation
6. verify bot PR
7. revoke old private key
```

Do **not** delete the old key before validating the replacement.

---

# 31. Revoke a Compromised Private Key

If the key may have leaked:

```text
1. treat it as compromised
2. generate replacement key
3. update Actions secret
4. revoke/delete compromised key in GitHub App settings
5. review GitHub audit/activity
6. review GitOps branches/PRs/commits
7. rotate any downstream credential if exposure expanded
8. run Gitleaks/history scan if the key touched a repository
```

GitHub App installation access tokens are short-lived, but the private key can mint new installation tokens until revoked.

---

# 32. Remove Repository Access

To remove the bot's GitOps access:

```text
Settings
  → Applications
  → Installed GitHub Apps
  → ai-platform-gitops-bot
  → Configure
```

Remove:

```text
ai-platform-gitops
```

or uninstall the App.

Then token generation for that repository should fail.

This is the emergency revocation boundary.

---

# 33. Rebuild the GitHub App from Zero

If the App registration is lost or intentionally replaced:

```text
[ ] Create new GitHub App
[ ] Configure Contents read/write
[ ] Configure Pull requests read/write
[ ] Disable unused webhooks
[ ] Restrict installation scope
[ ] Install on ai-platform-gitops only
[ ] Record Client ID/App ID
[ ] Generate private key
[ ] Update source Actions variable
[ ] Update source Actions private-key secret
[ ] Run token diagnostic
[ ] Verify /installation/repositories
[ ] Verify clone
[ ] Verify branch push
[ ] Verify bot identity
[ ] Verify PR creation
[ ] Verify GitOps validation
[ ] Revoke old App/credentials
```

---

# 34. Security Boundary

The bot is intentionally constrained.

It should be able to:

```text
read ai-platform-gitops
push automation branches
open PRs
```

It should **not** be able to:

```text
administer repositories
modify secrets
change repository rulesets
bypass branch protection
auto-merge deployment PRs
access unrelated repositories
```

The intended release boundary is:

```text
source required checks
       ↓
release builds
       ↓
GitHub App bot opens GitOps PR
       ↓
GitOps validation
       ↓
human merge
       ↓
Argo CD
       ↓
Kubernetes admission
```

The bot is automation, not deployment authority.

---

# 35. Full Validation Checklist

## GitHub App Registration

```text
[ ] App exists
[ ] App name/slug recorded
[ ] Webhook disabled unless intentionally required
[ ] Contents = Read & write
[ ] Pull requests = Read & write
[ ] no unnecessary repository permissions
[ ] no unnecessary organization permissions
```

## Installation

```text
[ ] App installed on correct account
[ ] Only selected repositories used
[ ] ai-platform-gitops selected
```

## Credentials

```text
[ ] correct Client ID/App ID stored
[ ] private key stored in Actions secret
[ ] private key not tracked in Git
[ ] secret name matches workflow
[ ] identifier variable name matches workflow
```

## Workflow

```text
[ ] create-github-app-token pinned to full SHA
[ ] owner exactly anselem-okeke
[ ] repository exactly ai-platform-gitops
[ ] token not printed
[ ] build-operator and build-api are dependencies
[ ] branch convention correct
[ ] only intended GitOps files modified
[ ] Kustomize render passes
[ ] git diff --check passes
```

## Identity

```text
[ ] bot user ID resolved
[ ] git user.name = ai-platform-gitops-bot[bot]
[ ] git user.email uses bot noreply format
[ ] commit appears as GitHub App bot
[ ] PR appears as GitHub App bot
```

## Promotion

```text
[ ] bot PR is not auto-merged
[ ] Validate GitOps Manifests runs
[ ] human merge required
[ ] Argo reconciles only after merge
```

## Recovery

```text
[ ] key rotation procedure documented
[ ] key compromise procedure documented
[ ] App uninstall/repository removal procedure documented
[ ] installation lookup failure documented
```

---

# 36. Useful Diagnostic Commands

## Inspect Workflow

```bash
cd /mnt/data/ai-platform-operator

grep -n -A50 -B10 \
  'create-github-app-token' \
  .github/workflows/release-images.yml
```

## Inspect Referenced Secrets / Variables

```bash
grep -nE \
  '\$\{\{ *(secrets|vars)\.' \
  .github/workflows/release-images.yml
```

## Source Workflow Runs

```bash
gh run list \
  --workflow release-images.yml \
  --limit 10
```

## GitOps PRs

```bash
gh pr list \
  --repo anselem-okeke/ai-platform-gitops
```

## Check Bot Account

```bash
gh api \
  '/users/ai-platform-gitops-bot[bot]' \
  --jq '{login,id,type}'
```

## Inspect Current GitOps Automation Branches

```bash
git ls-remote \
  --heads \
  https://github.com/anselem-okeke/ai-platform-gitops.git \
  'refs/heads/automation/*'
```

---

# 37. What Must Never Be Put in Documentation

Never record actual values for:

```text
GitHub App private key
installation token
JWT
GitHub secret value
private registry credential
Vault token
```

It is correct to document:

```text
secret/variable name
where it is configured
how it is rotated
what consumes it
how to verify it
```

It is not correct to document its secret value.

---

# 38. Implementation Evidence vs Rebuild Defaults

The following facts are confirmed for this project:

```text
GitOps repository:
anselem-okeke/ai-platform-gitops

Bot identity:
ai-platform-gitops-bot[bot]

Action:
actions/create-github-app-token

Pinned action SHA:
bcd2ba49218906704ab6c1aa796996da409d3eb1

Automation branch convention:
automation/image-<source-sha>

GitOps files updated:
platform/operator/overlays/dev/kustomization.yaml
platform/api/overlays/dev/kustomization.yaml

PR/commit convention:
chore(dev): deploy images from <source-sha>

Promotion:
manual PR merge
```

The exact **current repository secret/variable names** must be taken from:

```text
.github/workflows/release-images.yml
```

because those values were not preserved in the documentation evidence used to reconstruct this guide.

For a clean rebuild, this guide recommends:

```text
GITOPS_APP_CLIENT_ID
GITOPS_APP_PRIVATE_KEY
```

but do not rename an existing working configuration merely to match the recommendation.

---

# 39. Official References

GitHub App registration:

```text
https://docs.github.com/apps/creating-github-apps/registering-a-github-app
```

GitHub App permissions:

```text
https://docs.github.com/apps/creating-github-apps/registering-a-github-app/choosing-permissions-for-a-github-app
```

Install your own GitHub App:

```text
https://docs.github.com/apps/using-github-apps/installing-your-own-github-app
```

Private key management:

```text
https://docs.github.com/apps/creating-github-apps/authenticating-with-a-github-app/managing-private-keys-for-github-apps
```

Authenticating from GitHub Actions:

```text
https://docs.github.com/apps/creating-github-apps/authenticating-with-a-github-app/making-authenticated-api-requests-with-a-github-app-in-a-github-actions-workflow
```

GitHub-owned token action:

```text
https://github.com/actions/create-github-app-token
```

GitHub Actions secrets:

```text
https://docs.github.com/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions
```

GitHub CLI:

```text
https://cli.github.com/manual/
```

---

# 40. Related AI Platform Documentation

```text
019-source-ci-pipeline.md
023-github-container-registry.md
025-image-digest-update-workflow.md
026-gitops-pr-validation.md
027-branch-protection-and-rulesets.md
039-software-supply-chain-security.md
040-end-to-end-delivery-workflow.md
043-troubleshooting-guide.md
045-command-reference.md
047-design-decisions.md
```
