# Secret Scanning

## Purpose

This document is the **reproducible implementation and operating guide** for secret scanning in the AI Platform repositories.

The objective is to prevent secret material from entering source control and to detect previously committed credentials in repository history.

The current defense model is:

```text
developer workstation
      |
      v
.gitignore
      |
      v
local review
      |
      v
pull request
      |
      +--> Gitleaks
      +--> GitOps secret-pattern checks
      |
      v
required branch protection
      |
      v
merge only when secret scanning passes
```

The current project has validated:

```text
source repository current/history scan clean
GitOps repository current/history scan clean
Gitleaks used as a required source check
GitOps validation contains an additional secret-pattern defense-in-depth check
```

This guide explains how to:

```text
run Gitleaks locally
understand current-vs-history scanning
integrate scanning into GitHub Actions
make Gitleaks blocking
validate repository history
investigate findings
rotate exposed credentials
remove leaked material safely
avoid false confidence from `.gitignore`
avoid false positives in GitOps manifests
rebuild the controls from zero
```

---

# 1. Repositories

## Source Repository

```text
/mnt/data/ai-platform-operator
```

Remote:

```text
git@github.com:anselem-okeke/ai-platform-operator.git
```

## GitOps Repository

```text
/mnt/data/ai-platform-gitops
```

Remote:

```text
https://github.com/anselem-okeke/ai-platform-gitops.git
```

Both repositories must remain free of real secret material.

---

# 2. Why Secret Scanning Is Required

A repository can contain secrets even when:

```text
the current working tree is clean
```

because secrets may exist in:

```text
previous commits
deleted files
old branches
merge commits
tags
PR-related history
```

Therefore the platform treats:

```text
current content scanning
+
Git history scanning
```

as separate concerns.

---

# 3. What Counts as Secret Material

Examples include:

```text
private keys
passwords
JWTs
GitHub tokens
Vault tokens
cloud access keys
database credentials
TLS private keys
API keys
OAuth/OIDC client secrets
GitHub App private keys
registry credentials
```

A value does not become safe merely because it is:

```text
base64 encoded
inside YAML
inside JSON
inside an example file
inside deleted Git history
```

---

# 4. What Is Not Necessarily a Secret

Examples:

```text
public certificate
repository URL
GitHub organization name
Kubernetes Secret object name
secretKeyRef key name
client ID for a public OIDC client
public image digest
```

Do not over-classify architecture metadata as secret material.

---

# 5. `.gitignore` Is Preventive, Not Detective

The GitOps repository contains protective patterns such as:

```text
.local/
*.jwt
*.key
*.pem
.env
secret YAML patterns
```

This reduces accidental additions.

However:

```text
.gitignore does not scan
.gitignore does not detect history
.gitignore does not protect already tracked files
```

Therefore Gitleaks remains necessary.

---

# 6. Why `*.crt` Is Not Broadly Ignored

The repository intentionally does not use:

```text
*.crt
```

as a blanket secret pattern.

Reason:

```text
public certificates are not private keys
```

The sensitive counterpart is usually:

```text
*.key
*.pem
```

depending on content.

---

# 7. Gitleaks

The project uses Gitleaks as the primary repository secret scanner.

Gitleaks can identify:

```text
known token formats
private keys
high-confidence credential patterns
entropy-based suspicious values
provider-specific secrets
```

---

# 8. Source Required Check

The source repository branch ruleset requires:

```text
Gitleaks
```

before merge.

This means secret scanning is an enforcement gate, not merely informational.

The intended flow is:

```text
Gitleaks FAIL
    |
    v
PR merge blocked
```

---

# 9. Why Required-Check Status Matters

A security workflow is not effective if:

```text
it fails
but
merge still succeeds
```

Therefore `Gitleaks` is part of the protected-branch status-check set.

See:

```text
027-branch-protection-and-rulesets.md
```

---

# 10. Inspect Current Secret-Scanning Workflow

Source repository:

```bash
cd /mnt/data/ai-platform-operator

find .github/workflows \
  -maxdepth 1 \
  -type f \
  -print \
  | sort
```

Expected workflow:

```text
secret-scan.yml
```

Inspect:

```bash
sed -n '1,320p' \
  .github/workflows/secret-scan.yml
```

Do not invent action versions, flags, or step names.

Use the repository as the exact source of truth.

---

# 11. Representative Gitleaks Workflow Shape

A representative workflow may look like:

