# Tradutor do Parzprint: especificação de design

Data: 2026-11-22
Status: aguardando aprovação do David

## 1. Objetivo

Hoje, para traduzir algo, o David copia o texto, abre o Google Tradutor no navegador e cola.
O tradutor do Parzprint corta esse caminho. Ele seleciona o texto em qualquer programa,
aperta um atalho e uma janelinha abre perto do mouse com a tradução pronta. Dá para
escolher o idioma de origem e o de destino, como no Google Tradutor.

Precisa rodar em qualquer PC, inclusive nos fracos onde a gravação travava.

Sucesso significa:

- Selecionar um texto num site, PDF ou WhatsApp, apertar o atalho e ver a tradução em
  menos de 2 segundos com internet normal.
- Trocar o idioma de origem ou de destino na própria janela, e o app lembrar a escolha.
- O app nunca congelar esperando a internet.

## 2. Metas, não metas e o que seria fracasso

Metas:

- Atalho global próprio para traduzir, configurável, separado do atalho do print.
- Janela de tradução no estilo do Google: idioma de origem (com "Detectar idioma"),
  idioma de destino, botão de trocar, texto de origem editável e resultado com botão Copiar.
- Botão "Traduzir" no painel de texto do OCR.
- Item "Traduzir" no menu da bandeja, que abre a janela vazia para digitar.

Não metas (ficam fora desta versão):

- Tradução sem internet.
- Outros serviços (DeepL, Bing, modelos locais).
- Ler o texto em voz alta, dicionário, sinônimos, histórico de traduções.
- Traduzir por cima da imagem do print, no lugar do texto original.

Seria fracasso, mesmo funcionando:

- A interface travar enquanto espera o Google.
- O app ficar mais pesado para abrir ou ocupar mais memória parado. Nada novo é criado
  antes do primeiro uso do tradutor.
- Mandar qualquer texto para fora sem o David ter pedido a tradução.
- Puxar biblioteca nova pesada (requests, motor de navegador). Usa só o que o Python e o
  Qt já trazem.

## 3. Restrições

- Até agora o Parzprint não usa internet para nada. O tradutor é a primeira função que
  manda texto para fora, e só manda quando o David pede a tradução. A tela de configurações
  e o README dizem isso com todas as letras.
- O serviço é o endereço gratuito do Google Tradutor
  (`https://translate.googleapis.com/translate_a/single?client=gtx`), sem chave e sem
  cadastro. Ele não é oficial, e o Google pode limitar ou mudar sem aviso. Quando falhar,
  a janela diz isso e oferece abrir o texto no Google Tradutor do navegador.
- Mesmas regras do resto do app: textos de tela em português e sem travessão, marca
  Parzbyte (vermelho `#E11D2E`, grafite), sem marca de ferramenta, testes com pytest.
- Windows é o alvo principal. No Linux funciona em X11. No Wayland não existe atalho
  global, então o David liga o comando `parzprint --translate` a um atalho do sistema,
  como já acontece com `--capture`.

## 4. Jeitos de construir que consideramos

1. **Selecionar e apertar o atalho (escolhido).** O app faz o Ctrl+C sozinho e traduz o
   que estava selecionado. Tira um passo do caminho. Em alguns programas o Ctrl+C automático
   não pega nada (terminal, jogos); aí ele usa o que já estava copiado.
2. **Copiar e apertar o atalho.** Mais previsível, mas mantém o passo de copiar, que é
   justamente o que se quer cortar.
3. **Janela de navegador embutida com o site do Google Tradutor.** Descartado: exigiria o
   motor de navegador do Qt, que pesa centenas de MB e muita memória, o contrário de
   "rodar em qualquer PC".

Ficou o 1, que cai sozinho no 2 quando não consegue pegar a seleção. O David não discordou
quando propus e depois pediu a escolha de idiomas no estilo do Google, que entrou na janela.

## 5. Como funciona

### 5.1 Pegar o texto

Ao apertar o atalho de tradução:

- **Windows:** o app espera as teclas do atalho serem soltas (até 500 ms), anota o número
  de sequência da área de transferência (`GetClipboardSequenceNumber`), manda um Ctrl+C
  com `SendInput` e espera até 300 ms o número mudar. Se mudou e veio texto, usa esse texto.
  Se não mudou, usa o texto que já estava na área de transferência. Se não houver nenhum
  texto, abre a janela vazia com o cursor no campo de origem.
