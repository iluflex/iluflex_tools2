import customtkinter as ctk
from iluflex_tools.widgets.menu_button import menuButton

FG_BASE      = ("#E5E7EB", "#1F2937")
FG_ACTIVE    = ("#CBD5E1", "#334155")
FG_HOVER     = ("#94A3B8", "#475569")
TEXT_COLOR   = ("#0B1220", "#F8FAFC")
FRAME_COLOR  = ("#F3F4F6", "#111827")

class Sidebar(ctk.CTkFrame):
    WIDTH_COLLAPSED = 56
    WIDTH_EXPANDED  = 240

    def __init__(self, master, on_nav=None, collapsed=False, menu_items = []):
        super().__init__(master, corner_radius=0, fg_color=FRAME_COLOR)
        self.on_nav = on_nav
        self.collapsed = collapsed
        self.menu_items = menu_items
        self._buttons = {}
        # impede o conteúdo de forçar o frame a alargar
        self.grid_propagate(False)
        self._build()
        self._apply_width()

    def _build(self):
        for idx, (label, key, icon_name) in enumerate(self.menu_items):
            btn = menuButton(
                self,
                text=label,
                icon=icon_name,                  # <- nome do arquivo base (ex.: "server-cog")
                colapsed=self.collapsed,         # aceita 'colapsed' (typo) ou 'collapsed'
                anchor=("center" if self.collapsed else "w"),
                fg_color=FG_BASE, hover_color=FG_HOVER, text_color=TEXT_COLOR,
                command=lambda k=key: self.on_nav and self.on_nav(k),
                size_expanded=28, 
                size_collapsed=28
            )
            btn.grid(row=idx, column=0, sticky="ew", padx=6, pady=4)
            self._buttons[key] = (btn, label, icon_name)
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
        for _, (btn, label, _icon_name) in self._buttons.items():
            # o widget já cuida de texto/compound/anchor
            btn.set_collapsed(collapsed, text=label)
        self._apply_width()