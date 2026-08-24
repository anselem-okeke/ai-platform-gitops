# Policy Controller Observability

## Purpose

This document is the **reproducible observability guide** for Sigstore Policy Controller in the AI Platform.

The objective is to make admission-control health visible before it becomes a deployment outage.

The observability chain is:

```text
Policy Controller
      |
      +--> metrics service
      |
      v
ServiceMonitor
      |
      v
Prometheus
      |
      +--> target health
      +--> reconciliation metrics
      +--> webhook certificate metrics
      |
      v
PrometheusRule
      |
      v
alerts
```

This document explains how to:

```text
expose Policy Controller metrics
scrape them with Prometheus
validate the scrape target
query reconciliation health
observe webhook certificate failures
integrate ServiceMonitor and PrometheusRule through GitOps
troubleshoot missing metrics
verify Argo reconciliation
```

The current platform has empirically validated:

```text
metrics endpoint reachable
Prometheus target up = 1
policy_controller_reconcile_count present
ServiceMonitor selection works
PrometheusRule selector/label works
```

The platform has **not** empirically forced every alert into a firing state.

---

# 1. Validated Monitoring Stack

Current monitoring stack:

```text
kube-prometheus-stack
```

Prometheus version:

```text
v3.13.2-distroless
```

Namespace:

```text
monitoring
```

The platform's monitoring child Application is GitOps-managed.

---

# 2. Policy Controller Metrics Service

Validated metrics service:

```text
policy-controller-webhook-metrics
```

Namespace:

```text
cosign-system
```

Port:

```text
9090
```

This service exposes Policy Controller metrics for Prometheus.

---

# 3. Verify the Metrics Service

```bash
kubectl get svc \
  policy-controller-webhook-metrics \
  -n cosign-system
```

Expected:

```text
service exists
ClusterIP assigned
port 9090 exposed
```

Inspect:

```bash
kubectl describe svc \
  policy-controller-webhook-metrics \
  -n cosign-system
```

---

# 4. Verify Service Labels

This is important because the ServiceMonitor selects the service by labels.

Run:

```bash
kubectl get svc \
  policy-controller-webhook-metrics \
  -n cosign-system \
  --show-labels
```

Do not guess the selector.

The ServiceMonitor must match the actual labels on the service.

---

# 5. Verify Metrics Endpoint Directly

Port-forward:

```bash
kubectl port-forward \
  -n cosign-system \
  svc/policy-controller-webhook-metrics \
  9090:9090
```

Then in another terminal:

```bash
curl -s \
  http://127.0.0.1:9090/metrics \
  | head -n 60
```

Expected:

```text
Prometheus text exposition
```

---

# 6. Filter Policy Controller Metrics

```bash
curl -s \
  http://127.0.0.1:9090/metrics \
  | grep '^policy_controller_' \
  | head -n 80
```

Expected metric families include:

```text
policy_controller_client_latency
policy_controller_client_results
policy_controller_reconcile_count
policy_controller_reconcile_latency
policy_controller_request_count
policy_controller_request_latencies
```

Exact metrics may vary across versions.

---

# 7. Important Reconciliation Metric

Validated metric:

```text
policy_controller_reconcile_count
```

Observed labels include:

```text
namespace_name
reconciler
success
```

This metric is especially useful because it shows controller reconciliation success/failure.

---

# 8. Inspect Reconciliation Metrics

```bash
curl -s \
  http://127.0.0.1:9090/metrics \
  | grep '^policy_controller_reconcile_count'
```

Example shape:

```text
policy_controller_reconcile_count{namespace_name="",reconciler="WebhookCertificates",success="true"} 12
```

Do not rely on an example value.

The label set is what matters.

---

# 9. Why Counter Metrics Need `increase()`

A counter like:

```text
policy_controller_reconcile_count
```

only goes upward.

Therefore this is usually not useful:

```promql
policy_controller_reconcile_count{success="false"} > 5
```

