#!/usr/bin/env python3
"""Check composability and preservation of the existing operator manifests."""
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
        # Remote CRD assets have a separate online render/server-validation gate.
        if not path.is_dir() or path.name == "gateway-crds":
            continue
        objects = render(path)
        rendered[path.name] = objects
        configmaps = {obj["metadata"]["name"] for obj in objects if obj["kind"] == "ConfigMap"}
        for obj in objects:
            key = identity(obj)
            assert key not in owners, f"{key} is owned by {owners.get(key)} and {path.name}"
            owners[key] = path.name
            if obj["kind"] == "Job":
                pod = obj["spec"]["template"]["spec"]
                for volume in pod.get("volumes", []):
                    if "configMap" in volume:
                        assert volume["configMap"]["name"] in configmaps, volume
                assert obj["spec"]["activeDeadlineSeconds"] > 0
                assert obj["metadata"]["annotations"]["kustomize.toolkit.fluxcd.io/force"] == "enabled"
        print(f"{path.name}: {len(objects)} resources; ownership and Job references valid")

    # Splitting the original operator bundle must not alter its release specs.
    original = {identity(obj): obj for obj in render(ROOT / "deploy/flux-system") if obj["kind"] != "FluxInstance"}
    combined = {}
    for name in ("operators", "openbao", "controlplane-operator"):
        for obj in rendered[name]:
            obj = copy.deepcopy(obj)
            if obj["kind"] == "Namespace":
                obj["metadata"].pop("annotations", None)
            combined[identity(obj)] = obj
    assert original == combined, "The split changed the existing operator bundle"
    # Existing devstack overlays still build after the manifest moves.
    render(ROOT / "deploy/kind/base")
    render(ROOT / "deploy/kind/infrastructure")
    print("Original operator semantics and existing kind overlays preserved")


if __name__ == "__main__":
    main()
