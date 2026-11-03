"""Conversor de Vídeos.

Converte, em lote, entre mp4, mov, avi, mkv, webm e .raw (vídeo bruto sem
cabeçalho, usado em fluxos de glitch art). Usa o FFmpeg (embutido no .exe/.app,
ou o do sistema).

Interface: HTML/CSS em ui/ (design system "Argila", em ui/ds/), mostrada numa
janela nativa pelo pywebview (Edge WebView2 no Windows, WebKit no Mac). Os
arquivos podem ser arrastados para qualquer ponto da janela ou escolhidos pelo
botão "Adicionar arquivos" / clique na área de soltar.

Este arquivo cuida da fila e do lote; os comandos do FFmpeg ficam em
ffmpeg_utils.py e a parte comum da janela em argila.py.
"""

import os
import sys
import threading
import time

import argila
import ffmpeg_utils as fu

TITULO = "Conversor de Vídeos"
RAW_EXTENSIONS = {".raw"}

STATUS_PENDENTE = "pendente"
STATUS_CONVERTENDO = "convertendo"
STATUS_CONCLUIDO = "concluido"
STATUS_ERRO = "erro"
STATUS_CANCELADO = "cancelado"


def _format_size(path):
    try:
        size = os.path.getsize(path)
    except OSError:
        return ""
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            texto = f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
            return texto.replace(".", ",")
        size /= 1024
    return ""


def _is_raw(path):
    return os.path.splitext(path)[1].lower() in RAW_EXTENSIONS


def _unique_output_path(input_path, out_dir, out_format, used_names):
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    candidate = f"{base_name}_convertido.{out_format}"
    counter = 1
    while candidate in used_names:
        candidate = f"{base_name}_convertido_{counter}.{out_format}"
        counter += 1
    used_names.add(candidate)
    return os.path.join(out_dir, candidate)


