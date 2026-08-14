# Validated Procedure: Keycloak OIDC and Argo CD RBAC

**Validated:** 13 August 2026  
**Target:** Argo CD v3.5.1 and the Keycloak `ai-platform` realm

## 1. Audit result

The original document contains the correct architecture but mixes the first failed implementation with the corrected working implementation.

The following items in the original document must not be followed.

| Original instruction | Problem | Correct approach |
|---|---|---|
| Run `configure-argocd-oidc.sh` inside the Keycloak pod | The minimal image does not contain `jq` | Run the orchestration script on the Ansible server and invoke only `kcadm.sh` inside the pod |
| Use `kubectl cp` | `kubectl cp` needs `tar` in the target container; this Keycloak image has no `tar` | No pod copy is needed with the host-side wrapper; for emergency copying, stream through `kubectl exec -i` |
| Define `kcadm()` as `kcadm.sh --config FILE "$@"` | This places `--config` before the `get`, `create`, or `update` subcommand and fails on this Keycloak version | Invoke `kcadm.sh "$@" --config FILE` |
| Verify with bare `/opt/keycloak/bin/kcadm.sh get ...` | The authenticated session was saved in a non-default file | Add `--config /tmp/ai-platform-kcadm.config`, using the wrapper |
| Always use `kubectl apply --force-conflicts` | It silently takes server-side-apply field ownership and may overwrite another manager's fields | Dry-run, diff, and apply without force first; inspect any conflict |
| Treat the `ai-platform-cli` token test as complete Argo CD SSO proof | It proves the shared Keycloak mapper and scope, but not the Argo CD callback, ID token, session, or RBAC enforcement | Perform end-to-end Argo CD SSO tests after its HTTPS route exists |
| Configure the Keycloak issuer without considering its private CA | `argocd-server` must trust the Vault CA that issued the Keycloak TLS certificate | Add the public Vault root/issuing CA through `oidc.config.rootCA` and test DNS/reachability |

## 2. What is already complete

Do not recreate the following objects. They exist and were verified from the real Keycloak state:

- `platform-viewer`, `platform-deployer`, and `platform-admin` groups
- `viewer-user -> platform-viewer`
- `deployer-user -> platform-deployer`
- `admin-user -> platform-admin`
- Public OIDC client `ai-platform-argocd`
- Authorization Code flow enabled
- Direct Access Grants disabled
- PKCE challenge method `S256`
- Correct UI and CLI redirect URIs
- `groups` client scope
- Group-membership protocol mapper
- `groups` scope attached to `ai-platform-argocd` and `ai-platform-cli`
- A fresh `viewer-user` token containing `groups: ['platform-viewer']`
- Successful Kustomize compilation
- Successful static Argo CD RBAC validation

The Keycloak configuration is live. The Argo CD OIDC and RBAC manifests are prepared and validated but have not yet been proven live in the cluster.

## 3. Correct Keycloak automation pattern

This section records the correct implementation for future reruns or disaster recovery. It does not need to be run again now.

### 3.1 Select and export the Keycloak pod

```bash
cd /mnt/data/ai-platform-operator

export KEYCLOAK_POD="$(
  kubectl get pod \
    -n keycloak \
    -l app.kubernetes.io/name=keycloak \
    -o jsonpath='{.items[0].metadata.name}'
)"

test -n "${KEYCLOAK_POD}" &&
echo "PASS: Keycloak pod selected"
```

### 3.2 Use the host-side wrapper

The wrapper `.local/keycloak/bin/kcadm-in-pod` must contain this behavior:

```bash
#!/usr/bin/env bash
set -euo pipefail

: "${KEYCLOAK_POD:?KEYCLOAK_POD is required}"

exec kubectl exec \
  -n keycloak \
  "${KEYCLOAK_POD}" \
  -- /opt/keycloak/bin/kcadm.sh "$@"
```

The wrapper runs `kcadm.sh` in the pod but leaves JSON processing with `jq` on the Ansible server.

### 3.3 Use the correct `kcadm()` function

Inside `configure-argocd-oidc.sh`, the function must be:

```bash
kcadm() {
  "${KCADM}" \
    "$@" \
    --config "${KCADM_CONFIG}"
}
```

