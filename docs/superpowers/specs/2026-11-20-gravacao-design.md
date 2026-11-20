# Parzprint: gravação de tela

Data: 2026-11-20
Status: aguardando aprovação

## 1. Intenção

O Parzprint passa a gravar a tela além de tirar print e ler texto. Tudo sai do mesmo
atalho de captura: a pessoa escolhe a área (ou a tela inteira) e, na barra de baixo,
escolhe entre salvar, copiar, imprimir, ler o texto ou **gravar**. A gravação leva o som
do microfone e o som do computador. A referência de comportamento é o gravador da NVIDIA
(ShadowPlay): barrinha discreta, microfone escolhido na hora, vídeo salvo sozinho numa
pasta.

O pedido foi explícito em três pontos que definem o sucesso:

- funcionar em qualquer PC, inclusive sem placa de vídeo;
- poder gravar em resoluções menores, para o arquivo ficar menor e pesar menos no PC;
- comprimir no estilo do HandBrake, sem perder muita qualidade.

O tamanho do executável não importa. O que importa é a função completa como foi pedida.

## 2. Metas, fora de escopo e o que seria fracasso

Metas:

- Gravar uma área selecionada ou um monitor inteiro, em MP4 (H.264 + AAC).
- Gravar microfone e som do computador juntos, numa só faixa de áudio sincronizada.
- Escolher o microfone, mutar e trocar o modo do microfone durante a gravação.
- Resolução, quadros por segundo e qualidade configuráveis.
- Recompressão com x264 em qualidade constante, como o HandBrake.
- Os desenhos feitos antes de gravar aparecem no vídeo, e dá para desenhar durante a
  gravação (setas, linhas, texto etc.), também aparecendo no vídeo.

Fora de escopo:

- Gravação contínua em segundo plano do tipo "replay instantâneo" da NVIDIA.
- Webcam, edição/corte de vídeo, GIF, transmissão ao vivo.
- Gravação no Linux nesta etapa. O menu deve esconder o botão Gravar no Linux; nada no
  desenho impede fazer depois.

Seria fracasso, mesmo funcionando:

- Áudio fora de sincronia com o vídeo.
- A barrinha de gravação ou a borda da área aparecendo no vídeo.
- O PC travando durante a gravação de uma área em 1080p a 30 quadros por segundo.
- Perder a gravação inteira se algo der errado no fim (o arquivo gravado precisa
  sobreviver a uma falha da recompressão).
- O atalho de captura ou a tecla de apertar para falar chegando ao programa em foco (ver
  o ajuste recente do `RegisterHotKey`).

## 3. Restrições

- Windows 10 e 11, 64 bits, com ou sem placa de vídeo.
- Python 3.12, PySide6 6.12 (já tem `QScreenCapture`, `QMediaCaptureSession`,
  `QMediaRecorder`, `QVideoFrameInput`, `QAudioBufferInput`, `QAudioInput`,
  `QMediaDevices`; conferido em 2026-11-20).
- O Qt grava H.264 e AAC neste PC (conferido com `QMediaFormat`). O Qt escolhe sozinho o
  codificador: aceleração por hardware quando houver, senão o codificador por software do
  próprio Windows.
- Tudo local, sem rede.
- Textos da interface em português do Brasil, sem travessões.

## 4. Abordagens consideradas

1. **Qt para vídeo e microfone, biblioteca à parte para o som do computador (escolhida).**
   `QScreenCapture` captura o monitor; cada quadro é recortado para a área e entregue a um
   `QVideoFrameInput`. O microfone e o som do computador são capturados como amostras,
   misturados no Parzprint e entregues por `QAudioBufferInput`. Um único `QMediaRecorder`
   gera o MP4. Prós: uma dependência pequena nova, vídeo e áudio no mesmo relógio. Contra:
   o recorte quadro a quadro gasta processador; precisa ser medido.
2. **FFmpeg embutido gravando a tela.** Grava a área direto (gdigrab), mas no Windows não
   grava o som do computador sem um dispositivo virtual instalado. O som teria que ser
   gravado à parte e juntado no fim, com risco de dessincronia. Descartada.
3. **Captura acelerada por placa de vídeo, como a NVIDIA.** A mais leve em jogos, mas
   depende de placa de vídeo, o que fere a primeira meta. Descartada.

A pessoa escolheu a 1. A recompressão com x264 (seção 8) entra além dela.

## 5. Fluxo de uso

