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

## Última medição disponível

No SAR, o açude sem medição nos últimos 30 dias aparece como "sem informação". A API atual aplica essa regra: pedindo
uma data, devolve a medição mais próxima dentro de 30 dias. O painel mostra a última medição disponível (Diego,
07/10/2026): para o açude sem medição na janela, o coletor pergunta de novo recuando 30 dias por vez, até 2 anos
(`BUSCA_MEDICAO_ANTERIOR_DIAS = 730` em `coletor/config.py`), e a página mostra o valor com o aviso "Sem medição nos
últimos 30 dias". Sem nada em 2 anos, o açude fica "sem informação". Para voltar à regra do SAR, `0`.

## Avisos

Os avisos são issues deste repositório: o vigia abre uma quando algo pede atenção, e os robôs abrem uma quando falham.
Cada issue cita os usuários de `AVISAR` em `coletor/config.py` (hoje `dlpena`); a citação notifica a pessoa por e-mail
mesmo que ela não acompanhe o repositório, porque ele é público.

## Transferência para a organização da ANA

- O endereço do GitHub Pages muda (de `dlpena.github.io/...` para `<organização>.github.io/...`) e não há
  redirecionamento: atualizar o link no SAR e onde mais tiver sido divulgado.
- O token do cron-job.org precisa dar acesso ao repositório na organização (token fine-grained com a organização como
  dona, que pode depender de aprovação de um administrador, ou um token criado pela própria ANA), e as URLs dos dois
  jobs passam a ter o nome da organização.
- Ligar o GitHub Pages no repositório transferido (branch `main`, pasta `/docs`) e conferir os workflows na aba Actions.
- Rodar `vigia.yml` à mão uma vez e conferir que a issue de aviso, se houver, cita quem está em `AVISAR`.

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
