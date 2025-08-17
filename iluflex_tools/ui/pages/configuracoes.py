import customtkinter as ctk
from iluflex_tools.core.settings import load_settings, save_settings

class PreferenciasPage(ctk.CTkFrame):
    def __init__(self, master, get_settings):
        super().__init__(master)
        self.get_settings = get_settings
        self._build()

    def _build(self):
        s = self.get_settings()

        ctk.CTkLabel(self, text="Preferências", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(12,8), anchor="w", padx=10)

        row1 = ctk.CTkFrame(self); row1.pack(fill="x", padx=10, pady=6)
        ctk.CTkLabel(row1, text="Tema").pack(side="left", padx=(6,8))
        self.option_theme = ctk.CTkOptionMenu(row1, values=["system", "dark", "light"])
        self.option_theme.set(s.theme)
        self.option_theme.pack(side="left")

        row2 = ctk.CTkFrame(self); row2.pack(fill="x", padx=10, pady=6)
        ctk.CTkLabel(row2, text="Tempo padrão de busca de interfaces (ms)").pack(side="left", padx=(6,8))
        self.timeout = ctk.CTkEntry(row2, width=120)
        self.timeout.insert(0, str(s.discovery_timeout_ms))
        self.timeout.pack(side="left")

        row3 = ctk.CTkFrame(self); row3.pack(fill="x", padx=10, pady=6)
        ctk.CTkLabel(row3, text="Tempo Padrão de Cadastro de Novos Dispositivos (segundos)").pack(side="left", padx=(6,8))
        self.discover_timeout_entry = ctk.CTkEntry(row3, width=120); 
        self.discover_timeout_entry.insert(0, str(s.mesh_discovery_timeout_sec))
        self.discover_timeout_entry.pack(side="left")

        ctk.CTkButton(self, text="Salvar", command=self._save).pack(pady=12, padx=10, anchor="w")

    def _save(self):
        s = load_settings()
        try:
            s.discovery_timeout_ms = int(self.timeout.get())
            s.mesh_discovery_timeout_sec = int(self.discover_timeout_entry.get())
            s.theme = self.option_theme.get()
        except Exception as e:
            print("Valores inválidos em Configurações:", e)
            return
        save_settings(s)
        try:
            from iluflex_tools.theming.theme import apply_theme
            apply_theme(s.theme)
        except Exception:
            pass