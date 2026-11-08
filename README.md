# Parzprint

Captura de tela para Windows e Linux, no estilo do Lightshot, com anotações e um botão
**Texto** que extrai o texto da imagem com o [Indra OCR](https://github.com/datalab-to/indra),
rodando localmente, sem conta e sem API.

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

Feche o Parzprint antes (bandeja, Sair): com ele aberto, o Windows trava os arquivos de `dist/`.

O resultado fica em `dist/Parzprint/` (`Parzprint.exe` no Windows). Copie a pasta inteira
para onde quiser e abra o executável: ele fica na bandeja e, se a opção estiver ligada,
passa a iniciar com o sistema a partir desse local.

O pacote do Linux precisa ser gerado numa máquina Linux. O modelo do Indra (cerca de
76 MB) não vai no pacote: ele é baixado na primeira vez que o botão **Texto** é usado.

## Uso

- **Atalho padrão:** `Ctrl+Shift+S` (muda em Configurações, no menu da bandeja).
- `parzprint --capture` abre a captura na instância já aberta. No Wayland, cadastre esse
  comando no atalho de teclado do sistema, porque lá o atalho global não funciona.
- `parzprint --settings` abre as configurações.
- No editor: `Ctrl+Z` desfaz, `Ctrl+C` ou `Enter` copia a imagem, `Ctrl+S` salva, `Esc` fecha.
- A roda do mouse muda o tamanho da ferramenta escolhida (lápis, linha, seta, retângulo,
  marca-texto e texto). O botão de cor abre a janela Cor do Windows.
- No botão **Texto**: arraste sobre o texto da imagem para selecionar um trecho, clique duas
  vezes numa palavra para pegá-la e use o botão **Copiar** que aparece ao lado. `Ctrl+A`
  seleciona tudo e `Ctrl+C` copia a seleção.
