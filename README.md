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
