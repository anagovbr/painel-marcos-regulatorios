# -*- coding: utf-8 -*-
"""Confere se a página no ar está em dia: a hora da última leitura do SAR no painel.json publicado não pode ter mais de
LIMITE_HORAS. Falha (e o workflow abre issue) quando tem.

    python -m coletor.confere_pagina

Pega o que as rodadas sozinhas não acusam: publicação do Pages recusada várias vezes seguidas (a rodada não falha por
isso, porque a seguinte publica de novo), cron-job.org parado ou token vencido (aí só a reserva do schedule roda, a
cada 4 a 7 horas).
"""
import sys
from datetime import datetime

import requests

from . import boletins as B

URL = "https://anagovbr.github.io/painel-marcos-regulatorios/dados/painel.json"
LIMITE_HORAS = 3


def idade_horas(painel, agora):
    return (agora - datetime.fromisoformat(painel["fontes"]["medicao"]["lido_em"])).total_seconds() / 3600


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    agora = B.hoje_brasilia()
    r = requests.get(URL, params={"conferido": agora.strftime("%Y%m%d%H%M")}, timeout=60)
    r.raise_for_status()
    p = r.json()
    h = idade_horas(p, agora)
    print(f"página no ar: última leitura em {p['fontes']['medicao']['lido_em']} ({h:.1f} h atrás)")
    if h > LIMITE_HORAS:
        print(f"::error::A página no ar está há {h:.0f} horas sem atualizar (limite: {LIMITE_HORAS} h). Veja se as "
              f"publicações do Pages estão falhando e se os disparos do cron-job.org estão chegando.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
