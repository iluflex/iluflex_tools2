import customtkinter as ctk
from iluflex_tools.widgets.page_title import PageTitle


class AjudaPage(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        PageTitle(self, "Ajuda")
        ctk.CTkLabel(self, text="(conteúdo a implementar)").grid(
            row=1, column=0, padx=12, pady=6, sticky="w"
        )
