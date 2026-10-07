# Cadastro

Os açudes e sistemas hídricos que o painel conhece. Os arquivos `.csv` usam `;` como separador e UTF-8 com BOM, para
abrir direto no Excel. Editar, salvar no mesmo formato e rodar `py -m pytest coletor/testes`, que confere a consistência.

Entrar no cadastro não põe o açude no painel: ele aparece enquanto o sistema tiver boletim recente da COMAR
(`coletor/config.py`, `JANELA_BOLETIM_MESES`). O vigia (`coletor/vigia_boletins.py`) avisa por issue quando um sistema
entra ou sai, quando aparece boletim de sistema fora do cadastro e quando um link deixa de abrir.

## sistemas.csv (um sistema hídrico por linha)

| Coluna | O que é |
|---|---|
| `sistema` | identificador (o slug atual do boletim) |
| `nome`, `ufs` | como aparecem na página |
| `slugs` | todos os nomes que o boletim do sistema já teve na pasta da COMAR, separados por `\|`; o primeiro é o atual |
| `pagina_comar` | aba da UF e da campanha na página de alocação de água |
| `campanha`, `termo_link`, `vigencia`, `reuniao` | termo de alocação publicado; vigência e reunião como escritas no termo |
| `marco`, `marco_link` | resolução do marco regulatório citada no termo (ou na página de marcos); vazio = só alocação |
| `nota` | nota pública, mostrada abaixo dos açudes do sistema |

## reservatorios.csv (um açude por linha)

| Coluna | O que é |
|---|---|
| `res_id` | código do açude no SAR |
| `sistema` | sistema hídrico (coluna `sistema` de sistemas.csv) |
| `nome` | nome mostrado na página |
| `nome_boletim` | como aparece no boletim ("AÇUDE ..."); o vigia compara com o PDF |
| `nome_sar`, `uf` | nome e UF na fonte da medição; é por eles que o coletor casa o açude |
| `lat`, `lon` | posição no mapa (serviço de mapas do SAR no SNIRH) |
| `estado`, `estado_detalhe`, `estado_data_ref`, `estado_fonte` | estado hidrológico declarado no termo de alocação, com a data do volume de referência e o item do termo; vazio quando o termo não declara ou não foi publicado |
| `termo_data_ref`, `termo_cota_m`, `termo_volume_hm3` | cota e volume de referência citados no termo (conferência da identidade do açude contra o SAR) |

## slugs_ignorados.csv

Boletins que existem na pasta da COMAR mas não entram no painel (sistema de rio, açude fora do SAR), com o motivo.
Sem esta lista, o vigia avisaria todo dia de um "sistema novo".
