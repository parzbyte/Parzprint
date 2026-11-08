# Parzprint

Captura de tela para Windows e Linux no estilo do Lightshot. Dá para anotar a imagem e,
pelo botão Texto, copiar o texto que aparece nela. O texto é lido pelo
[Indra OCR](https://github.com/datalab-to/indra) no próprio computador, sem conta e sem API.

## Instalar

```bash
python -m venv .venv
.venv/Scripts/pip install -e .[dev]     # Linux: .venv/bin/pip
```

## Rodar

```bash
python -m parzprint
```

## Testar

```bash
pytest
```

## Gerar executável

```bash
python build.py
```

Feche o Parzprint pela bandeja (Sair) antes de gerar. Com ele aberto, o Windows trava os
arquivos de `dist/`.

O resultado fica em `dist/Parzprint/`. Copie a pasta inteira, não só o `Parzprint.exe`, e
abra o executável. Ele fica na bandeja e, com a opção ligada, passa a iniciar com o sistema
a partir da pasta onde está.

O modelo do Indra (cerca de 73 MB) vai dentro do pacote, então o botão Texto funciona sem
internet. O pacote do Linux precisa ser gerado numa máquina Linux.

## Uso

- O atalho padrão é `Ctrl+Shift+S`. Ele muda em Configurações, no menu da bandeja.
- `parzprint --capture` abre a captura na instância que já está aberta. No Wayland o atalho
  global não funciona, então cadastre esse comando no atalho de teclado do sistema.
- `parzprint --settings` abre as configurações.
- No editor, `Ctrl+Z` desfaz, `Ctrl+C` ou `Enter` copia a imagem, `Ctrl+S` salva e `Esc` fecha.
- A roda do mouse muda o tamanho da ferramenta escolhida. O botão de cor abre a janela Cor
  do Windows.
- Com o painel de texto aberto, arraste sobre o texto da imagem para selecionar um trecho ou
  clique duas vezes numa palavra. O botão Copiar aparece ao lado da seleção. `Ctrl+A`
  seleciona tudo e `Ctrl+C` copia o que estiver selecionado.
