from __future__ import annotations

import os
import sys
import subprocess
import json
from pathlib import Path
from typing import Optional, Dict, Any, List

import typer
import yaml
from jinja2 import Environment, FileSystemLoader

# K8s/OpenShift python client
from kubernetes import client, config, utils
from kubernetes.client import ApiClient

# Ansible Runner
import ansible_runner

app = typer.Typer(help="CI/CD orchestrator for OpenShift + Ansible")

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = ROOT / "openshift" / "manifests"
BUILD_DIR = ROOT / "build" / "manifests"


def _load_env_values(values_file: Optional[str]) -> Dict[str, Any]:
    """
    Load key=val plain file (like .env) into a dict.
    We keep it super simple: ignore empty lines and comments.
    """
    values: Dict[str, Any] = {}
    if not values_file:
        return values
    for line in Path(values_file).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        values[k.strip()] = v.strip()
    return values


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _oc_available() -> bool:
    return subprocess.call(["which", "oc"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def _kubectl_available() -> bool:
    return subprocess.call(["which", "kubectl"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def _kube_login_if_needed() -> None:
    """
    Try to load kubeconfig from env or in-cluster.
    """
    try:
        if os.environ.get("KUBERNETES_SERVICE_HOST"):
            config.load_incluster_config()
        else:
            config.load_kube_config()
    except Exception as e:
        typer.secho(f"[warn] kubeconfig not loaded: {e}", fg=typer.colors.YELLOW)


@app.command()
def oc_login(cluster_api: str = typer.Option(..., envvar="CLUSTER_API"),
             token: str = typer.Option(..., envvar="OC_TOKEN"),
             insecure_skip_tls_verify: bool = True):
    """
    Log into OpenShift using 'oc'. This is optional if you already have kubeconfig.
    """
    if not _oc_available():
        typer.secho("oc not found in PATH. Install OpenShift CLI.", fg=typer.colors.RED)
        raise typer.Exit(1)

    cmd = [
        "oc", "login", cluster_api,
        f"--token={token}",
    ]
    if insecure_skip_tls_verify:
        cmd.append("--insecure-skip-tls-verify=true")

    typer.echo(f"Running: {' '.join(cmd)}")
    subprocess.check_call(cmd)
    typer.secho("Logged in with oc.", fg=typer.colors.GREEN)


@app.command()
def render(values: Optional[str] = typer.Option(None, "--values", "-f",
                                               help="Path to .env-style values file"),
          outdir: str = typer.Option(str(BUILD_DIR), "--outdir", "-o")):
    """
    Render Jinja2 manifests with variables from --values.
    """
    vars_ = _load_env_values(values)
    _ensure_dir(Path(outdir))
    env = Environment(loader=FileSystemLoader(str(MANIFEST_DIR)))

    # files ending with .j2 are rendered; others copied
    for tmpl in MANIFEST_DIR.iterdir():
        if tmpl.is_dir():
            continue
        if tmpl.suffix == ".j2":
            template = env.get_template(tmpl.name)
            rendered = template.render(**vars_)
            out_path = Path(outdir) / tmpl.stem  # drop .j2
            out_path.write_text(rendered)
            typer.secho(f"Rendered {tmpl.name} -> {out_path}", fg=typer.colors.CYAN)
        else:
            out_path = Path(outdir) / tmpl.name
            out_path.write_text(tmpl.read_text())
            typer.secho(f"Copied {tmpl.name} -> {out_path}", fg=typer.colors.CYAN)

    typer.secho("Render complete.", fg=typer.colors.GREEN)


def _apply_with_python(manifest_dir: Path) -> None:
    """
    Apply YAMLs using Kubernetes python client. Best-effort 'kubectl apply' behaviour.
    """
    _kube_login_if_needed()
    k8s_client = ApiClient()
    for yf in sorted(manifest_dir.glob("*.y*ml")):
        typer.echo(f"Applying {yf.name} via Python client")
        with yf.open() as f:
            try:
                utils.create_from_yaml(k8s_client, yaml_file=f, verbose=True)
            except Exception as e:
                typer.secho(f"  warn: {e}", fg=typer.colors.YELLOW)


def _apply_with_oc(manifest_dir: Path) -> None:
    for yf in sorted(manifest_dir.glob("*.y*ml")):
        cmd = ["oc", "apply", "-f", str(yf)]
        typer.echo(f"Running: {' '.join(cmd)}")
        subprocess.check_call(cmd)


@app.command()
def apply(manifests: str = typer.Option(str(BUILD_DIR), "--manifests", "-m")):
    """
    Apply manifests from a directory. Prefers 'oc', falls back to python client, then kubectl.
    """
    mdir = Path(manifests)
    if not mdir.exists():
        typer.secho(f"Manifests not found: {mdir}", fg=typer.colors.RED)
        raise typer.Exit(1)

    if _oc_available():
        _apply_with_oc(mdir)
    else:
        typer.secho("oc not found, using python client (or kubectl if present)", fg=typer.colors.YELLOW)
        try:
            _apply_with_python(mdir)
        except Exception:
            if _kubectl_available():
                subprocess.check_call(["kubectl", "apply", "-f", str(mdir)])
            else:
                typer.secho("Neither oc nor kubectl available.", fg=typer.colors.RED)
                raise
    typer.secho("Apply complete.", fg=typer.colors.GREEN)


def _run_ansible(playbook: str, extravars: Dict[str, Any]) -> int:
    """
    Run an ansible playbook using ansible-runner.
    """
    typer.echo(f"> Ansible playbook: {playbook}")
    rc = ansible_runner.run(
        private_data_dir=str(ROOT / "ansible"),
        playbook=playbook,
        extravars=extravars,
        inventory=str(ROOT / "ansible" / "inventory" / "hosts.ini"),
        quiet=False,
    ).rc
    return rc


@app.command()
def deploy(values: Optional[str] = typer.Option(None, "--values", "-f")):
    """
    Render manifests and run the deploy playbook (pre -> apply -> post).
    """
    vars_ = _load_env_values(values)
    outdir = ROOT / "build" / "manifests"
    _ensure_dir(outdir)
    # Render first
    env = Environment(loader=FileSystemLoader(str(MANIFEST_DIR)))
    for tmpl in MANIFEST_DIR.iterdir():
        if tmpl.is_dir():
            continue
        if tmpl.suffix == ".j2":
            rendered = env.get_template(tmpl.name).render(**vars_)
            (outdir / tmpl.stem).write_text(rendered)
        else:
            (outdir / tmpl.name).write_text(tmpl.read_text())

    # Kick ansible pipeline
    rc = _run_ansible("deploy.yml", extravars={
        "manifest_dir": str(outdir),
        **vars_,
    })
    if rc != 0:
        typer.secho(f"Deploy failed with code {rc}", fg=typer.colors.RED)
        raise typer.Exit(rc)
    typer.secho("Deploy succeeded.", fg=typer.colors.GREEN)


@app.command()
def rollback(namespace: str = typer.Option(..., "--namespace", "-n")):
    """
    Roll back the Deployment to the previous ReplicaSet (simple strategy).
    """
    rc = _run_ansible("rollback.yml", extravars={"NAMESPACE": namespace})
    if rc != 0:
        typer.secho("Rollback failed", fg=typer.colors.RED)
        raise typer.Exit(rc)
    typer.secho("Rollback succeeded.", fg=typer.colors.GREEN)


@app.command("run-playbook")
def run_playbook(playbook: str, extravars: Optional[str] = typer.Option(None, "--extra-vars")):
    """
    Run any playbook in ansible/playbooks (extra vars as JSON string).
    """
    ev: Dict[str, Any] = json.loads(extravars) if extravars else {}
    rc = _run_ansible(playbook, extravars=ev)
    raise typer.Exit(rc)


if __name__ == "__main__":
    app()
