#!/usr/bin/env python3
"""Supprime du containerd du nœud les images qu'aucun workload ne déclare.

Le GC d'images du kubelet ne raisonne que sur « un conteneur tourne-t-il avec
cette image ? » : il ne distingue pas une ancienne version remplacée par
Renovate de l'image d'une app en veille Sablier (0 réplique). Ce script juge
d'après ce qui est DÉCLARÉ dans le cluster : il garde toute image référencée
par un Deployment, StatefulSet, DaemonSet, CronJob, Job ou Pod (réplicas à 0
compris), plus les images des conteneurs existants et l'image pause, et
supprime le reste. Les ReplicaSets ne comptent pas : les anciens portent
justement les versions remplacées.

DRY_RUN=true (défaut) : liste sans rien supprimer.
"""
import json
import os
import ssl
import subprocess
import urllib.request

SA = "/var/run/secrets/kubernetes.io/serviceaccount"
API = "https://kubernetes.default.svc"
CRICTL = ["/host-bin/crictl", "--runtime-endpoint", "unix:///run/k3s/containerd/containerd.sock"]
DRY_RUN = os.environ.get("DRY_RUN", "true").lower() != "false"
PATHS = [
    "/apis/apps/v1/deployments",
    "/apis/apps/v1/statefulsets",
    "/apis/apps/v1/daemonsets",
    "/apis/batch/v1/cronjobs",
    "/apis/batch/v1/jobs",
    "/api/v1/pods",
]


def api_get(path):
    token = open(f"{SA}/token").read()
    ctx = ssl.create_default_context(cafile=f"{SA}/ca.crt")
    req = urllib.request.Request(API + path, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, context=ctx) as r:
        return json.load(r)


def declared_images():
    found = set()

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("containers", "initContainers", "ephemeralContainers") and isinstance(v, list):
                    found.update(c["image"] for c in v if "image" in c)
                else:
                    walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)

    for p in PATHS:
        walk(api_get(p)["items"])
    return found


def normalize(ref):
    """Ramène une référence d'image à la forme stockée par containerd.

    `traefik/whoami` -> (`docker.io/traefik/whoami`, `latest`, None)
    `img:tag@sha256:x` -> (`docker.io/library/img`, `tag`, `sha256:x`)
    """
    digest = None
    if "@" in ref:
        ref, digest = ref.split("@", 1)
    name, tag = ref, None
    if ":" in ref.rsplit("/", 1)[-1]:
        name, tag = ref.rsplit(":", 1)
    first = name.split("/")[0]
    if "." not in first and ":" not in first and first != "localhost":
        name = "docker.io/" + name
    if name.startswith("docker.io/") and name.count("/") == 1:
        name = "docker.io/library/" + name.split("/", 1)[1]
    if tag is None and digest is None:
        tag = "latest"
    return name, tag, digest


def crictl_json(*args):
    return json.loads(subprocess.check_output(CRICTL + list(args) + ["-o", "json"]))


def main():
    keep_tags, keep_digests = set(), set()
    for ref in declared_images():
        name, tag, digest = normalize(ref)
        if digest:
            keep_digests.add(f"{name}@{digest}")
        else:
            keep_tags.add(f"{name}:{tag}")

    in_use = {c["imageRef"] for c in crictl_json("ps", "-a")["containers"]}
    to_remove, kept = [], 0
    for img in crictl_json("images")["images"]:
        tags, digests = img["repoTags"] or [], img["repoDigests"] or []
        if (
            img["id"] in in_use
            or img.get("pinned")
            or any("pause" in t for t in tags)
            or any(t in keep_tags for t in tags)
            or any(d in keep_digests for d in digests)
        ):
            kept += 1
            continue
        to_remove.append((int(img["size"]), img["id"], (tags or digests or [img["id"]])[0]))

    total = sum(s for s, _, _ in to_remove)
    mode = "DRY_RUN, rien n'est supprimé" if DRY_RUN else "suppression"
    print(f"{kept} images gardées, {len(to_remove)} à supprimer ({total / 2**30:.1f} Gi compressés) - {mode}")
    failed = 0
    for size, image_id, name in sorted(to_remove, reverse=True):
        print(f"{size / 2**30:6.2f} Gi  {name}")
        if not DRY_RUN:
            r = subprocess.run(CRICTL + ["rmi", image_id], capture_output=True, text=True)
            if r.returncode != 0:
                failed += 1
                print(f"   échec : {r.stderr.strip()}")
    if failed:
        raise SystemExit(f"{failed} suppressions en échec")


if __name__ == "__main__":
    main()