class Api:
    """Métodos chamados pela interface (window.pywebview.api.<metodo>).
    Atributos com _ ficam escondidos do JavaScript."""

    def __init__(self, emitir):
        self._emitir = emitir
        self._janela = None
        self._arquivos = []          # [{"path", "status", "log", "fracao"}]
        self._pasta = ""
        self._cancel_event = threading.Event()
        self._convertendo = False
        self._trava = threading.Lock()

    # ----- estado -> interface -----
    def _item_publico(self, item):
        path = item["path"]
        return {
            "path": path,
            "nome": os.path.basename(path),
            "ext": os.path.splitext(path)[1].lstrip(".").upper()[:4] or "?",
            "tamanho": _format_size(path),
            "raw": _is_raw(path),
            "status": item["status"],
            "fracao": item.get("fracao", 0),
        }

    def _enviar_fila(self):
        self._emitir({"tipo": "fila", "itens": [self._item_publico(i) for i in self._arquivos],
                      "pasta": self._pasta})

    def _status(self, path, status, fracao=None, inicio=False):
        for item in self._arquivos:
            if item["path"] == path:
                item["status"] = status
                item["fracao"] = fracao or 0
        self._emitir({"tipo": "item", "path": path, "status": status, "fracao": fracao or 0, "inicio": inicio})

    # ----- chamados pelo JavaScript -----
    def estado_inicial(self):
        return {"formatos": fu.VIDEO_FORMATS, "pix_fmts": fu.RAW_PIXEL_FORMATS,
                "ffmpeg": bool(fu.find_ffmpeg()), "mac": sys.platform == "darwin"}

    def escolher_arquivos(self):
        if self._convertendo:
            return
        escolhidos = self._janela.create_file_dialog(argila.TIPO_ABRIR, allow_multiple=True)
        if escolhidos:
            self.adicionar(list(escolhidos))

    def adicionar(self, paths):
        """Também usado pelo arrastar e soltar (ver ao_soltar)."""
        if self._convertendo:
            return
        paths = [os.path.normpath(p) for p in paths if p and os.path.isfile(p)]
        if not paths:
            return
        with self._trava:
            existentes = {item["path"] for item in self._arquivos}
            for path in paths:
                if path not in existentes:
                    existentes.add(path)
                    self._arquivos.append({"path": path, "status": STATUS_PENDENTE, "log": "", "fracao": 0})
            if not self._pasta:
                self._pasta = os.path.dirname(paths[0])
        self._enviar_fila()

    def remover(self, path):
        if self._convertendo:
            return
        with self._trava:
            self._arquivos = [i for i in self._arquivos if i["path"] != path]
        self._enviar_fila()

    def trocar_pasta(self):
        escolha = self._janela.create_file_dialog(
            argila.TIPO_PASTA, directory=self._pasta if os.path.isdir(self._pasta) else "")
        if escolha:
            self._pasta = os.path.normpath(escolha[0] if isinstance(escolha, (list, tuple)) else escolha)
            self._enviar_fila()

    def abrir_pasta(self):
        if self._pasta:
            try:
                argila.abrir_no_sistema(self._pasta)
            except Exception as e:
                self._emitir({"tipo": "aviso", "titulo": "Não foi possível abrir a pasta", "texto": str(e)[:200]})

    def ver_log(self, path):
        item = next((f for f in self._arquivos if f["path"] == path), None)
        if not item or not item["log"]:
            return ""
        return "\n".join(item["log"].strip().splitlines()[-25:])

    def cancelar(self):
        self._cancel_event.set()

    def converter(self, opcoes):
        """Valida e começa o lote. Devolve {"titulo", "texto"} se algo impedir."""
        if self._convertendo:
            return None
        if not self._arquivos:
            return {"titulo": "Atenção", "texto": "Adicione ao menos um arquivo."}
        out_dir = (self._pasta or "").strip()
        if not out_dir:
            return {"titulo": "Atenção", "texto": "Escolha uma pasta de saída."}
        if not fu.find_ffmpeg():
            return {"titulo": "FFmpeg não encontrado",
                    "texto": "Instale o FFmpeg e garanta que o comando 'ffmpeg' funcione no terminal "
                             "antes de usar este conversor."}

        raw_in = None
        if any(_is_raw(i["path"]) for i in self._arquivos):
            r = opcoes.get("raw_in") or {}
            try:
                raw_in = {
                    "width": int(str(r.get("largura", "")).strip()),
                    "height": int(str(r.get("altura", "")).strip()),
                    "pix_fmt": r.get("pix_fmt") or "rgb24",
                    "fps": float(str(r.get("fps", "")).strip().replace(",", ".")),
                }
            except ValueError:
                return {"titulo": "Atenção", "texto": "Largura, altura e FPS do .raw devem ser números."}

        out_format = opcoes.get("formato") or "mp4"
        if out_format not in fu.VIDEO_FORMATS:
            out_format = "mp4"
        raw_out = {"pix_fmt": opcoes.get("raw_out_pix") or "rgb24"} if out_format == "raw" else None

        for item in self._arquivos:
            item["status"], item["log"], item["fracao"] = STATUS_PENDENTE, "", 0
        self._cancel_event.clear()
        self._convertendo = True
        self._emitir({"tipo": "inicio"})
        threading.Thread(target=self._run_batch_thread,
                         args=(list(self._arquivos), out_dir, out_format, raw_in, raw_out),
                         daemon=True).start()
        return None

    # ----- o lote -----
    def _run_batch_thread(self, items, out_dir, out_format, raw_in, raw_out):
        total = len(items)
        used_names = set()
        done_count = 0
        error_count = 0
        os.makedirs(out_dir, exist_ok=True)

        for index, item in enumerate(items):
            path = item["path"]

            if self._cancel_event.is_set():
                self._status(path, STATUS_CANCELADO)
                continue

            self._status(path, STATUS_CONVERTENDO, 0, inicio=True)
            self._emitir({"tipo": "geral", "fracao": index / total,
                          "rotulo": f"Convertendo {index + 1} de {total} · {os.path.basename(path)}"})

            output_path = _unique_output_path(path, out_dir, out_format, used_names)
            item_raw_in = raw_in if _is_raw(path) else None

            if item_raw_in is not None:
                total_duration = fu.estimate_raw_duration_seconds(
                    path, item_raw_in["width"], item_raw_in["height"],
                    item_raw_in["pix_fmt"], item_raw_in["fps"],
                )
            else:
                total_duration = fu.probe_duration_seconds(path)

            base_progress = index / total
            ultimo = [0.0]

            def on_progress(fraction, base=base_progress, path=path):
                agora = time.monotonic()
                if agora - ultimo[0] < 0.12:   # no máximo ~8 atualizações por segundo
                    return
                ultimo[0] = agora
                self._status(path, STATUS_CONVERTENDO, fraction)
                self._emitir({"tipo": "geral", "fracao": base + (fraction or 0) / total})

            # 1º: copia sem recodificar (quando dá); 2º: recodifica com aceleração de vídeo;
            # 3º: recodifica pelo processador, que sempre funciona.
            tentativas = ({}, {"allow_copy": False}, {"allow_copy": False, "use_hw": False})
            ja_tentou = set()
            success, log, cancelled = False, "", False
            for opcoes in tentativas:
                cmd = fu.build_command(path, output_path, out_format, item_raw_in, raw_out, **opcoes)
                if tuple(cmd) in ja_tentou:
                    continue
                ja_tentou.add(tuple(cmd))
                success, log, cancelled = fu.run_conversion(
                    cmd, on_progress, total_duration, self._cancel_event.is_set
                )
                if success or cancelled:
                    break

            if cancelled:
                self._status(path, STATUS_CANCELADO)
            elif success:
                done_count += 1
                self._status(path, STATUS_CONCLUIDO, 1)
            else:
                error_count += 1
                item["log"] = log
                self._status(path, STATUS_ERRO)

            self._emitir({"tipo": "geral", "fracao": (index + 1) / total})

        self._on_batch_done(done_count, error_count, total)

    def _on_batch_done(self, done_count, error_count, total):
        self._convertendo = False
        if self._cancel_event.is_set():
            resumo = f"Cancelado. {done_count}/{total} concluídos antes de parar."
        elif error_count:
            resumo = f"Concluído com erros: {done_count} ok, {error_count} com erro de {total}."
        else:
            resumo = f"Concluído: {done_count}/{total} arquivos convertidos."
        self._emitir({"tipo": "fim", "resumo": resumo, "feitos": done_count,
                      "erros": error_count, "total": total})


def ao_soltar(api):
    """Arquivos arrastados para a janela: o pywebview informa o caminho completo."""
    def tratar(evento):
        arquivos = (evento.get("dataTransfer") or {}).get("files") or []
        api.adicionar([f.get("pywebviewFullPath") for f in arquivos])
    return tratar


def ligar_arrastar_e_soltar(janela, api):
    try:
        from webview.dom import DOMEventHandler

        janela.dom.document.events.drop += DOMEventHandler(ao_soltar(api), True, True)
    except Exception:
        pass   # sem arrastar e soltar, o botão de escolher arquivos continua valendo


def main():
    emitir = argila.Emissor("Conversor")
    api = Api(emitir)
    janela = argila.criar_janela(TITULO, api, 780, 780, 640, 560)
    api._janela = emitir.janela = janela
    janela.events.loaded += lambda: ligar_arrastar_e_soltar(janela, api)
    argila.iniciar(icone="icone_conversor.png", titulo=TITULO)


if __name__ == "__main__":
    main()
