#!/usr/bin/env python3
"""
build_mac.py

Gera "Conversor de Videos.app" a partir de ../main.py. O ffmpeg e o ffprobe
(instalados via "brew install ffmpeg") vao embutidos, entao o app roda em
qualquer Mac sem precisar instalar Python, ffmpeg nem as dependencias.

So funciona rodando no proprio Mac (o PyInstaller nao faz build cruzado).

Uso:
    cd mac
    pip3 install pyinstaller customtkinter pillow tkinterdnd2
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

ffmpeg_exe = shutil.which("ffmpeg")
ffprobe_exe = shutil.which("ffprobe")

if not ffmpeg_exe or not ffprobe_exe:
    sys.exit("ffmpeg/ffprobe nao encontrados no PATH. Rode 'brew install ffmpeg' antes.")

args = [
    os.path.join(RAIZ, "main.py"),
    "--noconfirm",
    "--clean",
    "--onefile",
    "--windowed",
    "--name", NOME,
    "--distpath", os.path.join(AQUI, "dist"),
    "--workpath", os.path.join(AQUI, "build"),
    "--specpath", AQUI,
    "--icon", os.path.join(RAIZ, "icone_conversor.icns"),
    "--add-data", f"{os.path.join(RAIZ, 'icone_conversor.png')}:.",
    "--add-binary", f"{ffmpeg_exe}:ffmpeg",
    "--add-binary", f"{ffprobe_exe}:ffmpeg",
    "--collect-all", "customtkinter",
    "--collect-all", "tkinterdnd2",
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
