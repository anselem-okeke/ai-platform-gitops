# Secret Management Strategy

## Purpose

This document is the **reproducible implementation and operating guide** for secret handling in the AI Platform.

The goal is to keep credentials and secret material out of Git while still allowing workloads, CI/CD automation, identity components, and platform services to consume the credentials they need.

The current security model is:

```text
Git
  |
  +--> stores configuration
  +--> stores secret references
  +--> never stores secret values
  |
  v
Vault
  |
  +--> source of truth for secrets
  |
  v
runtime secret delivery
  |
  +--> Kubernetes Secret where currently required
  +--> GitHub Actions Secrets for CI-only credentials
```

The current project deliberately does **not** claim that:

```text
External Secrets Operator
Vault CSI Driver
Secrets Store CSI Driver
```

are installed unless later verified.

This distinction is critical.

A new engineer should be able to:

```text
understand where each secret class belongs
provision secrets without putting them in Git
validate that repositories remain clean
rotate GitHub App credentials
rotate runtime credentials
recover from leaked credentials
understand current limitations
prepare for future External Secrets / Vault CSI integration
```

using this guide and the actual repositories.

---

# 1. Current Secret-Management Architecture

The validated current architecture is:

```text
                         +----------------------+
                         |   GitHub Actions     |
                         |                      |
                         | GitHub App secrets   |
                         +----------+-----------+
                                    |
                                    v
                         source release workflow
                                    |
                                    v
                         short-lived App token


+------------------+        +----------------------+
|      Git         |        |        Vault         |
|                  |        |                      |
| secret refs only |        | source of truth      |
| no secret values |        | runtime credentials  |
+--------+---------+        +----------+-----------+
         |                             |
         v                             v
      Argo CD                 provisioning mechanism
         |                     outside Git / current
         v                     implementation boundary
 Kubernetes manifests                   |
         |                              v
         +---------------------> Kubernetes Secret
                                          |
                                          v
                                      workload
```

---

# 2. Validated Vault Endpoint

Vault endpoint:

```text
https://vault.platform.local:8200
```

Vault is the platform's source of truth for runtime secrets.

Do not place the secret value itself in:

```text
Git
Kustomize
Argo Application values
ConfigMap
README
shell history
PR body
CI logs
```

---

# 3. Current Integration Boundary

Important current-state fact:

```text
Vault is the source of truth
```

but the project has **not yet verified** a GitOps-native automatic secret synchronization layer such as:

```text
External Secrets Operator
Vault CSI Driver
Secrets Store CSI
```

Therefore the current documentation must describe runtime secret delivery honestly as:

```text
provisioned outside Git
then consumed by workloads as Kubernetes Secrets
```

where that is the current implementation.

---

# 4. Why This Matters

It would be incorrect to write:

```text
Argo automatically pulls secrets from Vault
```

unless a verified controller/plugin actually exists.

Likewise, it would be incorrect to show:

```yaml
kind: ExternalSecret
```

as if it were currently deployed.

The current architecture is more accurately:

```text
Git declares references
secret values are provisioned separately
workloads consume Kubernetes Secret objects
```

---

# 5. Secret Categories

Secrets should be classified by purpose.

Current important categories include:

```text
GitHub App private key
GitHub App Client/App ID where treated as sensitive
registry credentials if needed
Vault authentication credentials
Keycloak bootstrap/admin credentials
OIDC client secrets where confidential clients are used
TLS private keys
application/runtime credentials
future MLflow/object-storage credentials
future database credentials
```

Not all of these use the same storage mechanism.

---

# 6. GitHub Actions Secrets

CI/CD-only credentials belong in:

```text
GitHub Actions Secrets
```

Examples:

```text
GitHub App private key
possibly GitHub App client/application identifier depending on chosen configuration
```

The current source release workflow uses a GitHub App to access:

```text
anselem-okeke/ai-platform-gitops
```

The App private key must never be committed.

---

# 7. GitHub App Secret Storage

GitHub UI path:

```text
Repository
  -> Settings
  -> Secrets and variables
  -> Actions
  -> Repository secrets
```

The exact secret names currently used by the workflow must be read from:

```text
.github/workflows/release-images.yml
```

Do not invent names.

A clean future naming convention can be:

```text
GITOPS_APP_PRIVATE_KEY
```

and, if needed:

```text
GITOPS_APP_CLIENT_ID
```

but preserve the actual workflow variable names until deliberately migrated.

---

# 8. Why Exact Secret Names Must Come from the Workflow

A workflow may reference:

```yaml
${{ secrets.SOME_NAME }}
```

or:

```yaml
${{ vars.SOME_NAME }}
```

Changing the secret name in GitHub without updating the workflow breaks release automation.