```yaml
name: Gitleaks

on:
  pull_request:
  push:
    branches:
      - main

permissions:
  contents: read

jobs:
  gitleaks:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@<PINNED_SHA>
        with:
          fetch-depth: 0

      - name: Run Gitleaks
        run: |
          gitleaks git \
            --redact
```

The exact production implementation must be read from the committed workflow.

---

# 12. Why `fetch-depth: 0` Matters

A shallow checkout may only contain:

```text
recent commit history
```

but history scanning requires:

```text
full reachable Git history
```

Therefore a history-scanning workflow often needs:

```yaml
fetch-depth: 0
```

Verify the actual workflow.

---

# 13. Current Tree vs Git History

Two concepts:

```text
working-tree/current scan
history scan
```

A current scan asks:

```text
does the repository currently contain a secret?
```

A history scan asks:

```text
was a secret ever committed?
```

The second is important even after a bad file is deleted.

---

# 14. Local History Scan

Representative:

```bash
cd /mnt/data/ai-platform-operator

gitleaks git \
  --redact
```

GitOps:

```bash
cd /mnt/data/ai-platform-gitops

gitleaks git \
  --redact
```

Use the exact project-standard command/version if the workflow differs.

---

# 15. Why `--redact` Matters

A scanner should not re-print the detected secret into logs.

`--redact` helps avoid turning:

```text
secret detection
```

into:

```text
secret disclosure
```

---

# 16. Avoid Full Secret Values in Findings

When investigating a finding, record:

```text
file
line
commit
rule ID
secret type
```

Do not copy the full credential value into:

```text
ticket
chat
README
PR comment
incident summary
```

---

# 17. Validate Source Repository Locally

```bash
cd /mnt/data/ai-platform-operator

git status --short
```

Then:

```bash
gitleaks git \
  --redact
```

Expected:

```text
no findings
exit code 0
```

---

# 18. Validate GitOps Repository Locally

```bash
cd /mnt/data/ai-platform-gitops

git status --short
```

Then:

```bash
gitleaks git \
  --redact
```

Expected:

```text
no findings
exit code 0
```

---

# 19. Current Validation Fact

The project has already validated:

```text
source current/history scans clean
GitOps current/history scans clean
```

Do not reinterpret this as:

```text
future commits are guaranteed secret-free
```

Continuous enforcement is still required.

---

# 20. GitOps Secret-Pattern Defense in Depth

The GitOps validation workflow also includes a lightweight secret-pattern check.

This is separate from Gitleaks.

Its purpose is to catch obvious manifest mistakes such as:

```text
raw passwords
private-key blocks
embedded tokens
secret values in YAML
```

before merge.

---

# 21. Why GitOps Needs Extra Scanning

GitOps repositories contain many files that look like:

```text
configuration
credentials references
Secret names
TLS settings
Helm values
```

A small mistake can turn a safe reference into a real secret value.

Therefore GitOps gets additional defense in depth.

---

# 22. Inspect GitOps Secret Check

Run:

```bash
cd /mnt/data/ai-platform-gitops

grep -nE \
  'secret|password|token|PRIVATE KEY|git grep|grep -R' \
  .github/workflows/validate.yml
```

Then inspect the full relevant block.

Do not invent the exact current regex.

---

# 23. Secret Reference Must Not Trigger False Failure

Safe:

```yaml
valueFrom:
  secretKeyRef:
    name: platform-db
    key: password
```

This contains the word:

```text
password
```

but not a password value.

A GitOps check must distinguish:

```text
reference metadata
```

from:

```text
embedded secret material
```

as much as practical.

---

# 24. Raw Secret Example That Should Be Rejected

Bad:

```yaml
env:
  - name: DATABASE_PASSWORD
    value: "real-secret-value"
```

This should fail review/scanning.

---

# 25. Base64 Kubernetes Secret Example

Bad:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: platform-db
type: Opaque
data:
  password: c2VjcmV0MTIz
```

Base64 does not make this safe for Git.

A scanning strategy should treat likely populated Secret data fields as sensitive.

---

# 26. Private-Key Block

Definite red flag:

```text
-----BEGIN PRIVATE KEY-----
...
-----END PRIVATE KEY-----
```

or provider-specific equivalents.

Search defensively:

```bash
git grep -nE \
  'BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY'
```

Expected:

```text
no real key material
```

---

# 27. Tracked Sensitive Extensions

Check source:

```bash
cd /mnt/data/ai-platform-operator

git ls-files \
  | grep -Ei '\.(pem|key|jwt)$'
