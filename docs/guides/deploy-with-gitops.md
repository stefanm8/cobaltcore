---
title: Deploy with GitOps
description: Compose CobaltCore Kustomize bases in a deployment repository and reconcile them with Flux.
---

# Deploy with GitOps

The reusable bundles under `deploy/gitops/bases` separate installation from
environment configuration. A deployment repository should reference a reviewed
CobaltCore commit under `bases/`, apply cluster settings under `overlays/`, and
declare the reconciliation order under `clusters/`.

```text
cobaltcore-deployment/
  bases/operators/kustomization.yaml
  overlays/minikube/operators/kustomization.yaml
  clusters/minikube/kustomization.yaml
  bootstrap/flux/
```

For example, the operators base can reference the fork directly:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - https://github.com/YOUR-ORG/cobaltcore//deploy/gitops/bases/operators?ref=FULL_COMMIT_SHA
```

An environment overlay references that base and patches chart versions, operator
image digests, replicas and resource requests. The existing operator Helm charts
remain the source of their CRDs, RBAC, webhooks and Deployments.

## Reconciliation order

Bootstrap the Flux runtime once. Then use a GitRepository and Flux
Kustomizations with `dependsOn` and health checks:

1. `gateway-crds` and `operators`: establish the APIs and wait for operator
   releases, including the K-ORC and RabbitMQ Kustomizations.
2. `tls`, then `openbao`: create the certificates before the server mounts them.
3. `dev-bootstrap`, then `secrets`: initialize local OpenBao, configure its
   authentication/policies, seed missing credentials, and wait for ESO.
4. `gateway` and `controlplane-operator`: wait for the local gateway and c5c3.
5. `controlplane`: apply the CR without waiting for aggregate readiness.
6. `database-onboarding`: wait for the projected MariaDB, configure the database
   engine, then wait for the Job and ControlPlane to become Ready.

The c5c3 stage depends on K-ORC readiness through `operators`; its Helm release
does not have to race missing K-ORC APIs. Do not wait for ControlPlane readiness
before database onboarding: dynamic credential provisioning can require that
onboarding to finish first.

## Minikube settings

Start with the Minimal Keystone/Horizon profile, one operator replica, the
`standard` default StorageClass and standalone OpenBao. The local gateway uses
`keystone.127-0-0-1.nip.io` and `horizon.127-0-0-1.nip.io`; set the Keystone
public endpoint to include port 8443 when accessing it with a port-forward.
Keep hypervisor/VM testing and storage extensions as separate overlays.

The local bootstrap Job requires the OpenBao Helm release to use
`install.disableWait: true` and `upgrade.disableWait: true`, because a sealed
server cannot report Ready before initialization. Readiness is enforced by the
next-stage Job instead. The development unseal CronJob handles server restarts.

These Jobs are explicitly for the local `openstack/controlplane` identity and
`shared-services/openbao-0`. They retain init keys and the root token in a
Kubernetes Secret. For production, replace them with the platform's secret
custody, unseal and tenant-onboarding process. Keep pruning disabled on stateful
stages and plan teardown separately.

For the exact base contract and validation command, read `deploy/gitops/README.md`.
For controller behavior, see the [Flux Kustomization documentation](https://fluxcd.io/flux/components/kustomize/kustomizations/).