Do not use this broken ordering:

```bash
"${KCADM}" --config "${KCADM_CONFIG}" "$@"
```

The credentials command itself remains valid because its subcommands already precede `--config`:

```bash
"${KCADM}" config credentials \
  --config "${KCADM_CONFIG}" \
  --server http://127.0.0.1:8080 \
  --realm master \
  --user "${KC_BOOTSTRAP_ADMIN_USERNAME}" \
  --password "${KC_BOOTSTRAP_ADMIN_PASSWORD}"
```

### 3.4 Run the script on the Ansible server

The bootstrap credential variables must be exported because the script runs as a child process. Never print their values.

```bash
test -n "${KC_BOOTSTRAP_ADMIN_USERNAME:-}" &&
test -n "${KC_BOOTSTRAP_ADMIN_PASSWORD:-}" &&
echo "PASS: Keycloak bootstrap credentials loaded"
```

```bash
KCADM="${PWD}/.local/keycloak/bin/kcadm-in-pod" \
KCADM_CONFIG="/tmp/ai-platform-kcadm.config" \
infrastructure/keycloak/scripts/configure-argocd-oidc.sh
```

Expected ending:

```text
PASS: Keycloak Argo CD OIDC configuration completed.
```

Then clear the bootstrap credentials:

```bash
unset KC_BOOTSTRAP_ADMIN_USERNAME
unset KC_BOOTSTRAP_ADMIN_PASSWORD
```

## 4. Correct Keycloak verification pattern

Use the host wrapper and explicitly reference the authenticated configuration stored inside the pod:

```bash
KCADM_IN_POD="${PWD}/.local/keycloak/bin/kcadm-in-pod"
KCADM_CONFIG="/tmp/ai-platform-kcadm.config"
```

Example:

```bash
"${KCADM_IN_POD}" \
  get groups \
  -r ai-platform \
  --fields id,name \
  --config "${KCADM_CONFIG}" |
jq -r '.[] | [.id, .name] | @tsv'
```

A command without `--config` can produce:

```text
No server specified. Use --server, or 'kcadm.sh config credentials'.
```

That message means the CLI did not load the saved administrative session. It does not mean the Keycloak server is down.

## 5. Meaning of the successful token test

The successful `viewer-user` test proved that:

1. The `ai-platform-cli` client can complete Authorization Code plus PKCE.
2. The `groups` scope is active for that client.
3. The mapper produces `groups: ['platform-viewer']`.
4. Keycloak has the correct user membership.

It did not yet prove that:

- `argocd.ai-platform.local` is reachable;
- the Argo CD callback works;
- Argo CD trusts the Keycloak TLS certificate;
- the Argo CD ID token contains the claim during its own login;
- Argo CD grants or denies the intended actions.

Those items require the later end-to-end SSO tests.

## 6. Validate Keycloak issuer reachability from the cluster

Argo CD must reach this discovery URL from inside the cluster:

```text
https://auth.ai-platform.local/realms/ai-platform/.well-known/openid-configuration
```

Run a temporary diagnostic pod in the `argocd` namespace:

```bash
kubectl run oidc-discovery-check \
  -n argocd \
  --image=curlimages/curl:8.12.1 \
  --restart=Never \
  --rm -i \
  -- \
  curl -kfsS \
  https://auth.ai-platform.local/realms/ai-platform/.well-known/openid-configuration
```

`-k` is used only in this temporary diagnostic to isolate DNS and routing from CA trust. Do not configure Argo CD to skip verification.

Expected JSON includes:

```text
"issuer":"https://auth.ai-platform.local/realms/ai-platform"
```

If the hostname cannot resolve or connect, stop. Fix cluster DNS or routing before applying the OIDC configuration.

## 7. Add the Vault CA to Argo CD OIDC configuration

Because `auth.ai-platform.local` uses a Vault-issued certificate, Argo CD must trust the corresponding public root or issuing CA.

Do not add:

- the Vault CA private key;
- the Keycloak leaf private key;
- a token or password;
- `oidc.tls.insecure.skip.verify: "true"`.

Inspect the intended public CA certificate before committing it:

```bash
openssl x509 \
  -in /path/to/vault-public-ca.pem \
  -noout \
  -subject \
  -issuer \
  -dates \
  -fingerprint \
  -sha256
```