1. A pessoa aperta o atalho de captura (hoje `Ctrl+Alt+S`). Abre o overlay de sempre.
2. Arrasta para escolher a área. **Novo:** um clique sem arrastar seleciona o monitor
   inteiro em que o mouse está. Vale para print também.
3. A barra de baixo ganha o botão **Gravar** (ícone de círculo), ao lado de Texto.
4. Ao clicar em Gravar:
   - o overlay escurecido some e a tela volta ao normal;
   - aparece uma borda fina (2 px, vermelha) em volta da área, fora dela, e uma contagem
     de 3 segundos no centro da área;
   - a gravação começa.
5. Durante a gravação aparece a **barrinha de gravação**, colada embaixo da área (ou em
   cima, se não couber; ou no canto do monitor quando a área é a tela inteira):

   ```
    ● 00:42   🎤 Microfone (fifine) ▾   Sempre ligado ▾   🔊 Som do PC ✓   [✎ Desenhar]  [Pausar] [■ Parar]
   ```

   - tempo de gravação;
   - lista de microfones, com "Nenhum";
   - modo do microfone: **Desligado**, **Sempre ligado**, **Apertar para falar**;
   - liga/desliga do som do computador;
   - **Desenhar** (liga e desliga o modo de desenho, seção 5.1);
   - **Pausar/Continuar** e **Parar**.
6. A borda, a contagem e a barrinha **nunca aparecem no vídeo** (seção 7.2).
7. Parar: botão Parar, ou o atalho de captura de novo (enquanto grava, o atalho de captura
   passa a significar "parar"), ou `Esc` com a barrinha em foco.
8. Ao parar, o vídeo é salvo sozinho em `Vídeos\Parzprint\Parzprint_AAAA-MM-DD_HH-MM-SS.mp4`
   e aparece um aviso na bandeja com o nome do arquivo. Clicar no aviso abre a pasta com o
   arquivo selecionado.

### 5.1 Desenhos na gravação

- O que já estava desenhado na área quando a pessoa clicou em Gravar continua na tela,
  no mesmo lugar, e aparece no vídeo do começo ao fim (até ser apagado).
- O botão **Desenhar** da barrinha liga o modo de desenho. Nele:
  - a barra lateral de ferramentas de sempre aparece ao lado da área (lápis, linha, seta,
    retângulo, marca-texto, texto, cor, desfazer), com a roda do mouse mudando o tamanho
    como hoje;
  - ganha um botão **Limpar**, que apaga todos os desenhos de uma vez;
  - o mouse desenha sobre a área em vez de clicar nos programas por baixo;
  - a gravação continua rodando: cada traço aparece no vídeo no instante em que é feito.
- Apertar **Desenhar** de novo (ou `Esc`) sai do modo de desenho: a barra lateral some, os
  desenhos ficam na tela e o mouse volta a clicar normalmente nos programas da área.
- A barra lateral nunca aparece no vídeo; os desenhos sempre aparecem.

### 5.2 Microfone

- Trocar o microfone durante a gravação vale na hora; o áudio não corta.
- Mutar não corta o vídeo: aquele trecho do microfone fica em silêncio.
- **Apertar para falar:** o microfone só entra enquanto a pessoa segura uma tecla
  (padrão `Ctrl+Alt+Espaço`, configurável). Essa tecla também é registrada no Windows
  como exclusiva enquanto a gravação estiver nesse modo. Observação para o construtor: o
  `RegisterHotKey` avisa quando a tecla é apertada, mas não quando é solta; para saber
  quando soltou, consultar o estado da tecla (`GetAsyncKeyState`) num temporizador
  curto enquanto ela estiver apertada.
- Microfone, modo e som do PC escolhidos ficam salvos e voltam na próxima gravação.
- Se o microfone salvo não existir mais, usa o microfone padrão do Windows.

## 6. Configurações

Nova seção "Gravação" na janela de configurações:

| Campo | Padrão | Opções |
|---|---|---|
| Pasta dos vídeos | `Vídeos\Parzprint` | escolher pasta |
| Resolução | Original | Original, 1080p, 720p, 480p |
| Quadros por segundo | 30 | 30, 15 |
| Qualidade | Média | Alta, Média, Leve |
| Comprimir depois de gravar | ligado | liga/desliga |
| Tecla de apertar para falar | `Ctrl+Alt+Espaço` | gravada como o atalho de captura |
| Contagem antes de gravar | ligada | liga/desliga |

Regras:

