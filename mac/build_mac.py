#!/usr/bin/env python3
"""
build_mac.py

Gera "Conversor de Videos.app" a partir de ../main.py. O ffmpeg e o ffprobe
vao embutidos, entao o app roda em qualquer Mac sem precisar instalar Python,
ffmpeg nem as dependencias. Por padrao usa os do PATH ("brew install ffmpeg");
para usar binarios estaticos (que nao dependem do Homebrew), aponte a pasta
deles na variavel FFMPEG_DIR - e o que faz a automacao do GitHub.

So funciona rodando no proprio Mac (o PyInstaller nao faz build cruzado).

Uso:
    cd mac
    pip3 install pyinstaller pywebview
    python3 build_mac.py

Depois, copie "dist/Conversor de Videos.app" para a pasta Aplicativos.
"""

import os
import shutil
import sys

if sys.platform != "darwin":
    sys.exit("build_mac.py so roda no macOS. No Windows, use build_exe.py.")

import PyInstaller.__main__

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
NOME = "Conversor de Videos"

PASTA_FFMPEG = os.environ.get("FFMPEG_DIR")
if PASTA_FFMPEG:
    ffmpeg_exe = os.path.join(PASTA_FFMPEG, "ffmpeg")
    ffprobe_exe = os.path.join(PASTA_FFMPEG, "ffprobe")
else:
    ffmpeg_exe = shutil.which("ffmpeg")
    ffprobe_exe = shutil.which("ffprobe")

if not ffmpeg_exe or not ffprobe_exe or not os.path.isfile(ffmpeg_exe) or not os.path.isfile(ffprobe_exe):
    sys.exit("ffmpeg/ffprobe nao encontrados. Rode 'brew install ffmpeg' antes (ou use FFMPEG_DIR).")

args = [
    os.path.join(RAIZ, "main.py"),
    "--noconfirm",
    "--clean",
    # pasta (onedir), o formato recomendado pelo PyInstaller para .app
    "--windowed",
    "--name", NOME,
    "--distpath", os.path.join(AQUI, "dist"),
    "--workpath", os.path.join(AQUI, "build"),
    "--specpath", AQUI,
    "--icon", os.path.join(RAIZ, "icone_conversor.icns"),
    "--add-data", f"{os.path.join(RAIZ, 'icone_conversor.png')}:.",
    "--add-binary", f"{ffmpeg_exe}:ffmpeg",
    "--add-binary", f"{ffprobe_exe}:ffmpeg",
    "--add-data", f"{os.path.join(RAIZ, 'ui')}:ui",   # a interface (HTML/CSS/JS, fontes e icones)
    "--collect-all", "webview",                       # pywebview (janela com o WebKit do Mac)
]

print("Gerando o aplicativo (pode levar alguns minutos)...\n")
PyInstaller.__main__.run(args)

destino = os.path.join(AQUI, "dist", f"{NOME}.app")
if os.path.isdir(destino):
    print(f"\nPronto: {destino}")

    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    if os.path.isdir(desktop):
        try:
            copia = os.path.join(desktop, f"{NOME}.app")
            if os.path.isdir(copia):
                shutil.rmtree(copia)
            shutil.copytree(destino, copia)
            print(f"Copiado para a Area de Trabalho: {copia}")
        except Exception as e:
            print(f"Nao consegui copiar para a Area de Trabalho automaticamente: {e}")
else:
    print("\nAlgo deu errado: o aplicativo nao foi encontrado em dist/.")
