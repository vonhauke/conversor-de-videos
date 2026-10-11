"""Gera "Conversor de Videos.exe" (arquivo único) em dist/, com ffmpeg e ffprobe embutidos.

Uso:
    pip install pyinstaller customtkinter pillow tkinterdnd2
    python build_exe.py
"""

import os
import PyInstaller.__main__

AQUI = os.path.dirname(os.path.abspath(__file__))
FFMPEG_BIN = r"C:\ffmpeg\bin"

args = [
    os.path.join(AQUI, "main.py"),
    "--noconfirm", "--clean", "--onefile", "--windowed",
    "--name", "Conversor de Videos",
    "--icon", os.path.join(AQUI, "icone_conversor.ico"),
    "--add-data", f"{os.path.join(AQUI, 'icone_conversor.png')};.",
    "--collect-all", "customtkinter",
    "--collect-all", "tkinterdnd2",
]
for nome in ("ffmpeg.exe", "ffprobe.exe"):
    caminho = os.path.join(FFMPEG_BIN, nome)
    if not os.path.isfile(caminho):
        raise SystemExit(f"{caminho} não encontrado: sem ele o .exe não leva o ffmpeg junto.")
    args += ["--add-binary", f"{caminho};ffmpeg"]

PyInstaller.__main__.run(args)