- **Resolução** limita a altura do vídeo (1080, 720, 480) mantendo a proporção. Nunca
  aumenta: uma área de 600 px de altura fica com 600 em qualquer opção. Largura e altura
  finais sempre pares (exigência do H.264).
- Os campos novos entram em `Settings` (`settings.json`) com validação por campo e volta
  ao padrão, como os atuais.

## 7. Como funciona por dentro

### 7.1 Vídeo

- `QScreenCapture` no monitor da área. A cada quadro (`QVideoSink.videoFrameChanged`),
  recorta a área (em pixels físicos, usando a mesma escala do `Monitor` atual), reduz para
  a resolução escolhida e envia por `QVideoFrameInput.sendVideoFrame`.
- Ritmo: entrega no máximo os quadros por segundo escolhidos; quadros a mais são
  descartados. Cada quadro leva o carimbo de tempo do relógio da gravação.
- Pausa: para de entregar quadros e áudio; o relógio da gravação também para, para o
  vídeo não ter buraco.

### 7.2 Manter a barrinha e a borda fora do vídeo

Usar `SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)` (Windows 10 2004 ou mais
novo) nas janelas da barrinha, da borda e da contagem. Assim a captura do Windows não as
enxerga, mesmo quando ficam por cima da área. Em Windows mais antigo, posicionar a
barrinha e a borda sempre fora da área recortada (a borda já fica fora; a barrinha vai
para fora ou para o canto de outro monitor). Decisão do construtor, revisável: num Windows
antigo, gravando a tela inteira de um único monitor, não há onde pôr a barrinha; ela fica
escondida e a gravação para pelo atalho de captura ou pelo menu da bandeja (item "Parar
gravação"), com um aviso na bandeja ao começar.

### 7.2.1 Camada de desenho

Decisão do construtor, revisável: os desenhos ficam numa janela transparente, sem borda,
sempre no topo, exatamente sobre a área. Essa janela **não** é excluída da captura, então
o Windows grava os desenhos junto com a tela, sem custo extra por quadro. Fora do modo de
desenho, a janela deixa os cliques passarem para os programas por baixo
(`WS_EX_TRANSPARENT` + `WS_EX_LAYERED`); no modo de desenho, recebe o mouse. Reaproveitar o
modelo de anotações atual (`AnnotationStack`, `paint_annotation`) e a `SideToolbar`, com a
barra lateral excluída da captura como a barrinha. As coordenadas dos desenhos feitos no
editor antes de gravar passam para a camada sem mudar de lugar na tela.

### 7.2.2 Ponteiro do mouse

Decisão do construtor, revisável: o ponteiro aparece no vídeo, como no gravador da NVIDIA.
Se o `QScreenCapture` não trouxer o ponteiro no Windows, desenhá-lo em cada quadro
(posição por `GetCursorInfo`, forma por `DrawIconEx` numa imagem pequena guardada em
cache por forma). Entra na medição de processador da seção 10.

### 7.3 Áudio

- **Microfone:** captura pelo Qt (`QAudioSource` no dispositivo escolhido) em 48 kHz,
  estéreo, float.
- **Som do computador:** captura em loopback WASAPI do dispositivo de saída padrão com a
  biblioteca PyAudioWPatch. Converter para 48 kHz estéreo float se a saída usar outro
  formato.
- **Mistura:** soma as duas fontes por bloco (ex.: 20 ms), com limitador simples para não
  estourar. Microfone mutado, desligado ou com a tecla de falar solta entra como silêncio.
  Sem som no computador, o loopback entrega nada; preencher com silêncio para o relógio
  do áudio não parar.
- Entrega por `QAudioBufferInput.sendAudioBuffer`, com carimbo de tempo do mesmo relógio
  do vídeo.
- Saída AAC 48 kHz estéreo, 160 kbps.

### 7.4 Gravação e recompressão

- `QMediaRecorder` grava um MP4 H.264/AAC em qualidade constante (Alta/Média/Leve
  mapeadas para `QMediaRecorder.Quality`), num arquivo temporário `.gravando.mp4` na pasta
  de destino.
- **Comprimir depois de gravar** (seção 8): se ligado, ao parar, recomprime o arquivo com
  x264. Só troca pelo arquivo final quando a recompressão termina sem erro. Se falhar ou o
  app fechar no meio, o arquivo gravado continua lá, renomeado para o nome final.
- Se desligado, o arquivo gravado é renomeado para o nome final na hora.

## 8. Compressão no estilo do HandBrake

Embutir o FFmpeg com libx264 (o binário do pacote `imageio-ffmpeg`, GPL, cerca de 70 MB)
e recomprimir assim:

| Qualidade | Parâmetros x264 |
|---|---|
| Alta | `-crf 20 -preset slow` |
| Média | `-crf 23 -preset medium` |
| Leve | `-crf 27 -preset medium` |

Sempre `-pix_fmt yuv420p -movflags +faststart`, áudio copiado sem recompressão.

- Roda em segundo plano, numa thread, com prioridade baixa do processo, para não pesar no
  PC enquanto a pessoa usa outras coisas.
- Aviso na bandeja: "Comprimindo vídeo…" e depois "Vídeo salvo" com o tamanho final.
- Se o arquivo comprimido sair maior que o original, mantém o original.
- Uma gravação nova pode começar enquanto outra comprime.
- Antes de embutir, confirmar que o binário do `imageio-ffmpeg` tem `libx264`
  (`ffmpeg -encoders`). Se não tiver, usar outro build GPL do FFmpeg para Windows.

## 9. Erros

- Nenhum microfone: o modo vira Desligado e a lista mostra "Nenhum microfone".
- Falha no loopback (sem saída de áudio, dispositivo trocado no meio): segue gravando sem
  o som do PC e mostra um aviso na barrinha.
- Falha ao iniciar a gravação (codificador indisponível, pasta sem permissão): aviso na
  bandeja com o motivo; nada fica preso na tela.
- Disco cheio no meio: para a gravação, mantém o que foi gravado e avisa.
- Fechar o app pela bandeja durante a gravação: para e salva antes de sair.

## 10. Testes

- Lógica sem janela, com pytest: cálculo da resolução final (pares, nunca aumenta),
  mistura de áudio (soma, limitador, silêncio quando mutado), relógio da gravação com
  pausa, nomes de arquivo, novos campos de `Settings`, montagem dos argumentos do x264,
  regra de "manter o original se o comprimido for maior".
- Gravação real de 5 segundos de uma área e da tela inteira, com tom gerado tocando no
  som do PC: conferir com `ffprobe` duração, resolução, quadros por segundo, faixa de
  áudio presente e sincronia.
- **Medição do processador** ao gravar uma área 1080p a 30 quadros: se passar de 50% de
  um núcleo só no recorte, rever o recorte antes de seguir.
- Conferir numa gravação que a barrinha, a borda e a barra lateral não aparecem no vídeo,
  e que os desenhos (feitos antes e durante a gravação) aparecem.
- Conferir que, fora do modo de desenho, um clique na área chega ao programa por baixo.

## 11. Decisões deixadas ao construtor

- Organização dos arquivos novos (sugestão: `recording/` com `session.py`, `audio.py`,
  `video.py`, `compress.py`, e `recordbar.py` para a barrinha).
- Tamanho do bloco de áudio e da fila entre as threads.
- Ícones novos (gravar, pausar, parar, microfone, som), no mesmo estilo dos atuais.
- Como reduzir o quadro (Qt `scaled` com suavização é suficiente).

## 12. Verificado em 2026-11-20

Gravação de teste de 5 s de uma área 800×600 no monitor principal (1920×1080, escala 1),
com `QScreenCapture` → recorte → `QVideoFrameInput` e loopback PyAudioWPatch →
`QAudioBufferInput`:

- O MP4 saiu com H.264 (Constrained Baseline, yuv420p), 800×600, 30 fps, e AAC 48 kHz
  estéreo. O Qt usou o `H264 Encoder MFT`, o codificador por software do próprio Windows,
  então não depende de placa de vídeo.
- Recorte e redução: 7,3 ms por quadro em média (p95 12,4 ms). O processo inteiro,
  gravando, usou 44% de um núcleo. Ficou abaixo do limite de 50%.
- Uma janela com `SetWindowDisplayAffinity(hwnd, 0x11)` por cima da área não apareceu
  em nenhum quadro.
- O `QScreenCapture` **não** traz o ponteiro do mouse: precisa ser desenhado (seção 7.2.2).
- Loopback: dispositivo padrão `Speakers (F11) [Loopback]`, 44,1 kHz, 2 canais, float32.
  Precisa reamostrar para 48 kHz.
- O FFmpeg do `imageio-ffmpeg` 0.8.1 (v9.0.2, 100 MB) tem `libx264`.