- **Linux X11:** lê a seleção primária do X (o texto selecionado, sem copiar), pelo modo
  `Selection` do `QClipboard`. Se vier vazia, usa a área de transferência normal.
- **Texto que já estava copiado não vai direto para o Google** (decisão do David). Ele pode
  ser de horas antes, até uma senha. Quando o texto veio da seleção, traduz na hora. Quando
  veio do que já estava copiado (ou da área de transferência normal no Linux), ele só
  preenche o campo de origem, selecionado, com o aviso "Texto que estava copiado. Aperte
  Enter para traduzir." Enter (ou o botão Traduzir) manda; digitar por cima troca o texto.
  Depois da primeira tradução, editar volta a traduzir sozinho após 600 ms.
- Uma opção nas configurações, "Pegar o texto selecionado", desliga o Ctrl+C automático.
  Com ela desligada, o atalho usa só o que já estava copiado, com a mesma confirmação.

Decisão minha: o texto copiado pelo Ctrl+C automático fica na área de transferência, como
se o David tivesse copiado. Restaurar o conteúdo anterior (que pode ser uma imagem ou um
arquivo) é frágil e pode estragar o que estava lá.

### 5.2 A janela

```
┌──────────────────────────────────────────────── [📌] [×] ┐
│ [Detectar idioma: inglês ▾]    [⇄]    [Português ▾]      │
│ ┌──────────────────────────┐  ┌────────────────────────┐ │
│ │ The quick brown fox...   │  │ A rápida raposa...     │ │
│ │ (editável)               │  │ (só leitura)           │ │
│ └──────────────────────────┘  └────────────────────────┘ │
│                                           [Copiar]       │
└──────────────────────────────────────────────────────────┘
```

- Abre perto do mouse, sempre inteira dentro da área útil da tela (acima da barra de
  tarefas), como a barra de gravação já faz.
- Origem e destino lado a lado quando a janela é larga; um em cima do outro quando é
  estreita. O tamanho que o David deixar fica salvo.
- **Idioma de origem:** lista com "Detectar idioma" no topo, depois os idiomas usados por
  último, depois todos os idiomas que o Google aceita, em ordem alfabética e com nome em
  português. Dá para digitar para filtrar. Com "Detectar idioma", o rótulo mostra o idioma
  detectado ("Detectar idioma: inglês").
- **Idioma de destino:** mesma lista, sem "Detectar idioma". Padrão: português.
- **Trocar (⇄):** inverte origem e destino e passa a tradução para o campo de origem. Se a
  origem estava em "Detectar idioma", usa o idioma detectado.
- A escolha de origem e destino fica salva para a próxima vez.
- Editar o texto de origem traduz de novo depois de 600 ms sem digitar. Trocar um idioma
  traduz na hora.
- **Copiar** copia a tradução. Ctrl+Enter também copia e fecha a janela.
- Esc fecha. Clicar fora fecha, a não ser que o alfinete (📌) esteja ligado; aí a janela
  fica aberta e por cima até ser fechada.
- Enquanto traduz, o resultado mostra "Traduzindo..." e a janela continua respondendo.

### 5.3 Falar com o Google

- Pedido HTTPS ao endereço gratuito, com `sl` (origem ou `auto`), `tl` (destino), `dt=t` e
  o texto. Texto mandado no corpo de um POST
  para não esbarrar no limite de tamanho do endereço.
- Usa o `QNetworkAccessManager` do Qt (o app já usa o QtNetwork na instância única), sem
  biblioteca nova e sem thread nossa: o pedido corre por fora e a interface não espera.
  Decisão minha: com `urllib` numa thread, um pedido preso faria os seguintes esperarem até
  8 s, e o Qt permite cancelar de verdade. Pedido novo cancela o anterior (`abort()`), então
  só a resposta do último pedido aparece.
- Tempo máximo de 8 segundos por pedido.
- Limite de 5.000 caracteres, o mesmo do Google Tradutor. Acima disso, traduz os primeiros
  5.000 e avisa que cortou.
- A resposta traz a tradução em pedaços e o idioma detectado. O app junta os pedaços e mostra.

### 5.4 Quando dá errado

