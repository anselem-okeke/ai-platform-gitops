# Argo CD Secure Access

## Purpose

This document describes how Argo CD is exposed securely without converting `argocd-server` into a directly exposed public LoadBalancer.

## Security Goal

Argo CD is a privileged platform control plane. Access must therefore combine:

1. controlled network exposure
2. HTTPS/TLS
3. centralized identity
4. RBAC authorization

## Implemented Access Model

```text
Browser / CLI
      |
      v
HTTPS
      |
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

Argo CD endpoint:

```text
https://argocd.ai-platform.local
```

`argocd-server` remains:

```text
Type: ClusterIP
```

Observed ClusterIP:

```text
10.96.128.244
```

## Why ClusterIP Is Kept

The control plane should not require a separate externally exposed LoadBalancer when the platform already has a controlled Gateway layer.

Benefits:

- smaller network exposure surface
- central TLS handling
- common routing layer
- clearer ownership
- fewer direct entry points to privileged services

## Bootstrap Access

Before external routing is fully established, use port-forwarding:

```bash
kubectl port-forward \
  -n argocd \
  svc/argocd-server \
  8080:443
```

This is a bootstrap/administrative access path, not the intended shared user endpoint.

## TLS Architecture

The platform design uses Vault PKI as the trust foundation.

Conceptually:

```text
Vault PKI
    |
    v
certificate issuance
    |
    v
Kubernetes TLS Secret
    |
    v
Envoy Gateway listener
    |
    v
HTTPS
    |
    v
Argo CD route
```

The implemented security goals include:

- HTTPS endpoint
- certificate hostname matches `argocd.ai-platform.local`
- trusted certificate chain
- no routine `--insecure` dependency
- no private-key material committed to Git

## Identity Layer

Authentication is delegated to Keycloak:

```text
Argo CD
   |
   v
OIDC
   |
   v
Keycloak realm: ai-platform
```

Argo roles are based on OIDC group membership rather than shared local administrator credentials.

## Local Admin Strategy

The initial local admin account is bootstrap-only.

The intended steady-state model is:

```text
Keycloak OIDC -> normal administration
local admin   -> disabled
break-glass   -> documented controlled recovery path
```

## Verification

### Service remains internal

```bash
kubectl get svc argocd-server \
  -n argocd \
  -o wide
```

Expected type:

```text
ClusterIP
```

### Endpoint

```bash
curl -I https://argocd.ai-platform.local
```

Expected behavior depends on route/authentication flow, but HTTPS should be reachable with the configured certificate.

### Certificate

```bash
openssl s_client \
  -connect argocd.ai-platform.local:443 \
  -servername argocd.ai-platform.local \
  </dev/null
```

Inspect:

- subject/SAN
- issuer
- chain
- verification result

### Authentication

Open:

```text
https://argocd.ai-platform.local
```

Authentication should flow through Keycloak.

## Failure Scenarios

### TLS hostname mismatch

Check the certificate SAN and Gateway listener hostname.

### Gateway route not attached

Inspect:

```bash
kubectl get gateway,httproute -A
```

and describe the relevant resources.

### OIDC redirect failure

Verify:

- Argo CD external URL
- Keycloak redirect URI
- browser-visible hostname
- OIDC client configuration

### Service accidentally exposed

Check:

```bash
kubectl get svc argocd-server \
  -n argocd \
  -o jsonpath='{.spec.type}{"\n"}'
```

Expected:

```text
ClusterIP
```

## Official References

- Argo CD access options: https://argo-cd.readthedocs.io/en/stable/getting_started/#3-access-the-argo-cd-api-server
- Argo CD ingress documentation: https://argo-cd.readthedocs.io/en/stable/operator-manual/ingress/
- Argo CD TLS/security: https://argo-cd.readthedocs.io/en/stable/operator-manual/security/
- Kubernetes Gateway API: https://gateway-api.sigs.k8s.io/
- Envoy Gateway documentation: https://gateway.envoyproxy.io/

## Related Documentation

- [006-argocd-installation.md](006-argocd-installation.md)
- [008-keycloak-oidc-integration.md](008-keycloak-oidc-integration.md)
- [009-argocd-rbac.md](009-argocd-rbac.md)
- [017-gateway-and-routing.md](017-gateway-and-routing.md)
