# Parzprint — especificação de design

Data: 2026-11-07
Status: aprovado em conversa, aguardando revisão do arquivo

## 1. Objetivo

Parzprint é um app de captura de tela para Windows e Linux, no estilo do Lightshot,
com uma adição: extrair o texto da imagem capturada (OCR) usando o Indra, rodando
100% local e offline. Uso pessoal. Sem conta, sem API, sem upload para nuvem.

Sucesso significa:

- Apertar um atalho configurável, selecionar uma área da tela, anotar com as mesmas
  ferramentas do Lightshot e salvar, copiar ou imprimir a imagem.
- Clicar em um botão "Texto" e, em poucos segundos, ter o texto da imagem em um painel
  editável, com os blocos destacados sobre a imagem, pronto para copiar inteiro ou
  em parte.
- O app ficar aberto na bandeja e iniciar junto com o sistema, nos dois sistemas.

## 2. Fora de escopo

- Upload para nuvem, link de compartilhamento, histórico de capturas.
- Gravação de vídeo ou GIF.
- OCR automático em toda captura (só roda quando o usuário clica em Texto).
- macOS (pode vir depois; nada no design impede).
- Tradução ou qualquer processamento do texto além do reconhecimento.

## 3. Tecnologia

| Papel | Escolha | Motivo |
|---|---|---|
| Linguagem | Python 3.11+ | O Indra é Python; evita processo separado |
| Interface | PySide6 (Qt 6) | Bandeja, janela sem borda em tela cheia, desenho, Windows e Linux |
| OCR | indra-ocr | Local, CPU, sem API; devolve texto com coordenadas |
| Captura de tela | mss | Rápido, múltiplos monitores, Windows e Linux (X11) |
| Atalho global | pynput | Windows e Linux X11 |
| Pastas do usuário | platformdirs | Config e cache no lugar certo em cada sistema |
| Empacotamento | PyInstaller (modo pasta) | Um executável por sistema |
| Testes | pytest | Lógica sem interface |

Dependência opcional: nada. O Indra baixa o modelo do Hugging Face na primeira vez
que o botão Texto é usado e guarda em cache. Depois disso não há rede.

## 4. Fluxo do usuário

1. O app inicia minimizado na bandeja. Ícone com menu: **Capturar**, **Configurações**,
   **Sair**. Clique duplo no ícone também captura.
2. Ao apertar o atalho (padrão `Ctrl+Shift+S`) ou escolher Capturar, o app fotografa
   todos os monitores e abre uma janela sem borda cobrindo cada monitor, com a foto
   escurecida.
3. O usuário arrasta para selecionar. Enquanto arrasta, a área selecionada aparece
   clara e um rótulo mostra largura × altura em pixels. `Esc` cancela.
4. Ao soltar, a seleção fica fixa, com alças nas bordas e cantos para ajustar.
   Aparecem duas barras coladas à seleção, iguais ao Lightshot:
   - **Barra lateral** (ferramentas): lápis, linha, seta, retângulo, marca-texto, texto,
     cor, desfazer.
   - **Barra inferior** (ações): salvar, copiar, imprimir, **Texto**, fechar.
   As barras se reposicionam se a seleção estiver perto da borda da tela.
5. Ações da barra inferior:
   - **Salvar**: diálogo de arquivo já na pasta padrão, nome `Parzprint_AAAA-MM-DD_HH-MM-SS`,
     formato da configuração (PNG ou JPG). Fecha a captura ao salvar.
   - **Copiar**: imagem com anotações para a área de transferência. Fecha a captura.
   - **Imprimir**: diálogo de impressão do Qt. Não fecha.
   - **Texto**: ver seção 5. Não fecha.
   - **Fechar** ou `Esc`: descarta.
6. Atalhos no editor: `Ctrl+Z` desfazer, `Ctrl+C` copiar imagem, `Ctrl+S` salvar,
   `Enter` copiar imagem e fechar.

### Ferramentas de anotação

| Ferramenta | Comportamento |
|---|---|
| Lápis | Traço livre, espessura fixa |
| Linha | Reta de ponto a ponto |
| Seta | Reta com ponta triangular na extremidade final |
| Retângulo | Contorno, sem preenchimento |
| Marca-texto | Faixa semitransparente, espessura maior |
| Texto | Clique posiciona, digita, `Enter` ou clique fora confirma |
| Cor | Paleta pequena fixa (vermelho padrão, amarelo, verde, azul, preto, branco) e seletor completo |
| Desfazer | Remove a última anotação |

Toda anotação é um objeto em uma lista; desenhar é percorrer a lista. Desfazer é
remover o último. A imagem final é a captura recortada com a lista desenhada por cima.

## 5. Botão Texto e painel de OCR

1. Ao clicar em Texto, a barra mostra um indicador de carregando e o Indra roda em uma
   thread separada sobre a área selecionada (sem as anotações). Na primeira vez pode
   haver download do modelo; o indicador avisa "baixando modelo".
2. Resultado: lista de blocos, cada um com texto e retângulo em coordenadas da seleção.
   Os blocos são ordenados de cima para baixo, esquerda para direita.
3. Abre um **painel** ao lado da seleção (à direita se couber, senão à esquerda):
   - Caixa de texto editável com todo o texto, um bloco por parágrafo.
   - Botões **Copiar tudo**, **Copiar seleção** e **Fechar painel**.
4. Sobre a imagem, cada bloco ganha uma caixa translúcida.
   - Passar o mouse sobre uma caixa destaca a linha correspondente no painel.
   - Passar o mouse sobre uma linha do painel destaca a caixa na imagem.
   - Arrastar o mouse sobre as caixas seleciona os blocos tocados; eles ficam destacados
     e **Copiar seleção** copia só esses, na ordem de leitura.
   - Clicar em uma caixa seleciona só ela.