because historical failures can keep the counter permanently above the threshold.

Use:

```promql
increase(...[10m])
```

to measure recent failures.

---

# 10. GitOps ServiceMonitor Location

Validated file:

```text
platform/monitoring/base/policy-controller-servicemonitor.yaml
```

This resource is part of the GitOps monitoring component.

---

# 11. Representative ServiceMonitor

A representative manifest shape is:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: policy-controller
  namespace: monitoring
spec:
  namespaceSelector:
    matchNames:
      - cosign-system

  selector:
    matchLabels:
      app.kubernetes.io/name: policy-controller

  endpoints:
    - port: metrics
      interval: 30s
      scrapeTimeout: 10s
```

The exact `matchLabels` and port name must match the live service.

---

# 12. Add the Prometheus Selection Label

The kube-prometheus-stack installation may select ServiceMonitors based on labels.

If the current monitoring configuration requires:

```yaml
metadata:
  labels:
    release: kps
```

include it.

Representative:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: policy-controller
  namespace: monitoring
  labels:
    release: kps
```

Verify the actual selector before relying on this.

---

# 13. Prometheus ServiceMonitor Selectors

Validated configuration accepts ServiceMonitors broadly:

```yaml
serviceMonitorSelector: {}
serviceMonitorNamespaceSelector: {}
```

This allows Prometheus to discover the ServiceMonitor in:

```text
monitoring
```

which selects a service in:

```text
cosign-system
```

---

# 14. Why `namespaceSelector` Is Required

The ServiceMonitor itself lives in:

```text
monitoring
```

but the metrics service lives in:

```text
cosign-system
```

Therefore the ServiceMonitor must explicitly select the target namespace.

Representative:

```yaml
namespaceSelector:
  matchNames:
    - cosign-system
```

---

# 15. Verify the ServiceMonitor Exists

```bash
kubectl get servicemonitor \
  -n monitoring
```

Expected:

```text
policy-controller
```

Inspect:

```bash
kubectl get servicemonitor \
  policy-controller \
  -n monitoring \
  -o yaml
```

---

# 16. Verify ServiceMonitor Selector Matches Service

Compare:

```bash
kubectl get svc \
  policy-controller-webhook-metrics \
  -n cosign-system \
  --show-labels
```

with:

```bash
kubectl get servicemonitor \
  policy-controller \
  -n monitoring \
  -o jsonpath='{.spec.selector.matchLabels}{"\n"}'
```

They must match.

---

# 17. Verify Endpoint Port Name

Inspect Service:

```bash
kubectl get svc \
  policy-controller-webhook-metrics \
  -n cosign-system \
  -o yaml
```

Look at:

```yaml
spec:
  ports:
    - name: metrics
      port: 9090
```

Then ServiceMonitor should use:

```yaml
endpoints:
  - port: metrics
```

The port name, not only number, is important to ServiceMonitor matching.

---

# 18. Render Monitoring GitOps Manifests

```bash
cd /mnt/data/ai-platform-gitops

kubectl kustomize \
  platform/monitoring/overlays/dev \
  >/tmp/monitoring.yaml
```

Expected:

```text
successful render
```

---

# 19. Verify ServiceMonitor Is in Rendered Output

```bash
grep -n \
  'kind: ServiceMonitor' \
  /tmp/monitoring.yaml
```

Then:

```bash
grep -n \
  'policy-controller' \
  /tmp/monitoring.yaml
```

---

# 20. Validate with kubeconform

```bash
kubeconform \
  -strict \
  -summary \
  -ignore-missing-schemas \
  /tmp/monitoring.yaml
```

CRD schemas for Prometheus Operator resources may be absent in default kubeconform catalogs, which is why the validated CI uses:

```text
-ignore-missing-schemas
```

---

# 21. Server-Side Dry Run

If the CRDs are installed:

```bash
kubectl apply \
  --dry-run=server \
  -f /tmp/monitoring.yaml
```

