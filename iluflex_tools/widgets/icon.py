# file: iluflex_tools/widgets/icons.py
from __future__ import annotations
from pathlib import Path
import sys

def _resource_ico() -> Path:
    """
    Resolve o caminho do .ico em dev e quando empacotado.
    Por quê: em PyInstaller, os assets podem ser extraídos em _MEIPASS.
    """
    ico_rel = Path("iluflex_tools/ui/iluflex-tools-icon.ico")
    if getattr(sys, "_MEIPASS", None):  # PyInstaller
        base = Path(sys._MEIPASS)
        # quando empacota, inclua o .ico como data; este caminho reflete a pasta do bundle
        cand = base / "iluflex_tools" / "ui" / "iluflex-tools-icon.ico"
        return cand if cand.exists() else ico_rel
    return Path(__file__).resolve().parents[1] / "ui" / "iluflex-tools-icon.ico"

def setup_window_icon(root) -> None:
    """
    Aplica o ícone na janela principal (titlebar/taskbar do Windows).
    Por quê: garante identidade visual do app independentemente do ambiente.
    """
    ico = _resource_ico()
    try:
        root.iconbitmap(default=str(ico))
    except Exception:
        # Tk no Linux/macOS pode falhar com .ico; como temos .ico e alvo é Windows, ignoramos.
        pass