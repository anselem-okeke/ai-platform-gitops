# Gateway and Routing

## Purpose

This document describes the platform's Envoy Gateway / Kubernetes Gateway API routing model for exposing internal platform services over HTTP(S).

## GitOps Path

```text
platform/gateway/
├── base/
└── overlays/
    └── dev/
```

Argo Application:

```text
ai-platform-gateway
```

## Gateway Address

Observed development LoadBalancer address:

```text
172.19.255.200
```

## Important Hostnames

```text
auth.ai-platform.local
argocd.ai-platform.local
api.ai-platform.local
```

## Architecture

```text
Client
  |
  | HTTPS
  v
Envoy Gateway
  |
  v
Gateway API listener
  |
  v
HTTPRoute
  |
  v
Kubernetes Service
  |
  v
Application Pod
```

## Argo CD Exposure

Argo CD uses:

```text
https://argocd.ai-platform.local
```

The backing service remains:

```text
argocd/argocd-server
Type: ClusterIP
```

This allows the Gateway to be the controlled external ingress point.

## API Exposure

The AI Platform API is reached through:

```text
https://api.ai-platform.local
```

Routing sends requests to the API Service in:

```text
ai-platform
```

## Identity Endpoint

Keycloak is reached through:

```text
https://auth.ai-platform.local
```

This endpoint participates in browser OIDC flows.

## TLS

The platform design uses Vault PKI for certificate issuance.

Conceptually:

```text
Vault PKI
   |
   v
certificate
   |
   v
TLS Secret
   |
   v
Gateway listener
   |
   v
HTTPS
```

The private-key lifecycle must remain outside plaintext Git.

## Validation

List Gateways and routes:

```bash
kubectl get gateway,httproute -A
```

Describe:

```bash
kubectl describe gateway <gateway-name> -n <namespace>
kubectl describe httproute <route-name> -n <namespace>
```

Inspect listener/parent attachment status and route conditions.

Check endpoint:

```bash
curl -I https://api.ai-platform.local
```

Check certificate:

```bash
openssl s_client \
  -connect api.ai-platform.local:443 \
  -servername api.ai-platform.local \
  </dev/null
```

## Troubleshooting

### HTTPRoute not attached

Check:

- `parentRefs`
- listener hostname
- allowed routes
- namespace permissions
- Gateway status conditions

### 404 from Gateway

Check host/path matching.

### Backend unavailable

Check:

```bash
kubectl get svc,endpoints,endpointslices -A
```

### TLS failure

Check:

- certificate SAN
- Secret namespace
- listener certificate reference
- trust chain
- DNS resolution

## Official References

- Kubernetes Gateway API: https://gateway-api.sigs.k8s.io/
- HTTP routing guide: https://gateway-api.sigs.k8s.io/guides/http-routing/
- TLS guide: https://gateway-api.sigs.k8s.io/guides/tls/
- Envoy Gateway documentation: https://gateway.envoyproxy.io/
- Envoy Gateway tasks: https://gateway.envoyproxy.io/latest/tasks/

## Related Documentation

- [007-argocd-secure-access.md](007-argocd-secure-access.md)
- [015-api-gitops-deployment.md](015-api-gitops-deployment.md)
