# Conversor de Vídeos

Aplicativo de janela para Windows e Mac que converte vários vídeos de uma vez entre **MP4, MOV, AVI, MKV, WEBM** e **RAW**
(vídeo bruto, sem cabeçalho, usado em fluxos de glitch art). A conversão é feita pelo [FFmpeg](https://ffmpeg.org/).

- Visual no estilo dos apps do Claude (design system **Argila**, em `ui/ds/`): fundo creme, laranja terracota,
  títulos em serifa e **tema escuro automático** que segue o Windows/Mac
- Arraste vídeos para qualquer ponto da janela, ou use **Adicionar arquivos**
- Conversão em lote: adicione vários arquivos e clique em **Converter tudo**
- Progresso por arquivo e progresso geral, com opção de **Cancelar**
- Suporte a `.raw` como entrada e como saída, com largura, altura, formato de pixel e FPS configuráveis
- Em caso de erro, o botão **ver detalhes** mostra o final do log do FFmpeg
- Os arquivos convertidos são salvos como `nome_convertido.formato`, sem sobrescrever os originais

![Conversor de Vídeos nos temas claro e escuro](docs/capturas/vitrine.png)

| Fila vazia | Convertendo | Detalhes de um erro |
|---|---|---|
| ![](docs/capturas/vazio-claro.png) | ![](docs/capturas/convertendo-claro.png) | ![](docs/capturas/erro-claro.png) |

## Baixar e usar (Windows)

1. Abra a página de [**Releases**](https://github.com/vonhauke/conversor-de-videos/releases/latest) e baixe o arquivo **Conversor de Videos.exe**.
2. Dê dois cliques nele. Não precisa instalar nada: o FFmpeg já vai dentro do programa.

> Na primeira vez, o Windows pode mostrar um aviso azul (SmartScreen), porque o programa não é assinado.
> Clique em **Mais informações → Executar assim mesmo**.

## Rodar pelo código-fonte

Se preferir rodar sem o `.exe`, você precisa de:

- Windows ou Mac (no Linux, também o WebKit: `sudo apt install python3-gi gir1.2-webkit2-4.1`)
- Python 3.10+
- [FFmpeg](https://ffmpeg.org/download.html) instalado e acessível no `PATH` (o comando `ffmpeg` precisa funcionar no terminal; o `ffprobe` é usado para calcular o progresso)

## Como usar

```
pip install pywebview
python main.py
```

1. **Arraste os vídeos** do Explorer para a janela, ou clique em **+ Adicionar arquivos** (ou na área pontilhada) e escolha-os.
2. Escolha o formato em **Converter para**.
3. Se quiser, troque a pasta em **Salvar em** (padrão: a pasta do primeiro vídeo adicionado).
4. Clique em **Converter tudo** e acompanhe o progresso.

## Arquivos .raw

Um `.raw` não tem cabeçalho, então o FFmpeg precisa saber como interpretá-lo.

- **Como entrada:** quando há um `.raw` na fila, aparece o painel *Parâmetros dos arquivos .raw*, com largura, altura,
  formato de pixel e FPS. Os valores valem para **todos** os `.raw` do lote; se eles foram exportados com
  configurações diferentes, converta-os em lotes separados.
- **Como saída:** ao escolher `RAW`, aparece o seletor de formato de pixel da saída (`rgb24`, `rgba`, `yuv420p`, entre outros).

## Velocidade e codecs

O app prioriza a velocidade:

- **Sem recodificar:** se o vídeo já está num codec que o formato de destino aceita (por exemplo, MOV com H.264 ou HEVC para MP4), o app só troca o "container" e copia o vídeo e o áudio como estão. Leva segundos, mesmo em arquivos grandes, e não perde qualidade.
- **MP4, MOV e MKV recodificados:** usa o chip de vídeo do computador (NVIDIA NVENC, Intel Quick Sync ou AMD AMF) quando houver um que funcione. Ele é testado automaticamente na primeira conversão. Se não houver, ou se falhar em algum arquivo, converte pelo processador com H.264 no modo `veryfast`.
- **WEBM recodificado:** VP9 no modo `realtime`, várias vezes mais rápido que o padrão do FFmpeg, com arquivo um pouco maior.
- Se a cópia falhar em algum arquivo, o app tenta de novo recodificando, sem você precisar fazer nada.
- No Mac, a aceleração por hardware (NVENC/Quick Sync/AMF) não existe, então recodificações usam sempre o processador (`libx264`), um pouco mais lentas.

| Formato | Vídeo | Áudio |
|---------|-------|-------|
| MP4, MOV | H.264 ou HEVC copiado; senão H.264 (hardware ou `libx264`) | AAC (ou o original, se compatível) |
| MKV | Copiado se compatível; senão H.264 | AAC (ou o original, se compatível) |
| AVI | MPEG-4 (`mpeg4`, tag `xvid`) | MP3 |
| WEBM | VP9 copiado, ou recodificado em `realtime` | Opus |
| RAW | `rawvideo` no formato de pixel escolhido | — |

O FFmpeg do seu sistema precisa ter esses codecs habilitados (as builds comuns para Windows já têm).

## Gerar o .exe (Windows)

Precisa do FFmpeg em `C:\ffmpeg\bin` (`ffmpeg.exe` e `ffprobe.exe`), que são embutidos no executável.

```
pip install pyinstaller pywebview
python build_exe.py
```

O executável sai em `dist/`, em um único arquivo.

## Gerar o .app (Mac)

Só funciona rodando no próprio Mac (o PyInstaller não faz build cruzado).

```
brew install python ffmpeg
cd mac
pip3 install pyinstaller pywebview
python3 build_mac.py
```

O script usa o `ffmpeg`/`ffprobe` do Homebrew (achados no PATH), empacota tudo com
PyInstaller e deixa o resultado em `mac/dist/Conversor de Videos.app`, copiando
também para a Área de Trabalho. Sem build, dá pra rodar direto o código-fonte:

```
brew install python ffmpeg
pip3 install pywebview
python3 main.py
```

## Estrutura

| Arquivo | Função |
|---------|--------|
| `main.py` | Fila e lote de conversão, e a ponte com a interface |
| `argila.py` | Parte Python do design system (janela, tema escuro, eventos para a interface), igual em todos os apps |
| `ui/` | A interface (`index.html`, `app.css`, `app.js`) e o design system Argila em `ui/ds/` |
| `.github/teste_e2e.py` | Teste de ponta a ponta na janela real (fila, conversão, .raw, erro, cancelar) |
| `build_exe.py` | Gera o `.exe` (Windows) com o FFmpeg embutido |
| `mac/build_mac.py` | Gera o `.app` (Mac) com o FFmpeg do Homebrew embutido |
| `ffmpeg_utils.py` | Monta os comandos do FFmpeg, executa a conversão e informa o progresso |
| `docs/capturas/` | Capturas de tela usadas neste README |

## Builds automáticos (GitHub Actions)

A cada envio para a `master`, a automação `.github/workflows/gerar-exe.yml` roda o teste de ponta a ponta
na janela real, num Windows e num Mac da nuvem do GitHub, e gera o `.exe` (Windows) e o `.app`
(Mac Apple Silicon e Mac Intel), com o FFmpeg embutido. Para baixar, abra a aba **Actions**, entre na
execução mais recente e role até **Artifacts**. No Mac, na primeira vez, clique no app com o botão
direito → **Abrir** (ele não é assinado com certificado da Apple).

## Design

A tela é feita em HTML/CSS e mostrada numa janela nativa pelo [pywebview](https://pywebview.flowrl.com/)
(Edge WebView2 no Windows, que já vem no Windows 11 e na maioria dos Windows 10; WebKit no Mac).
O design system **Argila** (`ui/ds/` e `argila.py`) é o mesmo do SnapYou, do Conversor de Imagens e do
my chaotic room: fontes Source Serif 4 e DM Sans (licença OFL), ícones [Lucide](https://lucide.dev)
(licença ISC). Veja `ui/ds/README.md`.

## Licenças

O arquivo `.exe` leva dentro o [FFmpeg](https://ffmpeg.org) (`ffmpeg.exe` e `ffprobe.exe`), versão 9.0.1 "essentials",
compilada por [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) com `--enable-gpl --enable-version3`,
ou seja, licenciada sob a **GNU GPL versão 3**. O FFmpeg não é obra minha: o código-fonte dele está em
<https://ffmpeg.org/download.html> e o da build usada, em <https://www.gyan.dev/ffmpeg/builds/>.
O texto da licença está em <https://www.gnu.org/licenses/gpl-3.0.html>.

