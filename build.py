"""Gera o executável com PyInstaller: python build.py

Saída: dist/Parzprint/Parzprint.exe (Windows) ou dist/Parzprint/Parzprint (Linux).
Gere o pacote de cada sistema na própria máquina desse sistema.
O modelo do Indra não vai no pacote: é baixado na primeira vez que o botão Texto é usado.
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
    args = [
        str(ROOT / "run_parzprint.py"),
        "--name", "Parzprint",
        "--windowed",
        "--onedir",
        "--noconfirm",
        "--clean",
        "--add-data", f"{ROOT / 'parzprint' / 'assets'}{SEP}parzprint/assets",
        "--collect-all", "indra_ocr",
        "--collect-all", "onnxruntime",
        "--collect-submodules", "pynput",
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
