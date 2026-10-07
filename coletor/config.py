# -*- coding: utf-8 -*-
"""Parâmetros do painel. Mudou a fonte da medição (API do novo SAR, Databricks)? Troque FONTE e mais nada."""
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CADASTRO_SISTEMAS = RAIZ / "cadastro" / "sistemas.csv"
CADASTRO_RESERVATORIOS = RAIZ / "cadastro" / "reservatorios.csv"
BOLETINS = RAIZ / "dados" / "boletins.json"  # mantido pelo vigia_boletins.py
PAINEL = RAIZ / "docs" / "dados" / "painel.json"  # o contrato que a página lê

# Módulo em coletor/fontes/ que entrega a última medição de cada reservatório.
FONTE = "sar_portal"

# Página da COMAR com os boletins de acompanhamento da alocação.
PASTA_COMAR = ("https://www.gov.br/ana/pt-br/assuntos/regulacao-e-fiscalizacao/alocacao-de-agua-e-marcos-regulatorios/"
               "alocacao-de-agua/")
PAGINA_COMAR = "https://www.gov.br/ana/pt-br/assuntos/regulacao-e-fiscalizacao/alocacao-de-agua-e-marcos-regulatorios"

# Um sistema aparece no painel enquanto o seu último boletim for, no máximo, deste número de meses mais antigo que o
# boletim mais recente publicado pela COMAR (Diego, 07/10/2026: só os açudes com boletim recente para linkar).
JANELA_BOLETIM_MESES = 2

# Conferências da medição: geram alerta ao lado do valor, nunca alteram o valor publicado pelo SAR.
DIAS_MEDICAO_ANTIGA = 30
VOLUME_PCT_MAXIMO = 110.0

FUSO = "America/Sao_Paulo"
