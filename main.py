"""Conversor de Vídeos - GUI em Tkinter.

Converte, em lote, entre mp4, mov, avi, mkv, webm e .raw (vídeo bruto sem
cabeçalho, usado em fluxos de glitch art). Usa o FFmpeg instalado no sistema.
"""

import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import ffmpeg_utils as fu

RAW_EXTENSIONS = {".raw"}

STATUS_PENDENTE = "Pendente"
STATUS_CONVERTENDO = "Convertendo..."
STATUS_CONCLUIDO = "Concluído"
STATUS_ERRO = "Erro"
STATUS_CANCELADO = "Cancelado"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Conversor de Vídeos")
        self.geometry("760x560")
        self.minsize(720, 520)
        self.resizable(True, True)

        # Cada item: {"path": str, "status": str, "log": str}
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

        self.status_text = tk.StringVar(value="Pronto.")

        self._cancel_event = threading.Event()
        self._converting = False

        self._build_ui()
        self._check_ffmpeg()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        frm_files = ttk.LabelFrame(self, text="Arquivos de entrada")
        frm_files.pack(fill="both", expand=True, **pad)

        # Empacota da direita para a esquerda: os botões (largura fixa) e a
        # barra de rolagem reservam seu espaço primeiro; a árvore de arquivos
        # (expand=True) ocupa o que sobrar. Assim os botões nunca são cortados.
        frm_file_btns = ttk.Frame(frm_files)
        frm_file_btns.pack(side="right", fill="y", padx=8, pady=8)
        ttk.Button(
            frm_file_btns, text="Adicionar...", width=14, command=self._add_files
        ).pack(fill="x", pady=(0, 4))
        self.btn_remove = ttk.Button(
            frm_file_btns, text="Remover", width=14, command=self._remove_selected
        )
        self.btn_remove.pack(fill="x", pady=4)
        ttk.Button(
            frm_file_btns, text="Limpar tudo", width=14, command=self._clear_files
        ).pack(fill="x", pady=4)
        self.btn_view_log = ttk.Button(
            frm_file_btns, text="Ver erro", width=14, command=self._view_selected_log
        )
        self.btn_view_log.pack(fill="x", pady=4)

        scrollbar = ttk.Scrollbar(frm_files, orient="vertical")
        scrollbar.pack(side="right", fill="y", pady=8)

        self.tree = ttk.Treeview(
            frm_files, columns=("status",), show="tree headings", height=8,
            yscrollcommand=scrollbar.set,
        )
        self.tree.heading("#0", text="Arquivo")
        self.tree.heading("status", text="Status")
        self.tree.column("#0", width=340)
        self.tree.column("status", width=110, anchor="center")
        self.tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._update_buttons_state())
        scrollbar.configure(command=self.tree.yview)

        self.frm_raw_in = ttk.LabelFrame(self, text="Parâmetros dos .raw de entrada (aplicados a todos no lote)")
        self._build_raw_in_fields(self.frm_raw_in)

        frm_out_fmt = ttk.LabelFrame(self, text="Formato de saída")
        frm_out_fmt.pack(fill="x", **pad)
        combo = ttk.Combobox(
            frm_out_fmt, textvariable=self.output_format,
            values=fu.VIDEO_FORMATS, state="readonly", width=15,
        )
        combo.pack(side="left", padx=8, pady=8)
        combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_visibility())

        self.frm_raw_out = ttk.LabelFrame(self, text="Parâmetros do .raw de saída")
        ttk.Label(self.frm_raw_out, text="Formato de pixel:").pack(
            side="left", padx=(8, 4), pady=8
        )
        ttk.Combobox(
            self.frm_raw_out, textvariable=self.raw_out_pix_fmt,
            values=fu.RAW_PIXEL_FORMATS, state="readonly", width=12,
        ).pack(side="left", padx=4, pady=8)

        frm_out_dir = ttk.LabelFrame(self, text="Pasta de saída")
        frm_out_dir.pack(fill="x", **pad)
        ttk.Entry(frm_out_dir, textvariable=self.output_dir, width=55).pack(
            side="left", padx=(8, 4), pady=8
        )
        ttk.Button(frm_out_dir, text="Escolher...", command=self._pick_output_dir).pack(
            side="left", padx=4, pady=8
        )

        frm_actions = ttk.Frame(self)
        frm_actions.pack(pady=(8, 4))
        self.btn_convert = ttk.Button(
            frm_actions, text="Converter tudo", command=self._start_batch
        )
        self.btn_convert.pack(side="left", padx=6)
        self.btn_cancel = ttk.Button(
            frm_actions, text="Cancelar", command=self._cancel_batch, state="disabled"
        )
        self.btn_cancel.pack(side="left", padx=6)

        self.progress = ttk.Progressbar(self, length=580, mode="determinate")
        self.progress.pack(pady=4)

        ttk.Label(self, textvariable=self.status_text, wraplength=600).pack(pady=4)

        self._refresh_visibility()
        self._update_buttons_state()

    def _build_raw_in_fields(self, parent):
        ttk.Label(parent, text="Largura:").grid(row=0, column=0, padx=6, pady=6)
        ttk.Entry(parent, textvariable=self.raw_in_width, width=8).grid(row=0, column=1)
        ttk.Label(parent, text="Altura:").grid(row=0, column=2, padx=6)
        ttk.Entry(parent, textvariable=self.raw_in_height, width=8).grid(row=0, column=3)
        ttk.Label(parent, text="Pixel fmt:").grid(row=0, column=4, padx=6)
        ttk.Combobox(
            parent, textvariable=self.raw_in_pix_fmt,
            values=fu.RAW_PIXEL_FORMATS, state="readonly", width=10,
        ).grid(row=0, column=5, padx=(0, 6))
        ttk.Label(parent, text="FPS:").grid(row=0, column=6, padx=6)
        ttk.Entry(parent, textvariable=self.raw_in_fps, width=6).grid(
            row=0, column=7, padx=(0, 8), pady=6
        )

    def _refresh_visibility(self):
        is_raw_out = self.output_format.get() == "raw"

        if self._any_raw_input():
            self.frm_raw_in.pack(fill="x", padx=10, pady=(0, 6))
        else:
            self.frm_raw_in.pack_forget()

        if is_raw_out:
            self.frm_raw_out.pack(fill="x", padx=10, pady=(0, 6))
        else:
            self.frm_raw_out.pack_forget()

    def _any_raw_input(self):
        return any(self._is_raw(item["path"]) for item in self.files)

    @staticmethod
    def _is_raw(path):
        _, ext = os.path.splitext(path)
        return ext.lower() in RAW_EXTENSIONS

    def _update_buttons_state(self):
        has_selection = bool(self.tree.selection())
        self.btn_remove.configure(state="normal" if has_selection and not self._converting else "disabled")
        self.btn_view_log.configure(state="normal" if has_selection else "disabled")

    # --------------------------------------------------------- lista de arquivos
    def _add_files(self):
        paths = filedialog.askopenfilenames(title="Escolha os arquivos de vídeo")
        if not paths:
            return
        existing = {item["path"] for item in self.files}
        for path in paths:
            if path in existing:
                continue
            self.files.append({"path": path, "status": STATUS_PENDENTE, "log": ""})
            self.tree.insert("", "end", iid=path, text=os.path.basename(path),
                              values=(STATUS_PENDENTE,))
        if not self.output_dir.get() and paths:
            self.output_dir.set(os.path.dirname(paths[0]))
        self._refresh_visibility()

    def _remove_selected(self):
        for iid in self.tree.selection():
            self.tree.delete(iid)
            self.files = [item for item in self.files if item["path"] != iid]
        self._refresh_visibility()
        self._update_buttons_state()

    def _clear_files(self):
        self.tree.delete(*self.tree.get_children())
        self.files = []
        self._refresh_visibility()
        self._update_buttons_state()

    def _view_selected_log(self):
        selection = self.tree.selection()
        if not selection:
            return
        path = selection[0]
        item = next((f for f in self.files if f["path"] == path), None)
        if not item or not item["log"]:
            messagebox.showinfo("Log", "Sem log de erro para este arquivo.")
            return
        tail = "\n".join(item["log"].strip().splitlines()[-25:])
        messagebox.showinfo(f"Log: {os.path.basename(path)}", tail)

    def _set_item_status(self, path, status):
        for item in self.files:
            if item["path"] == path:
                item["status"] = status
        if self.tree.exists(path):
            self.tree.set(path, "status", status)

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
            item["status"] = STATUS_PENDENTE
            item["log"] = ""
            self.tree.set(item["path"], "status", STATUS_PENDENTE)

        self._cancel_event.clear()
        self._converting = True
        self.btn_convert.configure(state="disabled")
        self.btn_cancel.configure(state="normal")
        self.btn_remove.configure(state="disabled")
        self.progress.configure(mode="determinate", value=0)

        thread = threading.Thread(
            target=self._run_batch_thread,
            args=(list(self.files), out_dir, out_format, raw_in, raw_out),
            daemon=True,
        )
        thread.start()

    def _cancel_batch(self):
        self._cancel_event.set()
        self.status_text.set("Cancelando...")

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

            self.after(0, self._set_item_status, path, STATUS_CONVERTENDO)
            self.after(0, self.status_text.set,
                       f"Convertendo {index + 1}/{total}: {os.path.basename(path)}")

            output_path = self._unique_output_path(path, out_dir, out_format, used_names)

            item_raw_in = raw_in if self._is_raw(path) else None
            cmd = fu.build_command(path, output_path, out_format, item_raw_in, raw_out)

            if item_raw_in is not None:
                total_duration = fu.estimate_raw_duration_seconds(
                    path, item_raw_in["width"], item_raw_in["height"],
                    item_raw_in["pix_fmt"], item_raw_in["fps"],
                )
            else:
                total_duration = fu.probe_duration_seconds(path)

            base_progress = index / total

            def on_progress(fraction, base=base_progress):
                overall = base + (fraction or 0) / total
                self.after(0, lambda: self.progress.configure(value=overall * 100))

            success, log, cancelled = fu.run_conversion(
                cmd, on_progress, total_duration, self._cancel_event.is_set
            )

            if cancelled:
                self.after(0, self._set_item_status, path, STATUS_CANCELADO)
            elif success:
                done_count += 1
                self.after(0, self._set_item_status, path, STATUS_CONCLUIDO)
            else:
                error_count += 1
                item["log"] = log
                self.after(0, self._set_item_status, path, STATUS_ERRO)

            self.after(0, lambda v=(index + 1) / total * 100: self.progress.configure(value=v))

        self.after(0, self._on_batch_done, done_count, error_count, total)

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
        self.btn_convert.configure(state="normal")
        self.btn_cancel.configure(state="disabled")
        self._update_buttons_state()

        if self._cancel_event.is_set():
            self.status_text.set(f"Cancelado. {done_count}/{total} concluídos antes de parar.")
        elif error_count:
            self.status_text.set(
                f"Concluído com erros: {done_count} ok, {error_count} com erro de {total}."
            )
        else:
            self.status_text.set(f"Concluído: {done_count}/{total} arquivos convertidos.")


if __name__ == "__main__":
    App().mainloop()
