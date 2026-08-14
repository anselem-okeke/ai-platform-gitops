# Argo CD Secure Access Runbook

This runbook records the secure-access work completed for the AI Platform Argo CD installation. It covers local bootstrap access, Keycloak OIDC and group-based RBAC, Vault-issued TLS, Envoy Gateway exposure, Windows SSH tunnelling, validation, and the failures encountered along the way.

> Environment-specific values in this runbook
>
> - Argo CD namespace: `argocd`
> - Argo CD version: `v3.5.1`
> - Keycloak namespace: `keycloak`
> - Keycloak realm: `ai-platform`
> - Argo CD OIDC client: `ai-platform-argocd`
> - Argo CD URL: `https://argocd.ai-platform.local`
> - Keycloak URL: `https://auth.ai-platform.local`
> - Shared Gateway: `gateway-system/shared-gateway`
> - Gateway address: `172.19.255.200`
> - Vault issuer: namespaced `Issuer` named `vault-issuer`
> - Vault signing path: `pki_modelservice/sign/modelservice`
> - Operator repository: `/mnt/data/ai-platform-operator`
> - GitOps repository: `/mnt/data/ai-platform-gitops`

## 1. Resulting access architecture

```text
Windows browser
  | hosts: auth.ai-platform.local and argocd.ai-platform.local -> 127.0.0.1
  | SSH local forward: 127.0.0.1:443 -> 172.19.255.200:443
  v
Envoy shared Gateway
  | SNI/hostname routing
  +--> auth.ai-platform.local   -> Keycloak
  +--> argocd.ai-platform.local -> Argo CD

Keycloak groups                 Argo CD RBAC
platform-viewer      ---------> role:platform-viewer
platform-deployer    ---------> role:platform-deployer
platform-admin       ---------> role:admin
```

The same HTTPS tunnel carries both hostnames. TLS Server Name Indication and Gateway host matching select the correct listener and route.

## 2. Installation checkpoint

The cluster installation was verified with:

```bash
kubectl get appproject ai-platform -n argocd
kubectl get svc argocd-server -n argocd
argocd version --client
```

The desired service type is `ClusterIP`. Argo CD was not exposed with a separate `LoadBalancer` or `NodePort`.

If the CLI is absent and the shell reports `argocd: command not found`, install the CLI release matching the server (`v3.5.1` in this environment), then verify it with `argocd version --client`. Installing the CLI does not expose the web UI; it only provides the local command.

## 3. Bootstrap access and initial administrator

Bootstrap access used a local port-forward while `argocd-server` remained internal.

Terminal 1:

```bash
kubectl port-forward -n argocd svc/argocd-server 8080:443
```

Terminal 2:

```bash
ARGOCD_INITIAL_PASSWORD="$(
  argocd admin initial-password -n argocd |
  head -n 1
)"

test -n "${ARGOCD_INITIAL_PASSWORD}" &&
echo "PASS: Argo CD bootstrap credential loaded"
```

The value was deliberately not printed.

Login and verification:

```bash
argocd login 127.0.0.1:8080 \
  --username admin \
  --password "${ARGOCD_INITIAL_PASSWORD}" \
  --insecure

argocd account get-user-info
argocd version
```

`--insecure` disables certificate verification for this local bootstrap session; the connection still uses HTTPS.

The initial password was rotated with:

```bash
argocd account update-password
```

After proving the new password worked, the generated initial-password Secret could be removed:

```bash
kubectl delete secret argocd-initial-admin-secret -n argocd
unset ARGOCD_INITIAL_PASSWORD
```

Do not infer that the built-in administrator is disabled merely because the initial Secret was deleted. These are separate controls. Confirm the current setting before changing it:

```bash
kubectl get configmap argocd-cm -n argocd \
  -o jsonpath='{.data.admin\.enabled}{"\n"}'

argocd account list
```

The built-in administrator should only be disabled after browser SSO and all three RBAC personas have been tested successfully.

## 4. Keycloak groups, users, and Argo CD client

