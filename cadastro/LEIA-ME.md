# Cadastro

Os açudes e sistemas hídricos que o painel conhece. Os arquivos `.csv` usam `;` como separador e UTF-8 com BOM, para
abrir direto no Excel. Editar, salvar no mesmo formato e rodar `py -m pytest coletor/testes`, que confere a consistência.

Entrar no cadastro não põe o açude no painel: ele aparece enquanto o sistema tiver boletim recente da COMAR
(`coletor/config.py`, `JANELA_BOLETIM_MESES`). O vigia (`coletor/vigia_boletins.py`) reconhece os boletins pelo
conteúdo do PDF (açudes, cabeçalho e UF) e avisa por issue quando um sistema entra ou sai, quando um boletim não bate
com nenhum sistema do cadastro e quando o link da página da alocação sai do ar.

Versão enxuta (07/10/2026): sem estado hidrológico, termo e resolução. O cadastro com essas colunas está no branch
`modelo-completo`.

## sistemas.csv (um sistema hídrico por linha)

| Coluna | O que é |
|---|---|
| `sistema` | identificador (o slug atual do boletim) |
| `nome`, `ufs` | como aparecem na página; as UFs também conferem o cabeçalho do boletim |
| `slugs` | nomes que o arquivo do boletim do sistema já teve na pasta da COMAR, separados por `\|`; servem para os boletins antigos, que não são lidos, e como prova a mais quando o conteúdo deixa dúvida |
| `pagina_comar` | página de alocação de água da UF (abre na campanha mais recente; não muda de um ano para o outro) |
| `nota` | nota pública, mostrada abaixo dos açudes do sistema |

## reservatorios.csv (um açude por linha)

| Coluna | O que é |
|---|---|
| `res_id` | código do açude no SAR |
| `sistema` | sistema hídrico (coluna `sistema` de sistemas.csv) |
| `nome` | nome mostrado na página |
| `nome_boletim` | como aparece no boletim ("AÇUDE ..."); é por ele que o vigia reconhece o boletim |
| `nome_sar`, `uf` | nome e UF na fonte da medição; é por eles que o coletor casa o açude |
| `lat`, `lon` | posição no mapa (serviço de mapas do SAR no SNIRH) |

## slugs_ignorados.csv

Boletins que existem na pasta da COMAR mas não entram no painel (sistema de rio, açude fora do SAR), com o motivo.
