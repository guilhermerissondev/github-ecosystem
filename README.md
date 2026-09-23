# github-ecosystem

Bot de manutenção da frota: onboarda **1 repo por dia** com pack de
Renovate + workflows, do mais ativo ao mais parado. Atividade legítima
(PRs de update, triagem de stale, health checks) — nenhum commit vazio.

## Fila

Repos próprios, sem fork, sem arquivados, sem `.github/renovate.json`.
Fora da fila: este hub, `tiktok-viral-generator` e `job-fit-triage`
(onboardados à mão) e `guilhermehrsilva` (perfil, sem código).

## Packs (`templates/`)

| Pack | Quando | Conteúdo |
|---|---|---|
| `full-uv` | `uv.lock` presente | renovate (uv) + ci + automerge + stale + health |
| `full-pip` | Python com `tests/` | renovate (pip) + ci + automerge + stale + health |
| `lite` | resto (notebooks, estáticos, etc.) | renovate (só actions) + stale, merge manual |

O script nunca sobrescreve o que o repo já tem (ex.: `ci.yml` próprio).
Automerge só funde PR do `renovate[bot]` após o CI ficar verde.

## Rodar

```bash
python rollout.py --dry-run            # ver a fila
python rollout.py --live               # próximo da fila
python rollout.py --live --repo NOME   # um específico
```

O workflow `rollout.yml` faz o `--live` todo dia 9h37 BRT sozinho.
Ele precisa do secret `ECOSYSTEM_TOKEN` (PAT clássico com `repo` + `workflow`):

```bash
gh secret set ECOSYSTEM_TOKEN --repo guilhermehrsilva/github-ecosystem
# cola um PAT com escopos repo + workflow
```