5. Enquanto o painel está aberto as ferramentas de anotação ficam desativadas, para
   que o arrastar sobre a imagem signifique seleção de texto. Fechar o painel reativa
   as ferramentas; anotações feitas antes continuam lá.
6. O resultado do OCR fica em cache para a captura atual; reabrir o painel não roda de novo.
7. Se o OCR não encontrar texto, o painel abre com a mensagem "Nenhum texto encontrado".
8. Se o Indra falhar (não instalado, sem modelo, erro), o painel mostra a mensagem de erro
   e um botão para tentar de novo. A captura de imagem continua funcionando normalmente.

## 6. Configurações

Janela acessível pela bandeja, com:

| Campo | Padrão | Observação |
|---|---|---|
| Atalho de captura | `Ctrl+Shift+S` | Campo que grava a combinação pressionada |
| Iniciar com o sistema | ligado | Aplica na hora (seção 7) |
| Pasta padrão para salvar | pasta Imagens do usuário | Botão para escolher |
| Formato | PNG | PNG ou JPG |
| Motor de OCR | Indra | Lista com um só item por enquanto; preparado para outros |

Arquivo `settings.json` na pasta de configuração do usuário (via platformdirs):
Windows `%APPDATA%\Parzprint\settings.json`, Linux `~/.config/parzprint/settings.json`.
Arquivo ausente ou inválido volta aos padrões sem travar.

## 7. Integração com o sistema

### Instância única e comando de captura

O app mantém um `QLocalServer` com nome fixo. Uma segunda execução de `parzprint`
detecta o servidor, envia a mensagem recebida na linha de comando e sai.
`parzprint --capture` aciona a captura na instância aberta.
`parzprint --settings` abre as configurações.

### Atalho global

- Windows e Linux X11: pynput escuta a combinação configurada.
- Linux Wayland: atalho global não é possível para apps comuns. O app detecta Wayland
  (`XDG_SESSION_TYPE`), não tenta registrar o atalho e mostra nas configurações a
  instrução: cadastre nas configurações de teclado do sistema o comando
  `parzprint --capture` com o atalho desejado. A captura em Wayland usa o portal
  do sistema via Qt quando disponível; se a captura falhar, mostra um aviso claro.

### Iniciar com o sistema

- Windows: valor `Parzprint` em `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`
  apontando para o executável.
- Linux: arquivo `~/.config/autostart/parzprint.desktop` com `Exec=` apontando para
  o executável.
- Desligar a opção remove o valor ou o arquivo.

## 8. Estrutura interna

```
parzprint/
  __main__.py      ponto de entrada: instância única, argumentos, inicia a bandeja
  app.py           QApplication, liga os módulos
  tray.py          ícone e menu da bandeja
  hotkey.py        registro do atalho global; detecta Wayland
  capture.py       fotografa monitores (mss), devolve imagens e geometrias
  overlay.py       janela de seleção e editor (uma por monitor)
  toolbar.py       barras lateral e inferior
  annotations.py   modelo das formas, lista com desfazer, renderização
  ocr/
    base.py        interface OcrEngine: recognize(image) -> list[TextBlock]
    indra.py       adaptador do Indra
  textpanel.py     painel de texto e destaques sobre a imagem
  settings.py      leitura e escrita do settings.json, padrões
  autostart.py     registro Windows e .desktop Linux
  export.py        salvar, copiar, imprimir
tests/
```

Cada módulo tem uma responsabilidade. A interface (overlay, toolbar, textpanel,
tray) depende dos modelos (annotations, settings, ocr), nunca o contrário.

`TextBlock` é um dado simples: `text`, `x`, `y`, `width`, `height`. Qualquer motor
de OCR que devolva isso serve, o que permite trocar o Indra por outro sem mexer na
interface.

## 9. Tratamento de erros

- Captura falha (Wayland sem portal, permissão): aviso na bandeja, app continua.
- Atalho não pode ser registrado (já em uso): aviso nas configurações, app continua.
- Indra ausente ou com erro: mensagem no painel, botão tentar de novo, imagem continua.
- Falha ao salvar (pasta sem permissão): diálogo de erro, captura permanece aberta.
- settings.json corrompido: padrões, arquivo reescrito.

## 10. Testes

Com pytest, sem interface:

- `annotations`: adicionar, desfazer, desenhar em uma imagem e verificar pixels.
- `settings`: padrões, leitura, escrita, arquivo inválido.
- `autostart`: gera o conteúdo correto do `.desktop` e da chave de registro (registro
  testado só no Windows, com chave temporária).
- `ocr`: adaptador com motor falso; conversão do resultado do Indra para `TextBlock`;
  ordenação de leitura.
- `hotkey`: conversão da combinação gravada para o formato do pynput e detecção de Wayland.

A interface é verificada rodando o app: seleção, cada ferramenta, cada ação, painel
de texto com sincronização, configurações, bandeja. Checklist manual no plano.

## 11. Riscos e primeiro passo

O Indra só foi testado pelos autores em Linux e macOS. O primeiro passo do plano é
instalar `indra-ocr` neste Windows e rodar em um print em português. Se funcionar,
segue o plano. Se não, o adaptador `ocr/indra.py` é substituído por um de Tesseract
ou do OCR nativo do Windows, e nada mais muda.

Segundo risco: Wayland. Tratado na seção 7 com o comando `--capture`.

## 12. Empacotamento

PyInstaller em modo pasta, um por sistema, gerados na própria máquina de cada sistema.
O modelo do Indra não vai dentro do pacote; é baixado na primeira vez e fica no cache
do usuário. Ícone do app e do tray em `assets/`.