This validates against the live Kubernetes API server.

---

# 22. Verify Monitoring Argo Application

```bash
argocd app get \
  ai-platform-monitoring \
  --refresh
```

Use the actual Application name from the GitOps repository if different.

Expected:

```text
Synced
Healthy
```

---

# 23. Prometheus Target Validation

The most important basic query is:

```promql
up{
  namespace="cosign-system",
  service="policy-controller-webhook-metrics"
}
```

Validated result:

```text
1
```

This proves Prometheus is successfully scraping the target.

---

# 24. Why `up == 1` Matters

`up` is generated by Prometheus itself.

Meaning:

```text
1
  -> scrape succeeded

0
  -> scrape failed
```

This is more reliable than merely checking whether the ServiceMonitor resource exists.

---

# 25. Query with Prometheus UI

Port-forward Prometheus if needed.

First discover:

```bash
kubectl get svc \
  -n monitoring
```

Then port-forward the Prometheus service selected by the current kube-prometheus-stack deployment.

Example concept:

```bash
kubectl port-forward \
  -n monitoring \
  svc/<PROMETHEUS_SERVICE> \
  9091:9090
```

Open/query Prometheus at the forwarded endpoint.

Use the actual service name from the cluster.

---

# 26. Query Using Prometheus HTTP API

Representative:

```bash
curl -sG \
  'http://127.0.0.1:9091/api/v1/query' \
  --data-urlencode \
  'query=up{namespace="cosign-system",service="policy-controller-webhook-metrics"}'
```

Expected result value:

```text
1
```

---

# 27. Verify Reconcile Metrics Through Prometheus

Query:

```promql
policy_controller_reconcile_count
```

Expected:

```text
non-empty series
```

Validated empirically.

---

# 28. Query Recent Reconcile Failures

```promql
sum(
  increase(
    policy_controller_reconcile_count{
      success="false"
    }[10m]
  )
)
```

This measures recent failures across reconcilers.

---

# 29. Query by Reconciler

```promql
sum by (reconciler) (
  increase(
    policy_controller_reconcile_count{
      success="false"
    }[10m]
  )
)
```

This shows which controller loop is failing.

---

# 30. Webhook Certificate Reconciler

Validated relevant reconciler:

```text
WebhookCertificates
```

Query:

```promql
increase(
  policy_controller_reconcile_count{
    reconciler="WebhookCertificates",
    success="false"
  }[10m]
)
```

---

# 31. Why Webhook Certificate Health Matters

Admission webhooks depend on TLS.

If webhook certificates fail:

```text
API server
    |
    X TLS validation
    |
Policy Controller webhook
```

admission requests may fail or become unavailable.

Therefore certificate reconciliation is security-critical availability.

---

# 32. GitOps PrometheusRule Location

Validated file:

```text
platform/monitoring/base/policy-controller-prometheusrule.yaml
```

---

# 33. PrometheusRule Selection Label

Validated label:

```yaml
metadata:
  labels:
    release: kps
```

This was required so the kube-prometheus-stack Prometheus instance selected the rule.

A previous selector/label mismatch was corrected.

---

# 34. Representative PrometheusRule

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: policy-controller
  namespace: monitoring
  labels:
    release: kps
spec:
  groups:
    - name: policy-controller.rules
      rules:
        # alert rules
```

---

# 35. Target Down Alert

Validated expression:

```promql
up{
  namespace="cosign-system",
  service="policy-controller-webhook-metrics"
} == 0
```

Validated duration:

```text
5m
```

Validated severity:

```text
critical
```

Representative snippet:

```yaml
- alert: PolicyControllerTargetDown
  expr: |
    up{
      namespace="cosign-system",
      service="policy-controller-webhook-metrics"
    } == 0
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: Policy Controller metrics target is down
```

---

# 36. Reconcile Failures Alert

Validated expression:

```promql
sum(
  increase(
    policy_controller_reconcile_count{
      success="false"
    }[10m]
  )
) > 5
```

Validated duration:

```text
5m
```

Validated severity:

```text
warning
```

Representative:

```yaml
- alert: PolicyControllerReconcileFailures
  expr: |
    sum(
      increase(
        policy_controller_reconcile_count{
          success="false"
        }[10m]
      )
    ) > 5
  for: 5m
  labels:
    severity: warning
