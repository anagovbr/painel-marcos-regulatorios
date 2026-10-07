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

# Regra do SAR (Nordeste e Semiárido): sem medição nos últimos 30 dias, o açude fica "sem informação". O painel aplica a
# mesma regra, qualquer que seja a fonte (a API atual já aplica; a do novo SAR pode não aplicar).
JANELA_MEDICAO_DIAS = 30
# Diego, 07/10/2026: mostrar a última medição disponível, mesmo com mais de 30 dias, com o aviso. Para o açude sem
# medição na janela, o coletor busca a última medição até este número de dias atrás (recua 30 dias por consulta; o
# limite evita dezenas de consultas por hora para um açude parado há anos). 0 = segue o SAR (sem informação).
BUSCA_MEDICAO_ANTERIOR_DIAS = 730

# Conferência da medição: gera alerta ao lado do valor, nunca altera o valor publicado pelo SAR.
VOLUME_PCT_MAXIMO = 110.0

FUSO = "America/Sao_Paulo"

# Quem recebe os avisos (issues): usuários do GitHub citados em cada issue. A citação notifica a pessoa por e-mail mesmo
# sem acompanhar o repositório (que é público), o que vale também depois da transferência para a organização da ANA.
AVISAR = ["dlpena"]


def citacao():
    """Linha 'cc @fulano @beltrano' para o fim das issues (vazia se ninguém estiver na lista)."""
    return ("cc " + " ".join("@" + u for u in AVISAR)) if AVISAR else ""
