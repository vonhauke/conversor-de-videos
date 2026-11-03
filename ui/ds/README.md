# Design system Argila

Visual comum aos apps (SnapYou, Conversor de Vídeos, Conversor de Imagens e my chaotic room),
inspirado nos apps do Claude: fundo creme, laranja terracota, títulos em serifa e interface em
sans geométrica, com tema escuro quente automático. A pasta é **idêntica** em todos os apps: para
mudar o visual, edite aqui e copie a pasta `ui/ds/` inteira para os outros.

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `tokens.css` | Fontes, cores (claro e escuro), espaçamentos, raios, sombras e movimento. |
| `components.css` | Componentes prontos (lista abaixo). |
| `ds.js` | Menus suspensos, `DS.toast()`, `DS.api()` (ponte com o Python) e `DS.escapar()`. |
| `icons.js` | Ícones Lucide: `icone("folder")` ou `<i data-icone="folder"></i>` + `desenharIcones()`. |
| `fonts/` | Source Serif 4 e DM Sans (licença OFL). |

## Tokens principais

| Token | Claro | Escuro | Uso |
|---|---|---|---|
| `--fundo` | `#FAF9F5` | `#262624` | Fundo da janela |
| `--superficie` | `#FFFFFF` | `#30302E` | Cartões, caixas |
| `--texto` | `#141413` | `#FAF9F5` | Texto principal |
| `--texto-2` | `#5E5D59` | `#C2C0B6` | Texto secundário (6,3:1) |
| `--acento` | `#D97757` | `#D97757` | Ícones, barra de progresso, foco |
| `--acento-fundo` | `#BB5835` | `#BB5835` | Botão principal (branco sobre ele: 4,6:1) |
| `--sucesso` / `--perigo` | `#4E6B35` / `#B53333` | `#9DB97F` / `#F08A80` | Estados |

Fontes: `--fonte-serif` (Source Serif 4) para títulos e nomes de itens; `--fonte-sans` (DM Sans) para o resto.

## Componentes

- **Botões:** `.btn` + `.btn-primario` | `.btn-secundario` | `.btn-fantasma` | `.btn-perigo` | `.btn-icone` | `.btn-enviar`; tamanhos `.btn-sm`, `.btn-lg`
- **Caixa estilo Claude:** `.composer` > `.composer-campo` + `.composer-barra`
- **Seleção:** `.segmentado` (botões com `aria-pressed`), `.pilula`, `.marcar` (caixa de seleção)
- **Conteúdo:** `.cartao` (+ `.cartao-corpo`, `.cartao-rodape`), `.tag` (`.tag-acento`, `.tag-sucesso`, `.tag-perigo`), `.lista` > `.item`, `.tabela`
- **Formulários:** `.campo`, `.entrada`, `.selecao`, `.area-texto`, `.busca`, `.ajuda`, `.rotulo`
- **Retorno:** `.aviso` (`.aviso-perigo`), `.progresso` (`.indeterminado`), `.etapas` > `.etapa` (`.feita`, `.ativa`) + `.trilho`, `.esqueleto`, `.girando`, `DS.toast()`
- **Janelas:** `.menu-ancora` > `[data-menu]` + `.menu`; `.fundo-modal` > `.modal`
- **Arquivos:** `.soltar` (`.arrastando`)
- **Tipografia:** `.titulo-lg`, `.titulo-md`, `.titulo-sm`, `.serif`, `.texto-2`, `.texto-3`, `.pequeno`, `.mini`, `.numeros`; marca: `.marca` > `img` + `.marca-nome` + `.marca-sub`