Inspect:

```bash
cd /mnt/data/ai-platform-operator

grep -RIn \
  'secrets\.|vars\.' \
  .github/workflows/release-images.yml
```

Record exact references before rebuilding.

---

# 9. GitHub App Token Flow

The private key itself is long-lived secret material.

The workflow uses it only to mint a short-lived installation token.

Conceptually:

```text
GitHub App private key
        |
        v
create-github-app-token action
        |
        v
short-lived installation token
        |
        v
clone / push / PR
```

This is safer than storing a permanent developer PAT.

---

# 10. GitHub App Token Action

Validated action:

```text
actions/create-github-app-token
```

Pinned SHA:

```text
bcd2ba49218906704ab6c1aa796996da409d3eb1
```

Representative workflow snippet:

```yaml
- name: Create GitHub App token
  id: app-token
  uses: actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1
  with:
    app-id: ${{ vars.<ACTUAL_APP_ID_VARIABLE> }}
    private-key: ${{ secrets.<ACTUAL_PRIVATE_KEY_SECRET> }}
    owner: anselem-okeke
    repositories: ai-platform-gitops
```

The identifiers in angle brackets must be replaced with the exact workflow names.

---

# 11. Why the Private Key Must Be a Secret, Not a Variable

Use GitHub Actions **Secrets** for:

```text
private keys
tokens
passwords
credential material
```

Use Variables for non-secret metadata such as:

```text
repository owner
application identifier
environment label
```

if the value is not sensitive.

---

# 12. Repository `.gitignore`

The GitOps repository includes secret-oriented exclusions.

Validated patterns include:

```text
.local/
*.jwt
*.key
*.pem
.env
secret YAML patterns
```

The repository intentionally does **not** broadly ignore:

```text
*.crt
```

because public certificates are not necessarily secret.

---

# 13. Why `.gitignore` Is Only Defense in Depth

`.gitignore` does not protect already-tracked files.

It also does not prevent a developer from explicitly adding a file with:

```bash
git add -f
```

Therefore additional controls are required:

```text
Gitleaks
history scan
review
CI secret-pattern checks
```

---

# 14. Gitleaks

Both source and GitOps repositories have been checked with Gitleaks.

The project validated:

```text
current tracked state clean
Git history scan clean
```

This is part of secret-management assurance.

---

# 15. Gitleaks Workflow Role

Gitleaks should be treated as:

```text
required enforcement
```

not merely:

```text
informational scanning
```

The source branch ruleset already requires:

```text
Gitleaks
```

before merge.

---

# 16. GitOps CI Secret Pattern Check

The GitOps validation workflow includes lightweight secret-pattern checks.

This is defense in depth.

It should detect obvious examples such as:

```text
private key blocks
password-like fields
token-like content
embedded credential values
```

The exact regex must be taken from:

```text
.github/workflows/validate.yml
```

Do not invent the current implementation.

---

# 17. Secret References vs Secret Values

Allowed in Git:

```yaml
env:
  - name: DATABASE_PASSWORD
    valueFrom:
      secretKeyRef:
        name: platform-db
        key: password
```

Not allowed in Git:

```yaml
env:
  - name: DATABASE_PASSWORD
    value: super-secret-password
```

This distinction is central.

---

# 18. Representative Kubernetes Secret Reference

Example Deployment snippet:

```yaml
env:
  - name: EXAMPLE_USERNAME
    valueFrom:
      secretKeyRef:
        name: example-runtime-credentials
        key: username

  - name: EXAMPLE_PASSWORD
    valueFrom:
      secretKeyRef:
        name: example-runtime-credentials
        key: password
```

The secret name can be committed.

The secret values cannot.

---

# 19. Representative Secret Volume Reference

For file-based credentials:

```yaml
volumes:
  - name: credentials
    secret:
      secretName: example-runtime-credentials

containers:
  - name: app
    volumeMounts:
      - name: credentials
        mountPath: /var/run/platform/credentials
        readOnly: true
```

Again:

```text
reference is Git-safe
secret material is not
```

---

# 20. Why Raw Kubernetes Secret YAML Is Dangerous

A Kubernetes Secret manifest like:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: example
type: Opaque
data:
  password: <BASE64_PASSWORD_PLACEHOLDER>
```

is **not encrypted**.

Base64 is encoding, not encryption.

Therefore do not commit such files to Git.

---

# 21. Base64 Is Not Security

Anyone can decode:

```bash
echo 'c3VwZXJzZWNyZXQ=' \
  | base64 -d
```

Therefore:

```text
Secret YAML + base64
```

must still be treated as plaintext secret material.

---

# 22. Current Runtime Secret Provisioning Model

Current honest model:

```text
Vault stores source secret
      |
      v