The Keycloak configuration script is:

```text
/mnt/data/ai-platform-operator/infrastructure/keycloak/scripts/configure-argocd-oidc.sh
```

Because the Keycloak image did not contain `tar`, `kubectl cp` failed. Streaming a file through standard input was the working fallback:

```bash
kubectl exec -i -n keycloak "${KEYCLOAK_POD}" -- \
  sh -c 'cat > /tmp/configure-argocd-oidc.sh && chmod 700 /tmp/configure-argocd-oidc.sh' \
  < infrastructure/keycloak/scripts/configure-argocd-oidc.sh
```

Running the script inside the Keycloak container then failed because `jq` was unavailable and the container's `kcadm.sh` invocation did not accept the wrapper's option placement. The successful approach was to run the script from the normal shell using the repository's `kcadm-in-pod` helper:

```bash
cd /mnt/data/ai-platform-operator

test -n "${KC_BOOTSTRAP_ADMIN_USERNAME:-}" &&
test -n "${KC_BOOTSTRAP_ADMIN_PASSWORD:-}" &&
echo "PASS: Keycloak bootstrap credentials loaded"

KCADM="${PWD}/.local/keycloak/bin/kcadm-in-pod" \
KCADM_CONFIG="/tmp/ai-platform-kcadm.config" \
infrastructure/keycloak/scripts/configure-argocd-oidc.sh

unset KC_BOOTSTRAP_ADMIN_USERNAME
unset KC_BOOTSTRAP_ADMIN_PASSWORD
```

The script created or reconciled:

- `platform-viewer`, `platform-deployer`, and `platform-admin` groups.
- `viewer-user`, `deployer-user`, and `admin-user` memberships.
- Public OIDC client `ai-platform-argocd`.
- Authorization Code flow enabled and Direct Access Grants disabled.
- PKCE method `S256`.
- `groups` client scope and group-membership protocol mapper.
- Default `groups` scope on `ai-platform-argocd` and `ai-platform-cli`.

### Verified Keycloak state

The direct `kubectl exec ... kcadm.sh get ...` check failed with `No server specified` because that new process had no authenticated kcadm context. The working helper retained the required in-pod configuration:

```bash
cd /mnt/data/ai-platform-operator

KCADM_IN_POD="${PWD}/.local/keycloak/bin/kcadm-in-pod"
KCADM_CONFIG="/tmp/ai-platform-kcadm.config"

"${KCADM_IN_POD}" get groups \
  -r ai-platform \
  --fields id,name \
  --config "${KCADM_CONFIG}" |
jq -r '.[] | [.id, .name] | @tsv'

"${KCADM_IN_POD}" get clients \
  -r ai-platform \
  -q clientId=ai-platform-argocd \
  --fields id,clientId,publicClient,standardFlowEnabled,directAccessGrantsEnabled \
  --config "${KCADM_CONFIG}" |
jq '.[0]'
```

Verified client characteristics:

```text
clientId:                  ai-platform-argocd
publicClient:              true
standardFlowEnabled:       true
directAccessGrantsEnabled: false
PKCE challenge method:     S256
```

Verified redirect URIs:

```text
https://argocd.ai-platform.local/auth/callback
https://argocd.ai-platform.local/pkce/verify
http://localhost:8085/auth/callback
```

The HTTPS callbacks serve browser/web SSO. `http://localhost:8085/auth/callback` is for Argo CD CLI SSO.

### Verified token group claim

The PKCE helper was run and the browser login was completed as `viewer-user`:

```bash
cd /mnt/data/ai-platform-operator
infrastructure/keycloak/scripts/pkce-login.py
```

The resulting access token was loaded correctly by assigning and exporting it in one command:

```bash
export TOKEN="$(
  tr -d '\r\n' < .local/keycloak/tokens/user-access-token.jwt
)"
```

Running only `export TOKEN` does not load a value and caused the earlier Python `KeyError: 'TOKEN'`.

Safe claim decoding:

