#!/usr/bin/env python3
"""Check reusable bundle boundaries and preservation of canonical releases."""
import copy
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASES = ROOT / "deploy/gitops/bases"


def render(path):
    manifest = subprocess.check_output(["kustomize", "build", str(path)])
    data = subprocess.check_output(
        ["yq", "eval-all", "-o=json", "[.]", "-"], input=manifest
    )
    return [obj for obj in json.loads(data) if obj]


def identity(obj):
    meta = obj["metadata"]
    return (obj["apiVersion"], obj["kind"], meta.get("namespace", ""), meta["name"])


def main():
    owners = {}
    rendered = {}
    for path in sorted(BASES.iterdir()):
        if not path.is_dir():
            continue
        objects = render(path)
        rendered[path.name] = objects
        for obj in objects:
            key = identity(obj)
            assert key not in owners, f"{key} is owned by {owners.get(key)} and {path.name}"
            owners[key] = path.name
            assert obj["kind"] not in {
                "ControlPlane", "Gateway", "GatewayClass", "EnvoyProxy",
                "ExternalSecret", "Job", "CronJob",
            }, f"Environment resource in reusable base: {key}"
        print(f"{path.name}: {len(objects)} resources; unique ownership and no environment instances")

    openbao = next(obj for obj in rendered["openbao"] if obj["kind"] == "HelmRelease")
    assert "storageClass" not in openbao["spec"]["values"]["server"]["dataStorage"], \
        "The environment must select the StorageClass"

    # Only the GitOps OpenBao base drops the legacy storage driver selection.
    original = {identity(obj): obj for obj in render(ROOT / "deploy/flux-system") if obj["kind"] != "FluxInstance"}
    original[identity(openbao)]["spec"]["values"]["server"]["dataStorage"].pop("storageClass")
    combined = {}
    for name in ("operators", "openbao", "controlplane-operator"):
        for obj in rendered[name]:
            obj = copy.deepcopy(obj)
            if obj["kind"] == "Namespace":
                annotations = obj["metadata"].get("annotations", {})
                annotations.pop("kustomize.toolkit.fluxcd.io/prune", None)
                if not annotations:
                    obj["metadata"].pop("annotations", None)
            combined[identity(obj)] = obj
    assert original == combined, "Unexpected change to canonical release semantics"
    # Existing devstack overlays still build after the manifest moves.
    render(ROOT / "deploy/kind/base")
    render(ROOT / "deploy/kind/infrastructure")
    # The optional helpers package ConfigMaps only; environments own execution.
    for path in ("deploy/openbao/bootstrap", "deploy/openbao/policies"):
        assert all(obj["kind"] == "ConfigMap" for obj in render(ROOT / path)), path
    print("Canonical releases preserved except StorageClass selection; existing kind overlays build")


if __name__ == "__main__":
    main()