```

GitOps:

```bash
cd /mnt/data/ai-platform-gitops

git ls-files \
  | grep -Ei '\.(pem|key|jwt)$'
```

Any result must be reviewed.

Documentation filenames can be false positives; actual content matters.

---

# 28. `.env` Files

Check:

```bash
git ls-files \
  | grep -E '(^|/)\.env($|\.)'
```

A real environment file containing credentials should not be tracked.

A safe template may instead be:

```text
.env.example
```

with placeholders only.

---

# 29. Safe `.env.example`

Example:

```bash
VAULT_ADDR=https://vault.platform.local:8200
DATABASE_USER=<SET_AT_RUNTIME>
DATABASE_PASSWORD=<SET_AT_RUNTIME>
```

Do not put:

```text
real passwords
real tokens
```

into template files.

---

# 30. GitHub App Private Key

The GitHub App private key must never appear in either repository.

Search:

```bash
git grep -nE \
  'BEGIN (RSA )?PRIVATE KEY'
```

Also rely on Gitleaks.

The correct storage is:

```text
GitHub Actions Secrets
```

---

# 31. JWT Files

JWTs often contain:

```text
header.payload.signature
```

The GitOps repository ignores:

```text
*.jwt
```

but history scanning is still required.

---

# 32. Vault Tokens

Vault tokens should never be committed.

Do not put:

```text
hvs....
s....
```

or other Vault token forms into:

```text
scripts
docs
YAML
shell examples
```

Use placeholders.

---

# 33. GitHub Tokens

Do not commit:

```text
PATs
installation tokens
workflow tokens
OAuth tokens
```

The GitHub App installation token should exist only during the workflow run.

---

# 34. OIDC Tokens

OIDC access/ID/refresh tokens are credentials.

The project previously wrote PKCE token files under:

```text
.local/keycloak/tokens
```

The `.local/` path must remain ignored.

Do not commit these tokens.

---

# 35. Keycloak Bootstrap Credentials

Bootstrap admin credentials are sensitive.

Do not commit:

```text
KC_BOOTSTRAP_ADMIN_PASSWORD
```

or equivalent real values.

The project later verified bootstrap env was unset after setup.

---

# 36. TLS Private Keys

Search for:

```text
*.key
*.pem
```

and private-key markers.

Public certificates may legitimately be present.

Private keys may not.

---

# 37. False Positive Handling

A scanner finding does not automatically mean:

```text
real secret
```

Possible false positives:

```text
test fixture
fake token
random digest
documentation example
public key
hash
UUID
```

Every finding should be classified.

---

# 38. Do Not Silence Findings Globally

Bad response:

```text
disable rule
exclude entire directory
ignore all YAML
```

Better:

```text
understand finding
use narrow allowlist if demonstrably false
document rationale
```

---

# 39. Allowlisting

If Gitleaks supports a narrow allowlist for a known fake value, scope it to:

```text
exact file
exact regex
exact rule
exact commit where possible
```

Do not create broad exceptions that can hide future real secrets.

---

# 40. Documentation Examples

Documentation should use obvious placeholders:

```text
<SECRET>
<TOKEN>
<PRIVATE_KEY>
<REAL_TRUSTED_DIGEST>
```

Avoid realistic-looking provider tokens unless necessary because they can trigger scanners.

---

# 41. Fake Tokens for Testing

If testing scanning, use a disposable test branch.

Do not use a real credential.

Use a scanner-supported synthetic pattern only if:

```text
it cannot authenticate anywhere
```

and delete/revert after validation.

---

# 42. Safe CI Negative Test

A controlled test can:

```text
create synthetic secret-like test fixture
verify Gitleaks fails
remove fixture
verify Gitleaks passes
```

Do not merge the failing fixture.

---

# 43. Branch Protection Validation

If Gitleaks fails on a PR:

```text
merge must be blocked
```

This validates the full control chain:

```text
scanner
  +
required check
```

---

# 44. Verify Required Gitleaks Check

Inspect PR:

```bash
gh pr checks <PR_NUMBER> \
  --repo anselem-okeke/ai-platform-operator
