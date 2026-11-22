# O que mudou

## 1.1.0 (2026-11-22)

### Novo: tradutor

O Parzprint agora traduz texto pelo Google Tradutor, sem abrir o navegador.

- **Atalho Ctrl+Alt+T** (Ctrl+Alt+Y no Linux): selecione um texto em qualquer programa e
  aperte. Uma janela abre perto do mouse já com a tradução.
- **Escolha dos idiomas** como no Google Tradutor: origem com "Detectar idioma" e destino à
  sua escolha. O botão ⇄ inverte os dois. Os idiomas que você usa por último aparecem no
  topo da lista, e a escolha fica salva.
- **Traduzir a imagem**: no print, escolha a área e clique no botão novo da barra. O app
  lê o texto da imagem e abre a tradução.
- **Botão Traduzir no painel de texto** do OCR, para traduzir o trecho selecionado ou o
  texto todo.
- **Item "Traduzir" na bandeja** e o comando `parzprint --translate`, para digitar ou
  colar um texto.
- **Configurações**: seção "Tradutor", com o atalho e a opção "Pegar o texto selecionado".

### Como o tradutor cuida do que você copia

- Texto que já estava copiado não vai direto para o Google. Ele aparece na janela e só é
  traduzido quando você aperta Enter, porque pode ser algo copiado horas antes, até uma
  senha.
- Nada sai do computador sem você pedir a tradução. Até esta versão o Parzprint não usava
  a internet; o tradutor é a única parte que usa.
- No console do Windows, no Windows Terminal e no mintty, o atalho não aperta Ctrl+C, para
  não interromper o que estiver rodando. Ele usa o texto já copiado e espera o Enter.

### Para saber

- O endereço gratuito do Google Tradutor não é oficial. Se o Google recusar ou mudar, a
  janela avisa e oferece abrir o texto no Google Tradutor do navegador.
- A janela do tradutor não aparece nas gravações de tela.
- Alguns editores, como o VS Code e o Excel, copiam a linha inteira quando nada está
  selecionado. Nesses casos é essa linha que vai ser traduzida.

## 1.0.1 (2026-11-22)

- A gravação de tela não trava mais em PC fraco. Antes, em computadores mais lentos, o app
  podia parar de responder poucos segundos depois de começar a gravar.

## 1.0.0 (2026-11-20)

Primeira versão.

- Print com atalho, seleção de área e as ferramentas de anotação (seta, linha, retângulo,
  lápis, marca-texto e texto).
- Copiar o texto da imagem com o Indra, sem internet e sem enviar nada para fora.
- Gravação de tela no Windows, da área ou da tela inteira, com microfone e som do
  computador, desenho durante a gravação e compressão no fim.
- Fica na bandeja, abre com o sistema e o atalho pode ser trocado.