authorized operator/provisioning step
      |
      v
Kubernetes Secret
      |
      v
workload secretKeyRef / volume
```

The exact automation mechanism is not yet standardized as a GitOps controller.

---

# 23. Manual Secret Provisioning Pattern

For current dev use, a controlled secret can be created without writing a YAML file to disk.

Representative:

```bash
kubectl create secret generic example-runtime-credentials \
  -n ai-platform \
  --from-literal=username="$USERNAME" \
  --from-literal=password="$PASSWORD"
```

This avoids committing a secret manifest.

However, shell history and process environment still require care.

---

# 24. Safer Temporary Shell Handling

Avoid:

```bash
export PASSWORD='literal-secret'
```

in long-lived shell sessions if history/process inspection is a concern.

Prefer reading securely from a credential source or ephemeral command context.

The exact Vault CLI/API workflow should be documented once authenticated access is standardized.

---

# 25. Server-Side Secret Creation from stdin

A safer pattern avoids writing plaintext YAML to disk.

Representative:

```bash
kubectl create secret generic example-runtime-credentials \
  -n ai-platform \
  --from-literal=username="$USERNAME" \
  --from-literal=password="$PASSWORD" \
  --dry-run=client \
  -o yaml \
  | kubectl apply -f -
```

The generated Secret still exists in the cluster, but not as a committed file.

---

# 26. Verify Secret Exists Without Printing Values

Good:

```bash
kubectl get secret \
  example-runtime-credentials \
  -n ai-platform
```

Good:

```bash
kubectl get secret \
  example-runtime-credentials \
  -n ai-platform \
  -o jsonpath='{.metadata.name}{"\n"}'
```

Avoid:

```bash
kubectl get secret \
  example-runtime-credentials \
  -n ai-platform \
  -o yaml
```

in shared logs because it prints base64-encoded secret data.

---

# 27. Verify Secret Keys Without Printing Values

Use:

```bash
kubectl get secret \
  example-runtime-credentials \
  -n ai-platform \
  -o json \
  | jq -r '.data | keys[]'
```

This shows keys only.

Example:

```text
username
password
```

---

# 28. Kubernetes Secret RBAC

Not every user/service account should be able to:

```text
get
list
watch
```

Secrets.

Secret read permission is equivalent to credential read permission.

RBAC should follow least privilege.

---

# 29. Avoid `list secrets` When Only One Secret Is Needed

A service account that needs one credential should not automatically receive:

```text
list/watch all secrets
```

Prefer narrow resource access where Kubernetes RBAC and architecture permit.

---

# 30. Secret Exposure Through Pod Spec

A `secretKeyRef` does not expose the value in the Deployment manifest.

Good:

```yaml
valueFrom:
  secretKeyRef:
```

The value remains in the Secret object and is injected at runtime.

---

# 31. Secret Exposure Through Logs

Applications must not log:

```text
passwords
tokens
JWTs
private keys
authorization headers
full environment dumps
```

This is a runtime concern, not just a Git concern.

---

# 32. Avoid Printing Environment During CI

Commands such as:

```bash
env
printenv
set
```

can expose masked or unmasked metadata.

Do not dump the entire environment in CI troubleshooting.

---

# 33. GitHub Secret Masking Is Not a Substitute for Good Logging

GitHub masks known secret values, but:

```text
derived values
encoded values
partial values
structured private keys
```

may still leak.

Do not rely solely on masking.

---

# 34. Vault as Source of Truth

Vault should own the authoritative runtime credential lifecycle:

```text
create
store
rotate
revoke
audit
```

Kubernetes Secrets are runtime delivery objects, not the long-term authoritative secret store.

---

# 35. Why Vault

Vault provides capabilities such as:

```text
centralized secret storage
access policy
audit
lease/revocation model
dynamic secrets where supported
PKI
```

The platform already uses Vault PKI elsewhere in the architecture.

---

# 36. Vault Authentication

The exact workload authentication mechanism must be documented from the real implementation.

Possible mechanisms include:

```text
Kubernetes auth
AppRole
OIDC/JWT
token
```

Do not assume which one is currently used if it has not been verified.

---

# 37. Vault Secret Path Naming

Use stable paths.

Representative future structure:

```text
secret/data/ai-platform/dev/api
secret/data/ai-platform/dev/operator
secret/data/ai-platform/dev/mlflow
secret/data/ai-platform/dev/object-storage
```

This is a recommended naming pattern, not a claim of existing paths.

---

# 38. Environment Separation

Do not reuse the same runtime credentials across:

```text
dev
staging
prod
```

Future Vault layout should separate environments.

Example:

```text
ai-platform/dev/...
ai-platform/staging/...
ai-platform/prod/...
```

---

# 39. Credential Rotation

Rotation should replace:

```text
secret material
```

without requiring:

```text
source-code change
```

A robust application should reference a stable secret name while the secret value changes.

---

# 40. Kubernetes Secret Rotation Flow

Current generic flow:

```text
create new secret value in Vault
        |
        v
