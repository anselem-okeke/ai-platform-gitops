# AI Platform GitOps

> The application reconciliation layer is implemented separately in the **[AI Platform Operator](https://github.com/anselem-okeke/ai-platform-operator)** repository.

GitOps repository for bootstrapping, securing, and operating the Kubernetes infrastructure behind the AI Platform.

This repository manages the **platform layer**: continuous delivery, identity, ingress, TLS, platform namespaces, and supporting services. Application lifecycle and `ModelService` reconciliation live separately in the AI Platform Operator repository.

---

## Overview

The platform is managed declaratively through Git and reconciled into Kubernetes by Argo CD.

The main infrastructure flow is:

```text
Platform Engineer
      │
      ▼
Git Repository
      │
      ▼
Argo CD
      │
      ├── Keycloak
      ├── Envoy Gateway
      ├── cert-manager
      ├── Vault PKI integration
      └── AI Platform components
```

The design keeps two responsibilities separate:

- **GitOps repository** — builds and manages the platform itself.
- **Operator repository** — manages model-serving workloads running on the platform.

---

## Architecture

![architecture](/img/ai-argocd-architecture.png)

```text
                         PLATFORM ENGINEER
                                │
                                │ git push
                                ▼
                         Git Repository
                                │
                                │ desired platform state
                                ▼
                           Argo CD
                                │
                 sync / health / drift correction
                                │
        ┌───────────────────────┼────────────────────────┐
        │                       │                        │
        ▼                       ▼                        ▼
    Keycloak              Envoy Gateway             cert-manager
 OIDC / Groups /          Gateway API /                  │
      Roles               HTTPRoutes                     │
        │                                                ▼
        │                                            Vault PKI
        │                                                │
        └───────────────────────┬────────────────────────┘
                                │
                                ▼
                    AI PLATFORM COMPONENTS
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
                REST API                Go Operator
```

### Runtime trust flow

```text
Platform User
     │
     │ HTTPS
     ▼
Envoy Gateway
     │
     ▼
Keycloak / OIDC
     │
     ▼
Authenticated platform request
```

### TLS flow

```text
Vault PKI
    │
    ▼
cert-manager
    │
    ▼
Kubernetes TLS Secret
    │
    ▼
Envoy Gateway HTTPS listener
```

---

## Repository Responsibilities

This repository owns the Kubernetes platform foundation.

### Continuous Delivery

- Argo CD
- `AppProject` definitions
- bootstrap configuration
- Git-driven reconciliation
- application synchronization
- drift detection and correction

### Identity and Access

- Keycloak
- OIDC integration
- platform groups and roles
- Argo CD authentication
- platform authentication configuration

Current platform groups include:

```text
platform-viewer
platform-deployer
platform-admin
```

### Network Entry Point

- Envoy Gateway
- Kubernetes Gateway API
- `Gateway`
- `HTTPRoute`
- HTTPS listeners
- platform routing

### Certificates and PKI

- cert-manager
- Vault Kubernetes authentication
- Vault PKI
- Kubernetes TLS Secrets
- certificate lifecycle automation

### Platform Services

The repository provides the deployment foundation for platform components such as:

```text
AI Platform REST API
AI Platform Operator
Identity services
Gateway services
Certificate services
Observability components
```

---

## GitOps Model

Git is the source of truth for platform configuration.

```text
Desired state in Git
        │
        ▼
     Argo CD
        │
        ▼
 Kubernetes API
        │
        ▼
 Actual cluster state
```

When the live cluster differs from the desired state stored in Git, Argo CD detects the difference and can reconcile the cluster back toward the declared state.

This provides a separate reconciliation layer from the AI Platform Operator:

```text
Platform infrastructure:
Git
→ Argo CD
→ Kubernetes platform components

Model workloads:
ModelService
→ Go Operator
→ serving resources
```

---

## Platform Components

| Area | Technology |
|---|---|
| GitOps | Argo CD |
| Kubernetes | Kubernetes |
| Identity | Keycloak |
| Authentication | OpenID Connect / OAuth 2.0 |
| Gateway | Envoy Gateway |
| Routing | Kubernetes Gateway API |
| Certificates | cert-manager |
| PKI | HashiCorp Vault |
| Authorization | OIDC claims, platform roles, policy enforcement |
| Operator | Go / controller-runtime |
| Platform API | Go |
| Observability | Prometheus / Grafana |
| Model serving | Kubernetes-native serving stack |

---

## Argo CD

Argo CD continuously reconciles the platform configuration stored in Git.

The platform currently uses:

```text
Namespace:
  argocd

AppProject:
  ai-platform
```

Argo CD is intentionally kept behind the platform access layer rather than exposed as an unrestricted public Kubernetes `LoadBalancer`.

### Access model

```text
User
  │
  ▼
HTTPS
  │
  ▼
Envoy Gateway
  │
  ▼
Argo CD
  │
  ▼
Keycloak OIDC
```

Authentication is delegated to Keycloak and authorization is mapped from identity claims into Argo CD permissions.

---

## Keycloak

Keycloak provides the platform identity layer.

```text
Namespace:
  keycloak

Realm:
  ai-platform
```

Platform roles/groups:

```text
platform-viewer
platform-deployer
platform-admin
```

The platform supports OIDC-based authentication for human users and platform clients.

### Argo CD OIDC

```text
Argo CD
   │
   ▼
Keycloak
   │
   ▼
OIDC token
   │
   ▼
group claims
   │
   ▼
Argo CD RBAC
```

The design removes the need to rely permanently on the bootstrap Argo CD administrator account.

---

## Envoy Gateway

Envoy Gateway is the platform network entry point.

It provides:

- HTTPS ingress
- Gateway API integration
- `HTTPRoute` routing
- TLS termination
- integration with authentication and authorization policy
- routing to internal platform services

Example conceptual flow:

```text
Client
  │
  │ HTTPS
  ▼
Envoy Gateway
  │
  ├── platform API
  ├── Argo CD
  └── other platform services
```

---

## Vault and cert-manager

TLS certificate issuance is automated through cert-manager and Vault PKI.

```text
cert-manager
     │
     │ Kubernetes authentication
     ▼
   Vault
     │
     │ signed certificate
     ▼
 Certificate
     │
     ▼
 TLS Secret
     │
     ▼
Envoy Gateway
```

The design avoids storing long-lived static Vault tokens in Kubernetes.

---

## Security Principles

The platform is designed around several security boundaries.

### No unrestricted public Argo CD service

Argo CD remains an internal Kubernetes service and is accessed through the platform gateway.

### OIDC-based identity

Human authentication is delegated to Keycloak rather than creating separate platform-local identities for each service.

### Short-lived credentials

OAuth/OIDC tokens and Kubernetes-native authentication mechanisms are preferred over static credentials.

### Automated TLS

Certificates are issued and renewed through cert-manager and Vault PKI.

### Least privilege

Platform components receive only the Kubernetes and application permissions required for their responsibility.

### Clear separation of responsibilities

```text
Argo CD
  manages platform configuration

Keycloak
  manages identity

Envoy Gateway
  manages network entry

Vault
  manages PKI

cert-manager
  manages certificate lifecycle

AI Platform Operator
  manages ModelService workloads
```

---

## Repository Layout

A typical layout for this repository is:

```text
ai-platform-gitops/
├── argocd/
│   ├── bootstrap/
│   ├── projects/
│   └── applications/
│
├── infrastructure/
│   ├── keycloak/
│   ├── envoy-gateway/
│   ├── cert-manager/
│   └── vault/
│
├── platform/
│   ├── api/
│   └── operator/
│
├── environments/
│   ├── local/
│   ├── staging/
│   └── production/
│
└── README.md
```

> The exact directory structure may evolve as the platform grows. Git should remain the authoritative source of desired platform state.

---

## Bootstrap Flow

A clean bootstrap sequence is:

```text
1. Kubernetes cluster
        ↓
2. Argo CD
        ↓
3. AppProject / bootstrap applications
        ↓
4. Keycloak
        ↓
5. Envoy Gateway
        ↓
6. Vault + cert-manager integration
        ↓
7. AI Platform services
        ↓
8. Observability and additional platform capabilities
```

### 1. Verify cluster access

```bash
kubectl config current-context
kubectl get nodes
```

### 2. Verify Argo CD

```bash
kubectl get pods -n argocd
kubectl get appproject -n argocd
kubectl get applications -n argocd
```

### 3. Verify Keycloak

```bash
kubectl get pods -n keycloak
```

### 4. Verify Gateway resources

```bash
kubectl get gateway -A
kubectl get httproute -A
```

### 5. Verify certificate resources

```bash
kubectl get certificate -A
kubectl get certificaterequest -A
kubectl get secret -A
```

---

## Validation

Useful platform validation includes:

```text
Argo CD:
  applications synchronized
  applications healthy
  expected AppProject exists

Identity:
  Keycloak reachable
  OIDC login succeeds
  group claims are present
  roles map correctly

Gateway:
  HTTP redirects to HTTPS
  expected hostnames resolve
  routes are accepted

TLS:
  certificates are Ready
  expected hostname is present
  trusted certificate chain is served

Authorization:
  viewer permissions enforced
  deployer permissions enforced
  admin permissions enforced
```

---

## Relationship to the AI Platform Operator

This repository does **not** implement the `ModelService` controller.

The operator repository owns application-level reconciliation:

```text
ModelService
      │
      ▼
Go Operator
      │
      ├── Deployment / serving workload
      ├── Service
      ├── ServiceAccount
      ├── storage
      ├── policies
      └── routes
```

This GitOps repository owns the platform those workloads run on:

```text
Git
 │
 ▼
Argo CD
 │
 ├── Identity
 ├── Gateway
 ├── TLS / PKI
 ├── platform services
 └── shared infrastructure
```

Together they provide two complementary control loops:

```text
GitOps reconciliation
Git → Argo CD → Platform

Workload reconciliation
ModelService → Go Operator → Model workload
```

---

## Design Goal

The goal is not to hide Kubernetes completely.

The goal is to give each user a stable interface at the correct level of abstraction while keeping infrastructure policy, security, identity, routing, and lifecycle management under platform control.

For a platform engineer:

```text
declare platform state in Git
→ Argo CD reconciles it
```

For a model user:

```text
request model deployment
→ platform creates ModelService
→ operator reconciles the workload
```

---

## Project Status

The platform is under active development.

Current work includes:

- Kubernetes-native GitOps bootstrap
- Argo CD platform management
- Keycloak OIDC integration
- role/group-based access
- Envoy Gateway exposure
- Vault-backed certificate issuance
- cert-manager certificate lifecycle
- AI Platform Operator integration
- platform REST API integration
- model-serving infrastructure
- observability

The repository will evolve as additional platform capabilities are implemented.

---

## Related Repository

The application reconciliation layer is implemented separately in the **AI Platform Operator** repository.

That project defines the `ModelService` custom resource and the Go reconciliation loop responsible for translating desired model state into Kubernetes resources.

---

## License

See the repository [LICENSE](LICENSE) for usage and distribution terms.
