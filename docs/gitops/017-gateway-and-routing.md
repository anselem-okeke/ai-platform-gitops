# Gateway and Routing

## Purpose

This document records how Envoy Gateway and Kubernetes Gateway API expose platform services over HTTP(S).

## GitOps Path

```text
platform/gateway/
├── base/
└── overlays/dev/
```

Argo Application:

```text
ai-platform-gateway
```

## Gateway Address

Observed development LoadBalancer:

```text
172.19.255.200
```

## Hostnames

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
Gateway listener
  |
  v
HTTPRoute
  |
  v
Kubernetes Service
  |
  v
Pod
```

## TLS Model

Vault PKI is the platform PKI foundation.

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
Gateway HTTPS listener
```

Private-key material must not be committed to Git.

## Render Gateway State

```bash
cd /mnt/data/ai-platform-gitops

kubectl kustomize \
  platform/gateway/overlays/dev \
  >/tmp/gateway.yaml
```

## Server Validation

```bash
kubectl apply \
  --dry-run=server \
  -f /tmp/gateway.yaml
```

## Argo Validation

```bash
argocd app get \
  ai-platform-gateway \
  --refresh
```

Expected:

```text
Synced
Healthy
```

## Live Gateway Resources

```bash
kubectl get gateway,httproute -A
```

Describe Gateway:

```bash
kubectl describe gateway \
  <gateway-name> \
  -n <gateway-namespace>
```

Describe route:

```bash
kubectl describe httproute \
  <route-name> \
  -n <route-namespace>
```

Check conditions:

```text
Accepted
ResolvedRefs
Programmed
```

as applicable to the resource/controller.

## API Endpoint Validation

```bash
curl -I \
  https://api.ai-platform.local
```

## Argo Endpoint Validation

```bash
curl -I \
  https://argocd.ai-platform.local
```

## Keycloak Endpoint Validation

```bash
curl -I \
  https://auth.ai-platform.local
```

## TLS Validation

API:

```bash
openssl s_client \
  -connect api.ai-platform.local:443 \
  -servername api.ai-platform.local \
  </dev/null
```

Repeat for Argo/Keycloak as needed.

## Backend Validation

List Services:

```bash
kubectl get svc -A
```

EndpointSlices:

```bash
kubectl get endpointslice -A
```

If Gateway returns 503/502, confirm backend Service selectors and endpoints.

## Troubleshooting

### Route not attached

Check:

- parentRefs
- listener hostname
- namespace route permissions
- route status conditions

### 404

Check:

- Host header
- route hostname
- path matches

### TLS error

Check:

- SAN
- Secret ref
- certificate namespace/reference permissions
- expiry
- trust chain

### Backend unavailable

Check:

```bash
kubectl get svc,endpointslice -n <namespace>
kubectl get pods -n <namespace>
```

## Official References

- Gateway API: https://gateway-api.sigs.k8s.io/
- HTTP routing: https://gateway-api.sigs.k8s.io/guides/http-routing/
- TLS: https://gateway-api.sigs.k8s.io/guides/tls/
- Envoy Gateway: https://gateway.envoyproxy.io/