update Kubernetes Secret
        |
        v
restart/reload workload if required
        |
        v
verify
        |
        v
revoke old credential
```

The exact order depends on whether both old and new credentials can coexist.

---

# 41. Zero-Downtime Rotation

For systems that support dual credentials:

```text
1. create new credential
2. make both old/new valid
3. update runtime Secret
4. roll workload
5. verify new credential
6. revoke old credential
```

This reduces downtime.

---

# 42. Rotation When Dual Credentials Are Not Supported

For a single password/token:

```text
1. plan maintenance window if needed
2. rotate upstream credential
3. immediately update runtime Secret
4. restart/reload workload
5. verify
```

Keep outage window minimal.

---

# 43. Secret Changes and Argo CD

Because raw Secret values are not stored in Git, Argo may not know the value changed.

If the application only reloads credentials on restart, the operator may need to trigger a rollout.

Do not use arbitrary Git changes solely to force restarts without documenting why.

---

# 44. Future External Secret Synchronization

A future implementation may add:

```text
External Secrets Operator
```

Then Git could safely store an object like:

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: example-runtime-credentials
spec:
  secretStoreRef:
    name: vault
    kind: ClusterSecretStore

  target:
    name: example-runtime-credentials

  data:
    - secretKey: password
      remoteRef:
        key: ai-platform/dev/example
        property: password
```

This is **future architecture only**.

Do not deploy this manifest unless the operator and CRDs are actually installed and reviewed.

---

# 45. Future Vault CSI Pattern

A future alternative is direct volume injection.

Representative future-only concept:

```yaml
volumes:
  - name: secrets-store
    csi:
      driver: secrets-store.csi.k8s.io
      readOnly: true
```

Again:

```text
not current verified implementation
```

---

# 46. Choosing External Secrets vs CSI Later

External Secrets is useful when workloads expect:

```text
native Kubernetes Secret objects
```

CSI is useful when workloads can consume:

```text
mounted secret files
```

The choice should be architecture-driven.

---

# 47. GitHub App Private-Key Rotation

The GitHub App private key is one of the most important CI secrets.

Rotation flow:

```text
1. generate new private key in GitHub App settings
2. add new key to GitHub Actions Secret
3. test token minting
4. test GitOps PR automation
5. revoke old private key
6. remove old local copies
```

Do not revoke the old key before verifying the new one.

---

# 48. Validate GitHub App Token After Rotation

Run a release or controlled token test.

Expected:

```text
token created
GitOps repository accessible
automation branch push works
PR creation works
```

If token creation fails, inspect the workflow secret reference first.

---

# 49. GitHub App Key Storage

Never store the private key under:

```text
.local/
*.pem
*.key
```

in a way that is accidentally tracked.

The `.gitignore` helps, but local files still need filesystem protection.

---

# 50. File Permissions for Local Private Keys

If a private key must temporarily exist locally:

```bash
chmod 600 \
  /path/to/private-key.pem
```

Delete it when no longer needed.

Do not share private key files through chat, tickets, or documentation.

---

# 51. Keycloak Secrets

Keycloak bootstrap/admin credentials are sensitive.

The project validated bootstrap configuration and later removed/unset bootstrap environment values.

Do not commit bootstrap credentials.

Long-term authentication should use normal Keycloak realm/users/clients rather than permanent bootstrap admin secrets.

---

# 52. OIDC Clients

The Argo CD client is public with PKCE:

```text
publicClient: true
standardFlowEnabled: true
directAccessGrantsEnabled: false
PKCE S256
```

A public client intentionally does not rely on a client secret.

This reduces secret-management burden for that client.

---

# 53. Confidential OIDC Clients

If a future client is confidential:

```text
client secret
```

must be stored outside Git.

Use Vault / runtime secret delivery.

Do not hardcode it in:

```text
Argo ConfigMap
Kustomize
Helm values
source code
```

---

# 54. TLS Private Keys

TLS private keys are secrets.

Public certificate:

```text
.crt
```

may be non-secret.

Private key:

```text
.key
.pem
```

must remain protected.

This is why the GitOps `.gitignore` does not need to blanket-ignore every certificate file.

---

# 55. Vault PKI

The platform architecture includes Vault PKI for TLS certificate issuance.

Private key lifecycle must stay outside Git.

Representative relationship:

