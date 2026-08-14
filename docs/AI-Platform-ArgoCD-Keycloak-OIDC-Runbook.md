# AI Platform Argo CD and Keycloak OIDC Runbook

**Date:** 13 August 2026  
**Argo CD version:** v3.5.1  
**Repositories:**

- `/mnt/data/ai-platform-operator`
- `/mnt/data/ai-platform-gitops`

## 1. Purpose

This runbook records the work completed to prepare Argo CD authentication through Keycloak using OpenID Connect (OIDC), OAuth 2.0 Authorization Code flow, and PKCE S256.

It also records the RBAC design for these Keycloak groups:

| Keycloak group | Argo CD role | Intended access |
|---|---|---|
| `platform-viewer` | `role:platform-viewer` | Read AI Platform applications, project information, and logs |
| `platform-deployer` | `role:platform-deployer` | Viewer access plus synchronization of AI Platform applications |
| `platform-admin` | Built-in `role:admin` | Argo CD administrative access |

No passwords, access tokens, refresh tokens, or client secrets belong in this document or in Git.

## 2. Current checkpoint

### Completed and verified

- Argo CD v3.5.1 is installed.
- The `ai-platform` AppProject exists in the `argocd` namespace.
- `argocd-server` remains an internal `ClusterIP` Service.
- A dedicated Keycloak public client named `ai-platform-argocd` exists.
- The client uses the Authorization Code flow and PKCE S256.
- Direct Access Grants are disabled.
- The three platform groups exist in Keycloak.
- The test users have the intended group memberships.
- A `groups` OIDC client scope and group-membership mapper exist.
- The `groups` scope is attached to `ai-platform-argocd` and `ai-platform-cli`.
- A real `viewer-user` token contains `groups: ['platform-viewer']`.
- The Argo CD OIDC and RBAC Kustomize patches compile successfully.
- The Argo CD CLI reports that the RBAC policy is valid.

### Prepared but not yet applied

- The rendered Argo CD OIDC configuration.
- The rendered Argo CD RBAC policy.

### Still pending

- Server-side dry-run and review of the Argo CD manifests.
- Applying the OIDC and RBAC configuration to the cluster.
- Restarting `argocd-server` and verifying the live ConfigMaps.
- Exposing `argocd.ai-platform.local` through HTTPS.
- Issuing and installing the Argo CD TLS certificate.
- Testing SSO and permissions for all three platform roles.
- Disabling the built-in local `admin` account.

> **Security stop:** Do not disable Argo CD's built-in `admin` account until Keycloak SSO has been tested successfully with `platform-admin` and the recovery path is understood.

## 3. Authentication and authorization flow

1. A user opens the Argo CD UI or starts an Argo CD CLI SSO login.
2. Argo CD redirects the user to the `ai-platform` realm in Keycloak.
3. Keycloak authenticates the user.
4. Authorization Code plus PKCE S256 protects the code exchange.
5. Keycloak returns tokens containing the user's `groups` claim.
6. Argo CD reads the `groups` claim.
7. Argo CD RBAC maps the Keycloak group to the appropriate Argo CD role.

The authentication decision belongs to Keycloak. The authorization decision belongs to Argo CD RBAC.

## 4. Initial PKCE token test

From the operator repository:

```bash
cd /mnt/data/ai-platform-operator

infrastructure/keycloak/scripts/pkce-login.py
```

The helper opened the Keycloak authorization URL, listened on `127.0.0.1:18080`, exchanged the authorization code, and wrote:

```text
.local/keycloak/tokens/user-token-response.json
.local/keycloak/tokens/user-access-token.jwt
```

The following message appeared during SSH callback forwarding:

```text
channel N: open failed: connect failed: Connection refused
```

The flow still ended with:

```text
PASS: Authorization Code + PKCE exchange completed.
```

Therefore, the temporary SSH channel message did not invalidate the successful OAuth exchange.

### Why `export TOKEN` originally failed

Running this alone does not load a token:

