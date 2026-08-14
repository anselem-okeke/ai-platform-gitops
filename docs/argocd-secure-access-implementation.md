# Argo CD Secure Access, Implementation Guide

![img](/img/argocd-secure.png)

> **Purpose:** Reproduce the secure Argo CD access architecture implemented for the AI Platform: Keycloak OIDC SSO with Authorization Code + PKCE, group-based Argo CD RBAC, Vault/cert-manager TLS, Envoy Gateway exposure, private-CA trust, HTTP→HTTPS redirect, CLI/UI access, least-privilege validation, built-in admin disablement, and break-glass recovery.
>
> **Reference implementation:** August 2026  
> **Argo CD:** v3.5.1  
> **Kubernetes:** v1.36.1  
> **Keycloak:** 26.7.0  
> **cert-manager:** v1.21.0  
> **Gateway:** Envoy Gateway / Kubernetes Gateway API

---

## Table of contents

1. [Outcome](#1-outcome)
2. [Architecture](#2-architecture)
3. [Concepts](#3-concepts)
4. [Reference environment](#4-reference-environment)
5. [Security model](#5-security-model)
6. [Keycloak implementation](#6-keycloak-implementation)
7. [Verify the Keycloak token](#7-verify-the-keycloak-token)
8. [Argo CD OIDC](#8-argo-cd-oidc)
9. [Argo CD RBAC](#9-argo-cd-rbac)
10. [Revision-override protection](#10-revision-override-protection)
11. [Gateway exposure](#11-gateway-exposure)
12. [Vault/cert-manager certificate](#12-vaultcert-manager-certificate)
13. [TLS termination and server.insecure](#13-tls-termination-and-serverinsecure)
14. [HTTP to HTTPS redirect](#14-http-to-https-redirect)
15. [Private CA trust](#15-private-ca-trust)
16. [Apply and verify](#16-apply-and-verify)
17. [Headless CLI SSO](#17-headless-cli-sso)
18. [Web UI SSO](#18-web-ui-sso)
19. [RBAC tests](#19-rbac-tests)
20. [Disable built-in admin](#20-disable-built-in-admin)
21. [Break-glass recovery](#21-break-glass-recovery)
22. [Troubleshooting from the real implementation](#22-troubleshooting-from-the-real-implementation)
23. [Final manifests](#23-final-manifests)
24. [Final verification checklist](#24-final-verification-checklist)
25. [Why this design is secure](#25-why-this-design-is-secure)
26. [How to adapt it elsewhere](#26-how-to-adapt-it-elsewhere)
27. [Official references](#27-official-references)

---

# 1. Outcome

At completion:

- `argocd-server` remains an internal `ClusterIP` Service.
- External access is only through the shared Envoy Gateway.
- Argo CD is reachable at `https://argocd.ai-platform.local`.
- TLS is issued by Vault through cert-manager.
- The certificate is ECDSA P-256, rotates keys, and contains both CN and SAN for `argocd.ai-platform.local`.
- HTTP redirects to HTTPS.
- Keycloak authenticates users through OIDC Authorization Code Flow + PKCE S256.
- Keycloak emits a `groups` claim.
- Argo CD maps groups to least-privilege RBAC roles.
- Viewer: read-only for the AI Platform project.
- Deployer: read + sync, but no override and no cluster/project administration.
- Admin: mapped to built-in `role:admin`.
- Argo CD explicitly trusts the private CA used by Keycloak.
- CLI/browser hosts trust the platform CA.
- Built-in Argo CD `admin` is disabled after SSO is proven.
- Kubernetes-admin access remains the break-glass recovery path.

```text
Keycloak                 Argo CD
(authentication)         (authorization)
     |                         |
     | OIDC token             | RBAC
     | + groups claim         |
     +------------------------>+
```

---

# 2. Architecture

## 2.1 Request path

```text
Browser / Argo CD CLI
        |
        | HTTPS
        v
Envoy Gateway
  gateway-system/shared-gateway
  listener: argocd-https
        |
        | TLS terminated
        | HTTP inside cluster
        v
HTTPRoute argocd/argocd
        |
        v
Service argocd/argocd-server:80
        |
        v
Argo CD API + UI
```

## 2.2 Authentication path

```text
User
 |
 v
Argo CD
 |
 | Authorization Code + PKCE S256
 v
Keycloak realm: ai-platform
 |
 | ID/access/refresh tokens
 | groups claim
 v
Argo CD token validation
 |
 v
Argo CD RBAC
```

## 2.3 Certificate path

```text
Certificate CR
    |
    v
cert-manager
    |
    v
Vault PKI
pki_modelservice/sign/modelservice
    |
    v
Secret gateway-system/argocd-ai-platform-local-tls
    |
    v
Gateway listener argocd-https
```

## 2.4 Three separate trust relationships

1. **Client → Argo CD:** the client trusts the CA signing `argocd.ai-platform.local`.
2. **Argo CD → Keycloak:** `argocd-server` trusts the CA signing `auth.ai-platform.local`.
3. **Token → RBAC:** Argo CD validates the OIDC token, then maps the `groups` claim to Argo CD roles.

Do not confuse TLS trust with RBAC. A valid certificate does not imply the user has permission, and a valid token does not fix a TLS trust failure.

---

# 3. Concepts

## OIDC

OpenID Connect is the identity layer used between Argo CD and Keycloak. Keycloak owns user authentication; Argo CD consumes identity claims.

```text
issuer   = https://auth.ai-platform.local/realms/ai-platform
clientID = ai-platform-argocd
```

## Authorization Code Flow

The browser authenticates with Keycloak. Keycloak returns a short-lived authorization code. The client exchanges that code for tokens. Argo CD never needs the user's Keycloak password.

## PKCE

PKCE (Proof Key for Code Exchange) protects the authorization-code exchange for a public client. The client creates a verifier and an S256 challenge. A stolen authorization code is not enough without the matching verifier.

We use:

```text
PKCE Method: S256
```

## Public OIDC client

The Argo CD Keycloak client is public:

```text
publicClient: true
```

There is no client secret distributed to CLI users. PKCE protects the code exchange.

## OIDC scopes

The implementation requests:

```text
openid
profile
email
groups
offline_access
```

- `openid`: activates OIDC.
- `profile`, `email`: standard identity claims.
- `groups`: group membership used by Argo CD RBAC.
- `offline_access`: enables refresh-token behavior subject to Keycloak policy.

## Group claim

Keycloak emits for example:

```json
{
  "groups": ["platform-viewer"]
}
```

Argo CD reads `groups` and maps exact values to roles.

## Authentication vs authorization

- **Authentication:** Who are you? → Keycloak.
- **Authorization:** What may you do? → Argo CD RBAC.

## RBAC policy entries

```text
p, role:platform-viewer, applications, get, ai-platform/*, allow
```

means:

```text
role     = role:platform-viewer
resource = applications
action   = get
object   = ai-platform/*
effect   = allow
```

Group mapping:

```text
g, platform-viewer, role:platform-viewer
```

means Keycloak group `platform-viewer` receives the Argo CD role `role:platform-viewer`.

## `sync` vs `override`

`sync` deploys the desired state already defined for the Application in Git.

`override` is more powerful and can permit deployment of a revision/manifests outside the normal desired revision.

Our deployer gets:

```text
sync     yes
override no
```

## `policy.default`

Every authenticated user receives the default role. We use:

```yaml
policy.default: role:authenticated
```

but give `role:authenticated` no useful policy lines. Access only comes from an explicitly mapped group.

## TLS termination

```text
client --HTTPS--> Envoy --HTTP--> argocd-server:80
```

TLS is still enforced externally. Argo CD itself does not terminate the external TLS connection.

## Gateway listener

A listener defines protocol, port, hostname, TLS certificate, and which Routes may attach.

## HTTPRoute

An HTTPRoute binds to a Gateway listener and maps HTTP requests to Kubernetes backends.

## `allowedRoutes`

The Gateway owner controls which namespaces may attach Routes. A selector such as:

```yaml
namespaces:
  from: Selector
  selector:
    matchLabels:
      shared-gateway-access: "true"
```

creates a cross-namespace trust boundary.

## Certificate and TLS Secret

The cert-manager `Certificate` is desired state. cert-manager creates the actual TLS Secret containing `tls.crt` and `tls.key`. The Gateway references the Secret.

## CN and SAN

The Vault role used here requires a Common Name. The final certificate therefore requests:

```text
CN  = argocd.ai-platform.local
SAN = DNS:argocd.ai-platform.local
```

The SAN remains the hostname identity used by modern TLS clients.

## ECDSA

The Vault role requires EC keys. The Certificate must therefore explicitly use:

```yaml
privateKey:
  algorithm: ECDSA
  size: 256
```

## `rotationPolicy: Always`

This makes cert-manager generate a new private key on reissuance instead of indefinitely reusing the original key.

---

# 4. Reference environment

| Purpose | Value |
|---|---|
| Argo CD version | `v3.5.1` |
| Kubernetes | `v1.36.1` |
| Argo CD namespace | `argocd` |
| Keycloak namespace | `keycloak` |
| Gateway namespace | `gateway-system` |
| AppProject | `ai-platform` |
| Gateway | `gateway-system/shared-gateway` |
| GatewayClass | `envoy` |
| Gateway address | `172.19.255.200` |
| Argo hostname | `argocd.ai-platform.local` |
| Keycloak hostname | `auth.ai-platform.local` |
| API hostname | `api.ai-platform.local` |
| Model hostname | `fraud-model.local` |
| Keycloak realm | `ai-platform` |
| OIDC client | `ai-platform-argocd` |
| Vault | `https://vault.platform.local:8200` |
| Vault PKI mount | `pki_modelservice/` |
| Vault signing role | `modelservice` |
| cert-manager Issuer | `gateway-system/vault-issuer` |
| Argo TLS Secret | `argocd-ai-platform-local-tls` |
| Root CA CN | `AI Platform ModelService Root CA` |
| GitOps repo | `/mnt/data/ai-platform-gitops` |
| Source repo | `/mnt/data/ai-platform-operator` |

---

# 5. Security model

Keep REST/API application roles separate from platform/GitOps groups:

```text
Keycloak realm roles
  model-viewer / model-deployer / model-admin
      -> application/API authorization

Keycloak groups
  platform-viewer / platform-deployer / platform-admin
      -> Argo CD authorization
```

Mappings:

| User | Keycloak group | Argo CD role |
|---|---|---|
| `viewer-user` | `platform-viewer` | `role:platform-viewer` |
| `deployer-user` | `platform-deployer` | `role:platform-deployer` |
| `admin-user` | `platform-admin` | built-in `role:admin` |

Expected capabilities:

| Capability | Viewer | Deployer | Admin |
|---|---:|---:|---:|
| Read AI Platform apps | Yes | Yes | Yes |
| Read AI Platform project | Yes | Yes | Yes |
| Read logs | Yes | Yes | Yes |
| Sync apps | No | Yes | Yes |
| Override revision/manifests | No | No | Yes |
| Read clusters globally | No | No | Yes |
| Modify project | No | No | Yes |
| Full administration | No | No | Yes |

---

# 6. Keycloak implementation

## 6.1 Groups

Create in realm `ai-platform`:

```text
platform-viewer
platform-deployer
platform-admin
```

Assign:

```text
viewer-user    -> platform-viewer
deployer-user  -> platform-deployer
admin-user     -> platform-admin
```

Do not remove existing realm roles such as `model-viewer`.

## 6.2 Argo CD OIDC client

Client ID:

```text
ai-platform-argocd
```

Settings:

```text
Client authentication: OFF
Authorization: OFF
Standard flow: ON
Direct access grants: OFF
Implicit flow: OFF
PKCE Method: S256
```

URLs:

```text
Root URL:
https://argocd.ai-platform.local

Home URL:
https://argocd.ai-platform.local/applications

Valid Redirect URIs:
https://argocd.ai-platform.local/auth/callback
https://argocd.ai-platform.local/pkce/verify
http://localhost:8085/auth/callback

Valid Post Logout Redirect URIs:
https://argocd.ai-platform.local/applications

Web Origins:
https://argocd.ai-platform.local
```

Use exact callback URIs rather than broad wildcards.

## 6.3 `groups` client scope

Create:

```text
Name: groups
Protocol: OpenID Connect
```

Add a Group Membership mapper:

```text
Name: groups
Token Claim Name: groups
Full group path: OFF
Add to ID token: ON
Add to access token: ON
Add to UserInfo: ON
```

Attach `groups` as a **Default** client scope to:

```text
ai-platform-argocd
ai-platform-cli
```

## 6.4 Automation pattern

Reference script:

```text
/mnt/data/ai-platform-operator/infrastructure/keycloak/scripts/configure-argocd-oidc.sh
```

The important design is:

- orchestration runs on the Ansible host where `jq` exists;
- Keycloak's supported `/opt/keycloak/bin/kcadm.sh` runs inside the Keycloak pod;
- no tooling is installed into the running hardened Keycloak image;
- bootstrap credentials are temporary environment variables and are unset after use;
- no password, access token, refresh token, or client secret is committed.

Wrapper concept:

```bash
kubectl exec \
  -n keycloak \
  "${KEYCLOAK_POD}" \
  -- /opt/keycloak/bin/kcadm.sh "$@"
```

Important `kcadm` ordering learned during implementation:

```text
Correct:   kcadm.sh get ... --config FILE
Incorrect: kcadm.sh --config FILE get ...
```

The implementation created/reconciled groups, memberships, the public PKCE client, the `groups` client scope, the group-membership mapper, and default-scope attachments.

---

# 7. Verify the Keycloak token

Use the existing PKCE helper:

```bash
cd /mnt/data/ai-platform-operator
infrastructure/keycloak/scripts/pkce-login.py
```

Load the token without printing it:

```bash
export TOKEN="$(
  tr -d '\r\n' \
    < .local/keycloak/tokens/user-access-token.jwt
)"
```

Decode selected claims only:

```bash
python3 - <<'PY'
import os, json, base64

token = os.environ["TOKEN"]
payload = token.split(".")[1]
payload += "=" * (-len(payload) % 4)
claims = json.loads(base64.urlsafe_b64decode(payload).decode())

for key in ("preferred_username", "groups", "realm_access"):
    print(f"{key}: {claims.get(key)}")
PY
```

Expected for the viewer:

```text
preferred_username: viewer-user
groups: ['platform-viewer']
realm_access: {'roles': ['model-viewer', ...]}
```

Then:

```bash
unset TOKEN
```

Never paste the JWT into Git, documentation, tickets, or logs.

---

# 8. Argo CD OIDC

File:

```text
/mnt/data/ai-platform-gitops/argocd/bootstrap/argocd-cm-patch.yaml
```

Final logical configuration:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-cm
data:
  url: https://argocd.ai-platform.local

  admin.enabled: "false"

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

    rootCA: |
      -----BEGIN CERTIFICATE-----
      <PUBLIC AI PLATFORM ROOT CA PEM>
      -----END CERTIFICATE-----
```

The `rootCA` contains only the public CA certificate. Never put `tls.key` or another private key into this ConfigMap.

### Why `rootCA` is necessary

The browser PKCE flow originally completed, but Argo CD later returned:

```text
invalid session: failed to verify the token
```

Server logs showed:

```text
failed to query provider ...
tls: failed to verify certificate:
x509: certificate signed by unknown authority
```

Argo CD could not fetch Keycloak OIDC discovery/JWKS over trusted TLS. Adding the private CA to `oidc.config.rootCA` fixed this.

---

# 9. Argo CD RBAC

File:

```text
argocd/bootstrap/argocd-rbac-cm-patch.yaml
```

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

    # Keycloak groups
    g, platform-viewer, role:platform-viewer
    g, platform-deployer, role:platform-deployer
    g, platform-admin, role:admin
```

Why not default to built-in `role:readonly`? Because that would be global read-only. The custom viewer is scoped to `ai-platform/*`.

---

# 10. Revision-override protection

Use:

```yaml
application.sync.requireOverridePrivilegeForRevisionSync: "true"
```

Deployer receives `applications, sync` but not `applications, override`.

This makes the intended model:

```text
Git defines desired revision
        |
        v
Deployer may sync it
        |
        X cannot override arbitrary revision/manifests
```

---

# 11. Gateway exposure

Existing shared Gateway:

```text
gateway-system/shared-gateway
```

Argo CD listener:

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

For a stricter production boundary, use a namespace selector instead of `from: All` for this listener.

HTTPS route:

```text
argocd/exposure/httproute.yaml
```

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: argocd
  namespace: argocd
spec:
  parentRefs:
    - name: shared-gateway
      namespace: gateway-system
      sectionName: argocd-https

  hostnames:
    - argocd.ai-platform.local

  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /
      backendRefs:
        - name: argocd-server
          port: 80
```

Expected:

```text
Accepted=True
ResolvedRefs=True
```

---

# 12. Vault/cert-manager certificate

File:

```text
argocd/exposure/certificate.yaml
```

Final working manifest:

```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: argocd-ai-platform-local
  namespace: gateway-system
spec:
  secretName: argocd-ai-platform-local-tls

  commonName: argocd.ai-platform.local

  privateKey:
    algorithm: ECDSA
    size: 256
    rotationPolicy: Always

  dnsNames:
    - argocd.ai-platform.local

  issuerRef:
    name: vault-issuer
    kind: Issuer
    group: cert-manager.io
```

The Vault signing path used was:

```text
pki_modelservice/sign/modelservice
```

The Vault role required EC keys and a Common Name, which is why both the `privateKey` and `commonName` fields matter.

Verify:

```bash
kubectl wait \
  --for=condition=Ready \
  certificate/argocd-ai-platform-local \
  -n gateway-system \
  --timeout=180s
```

Inspect only the public certificate:

```bash
kubectl get secret \
  argocd-ai-platform-local-tls \
  -n gateway-system \
  -o jsonpath='{.data.tls\.crt}' |
base64 -d |
openssl x509 \
  -noout \
  -subject \
  -issuer \
  -dates \
  -ext subjectAltName
```

Reference result:

```text
subject=CN = argocd.ai-platform.local
issuer=CN = AI Platform ModelService Root CA
DNS:argocd.ai-platform.local
```

Never print `tls.key`.

---

# 13. TLS termination and `server.insecure`

Initial HTTPS requests returned:

```text
HTTP/2 307
Location: https://argocd.ai-platform.local/api/version
```

This was a redirect to the same external URL.

Cause:

```text
HTTPS client
  -> Envoy terminates TLS
  -> HTTP to argocd-server:80
  -> Argo CD redirects HTTP to HTTPS
  -> same external URL
```

Fix:

File:

```text
argocd/bootstrap/argocd-cmd-params-cm-patch.yaml
```

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-cmd-params-cm
data:
  server.insecure: "true"
```

Add to bootstrap Kustomization:

```yaml
patches:
  - path: argocd-cm-patch.yaml
  - path: argocd-rbac-cm-patch.yaml
  - path: argocd-cmd-params-cm-patch.yaml
```

External traffic remains HTTPS. The internal Gateway→Argo hop is HTTP because TLS already terminated at Envoy.

---

# 14. HTTP to HTTPS redirect

Final route:

```text
argocd/exposure/httproute-redirect.yaml
```

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: argocd-http-redirect
  namespace: gateway-system
spec:
  parentRefs:
    - name: shared-gateway
      sectionName: http

  hostnames:
    - argocd.ai-platform.local

  rules:
    - filters:
        - type: RequestRedirect
          requestRedirect:
            scheme: https
            statusCode: 301
```

Shared HTTP listener:

```yaml
- name: http
  protocol: HTTP
  port: 80
  allowedRoutes:
    kinds:
      - group: gateway.networking.k8s.io
        kind: HTTPRoute
    namespaces:
      from: Selector
      selector:
        matchLabels:
          shared-gateway-access: "true"
```

Namespace requirement:

```yaml
metadata:
  labels:
    shared-gateway-access: "true"
```

Verify route status:

```text
Accepted=True
ResolvedRefs=True
```

Verify redirect:

```bash
curl --silent --show-error --head \
  http://argocd.ai-platform.local/
```

Expected:

```text
HTTP/1.1 301 Moved Permanently
location: https://argocd.ai-platform.local/
```

---

# 15. Private CA trust

## 15.1 Argo CD server trusts Keycloak

Add the public CA in `oidc.config.rootCA`.

Do **not** make `oidc.tls.insecure.skip.verify=true` the normal solution.

## 15.2 CLI host trusts Argo CD

On Debian/Ubuntu:

```bash
sudo cp \
  /mnt/data/ai-platform-operator/.local/keycloak/fraud-model-root-ca.crt \
  /usr/local/share/ca-certificates/ai-platform-root-ca.crt

sudo update-ca-certificates
```

Then:

```bash
curl \
  --silent \
  --show-error \
  https://argocd.ai-platform.local/api/version |
jq .
```

Expected:

```json
{"Version":"v3.5.1"}
```

No `--insecure` and no manual CA flag should be necessary afterward.

---

# 16. Apply and verify

Compile:

```bash
cd /mnt/data/ai-platform-gitops

kubectl kustomize argocd/bootstrap > /tmp/argocd-secure.yaml
kubectl kustomize argocd/exposure > /tmp/argocd-exposure.yaml
```

Review:

```bash
kubectl diff -k argocd/bootstrap
kubectl diff -k argocd/exposure
```

`kubectl diff` exit codes:

```text
0  no differences
1  differences found
>1 command error
```

Stop if a diff unexpectedly removes security-sensitive fields such as:

```text
privateKey
issuerRef
OIDC
rootCA
RBAC
TLS
NetworkPolicy
securityContext
```

Server-side dry run:

```bash
kubectl apply --server-side --dry-run=server -k argocd/bootstrap
kubectl apply --dry-run=server -k argocd/exposure
```

Apply:

```bash
kubectl apply --server-side -k argocd/bootstrap
kubectl apply -k argocd/exposure
```

Restart server after OIDC/server parameter changes:

```bash
kubectl rollout restart deployment/argocd-server -n argocd
kubectl rollout status deployment/argocd-server -n argocd --timeout=180s
```

---

# 17. Headless CLI SSO

Normal:

```bash
argocd login \
  argocd.ai-platform.local \
  --sso \
  --grpc-web
```

On the headless Ansible server this failed because `xdg-open` was absent.

Use:

```bash
argocd login \
  argocd.ai-platform.local \
  --sso \
  --grpc-web \
  --sso-launch-browser=false
```

The CLI listens on `localhost:8085` and prints the Keycloak authorization URL.

For a remote CLI, create an SSH tunnel from the workstation:

```bash
ssh -L 8085:127.0.0.1:8085 \
  ansible@<ANSIBLE_SERVER_IP>
```

Keep the tunnel open, paste the authorization URL in the workstation browser, and complete Keycloak login.

The browser callback:

```text
http://localhost:8085/auth/callback
```

is forwarded to the CLI process.

Successful result:

```text
Authentication successful
'admin-user@ai-platform.local' logged in successfully
Context 'argocd.ai-platform.local' updated
```

---

# 18. Web UI SSO

CLI login is not required for the UI.

Open:

```text
https://argocd.ai-platform.local
```

The browser machine must resolve:

```text
argocd.ai-platform.local -> 172.19.255.200
```

For a lab `/etc/hosts` entry:

```text
172.19.255.200 argocd.ai-platform.local
```

The browser machine must also trust the platform root CA.

Then select the Keycloak SSO login option.

Expected behavior:

```text
viewer-user   -> read-only AI Platform UI
deployer-user -> read + sync
admin-user    -> full administration
```

---

# 19. RBAC tests

## Admin

```bash
argocd account get-user-info --grpc-web
argocd app list --grpc-web
argocd proj list --grpc-web
argocd cluster list --grpc-web
```

Expected identity:

```text
Logged In: true
Groups: platform-admin
```

## Viewer

Expected identity:

```text
Groups: platform-viewer
```

Tests:

```bash
argocd account can-i get applications 'ai-platform/*' --grpc-web
# yes

argocd account can-i get projects ai-platform --grpc-web
# yes

argocd account can-i sync applications 'ai-platform/*' --grpc-web
# no

argocd account can-i override applications 'ai-platform/*' --grpc-web
# no

argocd account can-i get clusters '*' --grpc-web
# no

argocd account can-i update projects ai-platform --grpc-web
# no
```

Verified result:

```text
get applications      yes
get project           yes
sync applications     no
override              no
get clusters          no
update project        no
```

## Deployer

Expected identity:

```text
Groups: platform-deployer
```

Tests:

```bash
argocd account can-i get applications 'ai-platform/*' --grpc-web
# yes

argocd account can-i sync applications 'ai-platform/*' --grpc-web
# yes

argocd account can-i override applications 'ai-platform/*' --grpc-web
# no

argocd account can-i get clusters '*' --grpc-web
# no

argocd account can-i update projects ai-platform --grpc-web
# no
```

Verified result:

```text
get applications      yes
sync applications     yes
override              no
get clusters          no
update project        no
```

Validate policy syntax:

```bash
argocd admin settings rbac validate --namespace argocd
```

---

# 20. Disable built-in admin

Only after all SSO/RBAC tests pass, set:

```yaml
admin.enabled: "false"
```

Apply and restart Argo CD.

Verify:

```bash
kubectl get configmap argocd-cm -n argocd \
  -o jsonpath='{.data.admin\.enabled}'
echo
```

Expected:

```text
false
```

And:

```bash
argocd account list --grpc-web
```

Reference result:

```text
NAME   ENABLED  CAPABILITIES
admin  false    login
```

Normal login is now Keycloak SSO.

---

# 21. Break-glass recovery

If Keycloak/OIDC fails but Kubernetes admin access remains, temporarily restore the local admin:

```bash
kubectl patch configmap \
  argocd-cm \
  -n argocd \
  --type merge \
  -p '{"data":{"admin.enabled":"true"}}'
```

Restart:

```bash
kubectl rollout restart deployment/argocd-server -n argocd
kubectl rollout status deployment/argocd-server -n argocd --timeout=180s
```

This is break-glass only. After OIDC repair, Git desired state must restore:

```yaml
admin.enabled: "false"
```

---

# 22. Troubleshooting from the real implementation

## Kustomize patch target mismatch

Error:

```text
no resource matches strategic merge patch
"ConfigMap.v1.[noGrp]/argocd-cm.argocd"
```

Cause: patch declared `metadata.namespace: argocd` before the Kustomize namespace transformer had applied the namespace to the upstream resource.

Fix: remove namespace from the patch and keep:

```yaml
namespace: argocd
```

in the Kustomization.

## `kubectl cp` failed against Keycloak

Error:

```text
exec: "tar": executable file not found in $PATH
```

Cause: minimal Keycloak image had no `tar`.

Fix: do not install tools into a running hardened image. Run orchestration on the Ansible host or stream through stdin.

## Keycloak script lacked `jq`

Error:

```text
jq: command not found
```

Fix: run orchestration on the host, invoke only `kcadm.sh` in the pod.

## Vault rejected key type

Error:

```text
role requires keys of type ec
```

Cause: Git manifest had dropped:

```yaml
privateKey:
  algorithm: ECDSA
  rotationPolicy: Always
  size: 256
```

Fix: restore it.

Lesson: never ignore a diff that removes a security-sensitive field.

## Vault required Common Name

Error:

```text
the common_name field is required
```

Fix:

```yaml
commonName: argocd.ai-platform.local
```

while keeping the DNS SAN.

Verify CSR:

```bash
kubectl get certificaterequest "${ARGOCD_CERT_REQUEST}" \
  -n gateway-system \
  -o jsonpath='{.spec.request}' |
base64 -d |
openssl req -noout -subject -text |
grep -E 'Subject:|DNS:|Public Key Algorithm'
```

Working result:

```text
Subject: CN = argocd.ai-platform.local
Public Key Algorithm: id-ecPublicKey
DNS:argocd.ai-platform.local
```

## cert-manager retry/backoff

After correcting a failed Certificate, trigger reissuance:

```bash
cmctl renew argocd-ai-platform-local -n gateway-system
```

## 307 redirect loop

Observed:

```text
HTTP/2 307
Location: https://argocd.ai-platform.local/api/version
```

Cause: TLS terminated at Envoy, but Argo CD port 80 still redirected HTTP to HTTPS.

Fix:

```yaml
server.insecure: "true"
```

## HTTP redirect returned 404

Route status:

```text
Accepted=False
Reason=NotAllowedByListeners
ResolvedRefs=True
```

Cause: HTTP listener `allowedRoutes` policy did not allow that route attachment.

Fix: satisfy the namespace selector and explicitly allow HTTPRoute.

After reconciliation:

```text
Accepted=True
ResolvedRefs=True
```

and HTTP returned 301.

## Headless CLI failed to launch browser

Error:

```text
exec: "xdg-open": executable file not found
```

Fix:

```text
--sso-launch-browser=false
```

plus SSH port forwarding for callback port 8085.

## Authentication succeeded but token was rejected

CLI:

```text
Authentication successful
```

then:

```text
Logged In: false
invalid session: failed to verify the token
```

Server log:

```text
x509: certificate signed by unknown authority
```

Cause: `argocd-server` did not trust Keycloak's private CA.

Fix: configure `oidc.config.rootCA` and restart the server.

## CLI warned about Argo CD certificate

Observed:

```text
x509: certificate signed by unknown authority
Proceed insecurely (y/n)?
```

Fix: install the private root CA into the host OS trust store. Do not keep using insecure verification.

---

# 23. Final manifests

## Bootstrap Kustomization

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
  - path: argocd-cmd-params-cm-patch.yaml
```

## `argocd-cm-patch.yaml`

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-cm
data:
  url: https://argocd.ai-platform.local
  admin.enabled: "false"
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
    rootCA: |
      -----BEGIN CERTIFICATE-----
      <PUBLIC ROOT CA PEM>
      -----END CERTIFICATE-----
```

## `argocd-rbac-cm-patch.yaml`

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-rbac-cm
data:
  policy.default: role:authenticated
  scopes: '[groups]'
  policy.csv: |
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

## `argocd-cmd-params-cm-patch.yaml`

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-cmd-params-cm
data:
  server.insecure: "true"
```

## Exposure Kustomization

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - certificate.yaml
  - httproute.yaml
  - httproute-redirect.yaml
```

Do not set one namespace on this Kustomization because the resources intentionally span `argocd` and `gateway-system`.

## Certificate

```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: argocd-ai-platform-local
  namespace: gateway-system
spec:
  secretName: argocd-ai-platform-local-tls
  commonName: argocd.ai-platform.local
  privateKey:
    algorithm: ECDSA
    size: 256
    rotationPolicy: Always
  dnsNames:
    - argocd.ai-platform.local
  issuerRef:
    name: vault-issuer
    kind: Issuer
    group: cert-manager.io
```

## HTTPS HTTPRoute

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: argocd
  namespace: argocd
spec:
  parentRefs:
    - name: shared-gateway
      namespace: gateway-system
      sectionName: argocd-https
  hostnames:
    - argocd.ai-platform.local
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /
      backendRefs:
        - name: argocd-server
          port: 80
```

## Redirect HTTPRoute

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: argocd-http-redirect
  namespace: gateway-system
spec:
  parentRefs:
    - name: shared-gateway
      sectionName: http
  hostnames:
    - argocd.ai-platform.local
  rules:
    - filters:
        - type: RequestRedirect
          requestRedirect:
            scheme: https
            statusCode: 301
```

---

# 24. Final verification checklist

```text
[x] Argo CD v3.5.1 installed and healthy
[x] ai-platform AppProject exists
[x] argocd-server remains ClusterIP
[x] dedicated Keycloak client ai-platform-argocd
[x] Authorization Code Flow
[x] PKCE S256
[x] Direct Access Grants disabled
[x] platform-viewer group
[x] platform-deployer group
[x] platform-admin group
[x] groups claim included in token
[x] viewer token verified
[x] Argo CD OIDC config applied
[x] Argo CD RBAC applied
[x] revision override protection enabled
[x] private Keycloak CA trusted by Argo CD
[x] Vault-issued ECDSA certificate
[x] CN verified
[x] DNS SAN verified
[x] certificate Ready=True
[x] HTTPS listener Programmed=True
[x] HTTPS HTTPRoute Accepted=True
[x] HTTP redirect Accepted=True
[x] HTTP -> HTTPS returns 301
[x] server.insecure=true for TLS termination topology
[x] HTTPS /api/version returns v3.5.1
[x] CLI host trusts private CA
[x] platform-admin SSO works
[x] platform-viewer allow/deny tests pass
[x] platform-deployer allow/deny tests pass
[x] built-in admin disabled
[x] break-glass recovery documented
```

Useful checks:

```bash
kubectl get certificate argocd-ai-platform-local -n gateway-system
kubectl get httproute argocd -n argocd
kubectl get httproute argocd-http-redirect -n gateway-system
kubectl get gateway shared-gateway -n gateway-system
curl https://argocd.ai-platform.local/api/version | jq .
argocd account get-user-info --grpc-web
argocd account list --grpc-web
```

---

# 25. Why this design is secure

- User passwords remain in Keycloak.
- Public-client login is protected with PKCE S256.
- Redirect URIs are explicit.
- Groups are used for identity-to-role mapping.
- Viewer access is scoped to the AI Platform project instead of global read-only.
- Deployer can sync Git state but cannot override arbitrary revisions.
- Default authenticated role has no useful baseline permissions.
- External HTTP is redirected to HTTPS.
- TLS verification is not disabled as the permanent solution.
- Private CA trust is explicit on both server-to-Keycloak and client-to-Argo paths.
- The local superuser is removed from normal use after SSO is proven.
- Recovery is controlled by Kubernetes administrative access.
- No passwords, JWTs, refresh tokens, client secrets, or private keys belong in Git.

The implementation principle is:

```text
"Login works" is not sufficient.

Secure access is complete only when:
  identity is verified,
  TLS trust is verified,
  token verification is verified,
  allowed actions are verified,
  denied actions are verified,
  recovery is documented,
  and the bootstrap superuser is removed from normal use.
```

---

# 26. How to adapt it elsewhere

Replace environment-specific values such as:

```text
argocd.ai-platform.local
auth.ai-platform.local
ai-platform
ai-platform-argocd
platform-viewer
platform-deployer
platform-admin
gateway-system
shared-gateway
vault-issuer
argocd-ai-platform-local-tls
```

Then verify instead of assuming:

1. DNS/hosts resolution.
2. Gateway listener ownership and `allowedRoutes`.
3. Certificate issuer and Vault role restrictions.
4. Key algorithm accepted by the CA.
5. CN requirement of the CA role.
6. OIDC issuer TLS trust.
7. Exact Keycloak redirect URIs.
8. Exact `groups` claim values.
9. RBAC allow and deny behavior.
10. Admin SSO before disabling local admin.
11. Break-glass Kubernetes access.

---

# 27. Official references

## Argo CD

Keycloak + PKCE + groups:

https://argo-cd.readthedocs.io/en/latest/operator-manual/user-management/keycloak/

RBAC:

https://argo-cd.readthedocs.io/en/stable/operator-manual/rbac/

OIDC private root CA:

https://argo-cd.readthedocs.io/en/latest/operator-manual/user-management/

Gateway/Ingress/TLS termination and `server.insecure`:

https://argo-cd.readthedocs.io/en/latest/operator-manual/ingress/

## Gateway API

HTTPRoute:

https://gateway-api.sigs.k8s.io/reference/api-types/httproute/

Security and cross-namespace route binding:

https://gateway-api.sigs.k8s.io/docs/concepts/security/

Traffic matching / `allowedRoutes`:

https://gateway-api.sigs.k8s.io/docs/concepts/traffic-matching/

HTTP redirect:

https://gateway-api.sigs.k8s.io/guides/user-guides/http-redirect-rewrite/

## cert-manager

Certificates:

https://cert-manager.io/docs/usage/certificate/

Gateway usage:

https://cert-manager.io/docs/usage/gateway/

cmctl:

https://cert-manager.io/docs/reference/cmctl/

## HashiCorp Vault

PKI secrets engine:

https://developer.hashicorp.com/vault/docs/secrets/pki

PKI API:

https://developer.hashicorp.com/vault/api-docs/secret/pki

---

## End state

The secure-access phase is complete when both positive **and negative** behavior is proven:

```text
platform-viewer
  read yes
  sync no
  override no
  cluster admin no

platform-deployer
  read yes
  sync yes
  override no
  cluster admin no

platform-admin
  full administration

built-in admin
  disabled
```

That is the reproducible security contract for this implementation.
