---
title: Deploy with GitOps
description: Compose reusable CobaltCore Kustomize bases with environment configuration and reconcile them with Flux.
---

# Deploy with GitOps

The bundles under `deploy/gitops/bases` expose operator releases and shared
infrastructure independently of a target cluster. A deployment repository pins
a reviewed CobaltCore commit under `bases/`, owns environment settings under
`overlays/`, and declares reconciliation order under `clusters/`.

```text
cobaltcore-deployment/
  bases/operators/kustomization.yaml
  overlays/production/operators/kustomization.yaml
  overlays/production/controlplane/
  clusters/production/kustomization.yaml
  bootstrap/flux/
```

For example, the operators base can reference the fork directly:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - https://github.com/YOUR-ORG/cobaltcore//deploy/gitops/bases/operators?ref=FULL_COMMIT_SHA
```

The environment overlay selects chart versions, operator image digests, replicas
and resource requests. The existing Helm charts remain the source of their CRDs,
RBAC, webhooks and Deployments.

## Environment responsibilities

Create ControlPlane instances in the deployment repository. Select their sizing,
service configuration, public endpoints, gateway references and secret identities
there. The reusable bundles do not create an instance or install a gateway.

Choose the Gateway implementation and its CRDs, DNS names, certificate issuers,
load-balancer configuration and storage policy for the target cluster. OpenBao's
GitOps base uses the default StorageClass unless the environment overrides it.
Configure the TLS base's issuers and the shared ClusterSecretStore's namespace
allow-list and authentication to match the environment's trust policy.

The environment also owns OpenBao initialization, key custody, unsealing and
database tenant onboarding. Existing bootstrap scripts and policies can be
consumed as generated ConfigMaps from `deploy/openbao/bootstrap` and
`deploy/openbao/policies`; the fork does not schedule them as Jobs or CronJobs.

## Reconciliation order

Bootstrap the Flux runtime, then a GitRepository and root Kustomization for the
environment's cluster directory. Use Flux `dependsOn` and health checks to order:

1. `operators`: wait for operator releases, including the K-ORC and RabbitMQ
   Kustomizations.
2. `tls`, then `openbao`: create certificates before the server mounts them.
3. Environment-owned OpenBao bootstrap, then `secrets`: configure authentication
   and policies before waiting for the ClusterSecretStore.
4. `controlplane-operator`: install after all `operators` resources are Ready.
5. Environment-owned ControlPlane and networking resources: apply the instance
   before waiting for aggregate ControlPlane readiness.
6. Environment-owned database onboarding: wait for the projected database,
   configure its credential engine, then wait for the ControlPlane to become Ready.

An uninitialized OpenBao server cannot report Ready. If a separate bootstrap
stage requires its pod first, set `install.disableWait` and `upgrade.disableWait`
in the environment's OpenBao overlay and enforce readiness in that stage.
Likewise, waiting for aggregate ControlPlane readiness before database onboarding
can block the onboarding that its dynamic credentials require.

Choose pruning and teardown policies explicitly for stateful resources. For the
base contract and validation command, read `deploy/gitops/README.md`. For controller
behavior, see the [Flux Kustomization documentation](https://fluxcd.io/flux/components/kustomize/kustomizations/).