```

Expected:

```text
Gitleaks
```

among required checks.

---

# 45. Verify Ruleset

The source ruleset includes:

```text
Gitleaks
```

as a strict required check.

See:

```text
027-branch-protection-and-rulesets.md
```

---

# 46. Secret Found in Uncommitted Work

If a secret is only in an untracked/uncommitted local file:

```text
do not commit it
remove it
rotate if it may have been shared elsewhere
```

If it was never exposed outside the local machine, rotation risk depends on handling context.

---

# 47. Secret Found in Commit Not Yet Pushed

If committed locally but not pushed:

```text
remove from commit
rotate if exposure risk exists
rewrite local commit
re-run Gitleaks
```

Because the commit is not shared, local history cleanup is simpler.

---

# 48. Secret Found After Push

Treat it as compromised.

Immediate sequence:

```text
1. revoke/rotate
2. inspect usage/audit logs
3. remove from current branch
4. clean history if required
5. re-run scanners
6. document incident
```

---

# 49. Why Rotation Comes First

History cleanup cannot guarantee all copies disappear.

The secret may already exist in:

```text
clones
forks
CI logs
PR diffs
caches
backups
```

Therefore:

```text
revoke first
```

---

# 50. GitHub App Private-Key Leak Response

Immediate:

```text
1. generate replacement App private key
2. replace GitHub Actions Secret
3. verify token generation
4. revoke exposed key
5. inspect App activity
6. inspect GitOps pushes/PRs
```

---

# 51. Vault Token Leak Response

Generic:

```text
1. revoke token/lease
2. inspect Vault audit logs
3. rotate downstream credentials if exposed
4. update runtime secret delivery
5. verify workloads
```

---

# 52. Database Credential Leak

Generic:

```text
1. rotate database credential
2. update Vault
3. update Kubernetes runtime Secret
4. restart/reload consumer if needed
5. revoke old credential
6. inspect access logs
```

---

# 53. TLS Private-Key Leak

Generic:

```text
1. replace keypair
2. issue/reissue certificate
3. update TLS Secret
4. reload Gateway/API
5. revoke old certificate if supported
```

---

# 54. Remove Secret from Current Git State

Example:

```bash
git rm \
  path/to/leaked-secret-file
```

or edit the file and replace the value with a reference/placeholder.

Then:

```bash
git commit \
  -m "security: remove leaked secret material"
```

This does not remove historical copies.

---

# 55. History Cleanup

Use only after credential rotation.

Possible tools:

```text
git filter-repo
BFG Repo-Cleaner
GitHub support procedures
```

Choose based on repository policy.

History rewriting affects all collaborators.

---

# 56. Force Push Caution

Protected branches block force-push.

History cleanup may require a controlled break-glass process.

Do not disable branch protection casually.

Document:

```text
incident
authorization
exact refs rewritten
restore protection afterward
```

---

# 57. GitHub Cached Views

Even after history rewrite, GitHub may retain:

```text
cached commit pages
PR refs
forks
```

This is another reason rotation is mandatory.

---

# 58. Re-Scan After Cleanup

Source:

```bash
cd /mnt/data/ai-platform-operator

gitleaks git \
  --redact
```

GitOps:

```bash
cd /mnt/data/ai-platform-gitops

gitleaks git \
  --redact
```

Expected:

```text
clean
```

---

# 59. Re-Scan Current Tree

Also inspect:

```bash
git status --short
```

and defensive grep checks.

---

# 60. CI Log Review

If a secret was exposed through a workflow:

```text
inspect logs
delete/restrict affected artifacts if supported
rotate secret
fix logging
```

Do not assume masking caught everything.

---

# 61. Avoid `set -x`

In shell workflows:

```bash
set -x
```

can echo commands and expanded arguments.

Avoid around secret-handling steps.

If debugging is necessary, disable xtrace before credentials are used.

---

# 62. Avoid Printing Secret Variables

Bad:

```bash
echo "$TOKEN"
```

Bad:

```bash
env
```

Good:

```bash
test -n "$TOKEN"
```

to verify presence without printing it.

---

# 63. Verify Secret Exists Without Display

Example:

```bash
if [[ -z "${TOKEN:-}" ]]; then
  echo "ERROR: TOKEN is missing" >&2
  exit 1
fi
```

No value is printed.

---

# 64. Secret Scanning in PR Review

Reviewers should look for:

```text
new Secret YAML
new `.env`
private-key blocks
hardcoded passwords
new GitHub Actions secrets references
suspicious Helm values
new credential-bearing scripts
```

Automation complements review.

---

# 65. Changes to Secret-Scanning Workflow Are Security-Sensitive

A PR modifying:

```text
secret-scan.yml
Gitleaks config
allowlists
branch protection
GitOps secret regex
```

changes security enforcement.

Review these changes carefully.

---

# 66. Workflow Pinning

Actions used in secret-scanning workflows should be SHA-pinned where the project follows that standard.

Do not use mutable action tags casually in a security workflow.

---

# 67. Least Workflow Permissions

A secret-scanning job usually only needs:

```yaml
permissions:
  contents: read
