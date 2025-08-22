# file: configuracoes.py

import customtkinter as ctk
from tkinter import messagebox
from iluflex_tools.core.settings import load_settings, save_settings
from iluflex_tools.widgets.page_title import PageTitle


class PreferenciasPage(ctk.CTkFrame):
    """Ajuste focado **apenas** no mainFrame, conforme solicitado.

    Decisões:
    - Tudo centralizado dentro do frame.
    - Coluna do meio com **largura fixa** (OptionMenu/Entry com width fixo).
    - Espaçamentos compactos; botão Salvar imediatamente abaixo dos campos.
    - Sem "Reverter" e sem barra extra fora do mainFrame.
    """

    THEMES = ("system", "dark", "light")

    def __init__(self, master, get_settings):
        super().__init__(master)
        self.get_settings = get_settings
        self._build()

    # ------------------------------ UI ---------------------------------
    def _build(self) -> None:
        # Mantemos o resto da página intacto; criamos somente o mainFrame.
        PageTitle(self, "Preferências")

        self.mainFrame = ctk.CTkFrame(self)
        # Centralizado, sem grandes paddings para não "afastar" do Salvar externo (se houver)
        self.mainFrame.grid(row=1, column=0, padx=0, pady=0)

        # grade do formulário simples: [rótulo | campo fixo | unidade]
        for col in (0, 1, 2):
            self.mainFrame.grid_columnconfigure(col, weight=0)  # nada expande

        # largura fixa para a coluna do meio via largura dos widgets
        FIELD_WIDTH = 120  # largura fixa solicitada
        NUM_WIDTH = 120

        # linha 0: tema
        ctk.CTkLabel(self.mainFrame, text="Tema", anchor="e").grid(row=0, column=0, padx=(12, 8), pady=(10, 6), sticky="e")
        self.option_theme = ctk.CTkOptionMenu(self.mainFrame, values=list(self.THEMES), width=FIELD_WIDTH)
        self.option_theme.grid(row=0, column=1, padx=(8, 8), pady=(10, 6))  # central dentro do frame
        ctk.CTkLabel(self.mainFrame, text="").grid(row=0, column=2, padx=(8, 12), pady=(10, 6))

        # linha 1: tempo de busca (ms)
        ctk.CTkLabel(self.mainFrame, text="Tempo padrão de busca de interfaces (ms)", anchor="e").grid(
            row=1, column=0, padx=(12, 8), pady=6, sticky="e"
        )
        self.timeout_ms_entry = ctk.CTkEntry(self.mainFrame, width=NUM_WIDTH, placeholder_text="5000")
        self.timeout_ms_entry.grid(row=1, column=1, padx=(8, 8), pady=6)
        ctk.CTkLabel(self.mainFrame, text="Padrão: 5000. ").grid(row=1, column=2, padx=(8, 12), pady=6)

        # linha 2: tempo de cadastro (s)
        ctk.CTkLabel(self.mainFrame, text="Tempo padrão de cadastro de novos dispositivos (segundos)", anchor="e").grid(
            row=2, column=0, padx=(12, 8), pady=6, sticky="e"
        )
        self.discover_timeout_entry = ctk.CTkEntry(self.mainFrame, width=NUM_WIDTH, placeholder_text="120")
        self.discover_timeout_entry.grid(row=2, column=1, padx=(8, 8), pady=6)
        ctk.CTkLabel(self.mainFrame, text="Padrão: 120 (2 minutos)").grid(row=2, column=2, padx=(8, 12), pady=6)

        # linha 3: botão salvar logo abaixo dos campos, centralizado
        self.btn_save = ctk.CTkButton(self.mainFrame, text="Salvar", command=self._save)
        self.btn_save.grid(row=3, column=0, columnspan=3, pady=(10, 8))

        # valores iniciais
        s = self.get_settings()
        self.option_theme.set(s.theme if s.theme in self.THEMES else "system")
        self.timeout_ms_entry.delete(0, "end")
        self.timeout_ms_entry.insert(0, str(s.discovery_timeout_ms))
        self.discover_timeout_entry.delete(0, "end")
        self.discover_timeout_entry.insert(0, str(s.mesh_discovery_timeout_sec))

    # ------------------------------ Ações -------------------------------

    def _save(self) -> None:
        # Mantemos somente a ação de salvar, sem outros elementos fora do mainFrame
        s = load_settings()
        try:
            s.theme = self.option_theme.get()
            s.discovery_timeout_ms = self._parse_int(self.timeout_ms_entry.get(), field="Busca (ms)")
            s.mesh_discovery_timeout_sec = self._parse_int(self.discover_timeout_entry.get(), field="Cadastro (s)")
        except ValueError as err:
            messagebox.showerror("Preferências", str(err))  # feedback não intrusivo
            return

        save_settings(s)
        # tenta aplicar tema, sem alterar layout externo
        try:
            from iluflex_tools.theming.theme import apply_theme

            apply_theme(s.theme)
        except Exception:
            pass
        messagebox.showinfo("Preferências", "Preferências salvas com sucesso.")

    # ------------------------------ Util --------------------------------
    @staticmethod
    def _parse_int(value: str, *, field: str) -> int:
        value = (value or "").strip()
        if not value.isdigit():
            raise ValueError(f"{field}: informe inteiro positivo.")
        return int(value)
