#!/usr/bin/env bash
# The Minimal profile keeps its database in the openstack namespace.
set -euo pipefail
for _ in $(seq 1 120); do
  if kubectl -n openstack get mariadb/openstack-db >/dev/null 2>&1; then break; fi
  sleep 5
done
kubectl -n openstack wait mariadb/openstack-db --for=condition=Ready --timeout=10m
export BAO_TOKEN
trap 'unset BAO_TOKEN' EXIT
BAO_TOKEN="$(kubectl -n shared-services get secret openbao-init-keys -o jsonpath='{.data.init-output}' | base64 -d | jq -er .root_token)"
bash /scripts/setup-database-tenant.sh openstack controlplane
