#!/usr/bin/env python3
"""Onboarda 1 repo/dia no ecossistema de manutenção.

Fila: repos próprios, sem fork, sem arquivados, sem `.github/renovate.json`,
do mais recentemente ativo para o mais parado. PRs de update contam como
atividade legítima; nada aqui cria commit vazio.

Uso:
    python rollout.py --dry-run            # mostra a fila, não escreve nada
    python rollout.py --live               # onboarda o próximo da fila
    python rollout.py --live --repo NOME   # onboarda um repo específico

Autenticação via `gh` (usa GH_TOKEN quando definido).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

OWNER = "guilhermehrsilva"
BRANCH = "chore/ecosystem-pack"
GIT_AUTHOR = "guilhermehrsilva"
GIT_EMAIL = "guilhermehrsilva@users.noreply.github.com"

# Já onboardados à mão ou especiais: hub, portfólio com pack, perfil.
EXCLUDE = {"github-ecosystem", "tiktok-viral-generator", "job-fit-triage", "guilhermehrsilva"}

TEMPLATES = Path(__file__).resolve().parent / "templates"

PYTHON_MARKERS = {"pyproject.toml", "setup.py", "setup.cfg", "requirements.txt",
                  "Pipfile", "poetry.lock", "uv.lock"}
TEST_MARKERS = {"pytest.ini", "tox.ini", "conftest.py"}


def gh(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args], capture_output=True, text=True)


def list_candidates() -> list[dict]:
    p = gh("repo", "list", OWNER, "--limit", "200", "--json",
           "name,isFork,isArchived,defaultBranchRef,pushedAt")
    p.check_returncode()
    repos = json.loads(p.stdout or "[]")
    out = [r for r in repos
           if not r["isFork"] and not r["isArchived"] and r["name"] not in EXCLUDE]
    out.sort(key=lambda r: r.get("pushedAt") or "", reverse=True)
    return out


def has_renovate(repo: str) -> bool:
    p = gh("api", f"repos/{OWNER}/{repo}/contents/.github/renovate.json")
    return p.returncode == 0


def has_open_pack_pr(repo: str) -> bool:
    p = gh("pr", "list", "--repo", f"{OWNER}/{repo}", "--head", BRANCH,
           "--state", "open", "--json", "number")
    if p.returncode != 0:
        return False
    return len(json.loads(p.stdout or "[]")) > 0


def root_names(repo: str) -> set[str]:
    p = gh("api", f"repos/{OWNER}/{repo}/contents/", "--jq", ".[].name")
    if p.returncode != 0:
        return set()
    return set(p.stdout.split())


def detect_pack(names: set[str]) -> tuple[str, str]:
    if "uv.lock" in names:
        return "python-uv", "full-uv"
    if names & PYTHON_MARKERS:
        if "tests" in names or names & TEST_MARKERS or any(
                n.startswith("test_") and n.endswith(".py") for n in names):
            return "python-pip", "full-pip"
        return "python-sem-testes", "lite"
    return "outros", "lite"


def copy_pack(pack: str, dest: Path) -> list[str]:
    src = TEMPLATES / pack / ".github"
    added = []
    for f in sorted(src.rglob("*")):
        if f.is_dir():
            continue
        rel = f.relative_to(TEMPLATES / pack)
        target = dest / rel
        if target.exists():
            continue  # nunca sobrescreve o que o repo já tem (ex.: ci.yml próprio)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, target)
        added.append(str(rel))
    return added


def open_pr(repo: str, default_branch: str, pack: str) -> str:
    with tempfile.TemporaryDirectory(prefix="rollout-") as tmp:
        clone = Path(tmp) / repo
        r = subprocess.run(
            ["gh", "repo", "clone", f"{OWNER}/{repo}", str(clone)],
            capture_output=True, text=True)
        r.check_returncode()
        subprocess.run(["git", "-C", str(clone), "checkout", default_branch],
                       capture_output=True, check=True)
        added = copy_pack(pack, clone)
        if not added:
            return f"{repo}: nada novo a adicionar (pack já presente)"
        cfg = ["-c", f"user.name={GIT_AUTHOR}", "-c", f"user.email={GIT_EMAIL}"]
        subprocess.run(["git", "-C", str(clone), "checkout", "-B", BRANCH],
                       capture_output=True, check=True)
        subprocess.run(["git", "-C", str(clone), *cfg, "add", ".github"],
                       capture_output=True, check=True)
        subprocess.run(
            ["git", "-C", str(clone), *cfg, "commit", "-m",
             "chore: bot de manutencao (pack do ecossistema)"],
            capture_output=True, check=True)
        subprocess.run(
            ["git", "-C", str(clone), "push", "-u", "origin", BRANCH],
            capture_output=True, check=True)
        body = (
            "Pack do ecossistema de manutenção (1 repo/dia):\n\n"
            "- **renovate.json**: updates de deps + github-actions toda segunda 9h BRT\n"
            "- **automerge.yml**: funde PRs do Renovate após o CI ficar verde\n"
            "- **stale.yml**: marca issues/PRs parados há 30d, fecha após 7d\n"
            + ("- **ci.yml/health.yml**: suíte semanal\n" if pack.startswith("full") else "") +
            "\nCI existente preservado; nada no código muda."
        )
        p = subprocess.run(
            ["gh", "pr", "create", "--repo", f"{OWNER}/{repo}",
             "--title", "chore: bot de manutenção (pack do ecossistema)",
             "--body", body, "--head", BRANCH, "--base", default_branch],
            capture_output=True, text=True, cwd=str(clone))
        p.check_returncode()
        return p.stdout.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--repo", default="")
    args = ap.parse_args()
    if args.live and args.dry_run:
        print("escolha --live ou --dry-run", file=sys.stderr)
        return 2
    live = args.live

    repos = list_candidates()
    rows = []
    for r in repos:
        name = r["name"]
        onboarded = has_renovate(name) or has_open_pack_pr(name)
        names = root_names(name) if not onboarded else set()
        stack, pack = ("-", "-") if onboarded else detect_pack(names)
        rows.append({"name": name, "pushed": (r.get("pushedAt") or "")[:10],
                     "status": "onboarded" if onboarded else "na fila",
                     "stack": stack, "pack": pack})

    print(f"{'repo':32} {'push':10} {'status':10} {'stack':18} pack")
    for row in rows:
        print(f"{row['name']:32} {row['pushed']:10} {row['status']:10} "
              f"{row['stack']:18} {row['pack']}")

    if args.repo:
        pick = next((x for x in rows if x["name"] == args.repo), None)
        if pick is None:
            print(f"repo {args.repo} fora da fila (fork? arquivado? excluído?)",
                  file=sys.stderr)
            return 1
    else:
        pick = next((x for x in rows if x["status"] == "na fila"), None)
        if pick is None:
            print("\nFila esgotada: tudo onboarded.")
            return 0

    print(f"\nEscolhido: {pick['name']} (pack {pick['pack']})")
    if not live:
        print("dry-run: nada foi escrito. Rode com --live para abrir o PR.")
        return 0

    info = next(r for r in repos if r["name"] == pick["name"])
    branch = (info.get("defaultBranchRef") or {}).get("name", "main")
    print(open_pr(pick["name"], branch, pick["pack"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