```bash
python3 - <<'PY'
import os
import json
import base64

token = os.environ["TOKEN"]
parts = token.split(".")
if len(parts) != 3:
    raise SystemExit("ERROR: token is not a valid three-part JWT")

payload = parts[1]
payload += "=" * (-len(payload) % 4)
claims = json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))

for key in ("preferred_username", "groups", "realm_access"):
    print(f"{key}: {claims.get(key)}")
PY

unset TOKEN
```

Verified result:

```text
preferred_username: viewer-user
groups: ['platform-viewer']
realm_access: {'roles': ['model-viewer', ...]}
```

Never paste the JWT or credentials into documentation, chat, Git, YAML, `.env` files, or shell scripts.

## 5. Declarative Argo CD OIDC configuration

Repository:

```text
/mnt/data/ai-platform-gitops
```

OIDC patch:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-cm
data:
  url: https://argocd.ai-platform.local
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

RBAC patch:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-rbac-cm
data:
  policy.default: role:authenticated
  scopes: '[groups]'
  policy.csv: |
    # role:authenticated intentionally has no permissions.

    p, role:platform-viewer, applications, get, ai-platform/*, allow
    p, role:platform-viewer, projects, get, ai-platform, allow
    p, role:platform-viewer, logs, get, ai-platform/*, allow

    p, role:platform-deployer, applications, get, ai-platform/*, allow
    p, role:platform-deployer, applications, sync, ai-platform/*, allow
    p, role:platform-deployer, projects, get, ai-platform, allow
    p, role:platform-deployer, logs, get, ai-platform/*, allow

    g, platform-viewer, role:platform-viewer
    g, platform-deployer, role:platform-deployer
    g, platform-admin, role:admin
```

The default authenticated role has no useful permissions. Permissions are assigned through explicit Keycloak group mappings.

### Kustomize validation

```bash
cd /mnt/data/ai-platform-gitops

kubectl kustomize argocd/bootstrap > /tmp/argocd-v3.5.1-oidc.yaml

grep -nE \
  'url: https://argocd.ai-platform.local|oidc.config|issuer:|clientID: ai-platform-argocd|enablePKCEAuthentication|policy.default|platform-viewer|platform-deployer|platform-admin' \
  /tmp/argocd-v3.5.1-oidc.yaml
```

If Kustomize reports that no resource matches the `argocd-cm` patch, the rendered resource set does not contain a uniquely matching ConfigMap. Check that the base/install manifest is actually present in `resources`, that the remote URL is raw YAML rather than Markdown link syntax, and that the patch name/namespace match the rendered object.

Do not paste this into YAML:

```text
[https://example.invalid/install.yaml](https://example.invalid/install.yaml)
```

Use a plain URL:

```yaml
resources:
  - namespace.yaml
  - https://raw.githubusercontent.com/argoproj/argo-cd/v3.5.1/manifests/install.yaml
```

Apply only after local render and server dry-run succeed:

```bash
kubectl apply --server-side --force-conflicts --dry-run=server \
  -k argocd/bootstrap

kubectl apply --server-side --force-conflicts \
  -k argocd/bootstrap

kubectl rollout restart deployment/argocd-server -n argocd
kubectl rollout status deployment/argocd-server -n argocd --timeout=180s
```

Live verification:

```bash
kubectl get configmap argocd-cm -n argocd \
  -o jsonpath='{.data.oidc\.config}'
echo

kubectl get configmap argocd-rbac-cm -n argocd -o yaml
```

## 6. Vault PKI preparation

The existing API Certificate proved the correct issuer is:

```text
name: vault-issuer
kind: Issuer
namespace: gateway-system
```

It is not a `ClusterIssuer`.

Issuer verification:

```bash
kubectl get issuer vault-issuer -n gateway-system -o json |
jq '{
  name: .metadata.name,
  namespace: .metadata.namespace,
  ready: [.status.conditions[] | select(.type == "Ready")],
  vaultServer: .spec.vault.server,
  signingPath: .spec.vault.path
}'
```

Verified values:

```text
Ready:       True
signingPath: pki_modelservice/sign/modelservice
```

The Vault role source is:

```text
/mnt/data/ai-platform-operator/infrastructure/vault/scripts/configure-modelservice-pki.sh
```

Its allowed names were extended without removing the existing names:

```bash
allowed_domains="fraud-model.local,api.ai-platform.local,argocd.ai-platform.local"
```

The Ansible/server machine did not have the `vault` CLI. The live Vault role was therefore updated and verified from the jumpbox, where Vault access was already configured. There was no need to copy a Vault token to the Ansible server merely to issue the certificate.

Live Vault verification from the jumpbox:

```bash
vault read -format=json pki_modelservice/roles/modelservice |
jq '{
  allowed_domains: .data.allowed_domains,
  allow_bare_domains: .data.allow_bare_domains,
  allow_subdomains: .data.allow_subdomains,
  enforce_hostnames: .data.enforce_hostnames,
  key_type: .data.key_type,
  key_bits: .data.key_bits,
  max_ttl: .data.max_ttl
}'
```

Verified role properties:

```text
allowed_domains:     fraud-model.local, api.ai-platform.local, argocd.ai-platform.local
allow_bare_domains:  true
allow_subdomains:    false
enforce_hostnames:   true
key_type:            ec
key_bits:            256
```

## 7. Argo CD TLS Certificate

File:

```text
/mnt/data/ai-platform-gitops/argocd/exposure/certificate.yaml
```

Correct manifest:

```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: argocd-ai-platform-local
  namespace: gateway-system
spec:
  secretName: argocd-ai-platform-local-tls
  dnsNames:
    - argocd.ai-platform.local
  privateKey:
    algorithm: ECDSA
    size: 256
    rotationPolicy: Always
  issuerRef:
    name: vault-issuer
    kind: Issuer
    group: cert-manager.io
```

The Certificate is in `gateway-system` because cert-manager writes its target Secret into the Certificate's namespace, and the Gateway listener directly references that Secret in the Gateway namespace.

The first issuance failed with:

```text
role requires keys of type ec
```

Cause: the Vault role only accepts EC keys, while the Certificate initially requested cert-manager's default RSA key. Adding the explicit ECDSA-256 `privateKey` section triggered generation 2 and successful issuance.

Apply and wait:

```bash
cd /mnt/data/ai-platform-gitops

kubectl apply -f argocd/exposure/certificate.yaml

kubectl wait --for=condition=Ready \
  certificate/argocd-ai-platform-local \
  -n gateway-system \
  --timeout=180s
```

Verified result:

```text
Certificate: argocd-ai-platform-local
Ready:       True
Secret:      argocd-ai-platform-local-tls
Secret type: kubernetes.io/tls
CSR key:     id-ecPublicKey
SAN:         DNS:argocd.ai-platform.local
Issuer CN:   AI Platform ModelService Root CA
```

Safe certificate inspection (does not print `tls.key`):

```bash
kubectl get secret argocd-ai-platform-local-tls \
  -n gateway-system \
  -o jsonpath='{.data.tls\.crt}' |
base64 -d |
openssl x509 -noout -subject -issuer -dates -ext subjectAltName
```

## 8. Shared Envoy Gateway listener

The listener belongs in:

```text
/mnt/data/ai-platform-operator/config/platform/shared-gateway.yaml
```

It is added under `spec.listeners` alongside the existing HTTP, Keycloak, platform API, and fraud-model listeners:

```yaml
- name: argocd-https
  hostname: argocd.ai-platform.local
  port: 443
  protocol: HTTPS
  allowedRoutes:
    namespaces:
      from: All
  tls:
    mode: Terminate
    certificateRefs:
      - name: argocd-ai-platform-local-tls
        kind: Secret
        group: ""
```

The live Gateway was updated with:

```bash
cd /mnt/data/ai-platform-operator
kubectl apply -f config/platform/shared-gateway.yaml
```

Listener verification:

```bash
kubectl get gateway shared-gateway -n gateway-system \
  -o jsonpath='{range .spec.listeners[*]}{.name}{"\t"}{.hostname}{"\t"}{.protocol}{"\n"}{end}'
```

Before the TLS Secret existed, this listener correctly reported:

```text
Accepted=True
ResolvedRefs=False / InvalidCertificateRef
Programmed=False
```

That was an expected dependency failure, not proof that the listener YAML was wrong. After successful certificate issuance, recheck the listener:

```bash
kubectl get gateway shared-gateway -n gateway-system -o json |
jq '
  .status.listeners[]
  | select(.name == "argocd-https")
  | {name, attachedRoutes, conditions}
'
```

The healthy target is:

```text
Accepted=True
ResolvedRefs=True
Programmed=True
attachedRoutes >= 1
```

## 9. Argo CD HTTPRoutes

The exposure Kustomization should create the HTTPS Argo CD route and HTTP-to-HTTPS redirect route in namespace `argocd`.

Validation and apply:

```bash
cd /mnt/data/ai-platform-gitops

kubectl kustomize argocd/exposure > /tmp/argocd-exposure.yaml
kubectl apply --dry-run=server -k argocd/exposure
kubectl diff -k argocd/exposure
kubectl apply -k argocd/exposure
```

`kubectl diff` exit status `1` normally means that differences were found.

Verify route status:

```bash
kubectl get httproute argocd argocd-http-redirect -n argocd

kubectl get httproute argocd -n argocd -o json |
jq '.status.parents[].conditions'
```

Healthy route conditions include `Accepted=True` and `ResolvedRefs=True`.

## 10. Linux-side HTTPS validation

For a machine that can route directly to the Gateway, resolve:

```text
172.19.255.200 argocd.ai-platform.local
```

Do not repeatedly append duplicate `/etc/hosts` lines. Check first:

```bash
getent hosts argocd.ai-platform.local
```

Correct API request:

```bash
curl \
  --cacert /mnt/data/ai-platform-operator/.local/keycloak/fraud-model-root-ca.crt \
  --fail-with-body \
  --silent \
  --show-error \
  'https://argocd.ai-platform.local/api/version' |
jq .
```

Use the literal URL above. The following is Markdown link syntax, not a shell URL, and must never be pasted into a command:

```text
[https://argocd.ai-platform.local/api/version](https://argocd.ai-platform.local/api/version)
```

That malformed input, or an HTML/text error response, causes `jq: parse error: Invalid numeric literal`. When debugging, inspect the unparsed response first:

```bash
curl \
  --cacert /mnt/data/ai-platform-operator/.local/keycloak/fraud-model-root-ca.crt \
  --silent \
  --show-error \
  --dump-header /tmp/argocd-headers.txt \
  --output /tmp/argocd-body.txt \
  'https://argocd.ai-platform.local/api/version'

sed -n '1,80p' /tmp/argocd-headers.txt
sed -n '1,80p' /tmp/argocd-body.txt
```

## 11. Windows browser access through SSH

Windows resolved the Gateway IP after adding it to the hosts file, but TCP port 443 to `172.19.255.200` was unreachable from the desktop LAN. This is why direct browser access failed even though the Kubernetes Gateway was healthy.

Use an elevated editor for:

```text
C:\Windows\System32\drivers\etc\hosts
```

For SSH-tunnel access, use one hosts entry:

```text
# AI Platform Gateway through SSH tunnel
127.0.0.1 auth.ai-platform.local argocd.ai-platform.local
```

Do not use this malformed entry:

```text
127.0.0.1 argocd.ai-platform.local auth.ai-platform.local
```

Although Windows hosts files can contain several aliases after one address, maintaining one clear line for both tunnelled names avoids duplicate/conflicting entries.

Flush and verify:

```powershell
ipconfig /flushdns
ping -n 1 auth.ai-platform.local
ping -n 1 argocd.ai-platform.local
```

Both names must resolve to `127.0.0.1`. Ping success is not required; name resolution is the important part.

Start one tunnel in PowerShell and leave it running:

```powershell
ssh `
  -N `
  -o ExitOnForwardFailure=yes `
  -L 127.0.0.1:443:172.19.255.200:443 `
  ansible@192.168.0.58
```

This forwards Windows localhost port 443 to the Gateway through the Ansible server. A second `-L` is not required for Keycloak because both HTTPS hostnames share port 443 and the Gateway routes by hostname/SNI.

If the SSH host cannot itself connect to `172.19.255.200:443`, the tunnel cannot work. Check from the Ansible server:

```bash
curl -kI 'https://argocd.ai-platform.local'
```

Check the Windows endpoint while the tunnel is active:

```powershell
Test-NetConnection 127.0.0.1 -Port 443
Test-NetConnection argocd.ai-platform.local -Port 443
```

If SSH reports that it cannot bind port 443, identify the Windows process already using it:

```powershell
Get-NetTCPConnection -LocalPort 443 -State Listen -ErrorAction SilentlyContinue
```

After importing the AI Platform root CA into Windows **Trusted Root Certification Authorities**, open:

```text
https://argocd.ai-platform.local
```

The Argo CD login screen should offer the Keycloak login option. The Keycloak redirect remains reachable because `auth.ai-platform.local` resolves to the same tunnel endpoint.

## 12. Final SSO and authorization tests

Test each user in a clean browser profile or private window so an existing Keycloak session does not silently reuse the wrong identity.

Expected matrix:

| User | Keycloak group | Expected Argo CD access |
|---|---|---|
| `viewer-user` | `platform-viewer` | View applications/project/logs; cannot sync or administer |
| `deployer-user` | `platform-deployer` | View and sync `ai-platform/*`; cannot administer |
| `admin-user` | `platform-admin` | Argo CD administrative access |

Tests should prove both allowed and denied actions. A successful login alone does not prove RBAC is correct.

Useful CLI SSO command when the Argo CD CLI is installed:

```bash
argocd login argocd.ai-platform.local --sso
```

The `localhost:8085` Keycloak redirect URI exists for this CLI flow.

## 13. Disable the built-in administrator only at the end

Prerequisites:

- `admin-user` completes Keycloak SSO and has administrative access.
- `viewer-user` can read but cannot sync or administer.
- `deployer-user` can sync the intended project but cannot administer.
- HTTPS, Gateway, routes, and certificate remain healthy.
- The declarative configuration is committed and recoverable.

Then set this in the declarative `argocd-cm` patch:

```yaml
data:
  admin.enabled: "false"
```

Render, dry-run, apply, restart if required, and verify:

```bash
kubectl kustomize argocd/bootstrap > /tmp/argocd-final.yaml
kubectl apply --server-side --force-conflicts --dry-run=server -k argocd/bootstrap
kubectl apply --server-side --force-conflicts -k argocd/bootstrap

kubectl get configmap argocd-cm -n argocd \
  -o jsonpath='{.data.admin\.enabled}{"\n"}'

argocd account list
```

Expected value: `false`.

If this has already been done, still run the verification commands and keep the output with the deployment evidence. Never rely on an earlier narrative statement as proof of the live setting.

## 14. Current evidence checklist

The following were directly demonstrated in the captured command outputs:

- [x] Argo CD installation and `ai-platform` AppProject exist.
- [x] `argocd-server` remains `ClusterIP`.
- [x] Keycloak platform groups exist.
- [x] User-to-group memberships were configured.
- [x] `ai-platform-argocd` is a public Authorization Code client.
- [x] Direct Access Grants are disabled.
- [x] PKCE S256 is configured.
- [x] `groups` client scope and mapper exist.
- [x] `viewer-user` token contains `platform-viewer`.
- [x] Argo CD OIDC/RBAC configuration work was implemented.
- [x] Vault role permits `argocd.ai-platform.local`.
- [x] Certificate uses ECDSA-256.
- [x] Certificate is `Ready=True`.
- [x] TLS Secret exists in `gateway-system`.
- [x] Shared Gateway contains `argocd-https`.
- [x] Gateway reported an attached Argo CD route.
- [x] Windows name resolution was configured for tunnel access.

Re-verify these live before declaring secure access fully closed:

- [ ] `argocd-https`: `Accepted=True`, `ResolvedRefs=True`, `Programmed=True` after certificate issuance.
- [ ] Argo CD HTTPRoute: `Accepted=True`, `ResolvedRefs=True`.
- [ ] `/api/version` returns valid JSON over trusted HTTPS.
- [ ] Windows SSH tunnel accepts TCP 443.
- [ ] Browser displays Argo CD and redirects to Keycloak.
- [ ] `admin-user` has administrative access.
- [ ] `viewer-user` is unable to sync/administer.
- [ ] `deployer-user` can sync but cannot administer.
- [ ] Live `admin.enabled` value is confirmed; disable only after the preceding tests pass.

## 15. Compact health check

Run from the Linux management host:

```bash
kubectl get certificate argocd-ai-platform-local -n gateway-system

kubectl get secret argocd-ai-platform-local-tls -n gateway-system

kubectl get gateway shared-gateway -n gateway-system -o json |
jq '.status.listeners[] | select(.name == "argocd-https") | {name, attachedRoutes, conditions}'

kubectl get httproute argocd argocd-http-redirect -n argocd

kubectl get httproute argocd -n argocd -o json |
jq '.status.parents[].conditions'

curl \
  --cacert /mnt/data/ai-platform-operator/.local/keycloak/fraud-model-root-ca.crt \
  --fail-with-body \
  --silent \
  --show-error \
  'https://argocd.ai-platform.local/api/version' |
jq .

kubectl get configmap argocd-cm -n argocd \
  -o jsonpath='{.data.admin\.enabled}{"\n"}'
```

## 16. Troubleshooting index

| Symptom | Cause | Resolution |
|---|---|---|
| `argocd: command not found` | Argo CD CLI absent | Install the matching CLI release; this is independent of web exposure |
| Python `KeyError: 'TOKEN'` | Variable exported without assigning token content | `export TOKEN="$(tr -d '\r\n' < token-file)"` |
| `kubectl cp` fails because `tar` is missing | Minimal Keycloak container lacks `tar` | Stream through `kubectl exec -i ... cat > file` |
| `jq: command not found` inside Keycloak | Minimal image lacks `jq` | Run the script on the management host with `kcadm-in-pod` |
| `No server specified` from `kcadm.sh` | New process lacks authenticated kcadm context | Use the configured wrapper and `--config` path |
| Kustomize cannot find `argocd-cm` patch target | Base does not render that ConfigMap, URL is malformed, or identity does not match | Inspect `kubectl kustomize`; use raw URL and matching target |
| Vault script says `VAULT_TOKEN` missing | Management host lacks authenticated Vault environment | Use the already configured jumpbox; do not unnecessarily copy tokens |
| Certificate fails: `role requires keys of type ec` | Certificate requested RSA against EC-only Vault role | Set `privateKey.algorithm: ECDSA`, `size: 256` |
| Gateway `InvalidCertificateRef` | TLS Secret not created yet | Fix Certificate issuance; Secret must be in `gateway-system` |
| `jq: Invalid numeric literal` after curl | Markdown link pasted as URL or response is not JSON | Use quoted raw URL and inspect headers/body before piping to `jq` |
| Windows resolves `172.19.255.200` but port 443 fails | Gateway IP is not routed from desktop LAN | Map both hostnames to `127.0.0.1` and use the SSH local forward |
| Keycloak redirect fails through tunnel | `auth.ai-platform.local` does not resolve to tunnel endpoint | Put both auth and Argo CD hostnames on the `127.0.0.1` hosts line |

---

This file intentionally contains no passwords, Vault tokens, JWTs, private keys, or Kubernetes Secret data.
