# Painel dos açudes com alocação de água e marco regulatório

Situação atual dos açudes do SAR (Sistema de Acompanhamento de Reservatórios, ANA) que têm boletim de acompanhamento
da alocação de água publicado pela COMAR/ANA: última medição, estado hidrológico definido no termo de alocação e links
para o boletim, o termo e a resolução do marco regulatório. Identidade visual do protótipo do novo SAR
([dlpena/prototipo-sar-design](https://github.com/dlpena/prototipo-sar-design), tema B2).

Em teste.

## Como funciona

```
cadastro/*.csv ─────────────┐
dados/boletins.json ────────┼─> coletor/atualiza.py ─> docs/dados/painel.json ─> docs/index.html (GitHub Pages)
coletor/fontes/sar_portal.py┘
coletor/vigia_boletins.py ─> dados/boletins.json + issue com os avisos
```

- **Página** (`docs/`): HTML, CSS e JavaScript estáticos que leem só `docs/dados/painel.json`.
- **Contrato** (`docs/dados/painel.json`): sistemas no painel, açudes com a última medição, alertas e fontes com a hora
  da leitura. O histórico do Git guarda cada versão publicada.
- **Coletor** (`coletor/`): o único lugar que conhece as fontes.
  - `fontes/sar_portal.py`: API do portal do SAR. Quando sair a API do novo SAR (ou a leitura pelo Databricks),
    escreve-se outro módulo com a mesma função `ultimas_medicoes`, confere-se com
    `py -m coletor.atualiza --comparar sar_portal <novo>` e troca-se `FONTE` em `coletor/config.py`.
  - `vigia_boletins.py`: lê a pasta de boletins da COMAR, decide quem fica no painel e escreve os avisos.
- **Robôs** (`.github/workflows/`): `atualiza.yml` a cada 3 horas e `vigia.yml` uma vez por dia, disparados pelo
  cron-job.org (o `schedule` do Actions atrasa e fica só como rede de segurança). Falha ou aviso vira issue.

## Disparo pelo cron-job.org

Um job para cada workflow, com POST em
`https://api.github.com/repos/dlpena/painel-marcos-regulatorios/actions/workflows/<arquivo>/dispatches`, corpo
`{"ref":"main"}` e os cabeçalhos `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28` e
`Authorization: Bearer <token>`. O token é fine-grained, com acesso só a este repositório e permissão
"Actions: Read and write". Resposta esperada: 204.

| Job | Arquivo | Quando (America/Sao_Paulo) |
|---|---|---|
| Medições | `atualiza.yml` | minuto 20 de 0h, 3h, 6h, 9h, 12h, 15h, 18h e 21h |
| Boletins | `vigia.yml` | 7h40, todo dia |

## Rodar localmente

```
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt
.venv\Scripts\python -m pytest coletor/testes
.venv\Scripts\python -m coletor.vigia_boletins          # boletins da COMAR
.venv\Scripts\python -m coletor.atualiza --seco         # medições, sem gravar
.venv\Scripts\python -m coletor.atualiza                # grava docs/dados/painel.json
py -m http.server 8766 --directory docs                 # e abrir http://localhost:8766
```

O cadastro está descrito em [cadastro/LEIA-ME.md](cadastro/LEIA-ME.md).
