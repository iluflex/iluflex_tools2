import customtkinter as ctk

class Header(ctk.CTkFrame):
    def __init__(self, master, on_toggle_collapse=None):
        super().__init__(master, corner_radius=0, fg_color=("gray85","gray14"))
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0)

        self.toggle_btn = ctk.CTkButton(self, text="≡", width=36, command=on_toggle_collapse)
        self.toggle_btn.grid(row=0, column=0, padx=8, pady=6)

        self.title = ctk.CTkLabel(self, text="iluflex Tools", font=ctk.CTkFont(size=18, weight="bold"))
        self.title.grid(row=0, column=1, sticky="w")

        self.status_dot = ctk.CTkLabel(self, text="●", font=ctk.CTkFont(size=18))
        self.status_text = ctk.CTkLabel(self, text="Servidor desconectado")
        self.status_dot.grid(row=0, column=2, padx=(0,6))
        self.status_text.grid(row=0, column=3, padx=(0,12))

        self.set_connected(False)

    def set_connected(self, ok: bool):
        self.status_dot.configure(text_color="#2ecc71" if ok else "#e74c3c")
        self.status_text.configure(text="Servidor conectado" if ok else "Servidor desconectado")
