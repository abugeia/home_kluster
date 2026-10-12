#!/usr/bin/env python3
"""Rend chaque Application Argo CD comme le ferait le repo-server, puis valide
les manifests produits avec kubeconform.

Couvre les quatre formes de source du dépôt :
- chart Helm distant (repo HTTP ou registre OCI), valueFiles `$values/...` ;
- chart Helm local (path + Chart.yaml) ;
- kustomize (path + kustomization.yaml) ;
- dossier de manifests bruts (directory.include / exclude / recurse).

Le but est d'attraper ce qu'un bump Renovate peut casser : un chart qui ne se
rend plus avec nos values, un schéma refusé, un YAML invalide.
"""
import fnmatch
import glob
import os
import subprocess
import sys
import tempfile

import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
HELM = os.environ.get("HELM", "helm")
KUBECONFORM = os.environ.get("KUBECONFORM", "kubeconform")
KUBE_VERSION = os.environ.get("KUBE_VERSION", "1.36.0")
SELF_REPO = "github.com/abugeia/home_kluster"

KUBECONFORM_ARGS = [
    "-summary",
    "-output", "text",
    "-ignore-missing-schemas",
    # Le catalogue communautaire est plus strict que les CRDs installées :
    # il refuse le `creationTimestamp: null` qu'émet kubeseal, et exige un
    # `spec.namespace` que l'ImageUpdater du cluster n'impose pas.
    "-skip", "SealedSecret,ImageUpdater",
    "-schema-location", "default",
    # Schémas des CRDs courantes (Traefik, cert-manager, Argo CD, MetalLB…).
    "-schema-location",
    "https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json",
]


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def is_self(repo_url):
    return SELF_REPO in (repo_url or "")


def applications():
    for path in sorted(glob.glob(os.path.join(ROOT, "argocd", "**", "*.yaml"), recursive=True)):
        with open(path) as f:
            for doc in yaml.safe_load_all(f):
                if doc and doc.get("kind") == "Application":
                    yield os.path.relpath(path, ROOT), doc


def helm_values_args(helm):
    args = []
    for vf in helm.get("valueFiles", []):
        local = os.path.join(ROOT, vf.replace("$values/", "", 1))
        if not os.path.exists(local):
            if helm.get("ignoreMissingValueFiles"):
                continue
            raise RuntimeError(f"valueFile introuvable : {vf}")
        args += ["-f", local]
    inline = helm.get("valuesObject") or helm.get("values")
    if inline:
        tmp = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False)
        tmp.write(inline if isinstance(inline, str) else yaml.safe_dump(inline))
        tmp.close()
        args += ["-f", tmp.name]
    for p in helm.get("parameters", []):
        flag = "--set-string" if p.get("forceString") else "--set"
        args += [flag, f"{p['name']}={p['value']}"]
    return args


def render_helm_remote(src, release, namespace):
    helm = src.get("helm", {})
    repo, chart, version = src["repoURL"], src["chart"], src["targetRevision"]
    if repo.startswith("http"):
        target = [chart, "--repo", repo]
    else:  # Argo CD traite un repoURL sans schéma comme un registre OCI.
        target = [f"oci://{repo.rstrip('/')}/{chart}"]
    cmd = [HELM, "template", helm.get("releaseName", release), *target,
           "--version", version, "--namespace", namespace,
           "--kube-version", KUBE_VERSION, "--include-crds",
           *helm_values_args(helm)]
    return run(cmd)


def render_helm_local(src, release, namespace):
    helm = src.get("helm", {})
    path = os.path.join(ROOT, src["path"])
    with open(os.path.join(path, "Chart.yaml")) as f:
        if yaml.safe_load(f).get("dependencies"):
            dep = run([HELM, "dependency", "build", path])
            if dep.returncode:
                return dep
    # Dans une source locale, les valueFiles sont relatifs au chart.
    helm = dict(helm, valueFiles=[
        vf if vf.startswith("$values/") else os.path.join(src["path"], vf)
        for vf in helm.get("valueFiles", [])
    ])
    cmd = [HELM, "template", helm.get("releaseName", release), path,
           "--namespace", namespace, "--kube-version", KUBE_VERSION,
           "--include-crds", *helm_values_args(helm)]
    return run(cmd)