```

Do not grant:

```text
packages write
pull-requests write
id-token write
```

unless specifically required.

---

# 68. Fork PR Considerations

GitHub does not expose repository secrets to untrusted fork workflows by default in the same way as trusted branches.

A secret scanner should ideally require:

```text
no sensitive repository secret
```

to operate.

This reduces fork-related risk.

---

# 69. Scanner Version Pinning

Pin the Gitleaks version/tool acquisition method.

This makes:

```text
detections
rules
CI behavior
```

more reproducible.

The exact current version must be read from the source workflow.

---

# 70. Scanner Upgrade Procedure

Before upgrading:

```text
1. read Gitleaks release notes
2. test both repos locally
3. review new findings
4. classify false positives
5. update CI
6. verify required check
```

Do not upgrade and immediately suppress new findings globally.

---

# 71. New Finding After Scanner Upgrade

A new scanner version can detect old leaked content that prior versions missed.

Treat the finding seriously.

Classify:

```text
real secret
historical compromised secret
safe fake/example
false positive
```

Then act accordingly.

---

# 72. Gitleaks Configuration File

If the project introduces:

```text
.gitleaks.toml
```

document:

```text
custom rules
allowlists
paths
rationale
```

Do not create opaque exclusions.

---

# 73. No Secret Scanning of Binary Blobs Is Perfect

Large/binary artifacts can evade text-based controls.

Avoid storing unnecessary binaries in Git.

Use release/artifact systems for generated binaries.

---

# 74. Git LFS

If Git LFS is used later, secrets in LFS objects remain secrets.

Scanning strategy must account for LFS content separately.

The current project does not depend on Git LFS for secret handling.

---

# 75. Archives

Do not commit:

```text
.zip
.tar.gz
backup files
database dumps
```

containing secret material.

Scanners may not inspect every compressed format deeply.

---

# 76. Backup Files

Risky filenames:

```text
config.yaml.bak
.env.old
secret-copy.txt
id_rsa.old
```

`.gitignore` can help, but review/scanning remain required.

---

# 77. Generated Kubernetes Manifests

Generated output may accidentally embed:

```text
Secret data
Helm rendered credentials
TLS private keys
```

Do not commit rendered output blindly.

Inspect before saving to Git.

---

# 78. Helm Values

Bad:

```yaml
password: real-password
```

Good:

```yaml
existingSecret: mlflow-db-credentials
```

or another secret reference supported by the chart.

---

# 79. Kustomize SecretGenerator

`secretGenerator` can still produce Secret values in rendered output.

If literals/files are stored in Git, the secret is still in Git.

Do not assume Kustomize secretGenerator makes credentials secure.

---

# 80. SOPS/Sealed Secrets

The current project does not claim SOPS or Sealed Secrets is implemented.

If adopted later, scanning policy must understand encrypted secret files.

Do not exempt encrypted-secret directories before verifying encryption correctness.

---

# 81. External Secrets Future State

If External Secrets Operator is added later, Git will contain:

```text
remote references
SecretStore references
metadata
```

but not secret values.

Secret scanning remains useful because developers can still accidentally hardcode credentials elsewhere.

---

# 82. Vault CSI Future State

Similarly, CSI-mounted secrets reduce Kubernetes Secret persistence but do not eliminate:

```text
Git secret leak risk
CI secret leak risk
documentation leak risk
```

Secret scanning remains required.

---

# 83. Phase 8 Considerations

Future Phase 8 will likely introduce:

```text
MLflow database credentials
object-storage access keys
model registry credentials
possibly runtime tokens
```

These increase the importance of secret scanning.

No new secret should be added directly to:

```text
InferenceService manifests
ModelService CRs
Helm values
GitHub workflow YAML
```

---

# 84. Secret Scanning Test Matrix

| Test | Expected |
|---|---|
| Clean source repo | Pass |
| Clean GitOps repo | Pass |
| Fake private key pattern in PR | Fail |
| Real hardcoded token | Fail |
| `secretKeyRef` metadata | Pass |
| Public certificate | Pass unless rule intentionally flags |
| `.env` with real value | Fail/review |
| Base64 Kubernetes Secret data | Fail/review |
| Private key in deleted commit | History scan finds it |

---

# 85. Operational Checklist

```text
[ ] source Gitleaks workflow exists
[ ] GitOps defense-in-depth secret check exists
[ ] source branch requires Gitleaks
[ ] full history fetched where required
[ ] scanner logs redact secrets
[ ] source history scan clean
[ ] GitOps history scan clean
[ ] `.gitignore` contains sensitive extensions/paths
[ ] no real `.env` files tracked
[ ] no private keys tracked
[ ] no JWT files tracked
[ ] no raw Kubernetes Secret values committed
[ ] no broad allowlists hide findings
```

---

# 86. Incident Checklist

If a real secret is discovered:

```text
[ ] identify secret type
[ ] revoke/rotate immediately
[ ] identify affected systems
[ ] inspect audit/access logs
[ ] remove from current Git
[ ] determine whether history cleanup is required
[ ] clean history if authorized
[ ] restore branch protection
[ ] re-run Gitleaks
[ ] inspect CI logs/artifacts
[ ] verify replacement credential works
[ ] document root cause
[ ] add regression control
```

---

# 87. Rebuild from Zero

```text
[ ] install/pin Gitleaks
[ ] create source secret-scan workflow
[ ] trigger on PR
[ ] trigger on main push if desired
[ ] set minimal permissions
[ ] checkout full history
[ ] run Gitleaks with redaction
[ ] verify nonzero findings fail job
[ ] add Gitleaks to required branch checks
[ ] run history scan on source
[ ] run history scan on GitOps
[ ] add GitOps lightweight secret-pattern check
[ ] validate secretKeyRef does not false-positive
[ ] validate synthetic secret is blocked
[ ] validate merge blocked when Gitleaks fails
[ ] document leak response
```

---

# 88. Security Review Checklist

```text
[ ] scanner is blocking, not informational
[ ] full history is scanned
[ ] findings are redacted
[ ] workflow permissions are minimal
[ ] action/tool versions are pinned
[ ] scanner config changes reviewed
[ ] allowlists are narrow
[ ] current + historical repos clean
[ ] GitHub App private key absent from Git
[ ] Vault tokens absent from Git
[ ] runtime secrets referenced, not embedded
```

---

# 89. Known Implementation Facts

Validated project facts:

```text
Source:
Gitleaks required check exists

