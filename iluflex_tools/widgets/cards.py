import customtkinter as ctk

class DropDownCard(ctk.CTkFrame):

    """Indicador de status de conexão com fundo transparente usando um label "●".
    `size` controla o tamanho da fonte do ponto.
    """
    # Helper para criar "cards" colapsáveis
    @staticmethod
    def make_card(parent, title, row_index):
        card = ctk.CTkFrame(parent, corner_radius=6, border_width=1)
        card.grid(row=row_index, column=0, sticky="ew", padx=1, pady=(0, 8))
        card.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header, text=title, font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w"
        )

        arrow_var = ctk.StringVar(value="▼")  # ▼ aberto / ▶ fechado
        # placeholder inicial; será substituído após "content" existir
        toggle_btn = ctk.CTkButton(header, textvariable=arrow_var, width=24)
        toggle_btn.grid(row=0, column=1, sticky="e")

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        content.grid_columnconfigure(0, weight=1)

        def toggle():
            if content.winfo_viewable():
                content.grid_remove()
                arrow_var.set("▶")
            else:
                content.grid()
                arrow_var.set("▼")

        toggle_btn.configure(command=toggle)
        return content