# iluflex_tools_scaffold/iluflex_tools/widgets/column_tree.py
# Versão revisada: centraliza controle de fonte e rowheight no próprio widget

import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont
import platform
import customtkinter as ctk

class ColumnToggleTree(ctk.CTkFrame):
    """
    Treeview com menu no cabeçalho (clique direito) para exibir/ocultar colunas.
    Acompanha o tema do CustomTkinter e reestiliza ao vivo via apply_style().
    - Windows: usa 'vista' no modo light (tem separadores verticais de coluna)
               e 'clam' no modo dark (permite cabeçalho escuro).
    - Outras plataformas: 'clam' sempre.
    """

    # Tamanho padrão para novas instâncias (ajustável via set_default_font_size)
    DEFAULT_FONT_SIZE = 9

    def __init__(self, master, columns, height=12, font_size: int | None = None):
        super().__init__(master)
        # normalize column specs: accept dicts ({'key','width'}), tuples (name,width) or plain strings
        norm_columns = []
        self._all_cols = []
        self._col_anchor = {}
        for c in columns:
            if isinstance(c, dict):
                name = c.get("key") or c.get("name") or c.get("id")
                width = int(c.get("width", 120))
                anchor = str(c.get("anchor") or c.get("align") or "center").lower()
            elif isinstance(c, (tuple, list)) and len(c) >= 2:
                name, width = c[0], int(c[1])
                anchor = "center"
            else:
                name, width = str(c), 120
                anchor = "center"
            norm_columns.append((str(name), int(width), anchor))
            self._all_cols.append(str(name))
            self._col_anchor[str(name)] = anchor

        # estilo e tema
        self._style = ttk.Style(self)
        self._style_tv = "Ilfx.Treeview"
        self._style_hd = "Ilfx.Treeview.Heading"
        self._current_theme = None  # 'vista' ou 'clam'

        # fonte configurável por instância (ou global via DEFAULT_FONT_SIZE)
        self._font_size = int(font_size) if font_size is not None else int(self.DEFAULT_FONT_SIZE)

        # widget
        self.tree = ttk.Treeview(
            self, columns=self._all_cols, show="headings",
            height=height, style=self._style_tv
        )
        for col, width, anchor in norm_columns:
            # centraliza cabeçalho e células por padrão (ou usa anchor fornecido)
            self.tree.heading(col, text=col, anchor=anchor)
            self.tree.column(col, width=width, anchor=anchor, stretch=True)

        # Scrollbars CTk
        self.vsb = ctk.CTkScrollbar(self, command=self.tree.yview)
        self.hsb = ctk.CTkScrollbar(self, command=self.tree.xview, orientation="horizontal")
        self.tree.configure(yscrollcommand=self.vsb.set, xscrollcommand=self.hsb.set)

        # Layout
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.vsb.grid(row=0, column=1, sticky="ns")
        self.hsb.grid(row=1, column=0, sticky="ew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # menu de colunas
        self._menu = tk.Menu(self, tearoff=0)
        for col, _w, _a in norm_columns:
            self._menu.add_checkbutton(label=col, onvalue=True, offvalue=False,
                                       command=lambda c=col: self._toggle_col(c))

        # mapping de visibilidade
        self._visible = {col: True for col, _w, _a in norm_columns}

        # aplica estilo do tema atual (inclui fonte/rowheight)
        self.apply_style()

        # bind de clique direito para abrir menu
        self.tree.bind("<Button-3>", self._maybe_open_menu)

        # suporte a ordenação por cabeçalho (opcional)
        self._auto_sort_col = None
        self._auto_sort_asc = True

    # ---------- API de fonte centralizada ----------
    @classmethod
    def set_default_font_size(cls, size: int) -> None:
        """Define o tamanho padrão usado por novas instâncias."""
        try:
            cls.DEFAULT_FONT_SIZE = int(size)
        except Exception:
            pass

    def set_font_size(self, size: int) -> None:
        """Atualiza o tamanho desta instância e re-aplica o estilo."""
        try:
            self._font_size = int(size)
            self.apply_style()
        except Exception:
            pass

    # ---------- tema e cores ----------
    def _pick_ttk_theme(self) -> str:
        sys = platform.system().lower()
        try:
            mode = ctk.get_appearance_mode()  # "Light" / "Dark"
        except Exception:
            mode = "Light"
        if sys == "windows":
            return "vista" if mode == "Light" else "clam"
        return "clam"

    def _colors_for_mode(self):
        try:
            mode = ctk.get_appearance_mode()
        except Exception:
            mode = "Light"
        if mode == "Dark":
            BG = "#1f1f1f"; FG = "#eaeaea"; GRID = "#3a3a3a"; HD_BG = "#2a2a2a"
            ODD = "#232323"; EVEN = "#1b1b1b"; SELBG = "#3b82f6"; SELF = "#ffffff"
        else:
            BG = "#ffffff"; FG = "#111111"; GRID = "#d9d9d9"; HD_BG = "#f3f3f3"
            ODD = "#ffffff"; EVEN = "#fafafa"; SELBG = "#3b82f6"; SELF = "#ffffff"
        return BG, FG, GRID, SELBG, SELF, HD_BG, ODD, EVEN

    def apply_style(self):
        desired = self._pick_ttk_theme()
        if desired != self._current_theme:
            try:
                self._style.theme_use(desired)
                self._current_theme = desired
            except Exception:
                self._style.theme_use("clam")
                self._current_theme = "clam"

        BG, FG, GRID, SELBG, SELF, HD_BG, ODD, EVEN = self._colors_for_mode()

        # --- Fonte e altura derivadas do tamanho configurado ---
        try:
            base = tkfont.nametofont("TkDefaultFont")
            family = base.cget("family")
            fsize = int(getattr(self, "_font_size", 10))
            row_font = tkfont.Font(family=family, size=fsize)
            head_font = tkfont.Font(family=family, size=fsize, weight="bold")
            row_h = max(14, row_font.metrics("linespace") + 2)
        except Exception:
            row_font = None
            head_font = None
            row_h = 24

        # corpo (usa rowheight calculado e fonte quando disponível)
        kwargs_tv = dict(
            background=BG,
            fieldbackground=BG,
            foreground=FG,
            rowheight=row_h,
            bordercolor=GRID, lightcolor=GRID, darkcolor=GRID,
            borderwidth=1,
        )
        if row_font is not None:
            kwargs_tv["font"] = row_font
        self._style.configure(
            self._style_tv,
            **kwargs_tv
        )
        self._style.map(
            self._style_tv,
            background=[("selected", SELBG)],
            foreground=[("selected", SELF)],
        )

        # cabeçalho (usa fonte em negrito quando disponível)
        kwargs_hd = dict(
            background=HD_BG,
            foreground=FG,
            relief="flat",
            bordercolor=GRID,
        )
        if head_font is not None:
            kwargs_hd["font"] = head_font
        self._style.configure(
            self._style_hd,
            **kwargs_hd
        )
        self._style.map(
            self._style_hd,
            background=[("active", HD_BG)],
            relief=[("pressed", "flat"), ("!pressed", "flat")],
        )
        # como fallback, ajusta o heading padrão também
        fallback_hd = {"background": HD_BG, "foreground": FG, "relief": "flat"}
        if head_font is not None:
            fallback_hd["font"] = head_font
        self._style.configure("Treeview.Heading", **fallback_hd)

        # zebra rows
        try:
            self.tree.tag_configure("odd", background=ODD, foreground=FG)
            self.tree.tag_configure("even", background=EVEN, foreground=FG)
        except Exception:
            pass

        self.update_idletasks()

    # ---------- utilidades ----------
    def _maybe_open_menu(self, event):
        if self.tree.identify_region(event.x, event.y) == "heading":
            try:
                self._menu.tk_popup(event.x_root, event.y_root)
            finally:
                self._menu.grab_release()

    def _toggle_col(self, col):
        # alternar visibilidade
        cur = self._visible.get(col, True)
        self._visible[col] = not cur
        shown = [c for c, v in self._visible.items() if v]
        self.tree.configure(displaycolumns=shown)
        # atualiza check no menu
        try:
            for i in range(self._menu.index("end") + 1):
                label = self._menu.entrycget(i, "label")
                self._menu.entryconfigure(i, onvalue=True, offvalue=False, variable=tk.BooleanVar(value=self._visible.get(label, True)))
        except Exception:
            pass

    # ---------- API de dados ----------
    def set_rows(self, rows):
        self.tree.delete(*self.tree.get_children(""))
        if not rows:
            return
        # reconstrução simples com zebra + tag de fonte base
        for idx, row in enumerate(rows):
            values = [row.get(c, "") for c in self._all_cols]
            zebra = ("even" if idx % 2 == 0 else "odd")
            self.tree.insert("", "end", values=values, tags=("__basefont__", zebra))
        self._auto_sort_if_needed()

    def upsert_row(self, row: dict, key_cols=None):
        """Atualiza (ou insere) com base em colunas-chave.
        key_cols: lista de nomes de colunas. Se None, usa [primeira coluna].
        """
        if not key_cols:
            key_cols = [self._all_cols[0]]
        target_key = tuple(row.get(c, "") for c in key_cols)
        # busca linear por enquanto; dataset tende a ser pequeno
        match_iid = None
        for iid in self.tree.get_children():
            vals = self.tree.item(iid, "values")
            cur = tuple(vals[self._all_cols.index(c)] for c in key_cols)
            if cur == target_key:
                match_iid = iid
                break
        values = [row.get(c, "") for c in self._all_cols]
        if match_iid is None:
            idx = len(self.tree.get_children())
            zebra = ("even" if idx % 2 == 0 else "odd")
            self.tree.insert("", "end", values=values, tags=("__basefont__", zebra))
        else:
            self.tree.item(match_iid, values=values)
        self._auto_sort_if_needed()

    # ---------- Ordenação ----------
    def set_auto_sort(self, col_name: str, ascending: bool = True):
        """Define ordenação automática por coluna (quando set_rows/upsert_row)."""
        if col_name not in self._all_cols:
            return
        self._auto_sort_col = col_name
        self._auto_sort_asc = bool(ascending)
        # atrela o clique no cabeçalho
        self.tree.heading(col_name, command=self._on_header_click)

    def enable_header_sort(self):
        for col in self._all_cols:
            self.tree.heading(col, command=lambda c=col: self._sort_by(c, toggle=True))

    def _on_header_click(self):
        if self._auto_sort_col:
            self._sort_by(self._auto_sort_col, toggle=True)

    def _sort_by(self, col, toggle=False):
        # coleta valores atuais
        children = list(self.tree.get_children(""))
        idx = self._all_cols.index(col)
        def _key(iid):
            vals = self.tree.item(iid, "values")
            try:
                return int(vals[idx])
            except Exception:
                return str(vals[idx]).lower()
        reverse = not self._auto_sort_asc if toggle else not self._auto_sort_asc
        children.sort(key=_key, reverse=reverse)
        for i, iid in enumerate(children):
            self.tree.move(iid, "", i)
        # alterna zebra
        for i, iid in enumerate(self.tree.get_children("")):
            self.tree.item(iid, tags=(("even" if i % 2 == 0 else "odd"),))
        # alterna flag
        if toggle:
            self._auto_sort_asc = not self._auto_sort_asc

    def _auto_sort_if_needed(self):
        if self._auto_sort_col:
            self._sort_by(self._auto_sort_col, toggle=False)
