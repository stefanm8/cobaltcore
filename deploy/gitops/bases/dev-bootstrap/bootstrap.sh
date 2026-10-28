#!/usr/bin/env bash
# Local development only: the init keys remain in a Kubernetes Secret.
set -euo pipefail
export OPENBAO_NAMESPACE=shared-services OPENBAO_PODS=openbao-0
export POLICIES_DIR=/policies KORC_CONTROLPLANES=openstack/controlplane
for _ in $(seq 1 120); do
  if kubectl -n shared-services exec openbao-0 -- bao status -format=json 2>/dev/null | jq -e 'has("initialized")' >/dev/null; then
    break
  fi
  # Sealed OpenBao exits 2 even when the status document is valid.
  status="$(kubectl -n shared-services exec openbao-0 -- bao status -format=json 2>/dev/null || true)"
  if jq -e 'has("initialized")' <<<"$status" >/dev/null 2>&1; then break; fi
  sleep 5
done
bash /scripts/init-unseal.sh
if [[ "${1:-bootstrap}" == unseal ]]; then exit 0; fi
export BAO_TOKEN
trap 'unset BAO_TOKEN' EXIT
BAO_TOKEN="$(kubectl -n shared-services get secret openbao-init-keys -o jsonpath='{.data.init-output}' | base64 -d | jq -er .root_token)"
for script in setup-secret-engines setup-auth setup-policies write-bootstrap-secrets; do
  bash "/scripts/${script}.sh"
done
printf '%s\n' 'OpenBao bootstrap complete.'