Confirm that this CA validates the Keycloak TLS chain:

```bash
curl \
  --cacert /path/to/vault-public-ca.pem \
  -fsS \
  https://auth.ai-platform.local/realms/ai-platform/.well-known/openid-configuration \
  >/dev/null &&
echo "PASS: Vault CA validates Keycloak"
```

The public CA certificate may be stored in Git; it is not a secret.

## 8. Correct `argocd-cm` patch

File:

```text
/mnt/data/ai-platform-gitops/argocd/bootstrap/argocd-cm-patch.yaml
```

The patch must not contain `metadata.namespace`; the parent Kustomization supplies `namespace: argocd`.

Use:

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
    allowedAudiences:
      - ai-platform-argocd
    enablePKCEAuthentication: true
    refreshTokenThreshold: 2m
    requestedScopes:
      - openid
      - profile
      - email
      - groups
      - offline_access
    rootCA: |
      -----BEGIN CERTIFICATE-----
      REPLACE_WITH_THE_PUBLIC_VAULT_CA_CERTIFICATE
      -----END CERTIFICATE-----
```

Replace the placeholder with the real PEM content before compiling or applying.

Notes:

- `allowedAudiences` is explicit here; if omitted, Argo CD defaults it to `clientID` (and `cliClientID` when configured).
- Requesting `groups` is harmless even though the scope is attached as a Keycloak default scope.
- `offline_access` permits refresh-token-based sessions when Keycloak allows that scope.
- `application.sync.requireOverridePrivilegeForRevisionSync` ensures that `sync` alone does not authorize arbitrary revision selection.

## 9. Correct `argocd-rbac-cm` patch

File:

```text
/mnt/data/ai-platform-gitops/argocd/bootstrap/argocd-rbac-cm-patch.yaml
```

Use:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-rbac-cm
data:
  policy.default: role:authenticated
  scopes: '[groups]'

  policy.csv: |
    # The default authenticated role deliberately has no permissions.

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

This policy is valid for Applications in the normal `argocd` namespace. If “Applications in any namespace” is enabled later, the object pattern changes and the policy must be revisited.

The warning below is expected when the patch is validated alone:

```text
user defined roles not found in policies: role:admin
```

`role:admin` is built into Argo CD; its policy lines are not present in the standalone patch file.

## 10. Compile and validate locally

```bash
cd /mnt/data/ai-platform-gitops
```

Ensure there is no CA placeholder left:

```bash
if grep -R -n 'REPLACE_WITH_' argocd/bootstrap; then
  echo "ERROR: unresolved placeholder found" >&2
  exit 1
fi
```

Compile:

```bash
kubectl kustomize \
  argocd/bootstrap \
  > /tmp/argocd-v3.5.1-oidc.yaml
```

Validate RBAC:

```bash
argocd admin settings rbac validate \
  --policy-file argocd/bootstrap/argocd-rbac-cm-patch.yaml
```

Inspect the rendered settings:

```bash
grep -nE \
  'issuer:|clientID:|allowedAudiences:|enablePKCEAuthentication:|rootCA:|policy.default:|platform-viewer|platform-deployer|platform-admin' \
  /tmp/argocd-v3.5.1-oidc.yaml
```

Expected:

```text
Policy is valid.
```

## 11. Back up live ConfigMaps before applying

Backups belong outside Git-tracked paths. The repository already uses `.local/` for local-only artifacts.

```bash
mkdir -p .local/backups/argocd

kubectl get configmap argocd-cm \
  -n argocd \
  -o yaml \
  > .local/backups/argocd/argocd-cm.before-oidc.yaml

kubectl get configmap argocd-rbac-cm \
  -n argocd \
  -o yaml \
  > .local/backups/argocd/argocd-rbac-cm.before-oidc.yaml
```

Confirm `.local/` is ignored by Git before continuing:

```bash
git check-ignore .local/backups/argocd/argocd-cm.before-oidc.yaml
```

If it is not ignored, do not commit the backup files.

## 12. Server-side validation without forcing conflicts

Dry-run the complete Kustomization:

```bash
kubectl apply \
  --server-side \
  --field-manager=ai-platform-gitops \
  --dry-run=server \
  -k argocd/bootstrap
