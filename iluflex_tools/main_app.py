import customtkinter as ctk
from tkinter import ttk

from iluflex_tools.theming.theme import apply_theme
from iluflex_tools.core.state import AppState
from iluflex_tools.core.services import ConnectionService, OtaService, IrService, NetworkService
from iluflex_tools.core.settings import load_settings, save_settings
from iluflex_tools.ui.header import Header
from iluflex_tools.ui.sidebar import Sidebar
from iluflex_tools.ui.pages.dashboard import DashboardPage
from iluflex_tools.ui.pages.conexao import ConexaoPage
from iluflex_tools.ui.pages.gestao_dispositivos import GestaoDispositivosPage
from iluflex_tools.ui.pages.fw_upgrade import FWUpgradePage
from iluflex_tools.ui.pages.comandos_ir import ComandosIRPage
from iluflex_tools.ui.pages.interface_programacao import InterfaceProgramacaoPage
from iluflex_tools.ui.pages.configurar_master import ConfigurarMasterPage
from iluflex_tools.ui.pages.configuracoes import PreferenciasPage
from iluflex_tools.ui.pages.ajuda import AjudaPage



class MainApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        apply_theme() # fallback inicial (mantém comportamento atual)
        self.title("iLuFlex Tools")
        self.geometry("900x700")
        self.minsize(800, 500)

        self.settings = load_settings()
        # aplica o tema salvo no boot (evita iniciar sempre no "system")
        try:
            from iluflex_tools.theming.theme import apply_theme as _apply
            _apply(self.settings.theme)
        except Exception:
            pass

        self.app_state = AppState(
            ip=self.settings.last_ip,
            port=self.settings.last_port
        )
        self.conn = ConnectionService()
        self.ota = OtaService()
        self.ir = IrService()
        self.net = NetworkService()

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.header = Header(self, conn=self.conn, on_toggle_collapse=self._toggle_sidebar_collapse)
        self.header.grid(row=0, column=0, columnspan=2, sticky="ew")

        self.sidebar = Sidebar(self, on_nav=self.navigate, collapsed=False)
        self.sidebar.grid(row=1, column=0, sticky="nsw")

        self.content = ctk.CTkFrame(self, corner_radius=0)
        self.content.grid(row=1, column=1, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        self.pages = {}
        self._mount_pages()
        # self._apply_global_table_font(nsize=10)  # Aplica fonte global para todas as tabelas não funciona
        self.navigate("dashboard")

        # habilita auto‑reconnect (sem o main ouvir eventos)
        try:
            self.conn.enable_auto_reconnect(True, interval=5.0)
        except Exception:
            pass

    def _mount_pages(self):
        self.pages["dashboard"] = DashboardPage(self.content, on_quick_nav=self.navigate)
        self.pages["conexao"] = ConexaoPage(
            self.content,
            get_state=lambda: self.app_state,
            scan_func=self.net.scan_masters,
            get_discovery_timeout=lambda: self.settings.discovery_timeout_ms,
            conn=self.conn,
        )
        # >>> alteração: passa conn também, para a página ouvir RX de RRF,10
        self.pages["gestao_dispositivos"] = GestaoDispositivosPage(self.content, conn=self.conn)
        self.pages["fw_upgrade"] = FWUpgradePage(self.content, run_ota=self.ota.run_fw_upgrade)
        self.pages["comandos_ir"] = ComandosIRPage(self.content, ir_service=self.ir, conn=self.conn)
        self.pages["interface_programacao"] = InterfaceProgramacaoPage(self.content)
        self.pages["configurar_master"] = ConfigurarMasterPage(self.content)
        self.pages["preferencias"] = PreferenciasPage(
            self.content,
            get_settings=lambda: self.settings,
        )
        self.pages["ajuda"] = AjudaPage(self.content)

        for p in self.pages.values():
            p.grid(row=0, column=0, sticky="nsew")


    def navigate(self, key: str):
        if key not in self.pages:
            return
        self.pages[key].tkraise()
        self.sidebar.set_active(key)
        
        if key == "gestao_dispositivos":
            # dispara a mesma ação do botão, mas só se já estiver conectado
            try:
                self.after(50, self.pages[key].on_page_activated)
            except Exception:
                pass


    def _toggle_sidebar_collapse(self):
        self.sidebar.set_collapsed(not self.sidebar.collapsed)

def main():
    app = MainApp()
    app.mainloop()
