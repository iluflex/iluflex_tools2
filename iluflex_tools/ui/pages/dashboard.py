import customtkinter as ctk
from PIL import Image
import os
from iluflex_tools.widgets.page_title import PageTitle

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
        for idx, (label, route, icon) in enumerate(self.menu_items):
            text = f"{icon}  {label}"
            b = ctk.CTkButton(
                self.grid_wrap,
                text=text,
                height=52,
                width=260,            # evita “esticar” demais
                command=lambda r=route: self.on_quick_nav(r),
            )
            self.shortcut_buttons.append(b)

        # primeira disposição
        self._layout_shortcuts(cols=3)

    def _build_logo(self):
        # tenta carregar imagem; senão, usa texto
        path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "iluflex_logo_1500x750.png"))
        if os.path.exists(path):
            self._logo_img = Image.open(path)
            # tamanho inicial (1/3 de 1200px ~ 400px)
            self._logo_ctk = ctk.CTkImage(light_image=self._logo_img, dark_image=self._logo_img, size=(400, 200))
            self.logo_label = ctk.CTkLabel(self, image=self._logo_ctk, text="", bg_color="#F5F6F8")
        else:
            self.logo_label = ctk.CTkLabel(
                self,
                text="iluflex",
                font=ctk.CTkFont(size=28, weight="bold"),
                text_color="#0B1220",
                bg_color="#F5F6F8",
            )
        # posiciona o logo um pouco acima dos atalhos
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