Source ruleset:
requires Gitleaks

Source:
history/current secret scan validated clean

GitOps:
history/current secret scan validated clean

GitOps CI:
contains secret-pattern defense-in-depth check

GitOps `.gitignore` includes:
.local/
*.jwt
*.key
*.pem
.env
secret YAML patterns

GitOps `.gitignore` does not broadly ignore:
*.crt
```

---

# 90. What Must Be Verified from the Actual Repositories

Do not invent:

```text
exact Gitleaks version
exact Gitleaks install command
exact GitHub Action SHA used by secret-scan workflow
exact workflow/job name if changed
exact GitOps regex
exact allowlist configuration
exact scan flags
```

Inspect source:

```bash
cd /mnt/data/ai-platform-operator

sed -n '1,320p' \
  .github/workflows/secret-scan.yml
```

Inspect GitOps:

```bash
cd /mnt/data/ai-platform-gitops

grep -nE \
  'secret|password|token|PRIVATE KEY|grep' \
  .github/workflows/validate.yml
```

Then update this document with exact implementation values if they differ from the representative snippets.

---

# 91. Official References

Gitleaks:

```text
https://github.com/gitleaks/gitleaks
```

GitHub secret scanning concepts:

```text
https://docs.github.com/code-security/secret-scanning/introduction/about-secret-scanning
```

GitHub Actions security:

```text
https://docs.github.com/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions
```

GitHub Actions secrets:

```text
https://docs.github.com/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions
```

Git history rewrite guidance:

```text
https://docs.github.com/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository
```

Kubernetes Secrets:

```text
https://kubernetes.io/docs/concepts/configuration/secret/
```

---

# 92. Related AI Platform Documentation

```text
019-source-ci-pipeline.md
024-github-app-gitops-automation.md
026-gitops-pr-validation.md
027-branch-protection-and-rulesets.md
037-secret-management-strategy.md
039-software-supply-chain-security.md
040-end-to-end-delivery-workflow.md
041-validation-and-security-tests.md
042-rebuild-and-disaster-recovery.md
043-troubleshooting-guide.md
044-operations-runbook.md
045-command-reference.md
047-design-decisions.md
