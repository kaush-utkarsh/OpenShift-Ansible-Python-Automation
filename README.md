# 🚀 OpenShift + Ansible CI/CD (Python Automation Project)

This repository is a **ready-to-use Python project** that automates a CI/CD pipeline using **OpenShift** for deployments and **Ansible** for orchestration. It comes with:

* A **Python CLI tool (`cicd`)** for rendering manifests, applying them, and orchestrating deployments.
* **Ansible playbooks** for pre-deploy checks, deployments, post-deploy smoke tests, and rollback.
* **Templated OpenShift manifests** rendered with Jinja2.
* **GitHub Actions workflow** to automate builds, push images, and deploy to OpenShift.
* A clean project structure with a **Makefile** for common commands and a **sample `.env` file** for configuration.

This template is built for developers and DevOps teams who want a **repeatable, extensible, and production-ready workflow**.

---

## Repository Structure

```
openshift-ansible-cicd/
├── README.md               # You are here
├── .env.sample             # Example env vars for local runs
├── Makefile                # Convenience commands
├── pyproject.toml          # Poetry/Pip modern Python packaging
├── requirements.txt        # Dependencies (if not using poetry)
├── structure.txt           # General Project Structure
├── cicd/                   # Python CLI tool
│   └── cli.py
├── ansible/                # Ansible configs and playbooks
│   ├── ansible.cfg
│   ├── inventory/
│   │   └── hosts.ini
│   ├── playbooks/
│   │   ├── deploy.yml
│   │   ├── hooks.yml
│   │   └── rollback.yml
│   └── roles/
│       ├── app_deploy/
│       │   ├── tasks/
│       │   │   ├── deploy.yml
│       │   │   ├── post.yml
│       │   │   └── pre.yml
│       │   └── templates/
│       │       └── k8s/    # (unused by Ansible; we render with Python/Jinja) 
│       └── test.txt        # unused
├── openshift/              # Templated manifests
│   ├── manifests
│   │   ├── deployment.yaml.j2
│   │   ├── namespace.yaml
│   │   ├── rbac.yaml
│   │   ├── route.yaml.j2
│   │   ├── service.yaml.j2
│   │   └── serviceaccount.yaml
│   └── test.txt            # unused
├── ci/                     # GitHub Actions pipeline
│   └── github/
│       └── workflows/
│           └── cicd.yml
└── tests/                  # Example unit test for CLI
    └── test_cli.py
```

---

## Prerequisites

Before using this project, make sure you have:

* **Python 3.10+**
* **OpenShift CLI (`oc`)** installed and in PATH
* Access to an **OpenShift cluster** (API endpoint + token)
* **Ansible** (comes with project via `ansible-runner`)
* (Optional) **kubectl** if you want to fallback to standard Kubernetes tools
* A **container registry** (e.g., GitHub Container Registry `ghcr.io`)

---

## Setup

### 1. Clone and setup environment

```bash
git clone https://github.com/yourorg/openshift-ansible-cicd.git
cd openshift-ansible-cicd

# Create virtualenv & install
make setup
```

### 2. Configure environment variables

Copy `.env.sample` and fill in values:

```bash
cp .env.sample .env
```

Example:

```
APP_NAME=hello-app
NAMESPACE=demo
IMAGE=ghcr.io/yourorg/hello-app:latest
REPLICAS=2
CONTAINER_PORT=8080
CLUSTER_API=https://api.openshift.example.com:6443
OC_TOKEN=sha256~paste_your_token
```

> ever commit `.env` with real secrets. Use CI/CD secrets for production.

---

## Using the Python CLI

After setup, the CLI is available as `cicd`:

### 1. Login to OpenShift

```bash
cicd oc-login --cluster-api $CLUSTER_API --token $OC_TOKEN --insecure-skip-tls-verify
```

### 2. Render manifests

This takes Jinja2 templates and renders them using `.env` values.

```bash
cicd render --values .env --outdir build/manifests
```

### 3. Apply manifests

Apply rendered manifests to cluster:

```bash
cicd apply --manifests build/manifests
```

### 4. Deploy (with Ansible pre/post hooks)

This will:

* Run pre-deploy checks
* Apply manifests
* Run post-deploy smoke tests

```bash
cicd deploy --values .env
```

### 5. Rollback

Rollback to the previous ReplicaSet if needed:

```bash
cicd rollback --namespace demo
```

---

## Ansible Playbooks

* **`deploy.yml`**
  Runs pre-tasks → applies manifests → post-tasks.
* **`rollback.yml`**
  Rolls back a deployment using `kubectl rollout undo`.
* **`hooks.yml`**
  Example for running DB migrations or one-off jobs.

You can also run any playbook directly:

```bash
cicd run-playbook deploy.yml --extra-vars '{"APP_NAME":"hello-app","NAMESPACE":"demo"}'
```

---

## OpenShift Manifests

Manifests are in `openshift/manifests/` and templated with Jinja2:

* `deployment.yaml.j2` — Deployment spec (image, replicas, probes).
* `service.yaml.j2` — ClusterIP service.
* `route.yaml.j2` — OpenShift route with TLS.
* `rbac.yaml` — Role and RoleBinding for service account.

All variables are pulled from `.env` or passed through CLI.

---

## CI/CD with GitHub Actions

This repo includes `ci/github/workflows/cicd.yml`:

* Runs on `push` to `main`
* Steps:

  1. Lint & test Python code
  2. Build container image
  3. Push to `ghcr.io`
  4. Login to OpenShift (using `OS_API` and `OS_TOKEN` secrets)
  5. Deploy with Ansible

### Required GitHub Secrets

* `OS_API` → your cluster API (e.g., `https://api.openshift.example.com:6443`)
* `OS_TOKEN` → a service account token with permissions

---

## Local Testing

Run unit tests:

```bash
pytest -q
```

---

## Typical Workflow

1. **Dev**: Update app code, push to branch.
2. **CI**: Workflow builds and pushes container image.
3. **CD**: Workflow applies manifests to OpenShift.
4. **Rollback**: If something fails, run `cicd rollback`.

---

## Extending

* Add **stage/prod environments** with different `.env` files.
* Extend **pre/post hooks** for DB migrations or health checks.
* Swap **GitHub Actions** for GitLab CI, Jenkins, or ArgoCD.
* Use OpenShift **ImageStreams** instead of external registry if preferred.

---

## Notes & Best Practices

* Keep RBAC (`rbac.yaml`) minimal for least privilege.
* Always parameterize sensitive data using `.env` or CI/CD secrets.
* Use readiness/liveness probes for reliable rollouts.
* Consider approvals for staging → production promotion in CI/CD.

---

## Quick Commands (Makefile)

```bash
make render     # Render manifests
make apply      # Apply manifests
make deploy     # Run full Ansible deploy
make rollback   # Rollback to previous revision
```
---

## Quick Demo: Deploy Nginx in 15 Minutes

With this project, you get a **turnkey CI/CD setup** that can be adapted to almost any containerized application running on OpenShift, with Ansible giving you hooks for everything around deployment.

Below is a demo to deploy a simple **Nginx app** to OpenShift.

### 1. Clone & setup

```bash
git clone https://github.com/yourorg/openshift-ansible-cicd.git
cd openshift-ansible-cicd
make setup
```

### 2. Prepare demo `.env`

Create a `.env.demo` file:

```bash
APP_NAME=nginx-demo
NAMESPACE=demo
IMAGE=nginx:stable
REPLICAS=1
CONTAINER_PORT=80
CLUSTER_API=https://api.openshift.example.com:6443
OC_TOKEN=sha256~your_openshift_token
```

> Replace `CLUSTER_API` and `OC_TOKEN` with your actual OpenShift cluster details.
> If you don’t want to use `oc-login`, make sure your `oc` CLI is already logged in.

### 3. Login to OpenShift

```bash
cicd oc-login --cluster-api $CLUSTER_API --token $OC_TOKEN --insecure-skip-tls-verify
```

### 4. Render manifests

```bash
cicd render --values .env.demo --outdir build/demo
```

Inspect the generated manifests:

```bash
cat build/demo/deployment.yaml
```

You’ll see Nginx wired into a Deployment, Service, and Route.

### 5. Deploy with Ansible

```bash
cicd deploy --values .env.demo
```

This will:

* Run pre-deploy checks
* Apply manifests (`oc apply -f build/demo`)
* Run post-deploy rollout status checks

### 6. Access the app

Get the OpenShift route:

```bash
oc -n demo get route nginx-demo -o jsonpath='{.spec.host}{"\n"}'
```

Open that URL in your browser → 🎉 You should see the Nginx welcome page.

### 7. Rollback (optional)

If you deploy a bad config or wrong image, you can undo it:

```bash
cicd rollback --namespace demo
```

---

That’s it — in under 15 minutes, you’ve bootstrapped a CI/CD flow that builds, deploys, and manages a live app on OpenShift, with rollback safety built in.

---

## References

* [OpenShift CLI (`oc`) docs](https://docs.openshift.com/container-platform/latest/cli_reference/openshift_cli/getting-started-cli.html)
* [Kubernetes Python Client](https://github.com/kubernetes-client/python)
* [Ansible Runner](https://ansible-runner.readthedocs.io/)

---

## License

MIT License.

---