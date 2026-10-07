# Painel dos açudes com alocação de água e marco regulatório

Situação atual dos açudes do SAR (Sistema de Acompanhamento de Reservatórios, ANA) que têm boletim de acompanhamento
da alocação de água publicado pela COMAR/ANA: a última medição de cada açude e o link para o boletim e para a página da
alocação da UF (termos, apresentações e boletins anteriores). Identidade visual do protótipo do novo SAR
([dlpena/prototipo-sar-design](https://github.com/dlpena/prototipo-sar-design), tema B2).

Em teste. Versão enxuta, para quase não precisar de manutenção; o modelo com estado hidrológico, termo de alocação e
resolução do marco está no branch `modelo-completo`, para quando a COMAR pedir.

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
  - `vigia_boletins.py` e `boletins.py`: leem todo PDF novo da pasta da COMAR e reconhecem o boletim pelo conteúdo
    (açudes com página no boletim, nome do sistema e UF do cabeçalho), qualquer que seja o nome do arquivo. Na dúvida
    não ligam: o sistema fica com o boletim anterior e sai um aviso. Testes com 242 boletins reais de 10/2025 a 08/2026
    (`coletor/testes/test_boletins.py` cobre os casos sintéticos, inclusive os falsos positivos a evitar).
- **Robôs** (`.github/workflows/`): `atualiza.yml` e `vigia.yml` de hora em hora, disparados pelo
  cron-job.org (o `schedule` do Actions atrasa e fica só como rede de segurança). Falha ou aviso vira issue.

## Disparo pelo cron-job.org

Um job para cada workflow, com POST em
`https://api.github.com/repos/dlpena/painel-marcos-regulatorios/actions/workflows/<arquivo>/dispatches`, corpo
`{"ref":"main"}` e os cabeçalhos `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28` e
`Authorization: Bearer <token>`. O token é fine-grained, com acesso só a este repositório e permissão
"Actions: Read and write". Resposta esperada: 204.

| Job | Arquivo | Quando (America/Sao_Paulo) |
|---|---|---|
| Medições | `atualiza.yml` | de hora em hora, no minuto 20 |
| Boletins | `vigia.yml` | de hora em hora, no minuto 40 (os links do cadastro são conferidos uma vez por dia) |

As duas rodadas usam a mesma fila (`concurrency: dados`) e só fazem commit quando o dado muda.

## Medição sem informação

Como no SAR, o açude sem medição nos últimos 30 dias aparece como "sem informação" (`JANELA_MEDICAO_DIAS` em
`coletor/config.py`). A API atual já aplica a regra: pedindo uma data, devolve a medição mais próxima dentro de 30 dias.
Se a COMAR quiser a última medição qualquer que seja a idade, basta pôr `BUSCA_MEDICAO_ANTERIOR_DIAS = 365` (por
exemplo): o coletor pergunta de novo pelos açudes sem informação, recuando 30 dias por vez, e a página mostra o valor
com o aviso da idade.

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
