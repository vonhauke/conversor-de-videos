/* Conversor de Videos - logica da interface.
   O Python (main.py) expoe a API em window.pywebview.api e manda eventos
   chamando Conversor.receber({tipo, ...}). */

const $ = (id) => document.getElementById(id);

window.__erros = [];
window.addEventListener("error", (e) => window.__erros.push(String(e.message)));
window.addEventListener("unhandledrejection", (e) => window.__erros.push(String(e.reason)));

const Conversor = (() => {
  const s = {
    itens: [],          // [{path, nome, ext, tamanho, raw, status, fracao}]
    pasta: "",
    formato: "mp4",
    convertendo: false,
    cancelando: false,
  };
  let api = null;

  const ROTULO = {
    pendente: ["Na fila", ""],
    convertendo: ["Convertendo", "tag-acento"],
    concluido: ["Concluído", "tag-sucesso"],
    erro: ["Erro", "tag-perigo"],
    cancelado: ["Cancelado", ""],
  };

  /* ---------- fila ---------- */
  function desenharFila() {
    const temItens = s.itens.length > 0;
    $("soltar").classList.toggle("oculto", temItens);
    $("fila").classList.toggle("oculto", !temItens);
    $("fila-conta").textContent = temItens ? `${s.itens.length} ${s.itens.length === 1 ? "arquivo" : "arquivos"}` : "";
    $("subtitulo").textContent = temItens
      ? `${s.itens.length} ${s.itens.length === 1 ? "arquivo" : "arquivos"} na fila`
      : "Converta vários vídeos de uma vez";

    $("lista").innerHTML = s.itens.map((it, i) => `
      <div class="item" data-i="${i}">
        <div class="item-icone">${DS.escapar(it.ext)}</div>
        <div class="item-meio">
          <div class="item-titulo" title="${DS.escapar(it.path)}">${DS.escapar(it.nome)}</div>
          <div class="item-sub">${DS.escapar(it.tamanho)}</div>
          <div class="progresso oculto"><span></span></div>
        </div>
        <div class="item-estado"></div>
        <button class="btn btn-icone remover" title="Remover da fila"><i data-icone="x" data-tamanho="15"></i></button>
      </div>`).join("");
    desenharIcones($("lista"));
    s.itens.forEach((it, i) => pintarItem(i));
    $("painel-raw").classList.toggle("oculto", !s.itens.some((it) => it.raw));
    atualizarControles();
  }

  function pintarItem(i) {
    const it = s.itens[i];
    const linha = document.querySelector(`.item[data-i="${i}"]`);
    if (!linha) return;
    const [rotulo, classe] = ROTULO[it.status] || ROTULO.pendente;
    const conv = it.status === "convertendo";
    const pct = Math.floor((it.fracao || 0) * 100);
    linha.classList.toggle("ativo", conv);
    linha.querySelector(".item-sub").classList.toggle("oculto", conv);
    const barra = linha.querySelector(".progresso");
    barra.classList.toggle("oculto", !conv);
    barra.firstElementChild.style.width = `${pct}%`;
    let estado = `<span class="tag ${classe}">${it.status === "concluido" ? icone("check", 12, 2.5) : ""}${rotulo}${conv ? ` · ${pct}%` : ""}</span>`;
    if (it.status === "erro") estado += `<button class="btn-link ver-log">ver detalhes</button>`;
    linha.querySelector(".item-estado").innerHTML = estado;
    linha.querySelector(".remover").disabled = s.convertendo;
  }

  function resumoParado() {
    const total = s.itens.length;
    if (!total) return "Nenhum arquivo na fila";
    const feitos = s.itens.filter((i) => i.status === "concluido").length;
    const erros = s.itens.filter((i) => i.status === "erro").length;
    if (feitos || erros) {
      const partes = [];
      if (feitos) partes.push(`${feitos} ${feitos === 1 ? "concluído" : "concluídos"}`);
      if (erros) partes.push(`${erros} com erro`);
      return partes.join(" · ");
    }
    return `${total} ${total === 1 ? "arquivo" : "arquivos"} na fila`;
  }

  function atualizarControles() {
    $("barra-parada").classList.toggle("oculto", s.convertendo);
    $("barra-andando").classList.toggle("oculto", !s.convertendo);
    $("resumo").textContent = resumoParado();
    $("btn-converter").disabled = !s.itens.length || s.convertendo;
    $("btn-adicionar").disabled = s.convertendo;
    $("btn-trocar").disabled = s.convertendo;
    document.querySelectorAll("#formatos button").forEach((b) => (b.disabled = s.convertendo));
    document.querySelectorAll("#painel-raw input, #painel-raw select, #raw-saida-pix").forEach((c) => (c.disabled = s.convertendo));
    document.querySelectorAll(".remover").forEach((b) => (b.disabled = s.convertendo));
    $("btn-cancelar").disabled = s.cancelando;
    $("btn-cancelar").textContent = s.cancelando ? "Cancelando…" : "Cancelar";
    $("btn-abrir-pasta").classList.toggle("oculto", !s.pasta);
  }

  /* ---------- formato ---------- */
  function selecionarFormato(f) {
    s.formato = f;
    document.querySelectorAll("#formatos button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.f === f)));
    $("raw-saida").classList.toggle("oculto", f !== "raw");
  }

  /* ---------- avisos ---------- */
  function aviso(titulo, texto) {
    $("aviso-titulo").textContent = titulo;
    $("aviso-texto").textContent = texto || "";
    $("aviso").classList.remove("oculto", "entra"); void $("aviso").offsetWidth; $("aviso").classList.add("entra");
  }
  const fecharAviso = () => $("aviso").classList.add("oculto");

  /* ---------- detalhes do erro ---------- */
  async function verLog(path) {
    const texto = await api.ver_log(path);
    const it = s.itens.find((x) => x.path === path);
    $("log-titulo").textContent = `Detalhes do erro · ${it ? it.nome : ""}`;
    $("log-texto").textContent = texto || "Sem log de erro para este arquivo.";
    $("modal-log").classList.remove("oculto");
    $("log-ok").focus();
  }
  const fecharLog = () => $("modal-log").classList.add("oculto");

  /* ---------- acoes ---------- */
  async function converter() {
    if (s.convertendo || !s.itens.length) return;
    fecharAviso();
    const erro = await api.converter({
      formato: s.formato,
      raw_in: { largura: $("raw-largura").value, altura: $("raw-altura").value, pix_fmt: $("raw-pix").value, fps: $("raw-fps").value },
      raw_out_pix: $("raw-saida-pix").value,
    });
    if (erro) aviso(erro.titulo, erro.texto);
  }

  function cancelar() {
    if (!s.convertendo || s.cancelando) return;
    s.cancelando = true;
    $("geral-rotulo").textContent = "Cancelando…";
    atualizarControles();
    api.cancelar();
  }

  /* ---------- eventos do Python ---------- */
  function receber(ev) {
    switch (ev.tipo) {
      case "fila":
        s.itens = ev.itens;
        s.pasta = ev.pasta;
        $("pasta").textContent = ev.pasta || "Pasta do primeiro vídeo adicionado";
        $("pasta").title = ev.pasta || "";
        desenharFila();
        break;
      case "item": {
        const i = s.itens.findIndex((x) => x.path === ev.path);
        if (i < 0) return;
        Object.assign(s.itens[i], { status: ev.status, fracao: ev.fracao });
        pintarItem(i);
        if (ev.status === "convertendo" && ev.inicio) {
          document.querySelector(`.item[data-i="${i}"]`)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
        }
        break;
      }
      case "inicio":
        s.convertendo = true;
        s.cancelando = false;
        s.itens.forEach((it) => { it.status = "pendente"; it.fracao = 0; });
        s.itens.forEach((_, i) => pintarItem(i));
        $("geral-rotulo").textContent = "Preparando…";
        $("geral-resumo").textContent = "";
        geral(0);
        atualizarControles();
        break;
      case "geral":
        if (!s.cancelando && ev.rotulo) $("geral-rotulo").textContent = ev.rotulo;
        geral(ev.fracao);
        break;
      case "fim":
        s.convertendo = false;
        s.cancelando = false;
        atualizarControles();
        s.itens.forEach((_, i) => pintarItem(i));
        DS.toast(ev.resumo, s.pasta && ev.feitos ? { acao: () => api.abrir_pasta(), rotulo: "Abrir pasta", duracao: 7000 } : { duracao: 5000 });
        break;
      case "aviso":
        aviso(ev.titulo, ev.texto);
        break;
    }
  }

  function geral(fracao) {
    const pct = Math.floor((fracao || 0) * 100);
    $("geral-pct").textContent = `${pct}%`;
    $("geral-barra").firstElementChild.style.width = `${(fracao || 0) * 100}%`;
  }

  /* ---------- arrastar e soltar ---------- */
  function ativarArrastar() {
    let profundidade = 0;
    const mostrar = (sim) => $("soltar-tela").classList.toggle("oculto", !sim);
    const temArquivos = (e) => e.dataTransfer && [...(e.dataTransfer.types || [])].includes("Files");
    document.addEventListener("dragenter", (e) => {
      if (!temArquivos(e) || s.convertendo) return;
      e.preventDefault(); profundidade++; mostrar(true);
    });
    document.addEventListener("dragover", (e) => { if (temArquivos(e)) e.preventDefault(); });
    document.addEventListener("dragleave", () => { profundidade = Math.max(0, profundidade - 1); if (!profundidade) mostrar(false); });
    document.addEventListener("drop", (e) => {
      e.preventDefault(); profundidade = 0; mostrar(false);
      if (s.convertendo) return;
      // o caminho completo vem do pywebview (pywebviewFullPath); o Python tambem
      // recebe o evento e adiciona os arquivos. Aqui so cobrimos a falta dele.
      const arquivos = [...(e.dataTransfer?.files || [])];
      const caminhos = arquivos.map((f) => f.pywebviewFullPath).filter(Boolean);
      if (arquivos.length && !caminhos.length && !window.pywebview) {
        DS.toast("Não deu para ler os arquivos soltos. Use Adicionar arquivos.");
      }
    });
  }

  /* ---------- inicio ---------- */
  async function iniciar() {
    desenharIcones();
    api = await DS.api();
    const ini = await api.estado_inicial();
    $("formatos").innerHTML = ini.formatos.map((f) => `<button data-f="${f}" aria-pressed="false">${f.toUpperCase()}</button>`).join("");
    const opcoesPix = ini.pix_fmts.map((p) => `<option>${p}</option>`).join("");
    $("raw-pix").innerHTML = opcoesPix;
    $("raw-saida-pix").innerHTML = opcoesPix;
    selecionarFormato("mp4");
    if (!ini.ffmpeg) {
      aviso("FFmpeg não encontrado", "O FFmpeg não foi encontrado no sistema. Instale o FFmpeg e garanta que o comando 'ffmpeg' funcione no terminal antes de usar este conversor.");
    }
    receber({ tipo: "fila", itens: [], pasta: "" });

    $("btn-adicionar").onclick = () => api.escolher_arquivos();
    $("soltar").onclick = () => api.escolher_arquivos();
    $("btn-converter").onclick = converter;
    $("btn-cancelar").onclick = cancelar;
    $("btn-trocar").onclick = () => api.trocar_pasta();
    $("btn-abrir-pasta").onclick = () => api.abrir_pasta();
    $("aviso-fechar").onclick = fecharAviso;
    $("formatos").onclick = (e) => { const b = e.target.closest("button[data-f]"); if (b && !b.disabled) selecionarFormato(b.dataset.f); };
    $("lista").onclick = (e) => {
      const linha = e.target.closest(".item");
      if (!linha) return;
      const it = s.itens[Number(linha.dataset.i)];
      if (e.target.closest(".remover") && !s.convertendo) api.remover(it.path);
      else if (e.target.closest(".ver-log")) verLog(it.path);
    };
    $("log-fechar").onclick = $("log-ok").onclick = fecharLog;
    $("modal-log").onclick = (e) => { if (e.target === $("modal-log")) fecharLog(); };
    $("log-copiar").onclick = async () => {
      try { await navigator.clipboard.writeText($("log-texto").textContent); DS.toast("Detalhes copiados"); }
      catch (_) { DS.toast("Selecione o texto e copie com Ctrl+C"); }
    };
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        if (!$("modal-log").classList.contains("oculto")) fecharLog();
        else if (s.convertendo) cancelar();
        else fecharAviso();
      }
    });
    ativarArrastar();
    document.documentElement.classList.add("pronto");
  }

  document.addEventListener("DOMContentLoaded", iniciar);
  return { receber, _s: s };
})();