```text
Vault PKI
   |
   v
TLS certificate + private key
   |
   v
Kubernetes TLS Secret
   |
   v
Gateway/API
```

The exact issuance automation must be documented separately from secret storage if implemented.

---

# 56. Kubernetes TLS Secret

Representative runtime object:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: api-tls
type: kubernetes.io/tls
data:
  tls.crt: <base64>
  tls.key: <base64>
```

Do not commit the actual rendered Secret containing `tls.key`.

A template/reference may be documented, but not live values.

---

# 57. CI Secret Leak Response

If a GitHub Actions secret is exposed:

```text
1. revoke/rotate immediately
2. invalidate associated tokens
3. inspect workflow logs
4. inspect Git history
5. inspect PRs/issues/artifacts
6. replace secret in GitHub
7. retest automation
8. document incident
```

Deleting a log line is not enough.

---

# 58. Git Secret Leak Response

If a secret is committed:

```text
first rotate/revoke the credential
```

Then:

```text
remove it from current Git
clean history if necessary
re-run Gitleaks
notify affected systems
```

Do not rely on history rewriting as the first security response.

The secret must be considered compromised.

---

# 59. Why Rotation Comes Before Git History Cleanup

Once a secret reaches Git:

```text
copies may already exist
```

Even if the commit is force-removed, the credential may remain in:

```text
forks
clones
CI caches
PR diffs
logs
```

Therefore:

```text
revoke first
```

---

# 60. Gitleaks Revalidation After Incident

Run on source:

```bash
cd /mnt/data/ai-platform-operator

gitleaks git \
  --redact
```

Run on GitOps:

```bash
cd /mnt/data/ai-platform-gitops

gitleaks git \
  --redact
```

Use the exact Gitleaks command/version standardized by the workflows if different.

---

# 61. Search Tracked Files for Private Keys

Useful defensive check:

```bash
git grep -n \
  'BEGIN .*PRIVATE KEY'
```

Expected:

```text
no matches
```

---

# 62. Search Tracked Secret-like Values

Examples:

```bash
git grep -nEi \
  'password[[:space:]]*[:=][[:space:]]*[^$<{[:space:]]+'
```

Be careful with false positives.

Use automated scanners as the primary control.

---

# 63. Search for Raw Kubernetes Secrets

```bash
git grep -n \
  'kind: Secret'
```

A result is not automatically wrong.

Review whether it is:

```text
template/documentation
secret metadata only
generated example
actual secret material
```

The key rule is:

```text
no real secret values
```

---

# 64. GitOps CI Defense-in-Depth

The GitOps validation workflow should reject obvious secret material before merge.

This does not replace:

```text
Gitleaks
review
proper secret architecture
```

---

# 65. Secret Names Are Not Secret Values

A manifest containing:

```yaml
secretName: api-runtime-credentials
```

is acceptable.

Do not over-redact architecture documentation so much that rebuild instructions become unusable.

---

# 66. Avoid Secrets in URLs

Bad:

```text
https://user:password@example.internal
```

Good:

```text
https://example.internal
```

with credentials supplied separately.

---

# 67. Avoid Secrets in Command-Line Arguments

Commands may be visible in:

```text
shell history
process list
audit logs
```

Prefer stdin, files with restricted permissions, or authenticated tooling when possible.

---

# 68. Avoid Secrets in Environment Variables Where Possible

Environment variables are convenient but may leak through:

```text
process inspection
debug dumps
crash diagnostics
application logs
```

For highly sensitive credentials, mounted files may be preferable.

---

# 69. Kubernetes Secret at Rest

Kubernetes Secret storage in etcd should be protected with:

```text
encryption at rest
RBAC
cluster access controls
```

This project documentation does not claim a specific etcd encryption-at-rest configuration unless verified.

Do not imply Kubernetes Secret is equivalent to Vault.

---

# 70. Backup Considerations

Do not back up secrets into insecure archives.

If backing up Kubernetes or Vault:

```text
encrypt backup
control access
rotate credentials if exposure occurs
document restore procedure
```

---

# 71. Disaster Recovery

For rebuild, do not rely on Git to restore secrets.

A complete DR plan needs:

```text
Vault backup/restore
credential reissuance
GitHub App key regeneration
TLS certificate reissuance
runtime Secret recreation
```

This is separate from normal GitOps reconstruction.

---

# 72. GitOps Rebuild Without Secrets

A new engineer should be able to restore most declarative platform state from Git.

Then:

```text
secret provisioning
```

must happen as a separate secure step.

This is intentional.

---

# 73. Example Rebuild Sequence

```text
1. restore cluster
2. restore Argo/GitOps
3. restore Vault
4. restore/create runtime credentials
5. provision Kubernetes Secrets
6. restore GitHub Actions Secrets
7. validate workloads
8. rotate credentials if provenance uncertain
```

---

# 74. Future Object Storage Credentials

Phase 8 will likely require credentials for:

```text
S3-compatible object storage
```

These must follow the same model:

```text
Vault source of truth
no Git values
runtime secret reference
```

---

# 75. Future MLflow Credentials

Possible future secrets include:

```text
database password
object-store access key
object-store secret key
OIDC client secret if used
```

Keep them out of:

```text
MLflow Helm values committed to Git
```

unless the values are references only.

---

# 76. Future KServe Storage Credentials

KServe may need access to object storage.

Do not embed credentials inside:

```text
InferenceService YAML
ModelService CR
container arguments
```

Use secret references or supported service-account/storage credential mechanisms.

---

# 77. Secret Naming Convention

Recommended:

```text
<component>-<purpose>
```

Examples:

```text
api-runtime-credentials
mlflow-db-credentials
object-storage-credentials
gateway-tls
```

Avoid generic names like:

```text
secret1
prod-secret
password
```

---

# 78. Namespace Scope

Store runtime Secrets in the namespace that needs them whenever possible.

Examples:

```text
ai-platform
monitoring
keycloak
```

Avoid cross-namespace secret sharing through broad RBAC.

---

# 79. Immutable Secrets

Kubernetes supports immutable Secrets.

This can reduce accidental mutation but complicates rotation.

Use only when the credential lifecycle fits recreate-on-rotation behavior.

Do not enable blindly.

---

# 80. Secret Ownership

Every secret should have an owner.

Record:

```text
component
purpose
system of record
rotation method
rotation frequency
recovery owner
```

Do not create orphaned credentials.

---

# 81. Secret Inventory

Maintain an inventory containing metadata only.

Example:

```text
Name: GitOps GitHub App private key
System of record: GitHub App
Runtime store: GitHub Actions Secrets
Consumer: release-images workflow
Rotation: GitHub App key rotation