| Situação | O que aparece no resultado |
|----------|----------------------------|
| Sem internet ou demorou mais de 8 s | "Não consegui falar com o Google Tradutor. Confira a internet." + [Tentar de novo] |
| Google recusou (muitos pedidos, 429, ou outro erro) | "O Google Tradutor recusou o pedido agora. Espere um pouco e tente de novo." + [Tentar de novo] |
| Resposta num formato que o app não entende | "O Google Tradutor mudou o jeito de responder. Atualize o Parzprint." |

Nos três casos aparece também [Abrir no Google Tradutor], que abre o navegador com o texto e
os idiomas já preenchidos.

### 5.5 Outras entradas

- **Painel do OCR:** botão "Traduzir" ao lado de "Copiar seleção". Fecha a captura, como o
  "Copiar seleção" já faz, e abre a janela de tradução com o trecho selecionado ou, sem
  seleção, com o texto todo. Decisão minha: deixar a janela por cima da captura em tela cheia
  complicaria o foco e o "clicar fora fecha", e o David já pediu antes que copiar o texto
  feche a captura.
- **Durante uma gravação:** o tradutor funciona normalmente, e a janela fica fora do vídeo,
  com o mesmo recurso que já esconde a barra de gravação. Decisão minha.
- **Atalho do print (pedido do David):** na barra de ferramentas da captura, ao lado de
  "Ler o texto da imagem" e "Gravar a tela", entra o botão "Traduzir a imagem". O David
  aperta o atalho do print, escolhe a área e clica nele. O app lê o texto da área com o
  Indra (reaproveitando a leitura se o OCR já rodou nessa captura), mostrando "Lendo o
  texto..." no lugar de sempre. Com o texto pronto, a captura fecha e a janela de tradução
  abre junto da área escolhida, já traduzindo: o texto acabou de ser escolhido por ele, então
  não precisa de Enter. Se o Indra não achar texto, a captura continua aberta com o aviso
  "Não achei texto nessa área." Se o OCR falhar, aparece o mesmo erro do botão de texto.
- **Bandeja:** item "Traduzir" abre a janela vazia, pronta para digitar ou colar.
- **Linha de comando:** `parzprint --translate` faz o mesmo que o atalho (para o Wayland e
  para quem quiser ligar a outro atalho). Usa a instância que já está aberta, como o
  `--capture`.

### 5.6 Configurações

Seção nova "Tradutor" na janela de configurações:

- Atalho do tradutor. Padrão Ctrl+Alt+T no Windows e Ctrl+Alt+Y no Linux, porque lá o
  Ctrl+Alt+T já abre o terminal na maioria dos sistemas (decisão minha). Não pode ser igual ao atalho do print nem ao do
  aperte para falar.
- "Pegar o texto selecionado" (ligado por padrão).
- Aviso: "Para traduzir, o texto é enviado ao Google Tradutor. Nada sai do computador sem
  você pedir."

Ficam salvos em `settings.json`: `translate_hotkey`, `translate_grab_selection`,
`translate_source` (padrão `auto`), `translate_target` (padrão `pt`), `translate_recent`
(até 5 códigos), `translate_size` e `translate_pinned`. Valores inválidos voltam ao padrão,
como os outros campos.

## 6. Testes

- Montagem do pedido e leitura da resposta, com respostas reais gravadas como exemplo, incluindo
  respostas quebradas e erros.
- Lista de idiomas: códigos válidos, nomes em português, ordem com os recentes.
- Janela com um tradutor falso: troca de idiomas, botão de trocar, espera de 600 ms, só a
  última resposta aparece, mensagens de erro, Esc, alfinete.
- Pegar o texto com uma área de transferência falsa: seleção pega, seleção vazia, opção
  desligada, e que texto antigo nunca é enviado sem Enter.
- Configurações novas: padrões, validação, atalho repetido recusado.
- Nenhum teste acessa a internet. Um teste manual no exe confere a tradução de verdade.

## 7. Fica a critério de quem constrói

- Nomes de arquivos e classes (sugestão: `parzprint/translate/` com `google.py`,
  `languages.py`, `grab.py` e `window.py`).
- Visual exato da janela, dentro do tema escuro e da marca que o app já usa.
- Como a thread de pedidos se comunica com a interface (sinal do Qt é o caminho natural).
