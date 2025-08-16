import customtkinter as ctk
from tkinter import filedialog

class FWUpgradePage(ctk.CTkFrame):
    def __init__(self, master, run_ota):
        super().__init__(master)
        self.run_ota = run_ota
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="Atualização de Firmware", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(10,6))
        row = ctk.CTkFrame(self); row.pack(pady=10, fill="x")
        self.path_entry = ctk.CTkEntry(row); self.path_entry.pack(side="left", padx=6, expand=True, fill="x")
        ctk.CTkButton(row, text="Selecionar .frw", command=self._pick).pack(side="left", padx=6)
        ctk.CTkButton(self, text="Atualizar", command=self._run).pack(pady=6)
        self.log = ctk.CTkTextbox(self, height=160); self.log.pack(fill="both", expand=True, padx=6, pady=6)

    def _pick(self):
        p = filedialog.askopenfilename(title="Escolher firmware", filetypes=[("Firmware","*.frw"), ("Todos","*.*")])
        if p:
            self.path_entry.delete(0,"end"); self.path_entry.insert(0,p)
            self.log.insert("end", f"Selecionado: {p}\n"); self.log.see("end")

    def _run(self):
        p = self.path_entry.get().strip()
        if not p:
            self.log.insert("end","Selecione um arquivo primeiro.\n"); self.log.see("end"); return
        res = self.run_ota(p)
        self.log.insert("end", f"{res}\n"); self.log.see("end")
