"""argila.py - parte Python do design system "Argila", igual em todos os apps.

Cuida da janela (pywebview) que mostra a interface em ui/:
  - criar_janela(): abre no tamanho pedido, sem passar do tamanho da tela,
    com a cor de fundo do tema do sistema (sem "piscar" branco no escuro);
  - barra de titulo escura no Windows quando o sistema esta no modo escuro;
  - Emissor: manda eventos do Python para a interface (seguro entre threads);
  - abrir arquivos/pastas no sistema, mostrar um arquivo na pasta e ler o
    texto copiado (area de transferencia).
"""

import json
import os
import shutil
import subprocess
import sys
import threading

import webview

COR_FUNDO_CLARO, COR_FUNDO_ESCURO = "#FAF9F5", "#262624"   # = --fundo em ui/ds/tokens.css


def recurso(rel):
    """Caminho de um arquivo do app, funcionando no codigo-fonte e no .exe/.app."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


# ---------------------------------------------------------------- tema
def sistema_no_tema_escuro():
    try:
        if sys.platform == "win32":
            import winreg

            chave = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, chave) as k:
                return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
        if sys.platform == "darwin":
            r = subprocess.run(["defaults", "read", "-g", "AppleInterfaceStyle"],
                               capture_output=True, text=True, timeout=3)
            return "dark" in r.stdout.lower()
    except Exception:
        pass
    return False


def barra_de_titulo_escura(janela):
    """Windows 10/11: barra de titulo escura no modo escuro (o WebView2 nao faz sozinho)."""
    if sys.platform != "win32" or not sistema_no_tema_escuro():
        return
    try:
        import ctypes

        hwnd = janela.native.Handle.ToInt32()
        valor = ctypes.c_int(1)
        for atributo in (20, 19):   # DWMWA_USE_IMMERSIVE_DARK_MODE (atual e antigo)
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, atributo, ctypes.byref(valor), ctypes.sizeof(valor)) == 0:
                break
    except Exception:
        pass


# ---------------------------------------------------------------- janela
def _tamanho_que_cabe(largura, altura, min_largura, min_altura):
    """Nunca maior que a tela (com folga para a barra de tarefas e a de titulo)."""
    try:
        tela = webview.screens[0]
        max_w, max_h = int(tela.width * 0.94), int(tela.height * 0.86)
        largura, altura = min(largura, max_w), min(altura, max_h)
        min_largura, min_altura = min(min_largura, largura), min(min_altura, altura)
    except Exception:
        pass
    return largura, altura, min_largura, min_altura


def criar_janela(titulo, api, largura, altura, min_largura, min_altura, pagina="ui/index.html", **extra):
    largura, altura, min_largura, min_altura = _tamanho_que_cabe(largura, altura, min_largura, min_altura)
    janela = webview.create_window(
        titulo, url=recurso(pagina), js_api=api,
        width=largura, height=altura, min_size=(min_largura, min_altura),
        background_color=COR_FUNDO_ESCURO if sistema_no_tema_escuro() else COR_FUNDO_CLARO,
        text_select=False, **extra,
    )
    janela.events.shown += lambda: barra_de_titulo_escura(janela)
    return janela


URL_WEBVIEW2 = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"


def iniciar(funcao=None, args=None, icone="icone.png", debug_env="ARGILA_DEBUG", titulo="Aplicativo"):
    """Mostra a(s) janela(s) criadas e so volta quando forem fechadas."""
    caminho_icone = recurso(icone)
    try:
        webview.start(funcao, args, http_server=True, private_mode=True,
                      icon=caminho_icone if os.path.isfile(caminho_icone) else None,
                      debug=os.environ.get(debug_env) == "1")
    except Exception as erro:
        if sys.platform != "win32":
            raise
        # quase sempre: falta o Edge WebView2 (ja vem no Windows 11 e na maioria dos Windows 10)
        import ctypes
        import webbrowser

        texto = ("Para abrir, este aplicativo precisa do Microsoft Edge WebView2, "
                 "um componente gratuito da Microsoft que já vem no Windows 11.\n\n"
                 "Clique em OK para abrir a página de download. Depois de instalar, "
                 f"abra o aplicativo de novo.\n\nDetalhe técnico: {erro}")
        if ctypes.windll.user32.MessageBoxW(None, texto, titulo, 0x41) == 1:   # OK/Cancelar + aviso
            webbrowser.open(URL_WEBVIEW2)
        sys.exit(1)


TIPO_PASTA = getattr(getattr(webview, "FileDialog", None), "FOLDER", None) or webview.FOLDER_DIALOG
TIPO_ABRIR = getattr(getattr(webview, "FileDialog", None), "OPEN", None) or webview.OPEN_DIALOG
TIPO_SALVAR = getattr(getattr(webview, "FileDialog", None), "SAVE", None) or webview.SAVE_DIALOG


class Emissor:
    """Chama <objeto_js>.receber(evento) na interface. Pode ser usado de qualquer thread."""

    def __init__(self, objeto_js):
        self.objeto_js = objeto_js
        self.janela = None
        self._trava = threading.Lock()

    def __call__(self, evento):
        if self.janela is None:
            return
        codigo = f"{self.objeto_js}.receber({json.dumps(evento, ensure_ascii=False)})"
        with self._trava:
            try:
                self.janela.evaluate_js(codigo)
            except Exception:
                pass


# ---------------------------------------------------------------- sistema
def abrir_no_sistema(caminho):
    """Abre um arquivo ou pasta com o programa padrao. Levanta excecao se falhar."""
    if sys.platform == "win32":
        os.startfile(caminho)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.run(["open", caminho], check=True)
    else:
        subprocess.run(["xdg-open", caminho], check=True)


def mostrar_na_pasta(arquivo):
    """Abre a pasta do arquivo com ele ja selecionado (Explorer / Finder)."""
    arquivo = os.path.normpath(arquivo)
    if sys.platform == "win32":
        subprocess.run(["explorer", "/select,", arquivo])   # devolve 1 mesmo dando certo
    elif sys.platform == "darwin":
        subprocess.run(["open", "-R", arquivo], check=True)
    else:
        subprocess.run(["xdg-open", os.path.dirname(arquivo)], check=True)


def ler_area_de_transferencia():
    """Texto copiado (Ctrl+C) no sistema, ou "" se nao der para ler."""
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
            u32.GetClipboardData.restype = wintypes.HANDLE
            k32.GlobalLock.argtypes = [wintypes.HGLOBAL]
            k32.GlobalLock.restype = wintypes.LPVOID
            k32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
            if not u32.OpenClipboard(None):
                return ""
            try:
                h = u32.GetClipboardData(13)   # CF_UNICODETEXT
                if not h:
                    return ""
                p = k32.GlobalLock(h)
                try:
                    return ctypes.wstring_at(p) if p else ""
                finally:
                    k32.GlobalUnlock(h)
            finally:
                u32.CloseClipboard()
        if sys.platform == "darwin":
            r = subprocess.run(["pbpaste"], capture_output=True, timeout=3,
                               env=dict(os.environ, LANG="en_US.UTF-8"))
            return r.stdout.decode("utf-8", "replace")
        for cmd in (["wl-paste", "--no-newline"], ["xclip", "-o", "-selection", "clipboard"],
                    ["xsel", "--clipboard", "--output"]):
            if shutil.which(cmd[0]):
                r = subprocess.run(cmd, capture_output=True, timeout=3)
                if r.returncode == 0:
                    return r.stdout.decode("utf-8", "replace")
    except Exception:
        pass
    return ""
