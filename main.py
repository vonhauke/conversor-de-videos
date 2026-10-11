"""Conversor de Vídeos - GUI em CustomTkinter.

Converte, em lote, entre mp4, mov, avi, mkv, webm e .raw (vídeo bruto sem
cabeçalho, usado em fluxos de glitch art). Usa o FFmpeg instalado no sistema.

Layout e cores seguem design/maquete_conversor.png (grafite, marfim e âmbar).
Os arquivos podem ser arrastados do Explorer para qualquer ponto da janela
(tkinterdnd2) ou escolhidos pelo botão "+ Adicionar arquivos" / clique na área
de soltar, que abrem o diálogo de seleção de arquivos.
"""

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageTk
from tkinterdnd2 import DND_FILES, TkinterDnD

import ffmpeg_utils as fu

# ---------------------------------------------------------------- paleta
COL_BG = "#14171c"
COL_CARD = "#1c2027"
COL_CARD_ALT = "#232831"
COL_DROP_BG = "#171a20"
COL_DROP_BORDER = "#3a404b"
COL_BADGE_BG = "#2a2f38"
COL_TEXT = "#ece6d8"
COL_SUB = "#8b919b"
COL_MUTED = "#6c727c"
COL_DEST = "#b8b2a5"
COL_AMBER = "#d4a24c"
COL_AMBER_TEXT = "#1a1408"
COL_OK = "#7fb38a"
COL_ERR = "#e07a6a"
COL_X = "#4c525c"
COL_TRACK = "#2a2f38"
COL_TRACK_THIN = "#2f343e"

FONT = "Segoe UI"

RAW_EXTENSIONS = {".raw"}

STATUS_PENDENTE = "Pendente"
STATUS_CONVERTENDO = "Convertendo..."
STATUS_CONCLUIDO = "Concluído"
STATUS_ERRO = "Erro"
STATUS_CANCELADO = "Cancelado"

_HERE = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.join(_HERE, "icone_conversor.png")


def _format_size(path):
    try:
        size = os.path.getsize(path)
    except OSError:
        return ""
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return ""


class FileRow(ctk.CTkFrame):
    """Uma linha da fila: badge da extensão, nome/tamanho, status e remover."""

    def __init__(self, master, path, on_remove, on_view_log):
        super().__init__(master, fg_color="transparent", corner_radius=10)
        self.path = path
        self.status = STATUS_PENDENTE
        self.log = ""
        self._on_remove = on_remove
        self._on_view_log = on_view_log

        self.grid_columnconfigure(1, weight=1)

        ext = os.path.splitext(path)[1].lstrip(".").upper()[:4] or "?"
        ctk.CTkLabel(
            self, text=ext, width=40, height=40, corner_radius=8,
            fg_color=COL_BADGE_BG, text_color=COL_DEST,
            font=(FONT, 10, "bold"),
        ).grid(row=0, column=0, rowspan=2, padx=(10, 12), pady=10)

        self.name_label = ctk.CTkLabel(
            self, text=os.path.basename(path), text_color=COL_TEXT,
            font=(FONT, 13), anchor="w",
        )
        self.name_label.grid(row=0, column=1, sticky="ew", pady=(10, 0))

        self.meta_label = ctk.CTkLabel(
            self, text=_format_size(path), text_color=COL_MUTED,
            font=(FONT, 11), anchor="w",
        )
        self.meta_label.grid(row=1, column=1, sticky="ew", pady=(0, 10))

        self.progress = ctk.CTkProgressBar(
            self, height=4, corner_radius=9,
            fg_color=COL_TRACK_THIN, progress_color=COL_AMBER,
        )
        self.progress.set(0)

        self.status_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.status_frame.grid(row=0, column=2, rowspan=2, padx=(8, 2))
        self.status_label = ctk.CTkLabel(
            self.status_frame, text="Na fila", text_color=COL_MUTED,
            font=(FONT, 12, "bold"),
        )
        self.status_label.pack(side="left")
        self.detail_btn = ctk.CTkButton(
            self.status_frame, text="ver detalhes", width=1, height=18,
            fg_color="transparent", hover_color=COL_CARD_ALT,
            text_color=COL_ERR, font=(FONT, 12, "bold", "underline"),
            command=lambda: self._on_view_log(self.path),
        )

        ctk.CTkButton(
            self, text="✕", width=20, height=20, fg_color="transparent",
            hover_color=COL_CARD_ALT, text_color=COL_X, font=(FONT, 12),
            command=lambda: self._on_remove(self.path),
        ).grid(row=0, column=3, rowspan=2, padx=(4, 10))

    def set_status(self, status, fraction=None):
        self.status = status
        self.detail_btn.pack_forget()
        self.progress.grid_forget()
        self.meta_label.grid()

        if status == STATUS_PENDENTE:
            self.status_label.configure(text="Na fila", text_color=COL_MUTED)
            self.configure(fg_color="transparent")
        elif status == STATUS_CONVERTENDO:
            pct = int((fraction or 0) * 100)
            self.status_label.configure(text=f"Convertendo · {pct}%", text_color=COL_AMBER)
            self.progress.set(fraction or 0)
            self.progress.grid(row=1, column=1, sticky="ew", pady=(0, 10))
            self.meta_label.grid_remove()
            self.configure(fg_color=COL_CARD_ALT)
        elif status == STATUS_CONCLUIDO:
            self.status_label.configure(text="✓ Concluído", text_color=COL_OK)
            self.configure(fg_color="transparent")
        elif status == STATUS_ERRO:
            self.status_label.configure(text="Erro ·", text_color=COL_ERR)
            self.detail_btn.pack(side="left", padx=(4, 0))
            self.configure(fg_color="transparent")
        elif status == STATUS_CANCELADO:
            self.status_label.configure(text="Cancelado", text_color=COL_MUTED)
            self.configure(fg_color="transparent")

    def set_progress_fraction(self, fraction):
        if self.status == STATUS_CONVERTENDO:
            self.progress.set(fraction or 0)
            self.status_label.configure(text=f"Convertendo · {int((fraction or 0) * 100)}%")