```

Do not add `--force-conflicts` to the dry-run. A forced dry-run can hide the ownership conflict that should be reviewed.

Review the proposed changes:

```bash
kubectl diff \
  --server-side \
  --field-manager=ai-platform-gitops \
  -k argocd/bootstrap
```

`kubectl diff` exit codes:

```text
0  no changes
1  differences found; normal
>1 command or validation error
```

Pay particular attention to `argocd-cm`, `argocd-rbac-cm`, and any unexpected changes elsewhere in the full Argo CD installation manifest.

## 13. Apply without forcing conflicts

Only after the dry-run and diff are acceptable:

```bash
kubectl apply \
  --server-side \
  --field-manager=ai-platform-gitops \
  -k argocd/bootstrap
```

If Kubernetes reports a field-ownership conflict, stop and inspect the reported manager, resource, and field. Do not immediately rerun with `--force-conflicts`.

## 14. Restart and verify Argo CD

Restart the API server after the ConfigMaps are applied:

```bash
kubectl rollout restart \
  deployment/argocd-server \
  -n argocd

kubectl rollout status \
  deployment/argocd-server \
  -n argocd \
  --timeout=180s
```

Check readiness:

```bash
kubectl get pods -n argocd
```

Verify live OIDC data:

```bash
kubectl get configmap argocd-cm \
  -n argocd \
  -o jsonpath='{.data.oidc\.config}'

echo
```

Verify live RBAC data:

```bash
kubectl get configmap argocd-rbac-cm \
  -n argocd \
  -o yaml
```

Validate live RBAC:

```bash
argocd admin settings rbac validate \
  --namespace argocd
```

Inspect recent server logs without exposing credentials:

```bash
kubectl logs \
  -n argocd \
  deployment/argocd-server \
  --since=10m |
grep -Ei 'oidc|keycloak|x509|certificate|error|failed' || true
```

Stop if the logs contain issuer discovery, DNS, or certificate validation failures.

## 15. End-to-end SSO tests after the HTTPS endpoint exists

The next implementation block must create and validate:

```text
https://argocd.ai-platform.local
```

with a valid Vault-issued server certificate and the correct DNS/hosts resolution.

Then test in this order:

1. Keep the local `admin` account working as the recovery path.
2. Log in as `admin-user`; confirm the token groups and Argo CD administrative access.
3. Log in as `viewer-user`; confirm application/project/log visibility.
4. Prove that `viewer-user` cannot synchronize, update, delete, override, or administer.
5. Log in as `deployer-user`; confirm read and sync for `ai-platform/*`.
6. Prove that `deployer-user` cannot override revisions, administer Argo CD, or access another project.
7. Record the successful and denied tests.
8. Only then set `admin.enabled: "false"` and verify SSO administration again.

## 16. Current stopping point

At this moment:

```text
[x] Keycloak client and PKCE configuration
[x] Keycloak groups and memberships
[x] groups scope and mapper
[x] Keycloak-side token claim verification
[x] Kustomize compilation before adding the CA
[x] static RBAC validation
[ ] verify issuer DNS/routing from the argocd namespace
[ ] add and validate the Vault public CA in oidc.config.rootCA
[ ] recompile and revalidate
[ ] server-side dry-run without force
[ ] review server-side diff
[ ] apply Argo CD OIDC and RBAC configuration
[ ] restart and verify argocd-server
[ ] expose argocd.ai-platform.local with HTTPS
[ ] test the three SSO roles
[ ] disable built-in admin
```

Do not proceed to applying the manifests until the issuer reachability and Vault CA steps pass.

## 17. Official references

- [Keycloak Admin CLI](https://www.keycloak.org/docs/latest/server_admin/index.html)
- [Argo CD Keycloak with PKCE](https://argo-cd.readthedocs.io/en/stable/operator-manual/user-management/keycloak/)
- [Argo CD existing OIDC provider and custom root CA](https://argo-cd.readthedocs.io/en/stable/operator-manual/user-management/)
- [Argo CD RBAC](https://argo-cd.readthedocs.io/en/stable/operator-manual/rbac/)
- [Argo CD RBAC validation](https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_admin_settings_rbac_validate/)
