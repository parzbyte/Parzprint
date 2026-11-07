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
