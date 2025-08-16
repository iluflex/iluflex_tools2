import customtkinter as ctk

MENU_ITEMS = [
    ("INICIO", "dashboard", "🏠"),
    ("CONEXÃO", "conexao", "🔌"),
    ("GESTÃO DE DISPOSITIVOS", "gestao_dispositivos", "🗂"),
    ("ATUALIZAÇÃO DE FIRMWARE", "fw_upgrade", "⬆"),
    ("COMANDOS IR", "comandos_ir", "📡"),
    ("INTERFACE DE PROGRAMAÇÃO", "interface_programacao", "🛠"),
    ("CONFIGURAR MASTER", "configurar_master", "⚙"),
    ("PREFERÊNCIAS", "preferencias", "⚙️"),
    ("AJUDA", "ajuda", "❓"),
]

FG_BASE      = ("#E5E7EB", "#1F2937")
FG_ACTIVE    = ("#CBD5E1", "#334155")
FG_HOVER     = ("#94A3B8", "#475569")
TEXT_COLOR   = ("#0B1220", "#F8FAFC")
FRAME_COLOR  = ("#F3F4F6", "#111827")

class Sidebar(ctk.CTkFrame):
    WIDTH_COLLAPSED = 56
    WIDTH_EXPANDED  = 240

    def __init__(self, master, on_nav=None, collapsed=False):
        super().__init__(master, corner_radius=0, fg_color=FRAME_COLOR)
        self.on_nav = on_nav
        self.collapsed = collapsed
        self._buttons = {}
        # impede o conteúdo de forçar o frame a alargar
        self.grid_propagate(False)
        self._build()
        self._apply_width()

    def _build(self):
        for idx, (label, key, icon) in enumerate(MENU_ITEMS):
            txt = icon if self.collapsed else f"{icon}  {label}"
            anchor = "center" if self.collapsed else "w"
            btn = ctk.CTkButton(
                self, text=txt, anchor=anchor,
                fg_color=FG_BASE, hover_color=FG_HOVER, text_color=TEXT_COLOR,
                command=lambda k=key: self.on_nav and self.on_nav(k)
            )
            btn.grid(row=idx, column=0, sticky="ew", padx=6, pady=4)
            self._buttons[key] = (btn, label, icon)
        self.grid_columnconfigure(0, weight=1)

    def _target_width(self):
        return self.WIDTH_COLLAPSED if self.collapsed else self.WIDTH_EXPANDED

    def _apply_width(self):
        w = self._target_width()
        self.configure(width=w)     # largura “pedida” pelo frame
        self.update_idletasks()     # ajuda o grid a respeitar
        # OBS: quem fixa mesmo será o minsize no parent (feito no MainApp)

    def set_active(self, key: str):
        for k, (btn, _, _) in self._buttons.items():
            btn.configure(fg_color=FG_ACTIVE if k == key else FG_BASE)

    def set_collapsed(self, collapsed: bool):
        if self.collapsed == collapsed:
            return
        self.collapsed = collapsed
        for _, (btn, label, icon) in self._buttons.items():
            btn.configure(text=icon if collapsed else f"{icon}  {label}",
                          anchor="center" if collapsed else "w")
        self._apply_width()
