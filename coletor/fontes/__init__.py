# -*- coding: utf-8 -*-
"""Fontes da medição. Cada módulo oferece:

    ultimas_medicoes(reservatorios, hoje, busca_anterior_dias=0) -> dict[int, dict]

`reservatorios` são as linhas do cadastro (res_id, nome_sar, uf...). O resultado leva, para cada res_id, um dicionário
com as chaves de MEDICAO (valor ausente = None), e as constantes NOME e URL_PUBLICA, que o painel mostra como
fonte. Só o módulo da fonte conhece a API; quem chama não sabe de onde veio.
"""
from importlib import import_module

MEDICAO = ("data", "volume_pct", "volume_hm3", "capacidade_hm3", "cota_m")


def carregar(nome):
    return import_module(f"coletor.fontes.{nome}")
