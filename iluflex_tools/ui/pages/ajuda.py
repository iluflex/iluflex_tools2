# file: iluflex_tools/ui/pages/ajuda.py
from __future__ import annotations
import tkinter as tk
from tkhtmlview import HTMLLabel, HTMLScrolledText
import customtkinter as ctk
from iluflex_tools.widgets.page_title import PageTitle

ONLINE_HELP = (
    "https://www.iluflex.com.br/downloads/iluflextools/help/index.html"
)


class AjudaPage(ctk.CTkFrame):
    """Ajuda simples e nativo (HTML local). """

    def __init__(self, master) -> None:
        super().__init__(master)

        # Layout
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._htmltxt = self.htmlcontent()

        PageTitle(self, text="Ajuda").grid(row=0, column=0, sticky="w", padx=12, pady=(10, 6))

        hframe = ctk.CTkFrame(self, fg_color="white")
        hframe.grid(row=1, column=0, padx=5, pady=5, sticky=("nsew"))
        # 2) HTML ocupa todo o espaço do frame
        hframe.grid_rowconfigure(0, weight=1)
        hframe.grid_columnconfigure(0, weight=1)

        self.helphtmllabel = HTMLScrolledText(
            hframe,
            html=self._htmltxt,
            background="white",
            borderwidth=0,
            relief="flat",
            highlightthickness=0,
        )
        self.helphtmllabel.grid(row=0, column=0, padx=(20,2), pady=20, sticky="nsew")




    def htmlcontent(self) -> str:
        # CSS margin/padding não é suportado aqui; usamos tag_config acima.
        return """<div>
    <h2 style='text-align:center'>iluflex Tools V 2.0 — Ajuda</h2>
    <p>Este help local é enxuto e cobre as dúvidas mais frequentes.
        Para o conteúdo completo, use o link “Help completo online”.</p>
    <ul>
        <li>Conexão (onde tudo começa...)</li>
        <li>Gestão de Dispositivos - Cadastro rede Mesh</li>
        <li>Captura de Comandos de IR - Learner</li>
        <li>Configurar Interface Master IC-315 ou IC-215</li>
        <li><a href='https://www.iluflex.com.br/downloads/iluflextools/help/index.html' target='_blank'>Help completo online</a></li>
    </ul>
    <div>
        <h3>Conexão</h3>
        <p>Busca automática de interfaces master na rede LAN. <br>
        No campo endereço também são aceitos url´s</p>
        <p>Clique com botão da direita do mouse sobre o título da tabela para exibir ou ocultar colunas como Gateway, 
    </div>
</div>"""