```bash
export TOKEN
```

It only exports a variable if that variable already has a value. Python consequently raised:

```text
KeyError: 'TOKEN'
```

The corrected command was:

```bash
export TOKEN="$(
  tr -d '\r\n' \
    < .local/keycloak/tokens/user-access-token.jwt
)"
```

After inspection, the variable was removed:

```bash
unset TOKEN
```

## 5. Copying the Keycloak configuration script

The active Keycloak pod was selected with:

```bash
KEYCLOAK_POD="$(
  kubectl get pod \
    -n keycloak \
    -l app.kubernetes.io/name=keycloak \
    -o jsonpath='{.items[0].metadata.name}'
)"

echo "${KEYCLOAK_POD}"
```

### Error: `kubectl cp` required `tar`

The first copy attempt failed with:

```text
exec: "tar": executable file not found in $PATH
```

`kubectl cp` depends on `tar` inside the destination container. The hardened Keycloak image is minimal and does not contain it.

Instead of modifying the running Keycloak image, the script was streamed through standard input:

```bash
kubectl exec -i \
  -n keycloak \
  "${KEYCLOAK_POD}" \
  -- sh -c 'cat > /tmp/configure-argocd-oidc.sh && chmod 700 /tmp/configure-argocd-oidc.sh' \
  < infrastructure/keycloak/scripts/configure-argocd-oidc.sh
```

It was verified with:

```bash
kubectl exec \
  -n keycloak \
  "${KEYCLOAK_POD}" \
  -- ls -l /tmp/configure-argocd-oidc.sh
```

The script required Bash, and Bash was present at `/usr/bin/bash`.

## 6. Why the script was moved back to the Ansible server

Running the script inside the Keycloak container produced two problems:

```text
jq: command not found
Unknown options: '--config', '/tmp/ai-platform-kcadm.config'
```

These had separate causes.

### 6.1 Missing `jq`

The minimal Keycloak container intentionally does not contain general-purpose utilities such as `jq`. Installing tools into a running workload would be temporary and would weaken image immutability.

The final design runs the orchestration script on the Ansible server, where `jq` is available, and sends only `kcadm.sh` operations into the Keycloak pod.

### 6.2 Incorrect `kcadm.sh --config` order

The original wrapper effectively called:

```text
kcadm.sh --config FILE get ...
```

The correct ordering is:

```text
kcadm.sh get ... --config FILE
```

The wrapper was corrected so the requested subcommand and arguments precede `--config`.

## 7. Local `kcadm` pod wrapper

A local wrapper was created at:

```text
.local/keycloak/bin/kcadm-in-pod
```

Its purpose is to let the host-side configuration script invoke the Keycloak container's supported `kcadm.sh` executable.

Conceptually, it executes:

```bash
kubectl exec \
  -n keycloak \
  "${KEYCLOAK_POD}" \
  -- /opt/keycloak/bin/kcadm.sh "$@"
```

The bootstrap administrator username and password were loaded into temporary shell environment variables. Their values were never printed or committed.

After verifying that the variables existed, the configuration was executed with:

```bash
KCADM="${PWD}/.local/keycloak/bin/kcadm-in-pod" \
KCADM_CONFIG="/tmp/ai-platform-kcadm.config" \
infrastructure/keycloak/scripts/configure-argocd-oidc.sh
```

The result was:

```text
PASS: Keycloak Argo CD OIDC configuration completed.
```

The bootstrap credential variables were then removed:

```bash
unset KC_BOOTSTRAP_ADMIN_USERNAME
unset KC_BOOTSTRAP_ADMIN_PASSWORD
```

## 8. Keycloak objects created

The script created or reconciled the following desired state.

### Groups

```text
platform-viewer
platform-deployer
platform-admin
```

### User memberships

```text
viewer-user   -> platform-viewer
deployer-user -> platform-deployer
admin-user    -> platform-admin
```

### Argo CD OIDC client