def render_kustomize(src):
    # --enable-helm : comme Argo CD (kustomize.buildOptions dans argocd/helm/values.yaml).
    return run(["kubectl", "kustomize", "--enable-helm",
                os.path.join(ROOT, src["path"])])


def render_directory(src):
    dirspec = src.get("directory", {})
    base = os.path.join(ROOT, src["path"])
    pattern = "**/*" if dirspec.get("recurse") else "*"
    include = dirspec.get("include")
    exclude = dirspec.get("exclude")

    def matches(spec, rel):
        if not spec:
            return False
        spec = spec.strip("{}")
        return any(fnmatch.fnmatch(rel, p.strip()) or fnmatch.fnmatch(os.path.basename(rel), p.strip())
                   for p in spec.split(","))

    out = []
    for f in sorted(glob.glob(os.path.join(base, pattern), recursive=True)):
        rel = os.path.relpath(f, base)
        if not os.path.isfile(f) or not f.endswith((".yaml", ".yml", ".json")):
            continue
        if include and not matches(include, rel):
            continue
        if exclude and matches(exclude, rel):
            continue
        with open(f) as fh:
            out.append(fh.read())
    return subprocess.CompletedProcess([], 0, "\n---\n".join(out), "")


def render(src, app):
    release = app["metadata"]["name"]
    namespace = app["spec"].get("destination", {}).get("namespace", "default")
    if src.get("chart"):
        return "helm", render_helm_remote(src, release, namespace)
    path = src.get("path")
    if path is None:
        return None, None  # source `ref` seule : sert juste à fournir $values
    if not is_self(src.get("repoURL")):
        return None, None  # dépôt externe (ex. CRDs Gateway API) : hors périmètre
    full = os.path.join(ROOT, path)
    if os.path.exists(os.path.join(full, "Chart.yaml")):
        return "helm-local", render_helm_local(src, release, namespace)
    if os.path.exists(os.path.join(full, "kustomization.yaml")):
        return "kustomize", render_kustomize(src)
    return "directory", render_directory(src)


def validate(manifests):
    return run([KUBECONFORM, *KUBECONFORM_ARGS, "-"], input=manifests)


def main():
    failures = []
    for file, app in applications():
        spec = app["spec"]
        sources = spec.get("sources") or [spec.get("source")]
        for i, src in enumerate(s for s in sources if s):
            label = f"{app['metadata']['name']}[{i}]"
            try:
                kind, res = render(src, app)
            except Exception as e:  # valueFile manquant, Chart.yaml illisible…
                failures.append((label, file, f"rendu impossible : {e}"))
                print(f"✗ {label} — {e}")
                continue
            if kind is None:
                continue
            if res.returncode:
                failures.append((label, file, f"rendu {kind} en échec :\n{res.stderr.strip()}"))
                print(f"✗ {label} ({kind}) — rendu en échec")
                continue
            if not res.stdout.strip():
                print(f"· {label} ({kind}) — rien à valider")
                continue
            check = validate(res.stdout)
            if check.returncode:
                failures.append((label, file, f"kubeconform :\n{check.stdout.strip()}{check.stderr.strip()}"))
                print(f"✗ {label} ({kind}) — manifests invalides")
            else:
                print(f"✓ {label} ({kind}) — {check.stdout.strip().splitlines()[-1]}")

    if failures:
        print(f"\n{len(failures)} source(s) en échec :\n")
        for label, file, msg in failures:
            print(f"::error file={file}::{label}")
            print(f"--- {label} ({file})\n{msg}\n")
        return 1
    print("\nToutes les Applications se rendent et passent kubeconform.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
