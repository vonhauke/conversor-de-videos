"""Teste de ponta a ponta do Conversor de Vídeos (automação do GitHub e uso local).

Abre a janela real (pywebview) e usa o app como uma pessoa: adiciona vídeos à
fila, converte, testa .raw de entrada e de saída, a validação dos parâmetros,
um arquivo com erro (e o "ver detalhes"), cancela um lote no meio e remove
itens da fila, conferindo a tela e os arquivos no disco.

uso: python .github/teste_e2e.py   (ffmpeg no PATH ou em FFMPEG_DIR)
Sai com código 1 se algo falhar.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # o console do Windows usa cp1252
sys.path.insert(0, RAIZ)
if os.environ.get("FFMPEG_DIR"):
    os.environ["PATH"] = os.environ["FFMPEG_DIR"] + os.pathsep + os.environ["PATH"]

import argila  # noqa: E402
import main as app  # noqa: E402

TMP = tempfile.mkdtemp(prefix="conversor-teste-")
ENTRADA = os.path.join(TMP, "entrada")
SAIDA = os.path.join(TMP, "saida")
os.makedirs(ENTRADA)
CAPTURAS = os.environ.get("ARGILA_CAPTURAS")
falhas = []


def ffmpeg(*args):
    subprocess.run([shutil.which("ffmpeg") or "ffmpeg", "-loglevel", "error", "-y", *args], check=True)


def preparar_arquivos():
    curto = os.path.join(ENTRADA, "praia.mov")
    ffmpeg("-f", "lavfi", "-i", "testsrc2=size=640x360:rate=25", "-f", "lavfi", "-i", "sine=f=330",
           "-t", "4", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", curto)
    longo = os.path.join(ENTRADA, "show completo.mp4")
    ffmpeg("-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30", "-f", "lavfi", "-i", "sine=f=440",
           "-t", "120", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", longo)
    raw = os.path.join(ENTRADA, "glitch.raw")
    ffmpeg("-f", "lavfi", "-i", "testsrc=size=320x240:rate=10", "-t", "2", "-f", "rawvideo",
           "-pix_fmt", "rgb24", raw)
    quebrado = os.path.join(ENTRADA, "quebrado.avi")
    with open(quebrado, "wb") as f:
        f.write(b"isto nao e um video" * 100)
    return curto, longo, raw, quebrado


def verificar(cond, mensagem):
    print(("ok   " if cond else "FALHA ") + mensagem, flush=True)
    if not cond:
        falhas.append(mensagem)


def roteiro(janela, api, arquivos):
    curto, longo, raw, quebrado = arquivos
    js = janela.evaluate_js

    def esperar(condicao, limite=120, nome=""):
        fim = time.time() + limite
        while time.time() < fim:
            try:
                if js(condicao):
                    return True
            except Exception:
                pass
            time.sleep(0.25)
        verificar(False, f"tempo esgotado esperando: {nome or condicao}")
        return False

    def capturar(nome):
        if CAPTURAS and sys.platform.startswith("linux"):
            time.sleep(0.6)
            subprocess.run(["import", "-window", "root", os.path.join(CAPTURAS, nome + ".png")])

    def clicar(seletor):
        js(f"document.querySelector({json.dumps(seletor)}).click()")

    def converter(nome, limite=180):
        """Clica em Converter tudo e espera o lote terminar (o evento "fim" chegar)."""
        antes = js("Conversor._s.lotes")
        clicar("#btn-converter")
        return esperar(f"Conversor._s.lotes > {antes} && !Conversor._s.convertendo", limite, nome)

    def status():
        return json.loads(js("JSON.stringify(Conversor._s.itens.map(i => i.status))"))

    def saidas():
        return sorted(os.listdir(SAIDA)) if os.path.isdir(SAIDA) else []

    try:
        esperar("document.documentElement.classList.contains('pronto')", 90, "interface pronta")
        capturar("01-vazio")

        # 1) fila: adiciona (como se tivesse arrastado), repete um para testar duplicado, remove um
        api.adicionar([curto, raw, curto])
        esperar("Conversor._s.itens.length === 2", 10, "2 itens na fila")
        verificar(not js("document.getElementById('painel-raw').classList.contains('oculto')"),
                  "painel do .raw aparece com um .raw na fila")
        api.adicionar([quebrado])
        esperar("Conversor._s.itens.length === 3", 10, "3 itens")
        clicar('.item[data-i="2"] .remover')
        verificar(esperar("Conversor._s.itens.length === 2", 10, "remover"), "remover tira o item da fila")
        api._pasta = SAIDA
        api._enviar_fila()

        # 2) validação dos parâmetros do .raw
        js("document.getElementById('raw-largura').value = 'abc'")
        clicar("#btn-converter")
        verificar(esperar("!document.getElementById('aviso').classList.contains('oculto')", 10, "aviso"),
                  "parâmetro .raw inválido mostra aviso")
        capturar("02-aviso")
        js("document.getElementById('raw-largura').value = '320'; document.getElementById('raw-altura').value = '240';"
           "document.getElementById('raw-fps').value = '10'")

        # 3) converte para MP4 (o .mov copia sem recodificar; o .raw é decodificado)
        verificar(converter("lote terminou"), "lote termina")
        capturar("03-concluido")
        verificar(status() == ["concluido", "concluido"], f"os dois arquivos concluídos ({status()})")
        verificar("praia_convertido.mp4" in saidas() and "glitch_convertido.mp4" in saidas(),
                  f"arquivos MP4 gerados ({saidas()})")
        capturar("04-concluido")

        # 4) saída RAW
        clicar('#formatos button[data-f="raw"]')
        verificar(not js("document.getElementById('raw-saida').classList.contains('oculto')"),
                  "seletor do formato de pixel da saída .raw aparece")
        js("document.getElementById('raw-saida-pix').value = 'gray'")
        clicar('.item[data-i="1"] .remover')
        esperar("Conversor._s.itens.length === 1", 10, "fica só o .mov")
        converter("raw de saída")
        verificar("praia_convertido.raw" in saidas(), "arquivo .raw de saída gerado")

        # 5) arquivo com erro e "ver detalhes"
        clicar('#formatos button[data-f="webm"]')
        api.adicionar([quebrado])
        esperar("Conversor._s.itens.length === 2", 10, "quebrado na fila")
        converter("lote com erro")
        verificar(status()[1] == "erro", "arquivo quebrado termina com erro")
        clicar('.item[data-i="1"] .ver-log')
        verificar(esperar("!document.getElementById('modal-log').classList.contains('oculto') && "
                          "document.getElementById('log-texto').textContent.length > 10", 10, "log"),
                  "'ver detalhes' mostra o log do FFmpeg")
        capturar("05-erro-log")
        clicar("#log-ok")

        # 6) cancelar no meio (vídeo longo recodificado em WEBM)
        api.adicionar([longo])
        esperar("Conversor._s.itens.length === 3", 10, "longo na fila")
        clicar('.item[data-i="0"] .remover')
        clicar('.item[data-i="0"] .remover')
        esperar("Conversor._s.itens.length === 1", 10, "fica só o longo")
        antes = js("Conversor._s.lotes")
        clicar("#btn-converter")
        esperar("Conversor._s.itens[0].status === 'convertendo' && Conversor._s.itens[0].fracao > 0.01", 120,
                "conversão andando")
        capturar("06-andando")
        clicar("#btn-cancelar")
        verificar(esperar(f"Conversor._s.lotes > {antes} && !Conversor._s.convertendo", 60, "cancelou"),
                  "cancelar para o lote")
        verificar(status() == ["cancelado"], f"item fica como cancelado ({status()})")

        erros_js = js("JSON.stringify(window.__erros)")
        verificar(erros_js in ("[]", None), f"sem erros de JavaScript ({erros_js})")
    except Exception:
        traceback.print_exc()
        falhas.append("exceção no roteiro")
    finally:
        janela.destroy()


def main():
    arquivos = preparar_arquivos()
    emitir = argila.Emissor("Conversor")
    api = app.Api(emitir)
    janela = argila.criar_janela("Conversor de Vídeos (teste)", api, 780, 780, 640, 560)
    api._janela = emitir.janela = janela
    # abre pelo mesmo caminho do app de verdade (argila.iniciar, com o ícone)
    argila.iniciar(roteiro, (janela, api, arquivos), icone="icone_conversor.png", titulo=app.TITULO)
    shutil.rmtree(TMP, ignore_errors=True)
    if falhas:
        print(f"\n{len(falhas)} falha(s):\n- " + "\n- ".join(falhas))
        sys.exit(1)
    print("\nTudo certo: o conversor funcionou de ponta a ponta.")


if __name__ == "__main__":
    main()