```

---

# 37. Webhook Certificate Failure Alert

Validated expression:

```promql
increase(
  policy_controller_reconcile_count{
    reconciler="WebhookCertificates",
    success="false"
  }[10m]
) > 0
```

Validated duration:

```text
5m
```

Validated severity:

```text
critical
```

Representative:

```yaml
- alert: PolicyControllerWebhookCertificateFailures
  expr: |
    increase(
      policy_controller_reconcile_count{
        reconciler="WebhookCertificates",
        success="false"
      }[10m]
    ) > 0
  for: 5m
  labels:
    severity: critical
```

---

# 38. Why Target Down Is Critical

If Prometheus cannot scrape the target, possibilities include:

```text
Policy Controller down
metrics service broken
network path broken
selector mismatch
TLS/service failure
```

More importantly:

```text
you lose visibility into admission health
```

So the monitoring loss itself is critical.

---

# 39. Why Reconcile Failures Are Warning

A small transient number of reconciliation failures may self-recover.

The current threshold is:

```text
> 5 recent failures in 10m
for 5m
```

This reduces alert noise while still surfacing sustained problems.

---

# 40. Why Certificate Failures Are Critical

Certificate reconciliation failure can break the admission webhook itself.

This can directly block:

```text
Pod creation
Deployment rollouts
GitOps reconciliation
```

Therefore severity is:

```text
critical
```

---

# 41. Validate PrometheusRule Exists

```bash
kubectl get prometheusrule \
  -n monitoring
```

Expected:

```text
policy-controller
```

Inspect:

```bash
kubectl get prometheusrule \
  policy-controller \
  -n monitoring \
  -o yaml
```

---

# 42. Verify Rule Selection

Check Prometheus resource:

```bash
kubectl get prometheus \
  -n monitoring \
  -o yaml
```

Inspect:

```text
spec.ruleSelector
spec.ruleNamespaceSelector
```

Ensure the PrometheusRule labels and namespace match the selectors.

---

# 43. Common PrometheusRule Failure

Symptom:

```text
PrometheusRule exists
but rule does not appear in Prometheus
```

Likely cause:

```text
label selector mismatch
```

The validated fix included:

```yaml
metadata:
  labels:
    release: kps
```

---

# 44. Validate Rule Through Prometheus

Query the Prometheus rules API or UI.

Look for:

```text
PolicyControllerTargetDown
PolicyControllerReconcileFailures
PolicyControllerWebhookCertificateFailures
```

Do not claim each rule has fired unless intentionally tested.

---

# 45. Rule Syntax Validation

Prometheus Operator validates much of the structure.

For deeper syntax checks, use tools available in the monitoring stack or inspect Prometheus logs.

A malformed expression should be caught before relying on the alert.

---

# 46. Monitoring Kustomization Snippet

Representative:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - policy-controller-servicemonitor.yaml
  - policy-controller-prometheusrule.yaml
```

This ensures both resources are GitOps-managed.

---

# 47. Why Monitoring Is GitOps-Managed

Monitoring configuration is part of platform security.

Manual creation would cause:

```text
undocumented drift
non-reproducible alerting
missing recovery after rebuild
```

Therefore:

```text
ServiceMonitor
PrometheusRule
```

belong in Git.

---

# 48. Argo Drift

If someone manually edits the ServiceMonitor:

```text
live state
    !=
Git state
```

Argo should detect and self-heal the difference.

Do not maintain monitoring changes manually.

---

# 49. Troubleshooting: Metrics Service Missing

Check:

```bash
helm list -A \
  | grep policy-controller
```