```text
clientId:                  ai-platform-argocd
publicClient:              true
standardFlowEnabled:       true
directAccessGrantsEnabled: false
PKCE method:               S256
```

Approved redirect URIs:

```text
https://argocd.ai-platform.local/auth/callback
https://argocd.ai-platform.local/pkce/verify
http://localhost:8085/auth/callback
```

The localhost callback supports Argo CD CLI SSO. The two HTTPS callbacks support the Argo CD UI.

### Groups client scope and mapper

The `groups` client scope uses:

```text
protocol:       openid-connect
protocolMapper: oidc-group-membership-mapper
claim.name:     groups
full.path:      false
```

The mapper includes the claim in:

```text
ID token
access token
UserInfo response
```

The scope is attached as a default scope to:

```text
ai-platform-argocd
ai-platform-cli
```

## 9. Verifying Keycloak state

The verification commands required the temporary configuration file explicitly:

```bash
KCADM_IN_POD="${PWD}/.local/keycloak/bin/kcadm-in-pod"
KCADM_CONFIG="/tmp/ai-platform-kcadm.config"
```

Without `--config`, `kcadm.sh` reported:

```text
No server specified. Use --server, or 'kcadm.sh config credentials'.
```

This was not a Keycloak server failure. It meant that the command had not been told which authenticated `kcadm` configuration file to use.

### Verify groups

```bash
"${KCADM_IN_POD}" \
  get groups \
  -r ai-platform \
  --fields id,name \
  --config "${KCADM_CONFIG}" |
jq -r '.[] | [.id, .name] | @tsv'
```

All three platform groups were returned.

### Verify client configuration

```bash
"${KCADM_IN_POD}" \
  get clients \
  -r ai-platform \
  -q clientId=ai-platform-argocd \
  --fields id,clientId,publicClient,standardFlowEnabled,directAccessGrantsEnabled \
  --config "${KCADM_CONFIG}" |
jq '.[0]'
```

The returned values confirmed:

```text
publicClient: true
standardFlowEnabled: true
directAccessGrantsEnabled: false
```

A complete client inspection confirmed:

```text
pkce.code.challenge.method: S256
```

### Verify client scope and mapper

The `groups` client scope was found, and its mapper returned:

```text
protocolMapper:     oidc-group-membership-mapper
full.path:          false
id.token.claim:     true
access.token.claim: true
claim.name:         groups
```

## 10. Verifying a real user token

A new PKCE login was performed as `viewer-user`. The fresh access token was decoded locally without printing the JWT itself.

Verified claims:

```text
preferred_username: viewer-user
groups: ['platform-viewer']
realm_access roles include: model-viewer
```

This proves the full Keycloak side of the integration:

1. The user belongs to the intended Keycloak group.
2. The OIDC scope is attached to the client.
3. The mapper inserts the `groups` claim into the token.
4. Argo CD will be able to use that claim for RBAC after its OIDC configuration is applied.

## 11. Preparing the Argo CD GitOps configuration

Work then moved to:

```bash
cd /mnt/data/ai-platform-gitops
```

The bootstrap Kustomization contains:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: argocd

resources:
  - namespace.yaml
  - https://raw.githubusercontent.com/argoproj/argo-cd/v3.5.1/manifests/install.yaml

patches:
  - path: argocd-cm-patch.yaml
  - path: argocd-rbac-cm-patch.yaml
