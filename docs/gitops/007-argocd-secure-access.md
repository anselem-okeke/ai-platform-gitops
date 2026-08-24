# Argo CD Secure Access

## Purpose

This document explains how Argo CD is exposed over HTTPS while keeping the `argocd-server` Service internal and using Keycloak for identity.

## Security Goals

Argo CD is a privileged platform control plane.

Access must combine:

```text
network control
TLS
OIDC authentication
RBAC authorization
```

## Implemented Endpoint

```text
https://argocd.ai-platform.local
```

## Access Architecture

```text
Browser / CLI
     |
     | HTTPS
     v
Envoy Gateway
     |
     v
HTTPRoute
     |
     v
argocd-server
ClusterIP
```

## 1. Verify Internal Service

```bash
kubectl get svc argocd-server \
  -n argocd \
  -o wide
```

Expected:

```text
TYPE = ClusterIP
```

Observed ClusterIP:

```text
10.96.128.244
```

## 2. Verify Gateway Resources

```bash
kubectl get gateway,httproute -A
```

Locate the Argo CD route.

Describe:

```bash
kubectl describe httproute <argocd-route-name> \
  -n <route-namespace>
```

Check:

- parentRef
- hostname
- backend service
- route accepted/resolved references

## 3. Verify DNS

```bash
getent hosts argocd.ai-platform.local
```

or:

```bash
nslookup argocd.ai-platform.local
```

Expected development address is the shared Gateway endpoint configured for the environment.

## 4. Verify TLS

```bash
openssl s_client \
  -connect argocd.ai-platform.local:443 \
  -servername argocd.ai-platform.local \
  </dev/null
```

Check:

```text
SAN contains argocd.ai-platform.local
certificate chain is trusted
certificate is not expired
```

HTTP test:

```bash
curl -I https://argocd.ai-platform.local
```

## 5. Verify OIDC Redirect

Open:

```text
https://argocd.ai-platform.local
```

Authentication should redirect through:

```text
https://auth.ai-platform.local
```

and return to Argo CD.

## 6. Verify User Identity

After CLI login:

```bash
argocd account get-user-info
```

Confirm:

- expected username
- expected groups

## Bootstrap Port Forward

For emergency/bootstrap access:

```bash
kubectl port-forward \
  -n argocd \
  svc/argocd-server \
  8080:443
```

This is not the normal shared access model.

## Local Admin Strategy

Operating model:

```text
initial admin
   -> bootstrap only

Keycloak OIDC
   -> normal operation

break-glass admin
   -> documented recovery only
```

The built-in admin account should not be the day-to-day identity.

## Security Properties

- no separate public Argo LoadBalancer
- TLS terminated through controlled Gateway architecture
- centralized user identity
- group-based authorization
- no routine insecure TLS bypass

## Troubleshooting

### Gateway route unavailable

```bash
kubectl get gateway,httproute -A
kubectl describe httproute <name> -n <namespace>
```

### TLS mismatch

Inspect SAN/issuer with `openssl s_client`.

### Redirect URI error

Compare:

```text
Argo external URL
Keycloak redirect URIs
actual browser hostname
```

### Authentication succeeds but no permissions

Check:

```bash
argocd account get-user-info
```

Then inspect OIDC groups and Argo RBAC.

## Official References

- Argo CD API access: https://argo-cd.readthedocs.io/en/stable/getting_started/#3-access-the-argo-cd-api-server
- Argo CD ingress: https://argo-cd.readthedocs.io/en/stable/operator-manual/ingress/
- Argo CD security: https://argo-cd.readthedocs.io/en/stable/operator-manual/security/
- Gateway API: https://gateway-api.sigs.k8s.io/
- Envoy Gateway: https://gateway.envoyproxy.io/