class App(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()
        self._dnd_ok = self._ativar_arrastar_e_soltar()
        ctk.set_appearance_mode("dark")

        self.title("Conversor de Vídeos")
        self._ajustar_janela(760, 800, 720, 580)
        self._altura_max_real = self._cliente_max_real()[1]
        self.configure(fg_color=COL_BG)
        self._set_window_icon()

        # Cada item: {"path", "status", "log", "row"}
        self.files = []

        self.output_dir = tk.StringVar()
        self.output_format = tk.StringVar(value="mp4")

        # Parâmetros aplicados a QUALQUER .raw de entrada do lote (decodificação).
        # Assume-se que todos os .raw do lote foram exportados com as mesmas
        # configurações; se não for o caso, converta-os em lotes separados.
        self.raw_in_width = tk.StringVar(value="1920")
        self.raw_in_height = tk.StringVar(value="1080")
        self.raw_in_pix_fmt = tk.StringVar(value="rgb24")
        self.raw_in_fps = tk.StringVar(value="30")

        # Parâmetro para quando o FORMATO DE SAÍDA é .raw (codificação)
        self.raw_out_pix_fmt = tk.StringVar(value="rgb24")

        self._cancel_event = threading.Event()
        self._converting = False
        self._format_buttons = {}
        self._cor_borda_drop = COL_DROP_BORDER

        self._build_ui()
        self._encaixar_conteudo()
        self._check_ffmpeg()

    def _ativar_arrastar_e_soltar(self):
        """Faz a janela inteira aceitar arquivos arrastados do Explorer."""
        try:
            self.TkdndVersion = TkinterDnD._require(self)
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", self._on_drop)
            self.dnd_bind("<<DropEnter>>", lambda e: self._destacar_area(True))
            self.dnd_bind("<<DropLeave>>", lambda e: self._destacar_area(False))
            return True
        except Exception:
            return False  # sem arrastar e soltar, o botão de escolher arquivos continua valendo

    def _destacar_area(self, ativo):
        self._cor_borda_drop = COL_AMBER if ativo else COL_DROP_BORDER
        self.drop_zone.event_generate("<Configure>")

    def _on_drop(self, event):
        self._destacar_area(False)
        self._add_paths(self.tk.splitlist(event.data))
        return event.action

    @staticmethod
    def _area_util(tela_w, tela_h):
        """Área de trabalho em pixels reais (sem a barra de tarefas); estimativa se não achar."""
        try:
            import ctypes
            from ctypes import wintypes
            r = wintypes.RECT()
            if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(r), 0):
                return r.right - r.left, r.bottom - r.top
        except Exception:
            pass
        return tela_w, int(tela_h * 0.93)

    def _cliente_max_real(self):
        """Maior área (em pixels reais) que o conteúdo da janela pode ocupar, já descontando
        a barra de título e as bordas do Windows e uma folga nas margens da tela."""
        escala = self._get_window_scaling()
        util_w, util_h = self._area_util(self.winfo_screenwidth(), self.winfo_screenheight())
        return util_w - int(24 * escala) - 16, util_h - int(52 * escala) - 16

    def _encaixar_conteudo(self):
        """Em telas baixas, reduz a escala dos elementos para que nada fique cortado,
        mesmo com todos os painéis (.raw de entrada e de saída) abertos ao mesmo tempo."""
        self.raw_in_panel.grid(row=2, column=0, sticky="ew", padx=26, pady=(0, 14))
        self.raw_out_panel.grid(row=4, column=0, sticky="ew", padx=26, pady=(0, 14))
        self.update_idletasks()
        escala = self._get_window_scaling()
        lista_minima = 130 * escala
        necessario = self.winfo_reqheight() - self.body.winfo_reqheight() + lista_minima
        self._refresh_visibility()

        if necessario > self._altura_max_real:
            fator = max(0.7, self._altura_max_real / necessario)
            ctk.set_widget_scaling(fator)
            self.update_idletasks()

    def _ajustar_janela(self, largura, altura, min_largura, min_altura):
        """Abre a janela no tamanho ideal, mas nunca maior que a tela do computador em uso,
        centralizada. O CustomTkinter multiplica os valores pela escala do Windows (DPI),
        então converto o espaço disponível (pixels reais) para o tamanho "lógico"."""
        escala = self._get_window_scaling()
        max_w, max_h = (v / escala for v in self._cliente_max_real())

        largura, altura = min(largura, int(max_w)), min(altura, int(max_h))
        self.minsize(min(min_largura, largura), min(min_altura, altura))
        self.geometry(f"{largura}x{altura}")

        util_w, util_h = self._area_util(self.winfo_screenwidth(), self.winfo_screenheight())
        x = max((util_w - int(largura * escala) - int(24 * escala)) // 2, 0)
        y = max((util_h - int(altura * escala) - int(52 * escala)) // 2, 0)
        self.geometry(f"+{x}+{y}")

    def _set_window_icon(self):
        if not os.path.exists(ICON_PATH):
            return
        try:
            self._icon_ref = ImageTk.PhotoImage(Image.open(ICON_PATH))
            self.iconphoto(True, self._icon_ref)
        except (tk.TclError, OSError):
            pass

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_header()
        self._build_body()
        self.raw_in_panel = self._build_raw_in_panel()
        self._build_format_row()
        self.raw_out_panel = self._build_raw_out_panel()
        self._build_dest_row()
        self._build_bottom_bar()

        self._refresh_visibility()
        self._refresh_bottom_bar()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=26, pady=(22, 14))
        header.grid_columnconfigure(1, weight=1)

        if os.path.exists(ICON_PATH):
            icon_image = ctk.CTkImage(Image.open(ICON_PATH), size=(36, 36))
            ctk.CTkLabel(header, image=icon_image, text="").grid(
                row=0, column=0, rowspan=2, padx=(0, 12)
            )

        ctk.CTkLabel(
            header, text="Conversor de Vídeos", text_color=COL_TEXT,
            font=(FONT, 20, "bold"), anchor="w",
        ).grid(row=0, column=1, sticky="w")
        self.subtitle_label = ctk.CTkLabel(
            header, text="Converta vários vídeos de uma vez", text_color=COL_SUB,
            font=(FONT, 13), anchor="w",
        )
        self.subtitle_label.grid(row=1, column=1, sticky="w")

        ctk.CTkButton(
            header, text="+ Adicionar arquivos", fg_color=COL_CARD_ALT,
            hover_color=COL_BADGE_BG, text_color=COL_TEXT, corner_radius=10,
            height=36, font=(FONT, 13, "bold"), command=self._add_files,
        ).grid(row=0, column=2, rowspan=2, sticky="e")

    def _build_body(self):
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=1, column=0, sticky="nsew", padx=26, pady=(0, 14))
        self.body.grid_columnconfigure(0, weight=1)
        self.body.grid_rowconfigure(0, weight=1)

        self.drop_zone = self._build_drop_zone(self.body)
        self.queue_frame = self._build_queue(self.body)

    def _build_drop_zone(self, master):
        canvas = tk.Canvas(
            master, bg=COL_DROP_BG, highlightthickness=0, bd=0, cursor="hand2",
        )
        canvas.grid(row=0, column=0, sticky="nsew")

        def draw(_event=None):
            canvas.delete("border")
            w, h = canvas.winfo_width(), canvas.winfo_height()
            if w > 4 and h > 4:
                canvas.create_rectangle(
                    2, 2, w - 2, h - 2, outline=self._cor_borda_drop, width=2,
                    dash=(6, 4), tags="border",
                )

        canvas.bind("<Configure>", draw)
        canvas.bind("<Button-1>", lambda e: self._add_files())

        content = ctk.CTkFrame(canvas, fg_color=COL_DROP_BG)
        content.place(relx=0.5, rely=0.5, anchor="center")
        content.bind("<Button-1>", lambda e: self._add_files())

        ctk.CTkLabel(
            content, text="⇧", text_color=COL_AMBER, font=(FONT, 30, "bold"),
        ).pack(pady=(0, 8))
        ctk.CTkLabel(
            content, text="Arraste vídeos para cá", text_color=COL_TEXT,
            font=(FONT, 17, "bold"),
        ).pack()

        line = ctk.CTkFrame(content, fg_color=COL_DROP_BG)
        line.pack(pady=(4, 0))
        ctk.CTkLabel(line, text="ou ", text_color=COL_SUB, font=(FONT, 13)).pack(side="left")
        link = ctk.CTkLabel(
            line, text="escolha arquivos", text_color=COL_AMBER,
            font=(FONT, 13, "bold"), cursor="hand2",
        )
        link.pack(side="left")
        link.bind("<Button-1>", lambda e: self._add_files())
        ctk.CTkLabel(
            line, text=" · MP4, MOV, AVI, MKV, WEBM e RAW", text_color=COL_SUB,
            font=(FONT, 13),
        ).pack(side="left")

        return canvas

    def _build_queue(self, master):
        frame = ctk.CTkScrollableFrame(
            master, fg_color=COL_CARD, corner_radius=14,
            scrollbar_button_color=COL_CARD_ALT,
            scrollbar_button_hover_color=COL_BADGE_BG,
        )
        frame.grid(row=0, column=0, sticky="nsew")
        return frame

    def _build_raw_in_panel(self):
        outer = ctk.CTkFrame(self, fg_color=COL_CARD, corner_radius=12)
        outer.grid_columnconfigure(1, weight=1)

        accent = ctk.CTkFrame(outer, fg_color=COL_DROP_BORDER, width=3, height=1, corner_radius=0)
        accent.grid(row=0, column=0, sticky="ns")

        inner = ctk.CTkFrame(outer, fg_color="transparent")
        inner.grid(row=0, column=1, sticky="ew", padx=14, pady=10)

        title_row = ctk.CTkFrame(inner, fg_color="transparent")
        title_row.pack(anchor="w", pady=(0, 8))
        ctk.CTkLabel(
            title_row, text="Parâmetros dos arquivos .raw", text_color=COL_TEXT,
            font=(FONT, 13, "bold"),
        ).pack(side="left")
        ctk.CTkLabel(
            title_row, text=" · aplicados a todos os .raw da fila",
            text_color=COL_MUTED, font=(FONT, 12),
        ).pack(side="left")

        fields = ctk.CTkFrame(inner, fg_color="transparent")
        fields.pack(anchor="w")

        def field(label, var, width=60):
            col = ctk.CTkFrame(fields, fg_color="transparent")
            col.pack(side="left", padx=(0, 26))
            ctk.CTkLabel(
                col, text=label, text_color=COL_SUB, font=(FONT, 11, "bold"),
            ).pack(anchor="w")
            ctk.CTkEntry(
                col, textvariable=var, width=width, height=28, corner_radius=8,
                fg_color=COL_BADGE_BG, border_width=0, text_color=COL_TEXT,
                font=(FONT, 13, "bold"), justify="left",
            ).pack(anchor="w", pady=(2, 0))

        field("LARGURA", self.raw_in_width)
        field("ALTURA", self.raw_in_height)

        col = ctk.CTkFrame(fields, fg_color="transparent")
        col.pack(side="left", padx=(0, 26))
        ctk.CTkLabel(
            col, text="FORMATO DE PIXEL", text_color=COL_SUB, font=(FONT, 11, "bold"),
        ).pack(anchor="w")
        ctk.CTkOptionMenu(
            col, variable=self.raw_in_pix_fmt, values=fu.RAW_PIXEL_FORMATS,
            width=100, height=28, corner_radius=8, fg_color=COL_BADGE_BG,
            button_color=COL_BADGE_BG, button_hover_color=COL_CARD_ALT,
            text_color=COL_TEXT, font=(FONT, 12, "bold"),
            dropdown_fg_color=COL_CARD_ALT,
        ).pack(anchor="w", pady=(2, 0))

        field("FPS", self.raw_in_fps, width=50)

        return outer

    def _build_format_row(self):
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=3, column=0, sticky="ew", padx=26, pady=(0, 14))
        row.grid_columnconfigure(0, weight=1)

        col = ctk.CTkFrame(row, fg_color="transparent")
        col.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            col, text="CONVERTER PARA", text_color=COL_SUB, font=(FONT, 11, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        seg = ctk.CTkFrame(col, fg_color=COL_CARD, corner_radius=10)
        seg.pack(anchor="w")
        for fmt in fu.VIDEO_FORMATS:
            btn = ctk.CTkButton(
                seg, text=fmt.upper(), width=56, height=34, corner_radius=7,
                font=(FONT, 12, "bold"), command=lambda f=fmt: self._select_format(f),
            )
            btn.pack(side="left", padx=1, pady=4)
            self._format_buttons[fmt] = btn
        self._style_format_buttons()

    def _style_format_buttons(self):
        selected = self.output_format.get()
        for fmt, btn in self._format_buttons.items():
            if fmt == selected:
                btn.configure(fg_color=COL_AMBER, text_color=COL_AMBER_TEXT, hover_color=COL_AMBER)
            else:
                btn.configure(fg_color="transparent", text_color=COL_SUB, hover_color=COL_CARD_ALT)

    def _select_format(self, fmt):
        self.output_format.set(fmt)
        self._style_format_buttons()
        self._refresh_visibility()

    def _build_raw_out_panel(self):
        outer = ctk.CTkFrame(self, fg_color=COL_CARD, corner_radius=12)
        inner = ctk.CTkFrame(outer, fg_color="transparent")
        inner.pack(padx=14, pady=10, anchor="w")
        ctk.CTkLabel(
            inner, text="FORMATO DE PIXEL (SAÍDA .RAW)", text_color=COL_SUB,
            font=(FONT, 11, "bold"),
        ).pack(anchor="w", pady=(0, 4))
        ctk.CTkOptionMenu(
            inner, variable=self.raw_out_pix_fmt, values=fu.RAW_PIXEL_FORMATS,
            width=120, height=28, corner_radius=8, fg_color=COL_BADGE_BG,
            button_color=COL_BADGE_BG, button_hover_color=COL_CARD_ALT,
            text_color=COL_TEXT, font=(FONT, 12, "bold"),
            dropdown_fg_color=COL_CARD_ALT,
        ).pack(anchor="w")
        return outer

    def _build_dest_row(self):
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=5, column=0, sticky="ew", padx=26, pady=(0, 16))
        ctk.CTkLabel(
            row, text="SALVAR EM", text_color=COL_SUB, font=(FONT, 11, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        dest = ctk.CTkFrame(row, fg_color=COL_CARD, corner_radius=10, height=42)
        dest.pack(fill="x")
        dest.pack_propagate(False)

        ctk.CTkLabel(dest, text="📁", text_color=COL_SUB, font=(FONT, 13)).pack(
            side="left", padx=(14, 8)
        )
        self.dest_label = ctk.CTkLabel(
            dest, text="Pasta do primeiro vídeo adicionado", text_color=COL_DEST,
            font=(FONT, 13), anchor="w",
        )
        self.dest_label.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            dest, text="Trocar", width=1, height=24, fg_color="transparent",
            hover_color=COL_CARD_ALT, text_color=COL_AMBER, font=(FONT, 12, "bold"),
            command=self._pick_output_dir,
        ).pack(side="right", padx=14)

    def _build_bottom_bar(self):
        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.grid(row=6, column=0, sticky="ew", padx=26, pady=(0, 22))
        wrap.grid_columnconfigure(0, weight=1)

        # --- estado ocioso (fila vazia / pronta / concluída) ---
        self.bottom_idle = ctk.CTkFrame(wrap, fg_color=COL_CARD, corner_radius=12, height=56)
        self.bottom_idle.grid_propagate(False)
        self.bottom_idle.grid_columnconfigure(0, weight=1)
        self.idle_label = ctk.CTkLabel(
            self.bottom_idle, text="Nenhum arquivo na fila", text_color=COL_MUTED,
            font=(FONT, 12),
        )
        self.idle_label.grid(row=0, column=0, sticky="w", padx=16)
        self.convert_btn = ctk.CTkButton(
            self.bottom_idle, text="Converter tudo", fg_color=COL_AMBER,
            text_color=COL_AMBER_TEXT, hover_color="#c69643", corner_radius=10,
            height=42, width=150, font=(FONT, 14, "bold"), state="disabled",
            command=self._start_batch,
        )
        self.convert_btn.grid(row=0, column=1, sticky="e", padx=16)

        # --- estado convertendo ---
        self.bottom_run = ctk.CTkFrame(wrap, fg_color=COL_CARD, corner_radius=12)
        self.bottom_run.grid_columnconfigure(0, weight=1)

        ov = ctk.CTkFrame(self.bottom_run, fg_color="transparent")
        ov.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 6))
        ov.grid_columnconfigure(0, weight=1)
        self.convert_label = ctk.CTkLabel(
            ov, text="Convertendo 0 de 0", text_color=COL_TEXT, font=(FONT, 13, "bold"),
            anchor="w",
        )
        self.convert_label.grid(row=0, column=0, sticky="w")
        self.overall_pct_label = ctk.CTkLabel(
            ov, text="0%", text_color=COL_AMBER, font=(FONT, 20, "bold"),
        )
        self.overall_pct_label.grid(row=0, column=1, sticky="e")

        self.overall_progress = ctk.CTkProgressBar(
            self.bottom_run, height=8, corner_radius=99,
            fg_color=COL_TRACK, progress_color=COL_AMBER,
        )
        self.overall_progress.set(0)
        self.overall_progress.grid(row=1, column=0, sticky="ew", padx=16)

        br = ctk.CTkFrame(self.bottom_run, fg_color="transparent")
        br.grid(row=2, column=0, sticky="ew", padx=16, pady=(8, 14))
        br.grid_columnconfigure(0, weight=1)
        self.summary_label = ctk.CTkLabel(
            br, text="", text_color=COL_MUTED, font=(FONT, 12), anchor="w",
        )
        self.summary_label.grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            br, text="Cancelar", fg_color=COL_CARD_ALT, hover_color=COL_BADGE_BG,
            text_color=COL_TEXT, corner_radius=10, height=36, width=110,
            font=(FONT, 13, "bold"), command=self._cancel_batch,
        ).grid(row=0, column=1, sticky="e")

    # ------------------------------------------------------- visibilidade
    def _refresh_visibility(self):
        is_raw_out = self.output_format.get() == "raw"

        if self._any_raw_input():
            self.raw_in_panel.grid(row=2, column=0, sticky="ew", padx=26, pady=(0, 14))
        else:
            self.raw_in_panel.grid_forget()

        if is_raw_out:
            self.raw_out_panel.grid(row=4, column=0, sticky="ew", padx=26, pady=(0, 14))
        else:
            self.raw_out_panel.grid_forget()

        if self.files:
            self.drop_zone.grid_forget()
            self.queue_frame.grid(row=0, column=0, sticky="nsew")
        else:
            self.queue_frame.grid_forget()
            self.drop_zone.grid(row=0, column=0, sticky="nsew")

    def _any_raw_input(self):
        return any(self._is_raw(item["path"]) for item in self.files)

    @staticmethod
    def _is_raw(path):
        _, ext = os.path.splitext(path)
        return ext.lower() in RAW_EXTENSIONS

    def _refresh_bottom_bar(self):
        if self._converting:
            self.bottom_idle.grid_forget()
            self.bottom_run.grid(row=0, column=0, sticky="ew")
        else:
            self.bottom_run.grid_forget()
            self.bottom_idle.grid(row=0, column=0, sticky="ew")
            self._refresh_idle_text()

    def _refresh_idle_text(self):
        total = len(self.files)
        if total == 0:
            self.idle_label.configure(text="Nenhum arquivo na fila")
            self.convert_btn.configure(state="disabled", fg_color=COL_CARD_ALT, text_color=COL_MUTED)
            return

        done = sum(1 for f in self.files if f["status"] == STATUS_CONCLUIDO)
        errors = sum(1 for f in self.files if f["status"] == STATUS_ERRO)
        if done or errors:
            parts = []
            if done:
                parts.append(f"{done} concluído(s)")
            if errors:
                parts.append(f"{errors} com erro")
            self.idle_label.configure(text=" · ".join(parts))
        else:
            self.idle_label.configure(text=f"{total} arquivo(s) na fila")
        self.convert_btn.configure(state="normal", fg_color=COL_AMBER, text_color=COL_AMBER_TEXT)

    def _update_subtitle(self):
        if self.files:
            self.subtitle_label.configure(text=f"{len(self.files)} arquivos na fila")
        else:
            self.subtitle_label.configure(text="Converta vários vídeos de uma vez")

    # --------------------------------------------------------- lista de arquivos
    def _add_files(self):
        paths = filedialog.askopenfilenames(title="Escolha os arquivos de vídeo")
        self._add_paths(paths)

    def _add_paths(self, paths):
        paths = [os.path.normpath(p) for p in paths if os.path.isfile(p)]
        if not paths:
            return
        existing = {item["path"] for item in self.files}
        for path in paths:
            if path in existing:
                continue
            existing.add(path)
            row = FileRow(self.queue_frame, path, self._remove_file, self._view_log)
            row.pack(fill="x", padx=4, pady=2)
            self.files.append({"path": path, "status": STATUS_PENDENTE, "log": "", "row": row})
        if not self.output_dir.get():
            self.output_dir.set(os.path.dirname(paths[0]))
            self.dest_label.configure(text=self.output_dir.get())
        self._update_subtitle()
        self._refresh_visibility()
        self._refresh_bottom_bar()

    def _remove_file(self, path):
        if self._converting:
            return
        for item in self.files:
            if item["path"] == path:
                item["row"].destroy()
        self.files = [item for item in self.files if item["path"] != path]
        self._update_subtitle()
        self._refresh_visibility()
        self._refresh_bottom_bar()

    def _view_log(self, path):
        item = next((f for f in self.files if f["path"] == path), None)
        if not item or not item["log"]:
            messagebox.showinfo("Log", "Sem log de erro para este arquivo.")
            return
        tail = "\n".join(item["log"].strip().splitlines()[-25:])
        messagebox.showinfo(f"Log: {os.path.basename(path)}", tail)

    def _set_item_status(self, path, status, fraction=None):
        for item in self.files:
            if item["path"] == path:
                item["status"] = status
                item["row"].set_status(status, fraction)

    # -------------------------------------------------------------- ações
    def _check_ffmpeg(self):
        if not fu.find_ffmpeg():
            messagebox.showerror(
                "FFmpeg não encontrado",
                "O FFmpeg não foi encontrado no PATH do sistema.\n\n"
                "Instale o FFmpeg e garanta que o comando 'ffmpeg' funcione "
                "no terminal antes de usar este conversor.",
            )

    def _pick_output_dir(self):
        path = filedialog.askdirectory(title="Escolha a pasta de saída")
        if path:
            self.output_dir.set(path)
            self.dest_label.configure(text=path)

    def _start_batch(self):
        if self._converting:
            return
        if not self.files:
            messagebox.showwarning("Atenção", "Adicione ao menos um arquivo.")
            return
        out_dir = self.output_dir.get().strip()
        if not out_dir:
            messagebox.showwarning("Atenção", "Escolha uma pasta de saída.")
            return
        if not fu.find_ffmpeg():
            self._check_ffmpeg()
            return

        raw_in = None
        if self._any_raw_input():
            try:
                raw_in = {
                    "width": int(self.raw_in_width.get()),
                    "height": int(self.raw_in_height.get()),
                    "pix_fmt": self.raw_in_pix_fmt.get(),
                    "fps": float(self.raw_in_fps.get()),
                }
            except ValueError:
                messagebox.showwarning(
                    "Atenção", "Largura, altura e FPS do .raw devem ser números."
                )
                return

        out_format = self.output_format.get()
        raw_out = {"pix_fmt": self.raw_out_pix_fmt.get()} if out_format == "raw" else None

        for item in self.files:
            self._set_item_status(item["path"], STATUS_PENDENTE)
            item["log"] = ""

        self._cancel_event.clear()
        self._converting = True
        self.overall_progress.set(0)
        self.overall_pct_label.configure(text="0%")
        self.summary_label.configure(text="")
        self._refresh_bottom_bar()

        thread = threading.Thread(
            target=self._run_batch_thread,
            args=(list(self.files), out_dir, out_format, raw_in, raw_out),
            daemon=True,
        )
        thread.start()

    def _cancel_batch(self):
        self._cancel_event.set()
        self.convert_label.configure(text="Cancelando...")

    def _run_batch_thread(self, items, out_dir, out_format, raw_in, raw_out):
        total = len(items)
        used_names = set()
        done_count = 0
        error_count = 0

        for index, item in enumerate(items):
            path = item["path"]

            if self._cancel_event.is_set():
                self.after(0, self._set_item_status, path, STATUS_CANCELADO)
                continue

            self.after(0, self._set_item_status, path, STATUS_CONVERTENDO, 0)
            self.after(
                0, self.convert_label.configure,
                {"text": f"Convertendo {index + 1} de {total} · {os.path.basename(path)}"},
            )

            output_path = self._unique_output_path(path, out_dir, out_format, used_names)

            item_raw_in = raw_in if self._is_raw(path) else None

            if item_raw_in is not None:
                total_duration = fu.estimate_raw_duration_seconds(
                    path, item_raw_in["width"], item_raw_in["height"],
                    item_raw_in["pix_fmt"], item_raw_in["fps"],
                )
            else:
                total_duration = fu.probe_duration_seconds(path)

            base_progress = index / total

            def on_progress(fraction, base=base_progress, path=path):
                overall = base + (fraction or 0) / total
                self.after(0, self._update_progress_ui, path, fraction, overall)

            # 1º: copia sem recodificar (quando dá); 2º: recodifica com aceleração de vídeo;
            # 3º: recodifica pelo processador, que sempre funciona.
            tentativas = ({}, {"allow_copy": False}, {"allow_copy": False, "use_hw": False})
            ja_tentou = set()
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
                self.after(0, self._set_item_status, path, STATUS_CANCELADO)
            elif success:
                done_count += 1
                self.after(0, self._set_item_status, path, STATUS_CONCLUIDO)
            else:
                error_count += 1
                item["log"] = log
                self.after(0, self._set_item_status, path, STATUS_ERRO)

            overall_done = (index + 1) / total
            self.after(0, self.overall_progress.set, overall_done)
            self.after(0, self.overall_pct_label.configure, {"text": f"{int(overall_done * 100)}%"})

        self.after(0, self._on_batch_done, done_count, error_count, total)

    def _update_progress_ui(self, path, item_fraction, overall_fraction):
        self._set_item_status(path, STATUS_CONVERTENDO, item_fraction)
        self.overall_progress.set(overall_fraction)
        self.overall_pct_label.configure(text=f"{int(overall_fraction * 100)}%")

    @staticmethod
    def _unique_output_path(input_path, out_dir, out_format, used_names):
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        candidate = f"{base_name}_convertido.{out_format}"
        counter = 1
        while candidate in used_names:
            candidate = f"{base_name}_convertido_{counter}.{out_format}"
            counter += 1
        used_names.add(candidate)
        return os.path.join(out_dir, candidate)

    def _on_batch_done(self, done_count, error_count, total):
        self._converting = False

        if self._cancel_event.is_set():
            self.summary_label.configure(text=f"Cancelado. {done_count}/{total} concluídos antes de parar.")
        elif error_count:
            self.summary_label.configure(
                text=f"Concluído com erros: {done_count} ok, {error_count} com erro de {total}."
            )
        else:
            self.summary_label.configure(text=f"Concluído: {done_count}/{total} arquivos convertidos.")

        self._refresh_bottom_bar()


if __name__ == "__main__":
    App().mainloop()
