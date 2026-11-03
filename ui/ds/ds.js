/* Design system "Argila" - utilitarios de interface comuns aos apps.
   - Menus suspensos: <div class="menu-ancora"><button data-menu="id">..</button><div class="menu" id="id">..</div></div>
   - toast(texto, {acao, rotulo, duracao})
   - api(): espera a ponte do pywebview ficar pronta e devolve window.pywebview.api */

const DS = (() => {
  let menuAberto = null;

  function fecharMenu() {
    if (menuAberto) {
      menuAberto.classList.remove("aberto");
      const botao = document.querySelector(`[data-menu="${menuAberto.id}"]`);
      if (botao) botao.setAttribute("aria-expanded", "false");
      menuAberto = null;
    }
  }

  function alternarMenu(id) {
    const menu = document.getElementById(id);
    if (!menu) return;
    const estavaAberto = menu === menuAberto;
    fecharMenu();
    if (!estavaAberto) {
      menu.classList.add("aberto");
      const botao = document.querySelector(`[data-menu="${id}"]`);
      if (botao) botao.setAttribute("aria-expanded", "true");
      menuAberto = menu;
      const primeiro = menu.querySelector(".menu-item:not(:disabled)");
      if (primeiro) primeiro.focus({ preventScroll: true });
    }
  }

  document.addEventListener("click", (e) => {
    const gatilho = e.target.closest("[data-menu]");
    if (gatilho) {
      e.stopPropagation();
      if (!gatilho.disabled) alternarMenu(gatilho.dataset.menu);
      return;
    }
    if (menuAberto && !e.target.closest(".menu")) fecharMenu();
    if (e.target.closest(".menu-item")) fecharMenu();
  });

  document.addEventListener("keydown", (e) => {
    if (!menuAberto) return;
    const itens = [...menuAberto.querySelectorAll(".menu-item:not(:disabled)")];
    const i = itens.indexOf(document.activeElement);
    if (e.key === "Escape") { fecharMenu(); e.stopImmediatePropagation(); e.preventDefault(); }
    else if (e.key === "ArrowDown") { itens[(i + 1) % itens.length]?.focus(); e.preventDefault(); }
    else if (e.key === "ArrowUp") { itens[(i - 1 + itens.length) % itens.length]?.focus(); e.preventDefault(); }
  }, true);

  function toast(texto, opcoes = {}) {
    let area = document.querySelector(".toast-area");
    if (!area) {
      area = document.createElement("div");
      area.className = "toast-area";
      document.body.appendChild(area);
    }
    area.querySelectorAll(".toast").forEach((t) => t.remove());   // uma de cada vez
    const el = document.createElement("div");
    el.className = "toast";
    el.setAttribute("role", "status");
    el.textContent = texto;
    if (opcoes.acao) {
      const b = document.createElement("button");
      b.className = "btn btn-sm";
      b.textContent = opcoes.rotulo || "Desfazer";
      b.onclick = () => { opcoes.acao(); el.remove(); };
      el.appendChild(b);
    }
    area.appendChild(el);
    setTimeout(() => el.remove(), opcoes.duracao || 4000);
    return el;
  }

  /* A ponte do pywebview (window.pywebview.api) so existe depois do evento
     "pywebviewready". Fora do app (num navegador comum), devolve window.apiFalsa
     se existir - usado nos testes e nas maquetes. */
  function api() {
    return new Promise((resolve) => {
      if (window.pywebview && window.pywebview.api) return resolve(window.pywebview.api);
      if (window.apiFalsa) return resolve(window.apiFalsa);
      window.addEventListener("pywebviewready", () => resolve(window.pywebview.api), { once: true });
    });
  }

  function escapar(texto) {
    return String(texto ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  return { alternarMenu, fecharMenu, toast, api, escapar };
})();
