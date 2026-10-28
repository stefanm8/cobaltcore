# GitOps deployment bases

These Kustomize directories expose the existing Helm releases, certificates and
ControlPlane manifests as independently reconciled stages. They do not invoke
`make deploy-infra`. Keep cluster settings and version pins in a separate
deployment repository with `bases/`, `overlays/` and `clusters/` directories.

| Base | Prerequisite | Readiness gate |
| --- | --- | --- |
| `gateway-crds` | Kubernetes 1.33 or newer | CRDs established |
| `operators` | Flux source/Helm/Kustomize controllers | Helm releases and K-ORC/RabbitMQ Kustomizations Ready |
| `tls` | operators | Certificates and issuers Ready |
| `openbao` | TLS certificates | Helm release installed; see bootstrap below |
| `dev-bootstrap` | OpenBao installed | bootstrap Job Complete |
| `secrets` | bootstrap complete | ClusterSecretStore and Horizon ExternalSecret Ready |
| `gateway` | Gateway CRDs, operators, TLS | Envoy release and Gateway Ready |
| `controlplane-operator` | operators, including K-ORC | c5c3 Helm release Ready |
| `controlplane` | c5c3, secrets, gateway | apply only; database onboarding must run before waiting |
| `database-onboarding` | ControlPlane applied | Job Complete, then ControlPlane Ready |

Use Flux `Kustomization.spec.dependsOn` to encode these edges and `wait: true`
for each stage except `controlplane`. The database Job waits for the projected
MariaDB before configuring its OpenBao database engine. Waiting for the entire
ControlPlane before this Job can create a dependency cycle.

Reference a reviewed commit, for example:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - https://github.com/YOUR-ORG/cobaltcore//deploy/gitops/bases/operators?ref=FULL_COMMIT_SHA
```

`operators` reuses `deploy/flux-system` and excludes FluxInstance, OpenBao and
c5c3 so they have separate lifecycle/ordering. Existing devstack consumers still
use the same release manifests. The production TLS files now have their own
Kustomization under `deploy/flux-system/infrastructure/tls`.

## Local minikube profile

The initial service profile is Keystone and Horizon on one node. Use the
`Minimal` sizing profile, one replica per CobaltCore operator, standalone
OpenBao on the `standard` storage class, and a local gateway forward on 8443.
Set `spec.services.keystone.publicEndpoint` to
`https://keystone.127-0-0-1.nip.io:8443/v3`. The projected MariaDB uses the
cluster's default StorageClass; there is no ControlPlane `storageClass` field.
This profile does not install hypervisors, Ceph, or prove VM provisioning.

For standalone OpenBao, set the HelmRelease's `install.disableWait` and
`upgrade.disableWait` to `true`: an uninitialized server is deliberately not
Ready, while the next-stage Job needs its pod to exist. The bootstrap Job itself
checks the API and exits unsuccessfully if initialization cannot complete.

`dev-bootstrap` and `database-onboarding` are local development helpers, tied to
`shared-services/openbao-0` and `openstack/controlplane`. They reuse the canonical
bootstrap scripts and policies through hashed ConfigMaps. Jobs have bounded
retries and no TTL so Flux can inspect completion; a changed pod template is
replaced through the Job's Flux force annotation. A CronJob unseals the local
server after restarts. The init keys/root token remain in a Kubernetes Secret,
matching the devstack's existing trust model. Do not use this custody model in
production; supply a managed OpenBao/bootstrap process there. Bootstrap access
is namespace-scoped, but includes pod exec and secret creation in shared-services.

Keep `prune: false` on stateful stages (`openbao`, `dev-bootstrap`,
`controlplane`, `database-onboarding`) and explicitly plan any teardown.
Namespaces in `operators` are excluded from Flux pruning. Pin exact chart
versions and operator image digests in the environment overlay before promoting
it; the reusable upstream bases intentionally retain their existing ranges.

## Flux reconciliation

Bootstrap Flux once, then a GitRepository and root Kustomization targeting the
deployment repository's cluster directory. Subsequent configuration changes are
Git commits; no workstation-side unseal, live suspend patch, or Helm install is
part of the stack reconciliation.

Validate with `python3 hack/check-gitops-bundles.py` (requires `kustomize` and
Mike Farah's `yq`). See [Flux dependencies and health checks](https://fluxcd.io/flux/components/kustomize/kustomizations/).