```

The upstream installation source is pinned to Argo CD v3.5.1 rather than an unversioned branch.

## 12. Resolving the Kustomize patch error

The earlier compile attempt failed with:

```text
no resource matches strategic merge patch "ConfigMap.v1.[noGrp]/argocd-cm.argocd"
```

The patch declared `metadata.namespace: argocd`, but the upstream ConfigMap had no namespace at the stage when Kustomize attempted to identify the patch target. Kustomize therefore considered them different resource identities.

The fix was to remove `metadata.namespace` from both patch files and rely on this Kustomization-level transformer:

```yaml
namespace: argocd
```

Each patch now identifies its target only by API version, kind, and name.

## 13. Prepared Argo CD OIDC configuration

File:

```text
argocd/bootstrap/argocd-cm-patch.yaml
```

Desired configuration:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-cm
data:
  url: https://argocd.ai-platform.local

  application.sync.requireOverridePrivilegeForRevisionSync: "true"

  oidc.config: |
    name: Keycloak
    issuer: https://auth.ai-platform.local/realms/ai-platform
    clientID: ai-platform-argocd
    enablePKCEAuthentication: true
    refreshTokenThreshold: 2m
    requestedScopes:
      - openid
      - profile
      - email
      - groups
      - offline_access
```

### Why the revision-sync setting was added

```yaml
application.sync.requireOverridePrivilegeForRevisionSync: "true"
```

The deployer role receives `applications, sync`, but not the powerful `override` permission. This setting prevents a deployer from supplying an arbitrary Git revision during synchronization unless a separate override privilege is deliberately granted.

## 14. Prepared Argo CD RBAC configuration

File:

```text
argocd/bootstrap/argocd-rbac-cm-patch.yaml
```

