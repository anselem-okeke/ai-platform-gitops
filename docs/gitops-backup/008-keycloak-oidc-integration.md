# Keycloak OIDC Integration

## Purpose

This document records the Keycloak configuration used to authenticate users to Argo CD and the PKCE-based CLI authentication path.

## Environment

Keycloak endpoint:

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

## Identity Groups

The platform defines:

```text
platform-viewer
platform-deployer
platform-admin
```

Development user mappings used for validation:

```text
viewer-user   -> platform-viewer
deployer-user -> platform-deployer
admin-user    -> platform-admin
```

These users are examples from the development environment; the group model is the reusable design.

## Argo CD Client

Client:

```text
ai-platform-argocd
```

Important properties:

```text
publicClient: true
standardFlowEnabled: true
directAccessGrantsEnabled: false
```

The client is configured for Authorization Code flow with PKCE.

## Redirect URIs

The Argo CD client includes redirect URIs required by the browser/CLI OIDC flow, including Argo CD callback/PKCE endpoints.

The configured web origin includes:

```text
https://argocd.ai-platform.local
```

PKCE uses:

```text
S256
```

## Groups Claim

A Keycloak client scope named:

```text
groups
```

contains an OIDC group-membership mapper.

It is attached to:

```text
ai-platform-argocd
ai-platform-cli
```

This ensures Argo CD receives group membership claims required by RBAC.

## CLI Client

Client:

```text
ai-platform-cli
```

Callback used by the PKCE login utility:

```text
http://127.0.0.1:18080/callback
```

Requested scopes:

```text
openid profile email
```

A successful validation produced an Authorization Code + PKCE token exchange.

## Administrative Automation

Keycloak was configured using `kcadm` from inside the Keycloak environment.

A local wrapper was used:

```text
.local/keycloak/bin/kcadm-in-pod
```

KCADM config:

```text
/tmp/ai-platform-kcadm.config
```

A configuration script was delivered to the pod using stdin because `kubectl cp` failed when the container lacked `tar`.

This is an important troubleshooting detail:

```text
kubectl cp
    -> requires tar in container
    -> failed

kubectl exec -i ... > /tmp/script
    -> worked
```

## Verification

### Groups

Use the KCADM wrapper to list realm groups and confirm:

```text
platform-viewer
platform-deployer
platform-admin
```

### Client

Inspect:

```text
ai-platform-argocd
```

and confirm:

- public client
- standard flow enabled
- direct access grants disabled
- redirect URIs
- web origins
- PKCE S256

### Group mapper

Confirm the `groups` client scope contains the group-membership protocol mapper.

### Browser login

Open:

```text
https://argocd.ai-platform.local
```

The login flow should redirect through Keycloak and return to Argo CD.

### CLI PKCE

The PKCE utility should complete:

```text
Authorization Code + PKCE exchange completed
```

without storing long-lived credentials in Git.

## Security Rationale

### Why OIDC

- centralized user lifecycle
- centralized MFA capability
- reusable group membership
- no shared Argo CD credentials
- auditable identity boundaries

### Why PKCE

PKCE binds the authorization code to a client-generated verifier. This reduces the value of a stolen authorization code.

### Why no Direct Access Grants

Password grant/direct-access flows are not required for this design and are disabled for the Argo CD public client.

## Troubleshooting

### Connection refused during PKCE callback

Confirm the local callback listener is running and reachable on:

```text
127.0.0.1:18080
```

### Login works but no permissions

Inspect the ID/access token claims and confirm the `groups` claim is present.

Then inspect Argo RBAC mappings.

### Invalid redirect URI

The exact callback URL used by the client must be configured in Keycloak.

## Official References

- Argo CD Keycloak integration: https://argo-cd.readthedocs.io/en/stable/operator-manual/user-management/keycloak/
- Keycloak 26.7 server administration: https://www.keycloak.org/docs/26.7.0/server_admin/
- Keycloak documentation: https://www.keycloak.org/documentation
- OAuth 2.0 PKCE (RFC 7636): https://datatracker.ietf.org/doc/html/rfc7636
- OpenID Connect Core: https://openid.net/specs/openid-connect-core-1_0.html

## Related Documentation

- [007-argocd-secure-access.md](007-argocd-secure-access.md)
- [009-argocd-rbac.md](009-argocd-rbac.md)
