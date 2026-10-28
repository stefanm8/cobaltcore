# GitOps deployment bases

These Kustomize bases expose CobaltCore's existing operator releases and shared
infrastructure for reconciliation with Flux. Keep environment configuration in a
separate deployment repository with `bases/`, `overlays/` and `clusters/` directories.

| Base | Prerequisite | Readiness gate |
| --- | --- | --- |
| `operators` | Flux source, Helm and Kustomize controllers | Helm releases and K-ORC/RabbitMQ Kustomizations Ready |
| `tls` | cert-manager from `operators` | Certificates and issuers Ready |
| `openbao` | TLS certificates | OpenBao installed, initialized and unsealed |
| `secrets` | External Secrets Operator and configured OpenBao authentication | ClusterSecretStore Ready |
| `controlplane-operator` | `operators`, including K-ORC | c5c3 Helm release Ready |

Reference a reviewed commit in the deployment repository:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - https://github.com/YOUR-ORG/cobaltcore//deploy/gitops/bases/operators?ref=FULL_COMMIT_SHA
```

`operators` reuses `deploy/flux-system` and excludes FluxInstance, OpenBao and
c5c3 so the environment can manage their lifecycle and ordering separately.
Existing devstack consumers continue to use the same canonical release manifests.

The environment owns ControlPlane instances, service endpoints, Gateway
implementation and CRDs, certificates for public endpoints, StorageClasses,
sizing, version pins, and secret initialization/unseal/tenant-onboarding jobs.
These bases create no ControlPlane instance or Gateway and run no bootstrap jobs.
OpenBao inherits the cluster's default StorageClass unless an overlay selects one;
the legacy bundle's `local-path` choice is not carried into this base.

The bases retain the existing service namespaces and internal service names.
When changing these, update cross-resource references and OpenBao policies
together. The TLS base retains the existing self-signed CA setup; configure the
issuer and trust policy required by the target environment. The `secrets` base
contains the shared ClusterSecretStore; environment-owned ExternalSecrets must
use identities and paths permitted by the environment's OpenBao policies.

## Reconciliation

Bootstrap Flux, then create a GitRepository and root Kustomization targeting the
deployment repository's cluster directory. Express the prerequisites above with
`dependsOn` and health checks. Wait for all `operators` resources, including the
K-ORC Kustomization, before installing `controlplane-operator`.

OpenBao initialization and unsealing must complete before dependent secret stores
can become Ready. If an environment's bootstrap stage needs a running but sealed
OpenBao pod, its OpenBao overlay can set `install.disableWait` and
`upgrade.disableWait` to `true`; the bootstrap stage must then enforce readiness.
Reusable bootstrap scripts and policies are available as generated ConfigMaps
through `deploy/openbao/bootstrap` and `deploy/openbao/policies`. These directories
package the existing helpers; they do not execute them or choose a key-custody model.

When an environment provisions managed databases through a ControlPlane, apply
the instance before running tenant onboarding. Wait for aggregate ControlPlane
readiness after onboarding, to avoid a dependency cycle. Keep pruning disabled
for stateful resources unless the environment has an explicit teardown policy.
Namespaces in `operators` are excluded from Flux pruning.

Pin chart versions and operator image digests in the environment overlay before
promoting changes. The reusable bases retain the canonical chart version ranges.

Validate with `python3 hack/check-gitops-bundles.py` (requires `kustomize` and
Mike Farah's `yq`). See [Flux dependencies and health checks](https://fluxcd.io/flux/components/kustomize/kustomizations/).
