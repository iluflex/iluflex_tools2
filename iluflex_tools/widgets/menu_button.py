
import os, sys
from typing import Optional
from PIL import Image
import customtkinter as ctk

# Icons live in ../theming/icons relative to this file

from pathlib import Path

def _base_dir():
    # Quando empacotado, os dados vão para _MEIPASS/iluflex_tools
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / "iluflex_tools"
    # desenvolvimento: .../iluflex_tools
    return Path(__file__).resolve().parents[1]

ICON_DIR = _base_dir() / "theming" / "icons"

# ICON_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "theming", "icons"))

def _find_icon_pair(name: str, size: int):
    # tenta size pedido -> 28 -> 24
    for s in (size, 28, 24):
        lp = ICON_DIR / f"{name}_{s}px_light.png"
        dp = ICON_DIR / f"{name}_{s}px_dark.png"
        l = lp if lp.exists() else None
        d = dp if dp.exists() else None
        if l and d:
            return str(l), str(d)
        if l or d:
            return str(l) if l else None, str(d) if d else None
    return None, None

def ctk_image(name: str, size: int) -> ctk.CTkImage:
    light, dark = _find_icon_pair(name, size)
    if not (light or dark):
        # fallback neutro
        light, dark = _find_icon_pair("question-mark", size)
    li = Image.open(light) if light else None
    di = Image.open(dark)  if dark  else None
    if not (li or di):
        # última proteção: não derrubar a UI silenciosamente
        raise FileNotFoundError(f"Icon '{name}' {size}px não encontrado em {ICON_DIR}")
    return ctk.CTkImage(light_image=li or di, dark_image=di or li, size=(size, size))

def ctk_imageLight(name:str, size: int, theme: str = None) -> ctk.CTkImage:
    light, dark = _find_icon_pair(name, size)
    di = Image.open(dark)
    return ctk.CTkImage( dark_image=di, size=(size, size))


class MenuButton(ctk.CTkButton):
    """
    CTkButton com suporte integrado a ícone (light/dark), tooltip opcional
    e comportamento collapsed (ícone puro vs ícone + texto).

    Args:
        master: parent
        text: rótulo
        icon: nome do arquivo base (ex.: "server-cog"), sem o sufixo _sizepx_light/dark
        collapsed: se True, mostra apenas o ícone (compound='top' e text='')
        size_expanded: tamanho do ícone quando expandido
        size_collapsed: tamanho do ícone quando collapsed
        **kwargs: passa direto ao CTkButton (fg_color, hover_color, text_color, command, anchor, etc.)
    """
    def __init__(self, master, *, text: str, icon: str, 
                 collapsed: bool=False,
                 size_expanded: int=28, 
                 size_collapsed: int=28, 
                 **kwargs):
        self._label_text = text
        self._icon_name = icon
        self._img_expanded  = ctk_image(icon, size_expanded)
        self._img_collapsed = ctk_image(icon, size_collapsed)

        # Pega e remove 'anchor' dos kwargs pra podermos alternar depois
        anchor = kwargs.pop("anchor", "w")
        compound = "left"
        display_text = text
        display_img  = self._img_expanded

        if collapsed:
            display_text = ""
            anchor = "center"
            compound = "left"
            display_img = self._img_collapsed

        super().__init__(
            master,
            text=display_text,
            image=display_img,
            compound=compound,
            anchor=anchor,
            **kwargs
        )
        self._collapsed = collapsed

    # API simples pra Sidebar
    def set_collapsed(self, collapsed: bool, *, text: Optional[str]=None):
        """Alterna para modo collapsed/expanded. Pode opcionalmente trocar o label."""
        if text is not None:
            self._label_text = text

        if collapsed and not self._collapsed:
            self.configure(text="", image=self._img_collapsed, compound="top", anchor="center")
            self._collapsed = True
        elif (not collapsed) and self._collapsed:
            self.configure(text=self._label_text, image=self._img_expanded, compound="left", anchor="w")
            self._collapsed = False

# Factory no estilo pedido (funciona como no seu snippet):
def menuButton(master, *, text, icon, colapsed=False, collapsed=None, **kwargs):
    """
    Aceita tanto 'colapsed' (typo) quanto 'collapsed' pra conveniência.
    """
    if collapsed is None:
        collapsed = colapsed
    return MenuButton(master, text=text, icon=icon, collapsed=collapsed, **kwargs)