Then:

```bash
kubectl get svc \
  -n cosign-system
```

Possible causes:

```text
Policy Controller not installed
chart values changed
upgrade changed service naming
release unhealthy
```

---

# 50. Troubleshooting: Port 9090 Not Exposed

Inspect:

```bash
kubectl get svc \
  policy-controller-webhook-metrics \
  -n cosign-system \
  -o yaml
```

If the port changed after upgrade, update the ServiceMonitor only after validating upstream chart behavior.

Do not hardcode an obsolete port blindly.

---

# 51. Troubleshooting: Port-Forward Works but Prometheus Target Is Missing

This means:

```text
metrics endpoint works
but Prometheus discovery is broken
```

Check:

```text
ServiceMonitor exists
Prometheus selects ServiceMonitor
namespaceSelector correct
service selector labels match
endpoint port name correct
```

---

# 52. Troubleshooting: ServiceMonitor Exists but No Target

Compare service labels:

```bash
kubectl get svc \
  policy-controller-webhook-metrics \
  -n cosign-system \
  --show-labels
```

against:

```bash
kubectl get servicemonitor \
  policy-controller \
  -n monitoring \
  -o yaml
```

Most common cause:

```text
selector mismatch
```

---

# 53. Troubleshooting: Target Exists but `up == 0`

Inspect target endpoint and error in Prometheus Targets UI.

Possible causes:

```text
connection refused
service endpoints empty
Pod not Ready
wrong port
network policy
timeout
```

Check:

```bash
kubectl get endpoints \
  policy-controller-webhook-metrics \
  -n cosign-system
```

---

# 54. Troubleshooting: Service Has No Endpoints

Inspect Pod labels:

```bash
kubectl get pods \
  -n cosign-system \
  --show-labels
```

Compare with Service selector:

```bash
kubectl get svc \
  policy-controller-webhook-metrics \
  -n cosign-system \
  -o jsonpath='{.spec.selector}{"\n"}'
```

---

# 55. Troubleshooting: Reconcile Metric Missing

If:

```promql
policy_controller_reconcile_count
```

returns no series:

```text
metrics version changed
scrape target wrong
metric renamed
controller has not emitted series yet
```

Check raw `/metrics` output first.

---

# 56. Troubleshooting: Rule Does Not Load

Inspect Prometheus Operator logs:

```bash
kubectl get pods \
  -n monitoring \
  | grep operator
```

Then:

```bash
kubectl logs \
  -n monitoring \
  <PROMETHEUS_OPERATOR_POD> \
  --tail=300
```

Look for PrometheusRule validation errors.

---

# 57. Troubleshooting: PrometheusRule Selected but Alert Never Fires

Check:

```text
expression returns data
threshold reachable
for duration
label filters match real metric labels
```

Evaluate the raw expression without threshold first.

---

# 58. Query Raw Failure Increase

```promql
sum(
  increase(
    policy_controller_reconcile_count{
      success="false"
    }[10m]
  )
)
```

If result is:

```text
0
```

then the alert should not fire.

That is healthy behavior.

---

# 59. Test Target Down Safely

Do not intentionally break admission infrastructure in a shared environment just to fire the alert.

Safer options:

```text
use a disposable cluster
use a temporary monitoring-only target
test alert expression offline
```

Current project does not claim target-down alert firing was empirically tested.

---

# 60. Test Reconcile Failure Alert Safely

Likewise, do not deliberately corrupt Policy Controller just to produce failures in a primary environment.

A future dedicated validation environment can exercise controlled failure injection.

---

# 61. Observe During Policy Upgrade

During Policy Controller upgrade, monitor:

```promql
up{
  namespace="cosign-system",
  service="policy-controller-webhook-metrics"
}
```

and:

```promql
sum(
  increase(
    policy_controller_reconcile_count{
      success="false"
    }[10m]
  )
)
```

This provides early evidence of upgrade regressions.

---

