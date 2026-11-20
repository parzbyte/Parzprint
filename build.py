"""Gera o executável com PyInstaller: python build.py

Saída: dist/Parzprint/Parzprint.exe (Windows) ou dist/Parzprint/Parzprint (Linux).
Gere o pacote de cada sistema na própria máquina desse sistema.
O modelo do Indra (cerca de 73 MB) vai dentro do pacote, então o botão Texto
funciona sem internet desde o primeiro uso.
"""

import os
import sys
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parent
SEP = os.pathsep  # ";" no Windows, ":" no Linux


def main() -> None:
    # python build.py [pasta-de-saida]   (padrão: dist/)
    extra = ["--distpath", sys.argv[1], "--workpath", str(Path(sys.argv[1]) / "build")] if len(sys.argv) > 1 else []
    from indra_ocr.models import model_dir

    model = model_dir()  # baixa do Hugging Face na primeira vez, depois usa o cache
    args = [
        str(ROOT / "run_parzprint.py"),
        "--name", "Parzprint",
        "--windowed",
        "--onedir",
        "--noconfirm",
        "--clean",
        "--add-data", f"{ROOT / 'parzprint' / 'assets'}{SEP}parzprint/assets",
        "--add-data", f"{model}{SEP}parzprint/models/indra",
        "--collect-all", "indra_ocr",
        "--collect-all", "onnxruntime",
        "--collect-submodules", "pynput",
        "--hidden-import", "PySide6.QtMultimedia",
        "--hidden-import", "PySide6.QtSvg",
        "--collect-all", "imageio_ffmpeg",
        "--collect-all", "pyaudiowpatch",
        "--exclude-module", "PySide6.QtWebEngineCore",
        "--exclude-module", "PySide6.QtWebEngineWidgets",
        "--exclude-module", "PySide6.Qt3DCore",
        "--exclude-module", "tkinter",
        *extra,
    ]
    if sys.platform == "win32":
        args += ["--icon", str(ROOT / "parzprint" / "assets" / "icon.ico")]
    PyInstaller.__main__.run(args)


if __name__ == "__main__":
    main()
