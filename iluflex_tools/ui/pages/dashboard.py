import customtkinter as ctk
from PIL import Image
import os, sys
from iluflex_tools.widgets.page_title import PageTitle
from iluflex_tools.widgets.menu_button import ctk_imageLight
from pathlib import Path

class DashboardPage(ctk.CTkFrame):
    """
    Home com:
      - fundo claro fixo (independe do tema)
      - logo central (≈ 1/3 da largura)
      - atalhos em grade responsiva (1/2/3 colunas)
      - ícone antes do nome
    """
    def __init__(self, master, on_quick_nav, menu_items):
        super().__init__(master, fg_color="#F5F6F8")
        self.on_quick_nav = on_quick_nav
        self._logo_img = None
        self._logo_ctk = None
        self.menu_items=menu_items
        self._built_cols = None  # p/ evitar realocar sem necessidade
        self._build()

        # layout responsivo
        self.bind("<Configure>", self._on_resize)

    # -------------------- UI --------------------
    def _build(self):
        # estrutura principal
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, minsize=16)   # empurra conteúdo um pouco pra cima

        # logo
        self._build_logo()

        # título "ATALHOS"
        self.shortcuts_title = PageTitle(
            self, "ATALHOS", row=3, column=0, pady=(6, 6), sticky="n", padx=0
        )
        self.shortcuts_title.configure(text_color="#111827", bg_color="#F5F6F8")

        # container dos botões
        self.grid_wrap = ctk.CTkFrame(self, fg_color="#F5F6F8")
        self.grid_wrap.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 10))

        # cria os botões uma única vez (regridamos depois conforme nº de colunas)
        # obtem dados de MENU_ITEMS definido no main_app.py
        self.shortcut_buttons = []

        try:

            for idx, (label, route, icon_name) in enumerate(self.menu_items):
                img = ctk_imageLight(icon_name, size=28)  # use 24 se preferir menor
                b = ctk.CTkButton(
                    self.grid_wrap,
                    text=label,
                    image=img,           # << ícone real
                    compound="left",     # ícone à esquerda do texto
                    height=52,
                    width=260,           # mantém o mesmo “piso” de largura
                    command=lambda r=route: self.on_quick_nav(r),
                    # (opcional) se quiser padronizar o visual:
                    # fg_color="#FFFFFF", hover_color="#F1F5F9", text_color="#111827",
                    # anchor="w",
                )
                self.shortcut_buttons.append(b)
        except Exception as e:
            print(f"[DASHBOARD] Exception: {e}")
        pass

        # primeira disposição
        self._layout_shortcuts(cols=3)

    def _base_dir(self):
        # Alinha com o menu_button.py: no bundle, os dados ficam em _MEIPASS/iluflex_tools
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            return Path(sys._MEIPASS) / "iluflex_tools"
        # dev: .../iluflex_tools
        return Path(__file__).resolve().parents[1]

    def _build_logo(self):
        base = self._base_dir()
        # 1º tenta em ui/ (layout novo), 2º tenta na raiz (retrocompat.)
        candidates = [
            base / "ui" / "iluflex_logo_1500x750.png",
            base / "iluflex_logo_1500x750.png",
        ]
        for p in candidates:
            if p.exists():
                self._logo_img = Image.open(p)
                # tamanho inicial (1/3 da largura ≈ 400px), mantém proporção
                w0 = 400
                aspect = self._logo_img.height / self._logo_img.width
                h0 = int(w0 * aspect)
                self._logo_ctk = ctk.CTkImage(light_image=self._logo_img, dark_image=self._logo_img, size=(w0, h0))
                self.logo_label = ctk.CTkLabel(self, image=self._logo_ctk, text="", bg_color="#F5F6F8")
                break
        else:
            # fallback sem travar
            self.logo_label = ctk.CTkLabel(
                self, text="iluflex", font=ctk.CTkFont(size=28, weight="bold"),
                text_color="#0B1220", bg_color="#F5F6F8",
            )
        self.logo_label.grid(row=1, column=0, pady=(8, 2), sticky="n")

    # ------------------ LAYOUT ------------------
    def _layout_shortcuts(self, cols: int):
        """Distribui os botões em grade de 'cols' colunas (2–3 fileiras)."""
        if cols == self._built_cols:
            return
        self._built_cols = cols

        # limpa grid anterior
        for b in self.shortcut_buttons:
            b.grid_forget()

        # define colunas com peso para centralizar
        # (zera antigos até 5 colunas por garantia)
        for i in range(5):
            self.grid_wrap.grid_columnconfigure(i, weight=0)
        for c in range(cols):
            self.grid_wrap.grid_columnconfigure(c, weight=1)

        # regrida
        for i, b in enumerate(self.shortcut_buttons):
            r = i // cols
            c = i % cols
            # não esticar horizontalmente; centraliza em cada coluna
            b.grid(row=r, column=c, padx=8, pady=8, sticky="n")

    # ----------------- HANDLERS -----------------
    def _on_resize(self, event):
        # 1) Redimensiona o logo (≈ 1/3 da largura, mantendo proporção)
        if self._logo_img and self._logo_ctk:
            target_w = max(360, int(self.winfo_width() * 0.33))
            aspect = self._logo_img.height / self._logo_img.width
            target_h = int(target_w * aspect)
            self._logo_ctk.configure(size=(target_w, target_h))

        # 2) Define nº de colunas responsivo p/ atalhos
        w = self.winfo_width()
        if w < 800:
            cols = 1
        elif w < 1100:
            cols = 2
        else:
            cols = 3
        self._layout_shortcuts(cols)