Name: API runtime credential
System of record: Vault
Runtime store: Kubernetes Secret
Consumer: ai-platform-api
Rotation: Vault + Secret update
```

Do not put secret values in the inventory.

---

# 82. Rotation Frequency

The project should define rotation based on:

```text
credential risk
provider capabilities
compliance requirements
incident history
```

Do not invent arbitrary rotation periods without organizational policy.

---

# 83. Secret Expiry Monitoring

Where credentials expire, add monitoring before production.

Examples:

```text
certificates
tokens
leases
client credentials
```

The current Prometheus alerting focuses on Policy Controller; secret-expiry monitoring may be added later.

---

# 84. GitHub App Installation Token Lifetime

Installation tokens are short-lived.

This is intentional.

The workflow should create a fresh token per release run rather than persisting it.

---

# 85. Do Not Persist Installation Tokens

Never save GitHub App installation tokens into:

```text
repository secret
artifact
cache
file committed to Git
```

They should exist only for the workflow execution window.

---

# 86. Secret Masking in Workflow Output

Do not echo:

```yaml
${{ secrets.<SECRET> }}
```

Do not print the full installation token.

If debugging token creation, inspect:

```text
step success/failure
HTTP status
repository access
```

not token content.

---

# 87. Secret-Handling Review Checklist

```text
[ ] no raw secret values in Git
[ ] no private keys in Git
[ ] no JWT files in Git
[ ] `.local/` excluded
[ ] Gitleaks passes
[ ] Git history scan passes
[ ] GitOps secret-pattern check passes
[ ] GitHub App private key stored in Actions Secret
[ ] runtime secret source is Vault
[ ] Kubernetes workloads use Secret references
[ ] exact current Vault sync mechanism not overstated
[ ] secret-read RBAC minimized
[ ] logs do not print credentials
[ ] rotation procedure documented
[ ] incident response documented
```

---

# 88. Git Repository Validation

Source:

```bash
cd /mnt/data/ai-platform-operator

git status --short
```

GitOps:

```bash
cd /mnt/data/ai-platform-gitops

git status --short
```

Then run secret scanning according to the standardized project workflows.

---

# 89. Check for Tracked Sensitive Extensions

Source:

```bash
git ls-files \
  | grep -Ei '\.(pem|key|jwt)$'
```

GitOps:

```bash
git ls-files \
  | grep -Ei '\.(pem|key|jwt)$'
```

Expected:

```text
no real sensitive files
```

Documentation/examples must be reviewed carefully.

---

# 90. Check `.env` Files

```bash
git ls-files \
  | grep -E '(^|/)\.env($|\.)'
```

Real secret-bearing `.env` files should not be tracked.

---

# 91. Verify `.gitignore`

```bash
cd /mnt/data/ai-platform-gitops

