"""Usado pela automação quando um passo falha: publica as últimas linhas dos
logs como anotações de erro do GitHub (aparecem no resumo da execução).
uso: python .github/relatar_falha.py [arquivo1.log ...]   (sem argumentos: todos os *.log)

O GitHub corta anotações grandes, então vão só as últimas linhas, encurtadas,
e os logs mais importantes primeiro."""

import glob
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ORDEM = ["conferir_eventos", "conferir", "teste", "testes", "build", "webview2", "ffmpeg", "deps"]
LINHAS, LARGURA = 40, 200


def escapar(texto):
    return texto.replace("%", "%25").replace("\r", "").replace("\n", "%0A")


def prioridade(caminho):
    nome = os.path.splitext(os.path.basename(caminho))[0]
    return ORDEM.index(nome) if nome in ORDEM else len(ORDEM)


arquivos = sys.argv[1:] or sorted(glob.glob("*.log"), key=prioridade)
for caminho in arquivos[:8]:
    if not os.path.isfile(caminho):
        continue
    with open(caminho, encoding="utf-8", errors="replace") as f:
        linhas = [l.rstrip()[:LARGURA] for l in f if l.strip() and "━" not in l and "------" not in l]
    if linhas:
        print(f"::error title={os.path.basename(caminho)}::{escapar(chr(10).join(linhas[-LINHAS:]))}")
