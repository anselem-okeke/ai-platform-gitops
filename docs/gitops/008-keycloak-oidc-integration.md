# Keycloak OIDC Integration

## Purpose

This document records the Keycloak realm, clients, groups, PKCE configuration, group claims, implementation method, and validation steps used for Argo CD authentication.

## Environment

Endpoint:

```text
https://auth.ai-platform.local
```

Namespace:

```text
keycloak
```

Observed version:

```text
26.7.0
```

Realm:

```text
ai-platform
```

## Required Groups

```text
platform-viewer
platform-deployer
platform-admin
```

Development mappings used for testing:

```text
viewer-user   -> platform-viewer
deployer-user -> platform-deployer
admin-user    -> platform-admin
```

## Argo CD Client

```text
ai-platform-argocd
```

Validated client properties:

```text
publicClient: true
standardFlowEnabled: true
directAccessGrantsEnabled: false
```

PKCE:

```text
S256
```

Web origin includes:

```text
https://argocd.ai-platform.local
```

Redirect URIs include the Argo CD browser/PKCE callback paths required by the integration.

## CLI Client

```text
ai-platform-cli
```

Validated callback:

```text
http://127.0.0.1:18080/callback
```

Scopes:

```text
openid profile email
```

## Groups Client Scope

Client scope:

```text
groups
```

Protocol mapper:

```text
oidc-group-membership-mapper
```

The scope is attached to:

```text
ai-platform-argocd
ai-platform-cli
```

This enables Argo CD to receive group claims.

## KCADM Wrapper

Administrative wrapper:

```text
.local/keycloak/bin/kcadm-in-pod
```

KCADM config:

```text
/tmp/ai-platform-kcadm.config
```

## Script Delivery

An implementation issue occurred because:

```text
kubectl cp
```

requires `tar` in the container.

The container did not have `tar`.

The working approach was stdin delivery.

Example:

```bash
kubectl exec -i \
  -n keycloak \
  <keycloak-pod> \
  -- sh -c 'cat > /tmp/configure-argocd-oidc.sh' \
  < infrastructure/keycloak/scripts/configure-argocd-oidc.sh
```

Then:

```bash
kubectl exec \
  -n keycloak \
  <keycloak-pod> \
  -- chmod 700 /tmp/configure-argocd-oidc.sh
```

Run the script using the tested Keycloak/KCADM environment.

## Verification

### 1. Keycloak Pod

```bash
kubectl get pods -n keycloak
```

### 2. Realm Groups

Using the KCADM wrapper, list groups and confirm:

```text
platform-viewer
platform-deployer
platform-admin
```

### 3. Argo Client

Inspect:

```text
ai-platform-argocd
```

Confirm:

```text
public client
standard flow enabled
direct access grants disabled
PKCE S256
redirect URIs
web origins
```

### 4. Groups Scope

Confirm:

```text
groups
```

client scope exists and contains the group-membership mapper.

### 5. Browser Login

Open:

```text
https://argocd.ai-platform.local
```

Expected:

```text
Argo -> Keycloak -> successful authentication -> Argo
```

### 6. PKCE CLI Login

PKCE utility:

```text
infrastructure/keycloak/scripts/pkce-login.py
```

Expected successful result:

```text
Authorization Code + PKCE exchange completed
```

Tokens are written under ignored local paths rather than Git.

## Troubleshooting

### PKCE callback connection refused

Ensure the local listener is active before completing browser authorization.

Callback must exactly match:

```text
http://127.0.0.1:18080/callback
```

### Login works but group authorization does not

Inspect the token claims and verify:

```text
groups
```

claim is present.

Then inspect Argo RBAC mappings.

### Invalid redirect URI

The actual callback must exactly match a configured Keycloak redirect URI.

## Security Considerations

- use authorization code + PKCE
- do not enable password/direct grant without a specific reason
- do not store tokens in Git
- use groups for scalable RBAC
- separate browser and CLI clients where appropriate

## Official References

- Argo CD Keycloak integration: https://argo-cd.readthedocs.io/en/stable/operator-manual/user-management/keycloak/
- Keycloak server administration: https://www.keycloak.org/docs/latest/server_admin/
- OAuth PKCE RFC 7636: https://datatracker.ietf.org/doc/html/rfc7636
- OpenID Connect Core: https://openid.net/specs/openid-connect-core-1_0.html