cat .gitignore
```

Confirm expected secret patterns remain.

Do not blindly add:

```text
*.crt
```

because public certificates can be legitimate repository content.

---

# 92. Runtime Secret Validation Without Leakage

To confirm a Pod references the expected Secret:

```bash
kubectl get deployment \
  ai-platform-api \
  -n ai-platform \
  -o yaml \
  | grep -A6 -B3 'secretKeyRef\|secretName'
```

This shows references, not values.

---

# 93. Validate a Secret Consumer Pod

Inspect environment source:

```bash
kubectl describe pod \
  -n ai-platform \
  <POD>
```

Be cautious because `describe` can expose some configuration metadata.

It normally does not print Secret values for secretKeyRef.

---

# 94. Rotation Verification

After rotating a credential:

```text
workload starts
authentication succeeds
old credential revoked
no logs expose secret
Git remains unchanged except reference/config changes if needed
```

---

# 95. Secret-Related Failure Scenario — Workload Cannot Start

Check events:

```bash
kubectl get events \
  -n <namespace> \
  --sort-by=.lastTimestamp
```

Possible errors:

```text
Secret not found
key not found
volume mount failed
```

---

# 96. Secret Not Found

Check:

```bash
kubectl get secret \
  <SECRET_NAME> \
  -n <namespace>
```

If missing:

```text
provision it through the approved secret path
```

Do not add the secret value to Git as a quick fix.

---

# 97. Secret Key Missing

List keys only:

```bash
kubectl get secret \
  <SECRET_NAME> \
  -n <namespace> \
  -o json \
  | jq -r '.data | keys[]'
```

Compare to workload `secretKeyRef.key`.

---

# 98. Wrong Namespace

Secrets are namespace-scoped.

If Deployment is in:

```text
ai-platform
```

a Secret only in:

```text
default
```

cannot be referenced directly.

Provision into the intended namespace.

---

# 99. Secret Exists but Application Authentication Fails

Possible causes:

```text
credential value stale
upstream credential rotated
wrong username/password pair
secret mounted but app not reloaded
encoding/format issue
```

Do not print the credential to diagnose.

---

# 100. Application Needs Restart After Secret Change

Some applications read secrets only at startup.

After secret update:

```bash
kubectl rollout restart \
  deployment/<NAME> \
  -n <NAMESPACE>
```

Use only when required.

If Argo manages annotations/Pod templates, ensure restart action does not cause persistent Git drift.

---

# 101. Prefer Git-Driven Restart Metadata for Repeatability

For planned credential rotation, a GitOps-managed rollout annotation may be more auditable.

Example concept:

```yaml
metadata:
  annotations:
    platform.anselem.dev/restarted-at: "2026-08-22T12:00:00Z"
```

Use only if this pattern is deliberately standardized.

Do not generate meaningless Git churn.

---

# 102. Secret Compromise Severity

Treat compromise of:

```text
GitHub App private key
Vault token
TLS private key
database password
cloud access key
```

as a security incident.

Response should prioritize:

```text
revocation
rotation
containment
audit
```

---

# 103. GitHub App Private Key Compromise

Immediate steps:

```text
1. generate new App key
2. replace Actions Secret
3. verify new key
4. revoke compromised key
5. inspect App installation activity
6. inspect GitOps PR/push history
```

---

# 104. Vault Token Compromise

Immediate response depends on auth method.

Generic:

```text
revoke token/lease
rotate affected downstream credentials
review Vault audit logs
replace runtime Secret
verify workloads
```

---

# 105. TLS Private Key Compromise

Treat certificate identity as compromised.

Generic:

```text
revoke/replace certificate if supported
issue new keypair
update Kubernetes TLS Secret
roll/reload gateway
verify TLS
```

---

# 106. Prevent Secrets in Documentation

Do not paste:

```text
real tokens
private keys
passwords
real JWTs
```

into runbooks.

Use placeholders:

```text
<SECRET>
<REAL_TRUSTED_DIGEST>
<CLIENT_ID>
```

Architecture docs should remain shareable without credential cleanup.

---

# 107. Prevent Secrets in Screenshots

Screenshots can expose:

```text
terminal history
browser autofill
tokens
Vault UI values
GitHub secrets names/values
```

Redact before publication.

---

# 108. Prevent Secrets in LinkedIn/Public Posts

Public architecture posts should show:

```text
Vault
GitHub Actions Secrets
Kubernetes Secret reference
```

but never:

```text
actual secret names that reveal sensitive systems if unnecessary
values
keys
tokens
internal credentials
```

---

# 109. Future Desired State

A stronger future runtime model is:

```text
Vault
  |
  v
