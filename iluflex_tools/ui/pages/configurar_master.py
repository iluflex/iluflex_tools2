import customtkinter as ctk

class ConfigurarMasterPage(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        ctk.CTkLabel(self, text='Configurar Master', font=ctk.CTkFont(size=18, weight='bold')).pack(pady=12, anchor='w', padx=10)
        ctk.CTkLabel(self, text='(conteúdo a implementar)').pack(pady=6)
