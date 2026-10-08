# Painel dos açudes com alocação de água e marco regulatório

Situação atual dos açudes do SAR (Sistema de Acompanhamento de Reservatórios, ANA) que têm boletim de acompanhamento
da alocação de água publicado pela COMAR/ANA: a última medição de cada açude e o link para o boletim e para a página da
alocação da UF (termos, apresentações e boletins anteriores). Identidade visual do protótipo do novo SAR
([dlpena/prototipo-sar-design](https://github.com/dlpena/prototipo-sar-design), tema B2).

Painel publicado em <https://anagovbr.github.io/painel-marcos-regulatorios/>. Versão enxuta, para quase não precisar
de manutenção; o modelo com estado hidrológico, termo de alocação e
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
`https://api.github.com/repos/anagovbr/painel-marcos-regulatorios/actions/workflows/<arquivo>/dispatches`, corpo
`{"ref":"main"}` e os cabeçalhos `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28` e
`Authorization: Bearer <token>`. O token é fine-grained, com acesso só a este repositório e permissão
"Actions: Read and write". Resposta esperada: 204.

| Job | Arquivo | Quando (America/Sao_Paulo) |
|---|---|---|
| Medições | `atualiza.yml` | de hora em hora, no minuto 20 |
| Boletins | `vigia.yml` | de hora em hora, no minuto 40 (os links do cadastro são conferidos uma vez por dia) |

As duas rodadas usam a mesma fila (`concurrency: dados`) e só fazem commit quando o dado muda. Enquanto o cron-job.org
não estiver configurado, o `schedule` dos workflows roda os
dois de hora em hora, com os atrasos eventuais do Actions; depois ele pode continuar como rede de segurança.

## Última medição disponível

No SAR, o açude sem medição nos últimos 30 dias aparece como "sem informação". A API atual aplica essa regra: pedindo
uma data, devolve a medição mais próxima dentro de 30 dias. O painel mostra a última medição disponível (Diego,
07/10/2026): para o açude sem medição na janela, o coletor pergunta de novo recuando 30 dias por vez, até 2 anos
(`BUSCA_MEDICAO_ANTERIOR_DIAS = 730` em `coletor/config.py`), e a página mostra o valor com o aviso "Sem medição nos
últimos 30 dias". Sem nada em 2 anos, o açude fica "sem informação". Para voltar à regra do SAR, `0`.

## Avisos

Quando algo pede atenção (boletim que não bate com o cadastro, sistema que entra ou sai, link fora do ar) ou um robô
falha, abre-se uma issue neste repositório. Em falha que se repete, só a primeira gera issue.

**Para receber por e-mail, sem permissão nenhuma no repositório:** como ele é público, qualquer conta do GitHub pode
acompanhá-lo. Na página do repositório, **Watch > Custom > Issues** (ou **All Activity**): cada issue nova chega no
e-mail da conta. As issues também citam os usuários de `AVISAR` em `coletor/config.py`, o que notifica essas contas.

**Opcional, e-mail direto do robô** (`coletor/email_aviso.py`), para mandar os avisos de uma caixa institucional sem
depender do GitHub: quem tem acesso Admin ao repositório cadastra estes secrets em Settings > Secrets and variables >
Actions > New repository secret:

| Secret | Valor |
|---|---|
| `AVISO_SMTP_HOST` | servidor SMTP da conta remetente (Gmail: `smtp.gmail.com`) |
| `AVISO_SMTP_PORTA` | `465` (SSL) ou `587` (STARTTLS); se não cadastrar, usa 465 |
| `AVISO_SMTP_USUARIO` | endereço da conta remetente |
| `AVISO_SMTP_SENHA` | senha da conta; no Gmail, uma "senha de app" (exige verificação em duas etapas) |
| `AVISO_PARA` | quem recebe, separado por vírgula |

Depois, rode à mão **Actions > Teste do aviso por e-mail > Run workflow**: o e-mail de teste tem de chegar. Sem os
secrets, os robôs funcionam normalmente e o log diz que o e-mail não foi enviado.

## Repositório na organização da ANA

O painel começou em `dlpena/painel-marcos-regulatorios` e passou para `anagovbr/painel-marcos-regulatorios` em
08/10/2026; o endereço antigo do GitHub Pages ficou só com um aviso apontando para o novo. O que este repositório
precisa para funcionar:

- **Público.** No plano da organização, o GitHub Pages só publica a partir de repositório público, e em repositório
  público os minutos do Actions não contam na cota da organização.
- **GitHub Pages:** branch `main`, pasta `/docs`.
- **Permissão dos workflows:** Settings > Actions > General > Workflow permissions = "Read and write permissions" (os
  workflows também declaram `contents: write` e `issues: write`); os robôs gravam `dados/` e `docs/dados/` com o
  token do próprio Actions.
- **Branch `main`:** sem regra que exija pull request para o robô (ou com o `github-actions` como exceção); senão os
  commits automáticos de dados param.
- **Ações usadas:** só as do GitHub (`actions/checkout`, `actions/setup-python`).
- **Acesso de quem mantém:** Write para o dia a dia (cadastro, código, rodar os robôs à mão, responder às issues);
  Admin para configurações (Pages, secrets, permissões).
- **Token do cron-job.org:** fine-grained, com a organização como dona, acesso só a este repositório e "Actions: Read
  and write". O GitHub só deixa criar token fine-grained da organização para quem é **membro** dela (colaborador
  externo não consegue); se a organização exigir aprovação, um administrador aprova o pedido.

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