Desired configuration:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-rbac-cm
data:
  policy.default: role:authenticated
  scopes: '[groups]'

  policy.csv: |
    # platform-viewer
    p, role:platform-viewer, applications, get, ai-platform/*, allow
    p, role:platform-viewer, projects, get, ai-platform, allow
    p, role:platform-viewer, logs, get, ai-platform/*, allow

    # platform-deployer
    p, role:platform-deployer, applications, get, ai-platform/*, allow
    p, role:platform-deployer, applications, sync, ai-platform/*, allow
    p, role:platform-deployer, projects, get, ai-platform, allow
    p, role:platform-deployer, logs, get, ai-platform/*, allow

    # Keycloak group mappings
    g, platform-viewer, role:platform-viewer
    g, platform-deployer, role:platform-deployer
    g, platform-admin, role:admin
```

### Why the default role has no policy lines

Every authenticated user receives `policy.default`. Permissions assigned there cannot later be removed by a more restrictive group rule.

`role:authenticated` is therefore deliberately defined as the default but receives no useful permissions. Access comes only through an explicitly mapped Keycloak group.

### Why deployers do not receive `override`

The `sync` permission deploys the desired state already defined in Git. The `override` permission can deploy arbitrary local manifests or revisions and is considerably more powerful. It is intentionally absent from the deployer role.

## 15. Compile and policy-validation results

The Kustomization was compiled with:

```bash
kubectl kustomize \
  argocd/bootstrap \
  > /tmp/argocd-v3.5.1-oidc.yaml

echo "exit code: $?"
```

Result:

```text
exit code: 0
```

The RBAC patch was validated with:

```bash
argocd admin settings rbac validate \
  --policy-file argocd/bootstrap/argocd-rbac-cm-patch.yaml
```

Result:

```text
Policy is valid.
```

The validator also printed:

```text
user defined roles not found in policies: role:admin
```

This warning is expected when validating the patch in isolation. `role:admin` is a built-in Argo CD role, but the standalone patch file does not contain Argo CD's built-in policy definitions. It does not make the policy invalid.

The rendered YAML was inspected and confirmed to contain:

- `issuer: https://auth.ai-platform.local/realms/ai-platform`
- `clientID: ai-platform-argocd`
- `enablePKCEAuthentication: true`
- `application.sync.requireOverridePrivilegeForRevisionSync: "true"`
- `policy.default: role:authenticated`
- All three Keycloak group mappings

## 16. Exact state at the stopping point

The Keycloak configuration is live and verified.

The Argo CD configuration exists in Git-oriented Kustomize patches and produces valid rendered YAML. It has **not yet been proven live in the Kubernetes cluster**.

Therefore, do not mark these items complete yet:

```text
[ ] Argo CD OIDC ConfigMap applied
[ ] Argo CD RBAC ConfigMap applied
[ ] argocd-server restarted successfully
[ ] live ConfigMaps verified
[ ] Keycloak SSO login to Argo CD verified
[ ] role permissions verified
[ ] local admin disabled
```

## 17. Next immediate step: apply the prepared configuration safely

This section is the next operational checkpoint. It should be performed before exposing and testing the external Argo CD endpoint.

### 17.1 Server-side dry-run

```bash
cd /mnt/data/ai-platform-gitops

kubectl apply \
  --server-side \
  --dry-run=server \
  -k argocd/bootstrap
```

Stop if Kubernetes returns an error.

### 17.2 Review the proposed changes

```bash
kubectl diff \
  -k argocd/bootstrap
```

Exit codes:

```text
0  no differences
1  differences found; this is normal
>1 actual error
```

Review changes to `argocd-cm` and `argocd-rbac-cm`. Confirm that unrelated configuration is not being removed.

### 17.3 Apply without force first

```bash
kubectl apply \
  --server-side \
  -k argocd/bootstrap
```

Do not add `--force-conflicts` automatically. If Kubernetes reports a field-ownership conflict, inspect the exact conflicting resource and field first.

### 17.4 Restart and wait for Argo CD server

```bash
kubectl rollout restart \
  deployment/argocd-server \
  -n argocd

kubectl rollout status \
  deployment/argocd-server \
  -n argocd \
  --timeout=180s
```

### 17.5 Verify live settings

```bash
kubectl get configmap \
  argocd-cm \
  -n argocd \
  -o jsonpath='{.data.oidc\.config}'

echo
```

```bash
kubectl get configmap \
  argocd-rbac-cm \
  -n argocd \
  -o yaml
```

```bash
argocd admin settings rbac validate \
  --namespace argocd
```

Only after these checks pass can the OIDC and RBAC ConfigMaps be marked as live.

## 18. Following checkpoint: HTTPS endpoint and SSO authorization tests

After the prepared configuration is live, the next implementation block is:

1. Create the HTTPS route for `argocd.ai-platform.local`.
2. Obtain and install a Vault-issued TLS certificate.
3. Validate the certificate chain and hostname.
4. Log in as `admin-user` and confirm the `platform-admin` group receives administrative access.
5. Log in as `viewer-user` and prove it can read but cannot synchronize.
6. Log in as `deployer-user` and prove it can synchronize `ai-platform/*` but cannot administer Argo CD or override revisions.
7. Retain the built-in local `admin` account while correcting any SSO or RBAC issue.
8. Disable the built-in `admin` account only after all tests pass and recovery access is documented.

## 19. Security rules retained throughout

- Do not paste passwords, JWTs, authorization codes, client secrets, or refresh tokens into terminal transcripts or documentation.
- Do not commit `.local/` token or credential files.
- Keep the Argo CD Service internal until the HTTPS route and certificate are ready.
- Use PKCE S256 for the public OIDC client.
- Keep Direct Access Grants disabled.
- Grant permissions through groups, not individual user mappings.
- Keep the default authenticated role effectively empty.
- Do not grant deployers `override` by default.
- Do not disable local `admin` before proving SSO administration and recovery.
- Remove temporary `kcadm` configuration and copied scripts after administrative work.

## 20. Optional cleanup of temporary Keycloak files

If they still exist in the current Keycloak pod:

```bash
kubectl exec \
  -n keycloak \
  "${KEYCLOAK_POD}" \
  -- rm -f \
  /tmp/ai-platform-kcadm.config \
  /tmp/configure-argocd-oidc.sh
```

This removes only temporary pod-local files. It does not undo the Keycloak realm configuration.

## 21. Official references

- [Argo CD Keycloak integration](https://argo-cd.readthedocs.io/en/stable/operator-manual/user-management/keycloak/)
- [Argo CD RBAC configuration](https://argo-cd.readthedocs.io/en/stable/operator-manual/rbac/)
- [Argo CD RBAC policy validation](https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_admin_settings_rbac_validate/)

