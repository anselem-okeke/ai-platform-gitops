# Argo CD RBAC

## Purpose

This document defines how authenticated Keycloak groups are mapped to Argo CD permissions and how least privilege is applied.

## Authentication vs Authorization

```text
Keycloak
  |
  | proves identity and groups
  v
Argo CD
  |
  | RBAC
  v
allowed / denied
```

## Groups

```text
platform-viewer
platform-deployer
platform-admin
```

## Role Intent

### Viewer

Expected capabilities:

```text
list Applications
view sync/health
inspect manifests/status
no routine mutations
```

### Deployer

Expected capabilities:

```text
deployment-oriented actions explicitly granted by policy
```

### Admin

Expected capabilities:

```text
platform administration
```

Membership should remain tightly controlled.

## Local Admin

The built-in Argo CD `admin` account is bootstrap/break-glass only.

Steady-state access:

```text
Keycloak OIDC + Argo RBAC
```

## Default Policy Principle

Keep:

```text
policy.default
```

minimal.

The default role applies broadly to authenticated users.

Grant elevated permissions explicitly through group-to-role mapping.

## Validate Logged-In Identity

```bash
argocd account get-user-info
```

Confirm:

- username
- group claims

## Viewer Validation

Authenticate as a viewer.

Expected success:

```bash
argocd app list
argocd app get ai-platform-api
```

Expected denial for privileged mutation unless explicitly granted:

```bash
argocd app sync ai-platform-api
```

## Deployer Validation

Authenticate as a deployer and verify only intended deployment actions succeed.

## Admin Validation

Authenticate as a platform admin and verify administrative actions expected by the role.

## Troubleshooting

### User has no permissions

Check:

1. user is in Keycloak group
2. `groups` client scope attached
3. groups claim present
4. Argo RBAC exact group name matches
5. project restrictions are not denying the resource

### User has too many permissions

Check:

```text
policy.default
global role policies
project roles
unexpected group membership
```

## Security Review Checklist

```text
[ ] default role minimal
[ ] viewer read-only
[ ] deployer scoped
[ ] admin limited to trusted group
[ ] local admin disabled for routine use
[ ] OIDC groups verified
[ ] project permissions also least-privilege
```

## Official References

- Argo CD RBAC: https://argo-cd.readthedocs.io/en/stable/operator-manual/rbac/
- Argo CD projects: https://argo-cd.readthedocs.io/en/stable/user-guide/projects/
- Argo CD Keycloak: https://argo-cd.readthedocs.io/en/stable/operator-manual/user-management/keycloak/
