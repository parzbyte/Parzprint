# Parzprint

Parzprint é uma ferramenta de captura de tela para Windows, no estilo do Lightshot. Com um
atalho você escolhe uma área da tela e, a partir dela, pode:

- anotar a imagem com setas, linhas, retângulos, marca-texto e texto, e depois salvar,
  copiar ou imprimir;
- copiar o texto que aparece na imagem, lido no próprio computador pelo
  [Indra OCR](https://github.com/datalab-to/indra), sem conta, sem internet e sem API;
- gravar a área (ou a tela inteira) em vídeo, com o som do microfone e o som do computador,
  desenhando por cima enquanto grava.

O app fica na bandeja do sistema e abre junto com o Windows.

![Anotações feitas no Parzprint](docs/img/anotacoes.png)

## Como usar

### Print e anotações

Aperte o atalho de captura (o padrão é `Ctrl+Shift+S`, e dá para trocar em Configurações).
A tela escurece; arraste para escolher a área, ou clique sem arrastar para pegar o monitor
inteiro. Aparecem duas barras coladas na seleção, como no Lightshot.

| Ferramentas | Ações |
|---|---|
| ![Barra de ferramentas](docs/img/barra-lateral.png) | ![Barra de ações](docs/img/barra-acoes.png) |

A barra lateral tem lápis, linha, seta, retângulo, marca-texto, texto, cor e desfazer. A roda
do mouse muda o tamanho da ferramenta escolhida, e o botão de cor abre a janela Cor do
próprio Windows. A barra de baixo salva, copia, imprime, lê o texto, grava e fecha.

No editor, `Ctrl+Z` desfaz, `Ctrl+C` ou `Enter` copia a imagem, `Ctrl+S` salva e `Esc` fecha.

### Copiar o texto da imagem

O botão de texto lê a área selecionada e abre um painel ao lado. A seleção funciona como no
Google Lens: você arrasta sobre o texto da própria imagem, de qualquer letra até qualquer
outra, e o trecho fica marcado. Um clique duplo pega uma palavra e `Ctrl+A` pega tudo. Ao
copiar, a captura fecha sozinha, porque o trabalho já terminou.

![Painel de texto](docs/img/painel-texto.png)

O modelo do Indra (cerca de 73 MB) vai dentro do executável, então isso funciona offline
desde o primeiro uso.

### Gravar a tela

Depois de escolher a área, clique em Gravar. Uma contagem de 3 segundos aparece e a gravação
começa. Uma barrinha fica colada embaixo da área:

![Barrinha de gravação](docs/img/barra-gravacao.png)

Nela você vê o tempo, troca o microfone, escolhe o modo dele (desligado, sempre ligado ou
apertar para falar com `Ctrl+Alt+Espaço`), liga o som do computador, desenha, pausa e para.
A barrinha e a borda vermelha em volta da área não aparecem no vídeo. Os desenhos e o
ponteiro do mouse aparecem.

Para parar, use o botão da barrinha, o mesmo atalho de captura ou o item "Parar gravação"
da bandeja. O vídeo vai para `Vídeos\Parzprint` em MP4 e é recomprimido em segundo plano
com x264, do mesmo jeito que o HandBrake faz. Resolução (original, 1080p, 720p ou 480p),
quadros por segundo e qualidade ficam em Configurações.

## Instalar

### Pelo executável

Gere a pasta `dist/Parzprint` com `python build.py` (veja abaixo), coloque onde quiser e abra o
`Parzprint.exe`. Não precisa instalar nada: o pacote já traz o Python, o Qt, o modelo do
Indra e o FFmpeg. Copie a pasta inteira, porque o executável depende da pasta `_internal`
que fica ao lado dele.

Na primeira vez o Windows pode mostrar "O Windows protegeu o computador", porque o
executável não tem assinatura digital. Clique em "Mais informações" e em "Executar assim
mesmo".

### Pelo código

Precisa do Python 3.11 ou mais novo.

```bash
python -m venv .venv
.venv/Scripts/pip install -e .[dev]
python -m parzprint
```

Para gerar o executável (feche o Parzprint antes, porque com ele aberto o Windows trava os
arquivos de `dist/`):

```bash
python build.py
```

Para rodar os testes:

```bash
pytest
```

## Como foi feito

O Parzprint é escrito em Python com PySide6 (Qt 6). A interface inteira é desenhada pelo
próprio app: os ícones são SVG feitos para ele, e as anotações são desenhadas com o
`QPainter` do Qt, com suavização, o mesmo código na tela e na imagem salva.

### Captura e editor

Ao apertar o atalho, o app fotografa cada monitor com `QScreen.grabWindow` e abre por cima
de cada um uma janela sem borda com essa foto escurecida. Cada monitor guarda a própria
geometria em pixels lógicos e a foto em pixels físicos. É isso que mantém o recorte certo
quando os monitores têm escalas diferentes. As anotações ficam numa lista de objetos (seta,
linha, retângulo...) e desfazer é tirar o último da lista.

### Atalho global

No Windows o atalho é registrado com `RegisterHotKey`, como o Lightshot faz. Assim a
combinação vai só para o Parzprint e não chega ao programa em foco. Isso resolveu um
conflito real com o WhatsApp Web, que também usa `Ctrl+Alt+S`. Uma segunda execução do
programa não abre outra cópia: ela avisa a que já está aberta por um `QLocalServer`.

### Texto da imagem

O Indra devolve a caixa de cada linha de texto. Como a seleção precisa ir de uma letra até
outra, o Parzprint estima onde cada letra fica dentro da linha pela largura relativa das
letras na fonte da tela. O OCR roda numa thread separada para a tela não travar, e sem o
modelo de orientação do Indra, porque um print de tela está sempre de pé.

### Gravação

A gravação junta três fontes num único relógio:

1. **Vídeo.** O `QScreenCapture` do Qt entrega os quadros do monitor. Cada quadro é recortado
   para a área, recebe o ponteiro do mouse desenhado por cima (o Qt não traz o ponteiro) e
   segue para um `QVideoFrameInput`, no máximo 30 quadros por segundo.
2. **Microfone.** Vem de um `QAudioSource` do Qt.
3. **Som do computador.** O Qt não grava a saída de som, então ela vem por loopback WASAPI
   com a biblioteca PyAudioWPatch.

Os dois áudios são convertidos para 48 kHz estéreo, misturados em blocos de 20 ms com um
limitador simples e entregues a um `QAudioBufferInput`. Um `QMediaRecorder` grava o MP4 em
H.264 e AAC, usando o codificador do próprio Windows, que funciona com ou sem placa de vídeo.

Para a barrinha e a borda ficarem fora do vídeo, essas janelas usam
`SetWindowDisplayAffinity` com `WDA_EXCLUDEFROMCAPTURE`. A camada de desenho é o contrário:
uma janela transparente por cima da área que o Windows grava junto com a tela. Fora do modo
de desenho ela deixa os cliques passarem para os programas de baixo.

Ao parar, o FFmpeg embutido recomprime o vídeo com x264 em qualidade constante (CRF 20, 23
ou 27, conforme a qualidade escolhida). O arquivo original só é trocado se a compressão der
certo e ficar menor.

### O que foi medido

| Medição | Resultado |
|---|---|
| Processador gravando uma área 800×600 a 30 quadros por segundo | 44% de um núcleo |
| Sincronia entre áudio e vídeo | áudio de 43 a 86 ms depois da imagem |
| Recompressão x264 de 5 segundos | de 758 KB para 136 KB em 0,4 s |
| Leitura do Indra numa imagem pequena | 0,06 s depois de carregar o modelo |

A sincronia anda em passos de 43 ms porque esse é o tamanho de um bloco de áudio AAC.

### Testes

São 210 testes automáticos com pytest. A lógica sem tela (geometria, mistura de áudio,
relógio com pausa, compressão, configurações) é testada direto, e a interface é testada numa
janela do Qt sem tela. Os comportamentos que dependem do Windows de verdade (captura,
exclusão da captura, atalho global, som do computador) foram conferidos com gravações reais
e medidos com o FFmpeg.

Os documentos de design e os planos de implementação de cada etapa estão em
[`docs/superpowers`](docs/superpowers).

## Estrutura

```
parzprint/
  app.py               liga bandeja, atalho, captura, editor e gravação
  overlay.py           janela de seleção de área, uma por monitor
  editor.py            anotações, ações e modo de texto
  annotations.py       modelo das anotações e desenho
  textpanel.py         painel de texto e seleção contínua
  ocr/                 adaptador do Indra
  hotkey.py            atalho global (RegisterHotKey no Windows)
  recording/
    session.py         sessão de gravação e gravador MP4
    audio.py           microfone, som do computador e mistura
    video.py           recorte dos quadros e ponteiro do mouse
    drawlayer.py       camada de desenho durante a gravação
    recordbar.py       barrinha de gravação
    compress.py        recompressão com x264
tests/                 testes automáticos
build.py               gera o executável com PyInstaller
```

## Limitações conhecidas

- O app foi feito pensando também no Linux, mas só foi testado no Windows. No Linux o botão
  Gravar não aparece.
- Em Windows 10 de antes da versão 2004, o Windows não consegue esconder a barrinha do vídeo.
- O ponteiro de texto (a barrinha "I") sai branco no vídeo e some sobre fundo branco.
- O Indra lê "Última" como "Ultima" em letras maiúsculas acentuadas, um limite do modelo.

## Licenças de terceiros

O executável inclui software de terceiros com licenças próprias:

- [Indra OCR](https://github.com/datalab-to/indra): código Apache 2.0. Os pesos do modelo
  usam uma licença OpenRAIL-M modificada, livre para pesquisa, uso pessoal e empresas com
  menos de US$ 20 milhões de faturamento ou investimento, e que não permite concorrer com a
  API da Datalab.
- [Qt / PySide6](https://www.qt.io/): LGPL v3.
- [FFmpeg](https://ffmpeg.org/) com x264, vindo do pacote `imageio-ffmpeg`: GPL.
- [PyAudioWPatch](https://github.com/s0d3s/PyAudioWPatch): MIT.