# 62. Observe During Trust Policy Update

After changing:

```text
TrustRoot
ClusterImagePolicy
trust-policies chart
```

watch:

```text
Policy Controller reconciliation
admission tests
Prometheus target
```

A trust-policy change can be operational even if the controller Pod remains Ready.

---

# 63. Observe During Certificate Rotation

Watch:

```promql
increase(
  policy_controller_reconcile_count{
    reconciler="WebhookCertificates",
    success="false"
  }[10m]
)
```

Certificate rotation failures deserve immediate investigation.

---

# 64. Argo Monitoring

Argo should report the monitoring child Application:

```text
Synced
Healthy
```

after changes.

Example:

```bash
argocd app get \
  ai-platform-monitoring \
  --refresh
```

---

# 65. Validate No Monitoring Drift

```bash
argocd app diff \
  ai-platform-monitoring
```

Expected:

```text
no unintended diff
```

---

# 66. Monitoring Security Boundary

Observability should not weaken the security system.

Do not expose:

```text
private keys
attestation secrets
tokens
credential values
```

through metrics.

Policy Controller metrics should contain operational metadata only.

---

# 67. RBAC Consideration

Prometheus needs enough access to discover:

```text
ServiceMonitor
Service
Endpoints/EndpointSlice
```

through the kube-prometheus-stack model.

Do not add cluster-admin permissions just to make one scrape target work.

---

# 68. NetworkPolicy Consideration

If NetworkPolicies are introduced around:

```text
cosign-system
monitoring
```

ensure Prometheus can reach the metrics port.

Allow only the necessary path:

```text
Prometheus
  -> policy-controller-webhook-metrics:9090
```

---

# 69. Future Grafana Dashboard

A future dashboard can include:

```text
Policy Controller target status
reconcile successes/failures
failure rate by reconciler
webhook certificate failures
request count
request latency
```

Do not build a dashboard that depends on unverified metric names.

Query the live metric catalog first.

---

# 70. Suggested Dashboard Panels

Useful future panels:

```text
Target Up
Recent Reconcile Failures
Reconcile Failure Rate by Reconciler
Webhook Certificate Failure Count
Admission Request Rate
Admission Latency
```

---

# 71. Latency Metrics

If available:

```text
policy_controller_request_latencies
policy_controller_reconcile_latency
```

can be used to detect performance degradation.

Exact histogram/summary label structure should be inspected before writing PromQL.

---

# 72. Alerting on Latency

Do not invent a latency SLO without evidence.

First establish:

```text
normal baseline
expected admission latency
cluster size
request volume
```

Then define thresholds.

---

# 73. Alert Routing

This document defines PrometheusRule generation, not Alertmanager receiver configuration.

If alert routing is implemented later, document:

```text
receiver
severity routing
notification channel
silence policy
on-call ownership
```

separately.

---

# 74. Operational Validation Matrix

| Check | Expected |
|---|---|
| Metrics service exists | Yes |
| Metrics port | 9090 |
| `/metrics` responds | Yes |
| ServiceMonitor exists | Yes |
| Prometheus target discovered | Yes |
| `up` | 1 |
| `policy_controller_reconcile_count` | Non-empty |
| PrometheusRule exists | Yes |
| Rule label matches selector | Yes |
| Argo monitoring app | Synced/Healthy |

---

# 75. Troubleshooting Matrix

| Symptom | Likely Cause |
|---|---|
| Port-forward fails | Service/pod missing |
| `/metrics` works, target absent | ServiceMonitor discovery issue |
| Target present, `up=0` | endpoint/network/service issue |
| Target `up=1`, metric missing | metric renamed/not emitted |
| Rule resource exists, rule absent | Prometheus selector mismatch |
| Rule loads, never fires | expression/threshold not met |
| Argo OutOfSync | manual drift or Git mismatch |

---

# 76. Rebuild from Zero