External Secrets Operator
  |
  v
Kubernetes Secret
  |
  v
workload
```

or:

```text
Vault
  |
  v
Secrets Store CSI
  |
  v
mounted secret file
  |
  v
workload
```

The project should select one intentionally rather than adding both without need.

---

# 110. Future External Secrets Security Requirements

If adopted:

```text
pin operator version
GitOps-manage installation
least-privilege Vault auth
namespace-scoped SecretStores where practical
avoid broad ClusterSecretStore unless needed
monitor reconciliation failures
test secret rotation
test Vault outage behavior
```

---

# 111. Future CSI Security Requirements

If adopted:

```text
pin CSI versions
least-privilege Vault role
read-only mounts
avoid syncing to Kubernetes Secret unless needed
monitor mount failures
document rotation behavior
```

---

# 112. Rebuild from Zero

```text
[ ] restore Git repositories
[ ] verify `.gitignore`
[ ] run Gitleaks
[ ] verify no private keys/JWTs tracked
[ ] restore Vault
[ ] verify Vault endpoint
[ ] restore runtime secret records
[ ] create/restore GitHub App
[ ] create new App private key
[ ] store App key in GitHub Actions Secret
[ ] verify workflow references exact secret/variable names
[ ] test short-lived App token
[ ] provision Kubernetes Secrets outside Git
[ ] verify Secret names/keys only
[ ] verify workloads use secretKeyRef/secret volumes
[ ] verify workloads authenticate
[ ] verify no secret values in logs
[ ] verify secret-read RBAC
[ ] test rotation procedure
[ ] document current manual/provisioning boundary
```

---

# 113. Current Implementation Facts

Validated:

```text
Vault endpoint:
https://vault.platform.local:8200

Vault:
source of truth for runtime secrets

GitHub Actions Secrets:
used for GitHub App credentials

Git:
stores secret references/configuration only

Gitleaks:
used in source CI/history checks

GitOps:
also scanned / secret-pattern guarded

GitOps `.gitignore` includes:
.local/
*.jwt
*.key
*.pem
.env
secret YAML patterns

GitOps `.gitignore` does not broadly ignore:
*.crt

External Secrets Operator:
not currently verified as installed

Vault CSI:
not currently verified as installed

runtime dev credentials:
may be provisioned outside Git into Kubernetes Secrets
```

---

# 114. What Must Be Verified from the Actual Repositories

Do not invent:

```text
exact GitHub Actions secret names
exact GitHub Actions variable names
exact current Vault auth method
exact Vault secret paths
exact runtime Kubernetes Secret names
exact secret key names
exact current secret provisioning scripts
exact current GitOps secret-pattern regex
```

Inspect:

```bash
cd /mnt/data/ai-platform-operator

grep -RIn \
  'secrets\.|vars\.|secretKeyRef|secretName' \
  .github \
  api \
  config \
  controllers \
  2>/dev/null
```

GitOps:

```bash
cd /mnt/data/ai-platform-gitops

grep -RIn \
  'secretKeyRef|secretName|kind: Secret|vault' \
  platform \
  clusters \
  argocd \
  2>/dev/null
```

Then document exact names only after verification.

---

# 115. Official References

HashiCorp Vault:

```text
https://developer.hashicorp.com/vault/docs
```

Kubernetes Secrets:

```text
https://kubernetes.io/docs/concepts/configuration/secret/
```

Kubernetes RBAC:

```text
https://kubernetes.io/docs/reference/access-authn-authz/rbac/
```

GitHub Actions secrets:

```text
https://docs.github.com/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions
```

GitHub Apps authentication:

```text
https://docs.github.com/apps/creating-github-apps/authenticating-with-a-github-app
```

Gitleaks:

```text
https://github.com/gitleaks/gitleaks
```

External Secrets Operator:

```text
https://external-secrets.io/
```

Secrets Store CSI Driver:

```text
https://secrets-store-csi-driver.sigs.k8s.io/
```

Vault CSI / Kubernetes integration:

```text
https://developer.hashicorp.com/vault/docs/platform/k8s
```

---

# 116. Related AI Platform Documentation

```text
007-keycloak-bootstrap.md
008-keycloak-oidc-clients.md
019-source-ci-pipeline.md
024-github-app-gitops-automation.md
025-image-digest-update-workflow.md
031-sigstore-policy-controller.md
032-github-attestation-trust.md
038-secret-scanning.md
039-software-supply-chain-security.md
040-end-to-end-delivery-workflow.md
041-validation-and-security-tests.md
042-rebuild-and-disaster-recovery.md
043-troubleshooting-guide.md
044-operations-runbook.md
045-command-reference.md
047-design-decisions.md
