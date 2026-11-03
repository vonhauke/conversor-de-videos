"""Usado pela automação quando um passo falha: publica as últimas linhas dos
logs como anotações de erro do GitHub (aparecem no resumo da execução).
uso: python .github/relatar_falha.py arquivo1.log [arquivo2.log ...]"""

import os
import sys


def escapar(texto):
    return texto.replace("%", "%25").replace("\r", "").replace("\n", "%0A")


for caminho in sys.argv[1:]:
    if not os.path.isfile(caminho):
        continue
    with open(caminho, encoding="utf-8", errors="replace") as f:
        linhas = [l.rstrip() for l in f if l.strip()]
    if linhas:
        print(f"::error title=Últimas linhas de {os.path.basename(caminho)}::{escapar(chr(10).join(linhas[-60:]))}")
