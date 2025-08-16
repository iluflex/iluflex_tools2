import customtkinter as ctk

class PreferenciasPage(ctk.CTkFrame):
    def __init__(self, master, get_settings, apply_and_save):
        super().__init__(master)
        self.get_settings = get_settings
        self.apply_and_save = apply_and_save
        self._build()

    def _build(self):
        s = self.get_settings()

        ctk.CTkLabel(self, text="Preferências", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(12,8), anchor="w", padx=10)

        row1 = ctk.CTkFrame(self); row1.pack(fill="x", padx=10, pady=6)
        ctk.CTkLabel(row1, text="Tema").pack(side="left", padx=(6,8))
        self.theme = ctk.CTkOptionMenu(row1, values=["system", "dark", "light"])
        self.theme.set(s.theme); self.theme.pack(side="left")

        row2 = ctk.CTkFrame(self); row2.pack(fill="x", padx=10, pady=6)
        ctk.CTkLabel(row2, text="Tempo padrão de descoberta (ms)").pack(side="left", padx=(6,8))
        self.timeout = ctk.CTkEntry(row2, width=120); self.timeout.insert(0, str(s.discovery_timeout_ms))
        self.timeout.pack(side="left")

        ctk.CTkButton(self, text="Salvar", command=self._save).pack(pady=12, padx=10, anchor="w")

    def _save(self):
        try:
            t = int(self.timeout.get())
        except Exception:
            t = 2000
        self.apply_and_save(theme=self.theme.get(), discovery_timeout_ms=t)