```text
[ ] verify Policy Controller installed
[ ] identify metrics service
[ ] verify port 9090
[ ] inspect service labels
[ ] port-forward and test /metrics
[ ] identify stable metric names
[ ] create ServiceMonitor
[ ] select cosign-system
[ ] match exact service labels
[ ] use correct port name
[ ] add required release: kps label if selector requires it
[ ] add ServiceMonitor to monitoring Kustomization
[ ] render monitoring overlay
[ ] validate manifests
[ ] merge GitOps PR
[ ] verify Argo sync
[ ] verify ServiceMonitor exists
[ ] verify Prometheus target
[ ] query up == 1
[ ] query policy_controller_reconcile_count
[ ] create PrometheusRule
[ ] add target-down alert
[ ] add reconcile-failure alert
[ ] add webhook-certificate alert
[ ] add release: kps label to PrometheusRule if required
[ ] verify rules loaded
[ ] document that alert firing is not yet empirically tested
```

---

# 77. Security Review Checklist

```text
[ ] monitoring is GitOps-managed
[ ] metrics target is continuously scraped
[ ] target-down alert exists
[ ] reconcile failures are observable
[ ] webhook certificate failures are observable
[ ] PrometheusRule selected correctly
[ ] monitoring does not expose secrets
[ ] no cluster-admin workaround introduced
[ ] no broad NetworkPolicy exception introduced
```

---

# 78. Known Implementation Facts

Validated project facts:

```text
Monitoring stack:
kube-prometheus-stack

Prometheus:
v3.13.2-distroless

Monitoring namespace:
monitoring

Policy Controller namespace:
cosign-system

Metrics service:
policy-controller-webhook-metrics

Metrics port:
9090

ServiceMonitor:
platform/monitoring/base/policy-controller-servicemonitor.yaml

PrometheusRule:
platform/monitoring/base/policy-controller-prometheusrule.yaml

Prometheus target:
up = 1 validated

Metric:
policy_controller_reconcile_count validated

PrometheusRule selector fix:
release: kps

Alerts defined:
PolicyControllerTargetDown
PolicyControllerReconcileFailures
PolicyControllerWebhookCertificateFailures
```

---

# 79. What Has Not Been Empirically Validated

Do not claim:

```text
all alerts intentionally fired
all Alertmanager routes tested
all latency SLOs defined
all failure-injection scenarios tested
```

These remain future validation work.

---

# 80. What Must Be Verified from the Actual Repository

Before claiming exact manifest parity, inspect:

```text
exact ServiceMonitor selector labels
exact metrics port name
exact PrometheusRule names
exact annotations
exact monitoring Application name
exact Prometheus selectors
exact current metric label set
```

Commands:

```bash
cd /mnt/data/ai-platform-gitops

sed -n '1,240p' \
  platform/monitoring/base/policy-controller-servicemonitor.yaml

sed -n '1,320p' \
  platform/monitoring/base/policy-controller-prometheusrule.yaml
```

Then compare against live cluster resources.

---

# 81. Official References

Prometheus Operator ServiceMonitor:

```text
https://prometheus-operator.dev/docs/api-reference/api/
```

Prometheus querying:

```text
https://prometheus.io/docs/prometheus/latest/querying/basics/
```

Prometheus alerting rules:

```text
https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/
```

Sigstore Policy Controller:

```text
https://docs.sigstore.dev/policy-controller/overview/
```

Argo CD:

```text
https://argo-cd.readthedocs.io/
```

Kustomize:

```text
https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/
```

---

# 82. Related AI Platform Documentation

```text
031-sigstore-policy-controller.md
032-github-attestation-trust.md
033-image-admission-policies.md
034-pod-init-and-ephemeral-container-policy.md
036-policy-controller-alerting.md
039-software-supply-chain-security.md
040-end-to-end-delivery-workflow.md
041-validation-and-security-tests.md
043-troubleshooting-guide.md
044-operations-runbook.md
045-command-reference.md
047-design-decisions.md
