# -*- coding: utf-8 -*-
"""Leitura do cadastro (cadastro/*.csv: separador ';', UTF-8 com BOM, para abrir no Excel)."""
import csv

from . import config


def _ler(caminho):
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def sistemas():
    linhas = _ler(config.CADASTRO_SISTEMAS)
    for s in linhas:
        s["slugs"] = [x for x in s["slugs"].split("|") if x]
    return {s["sistema"]: s for s in linhas}


def reservatorios():
    linhas = _ler(config.CADASTRO_RESERVATORIOS)
    for r in linhas:
        r["res_id"] = int(r["res_id"])
        r["lat"] = float(r["lat"]) if r["lat"] else None
        r["lon"] = float(r["lon"]) if r["lon"] else None
    return linhas
