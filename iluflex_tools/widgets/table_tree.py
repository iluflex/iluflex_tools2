# iluflex_tools/widgets/column_tree.py
# Mantém a API. Cores 100% centralizadas em _colors_for_mode() e passadas como dict.

from __future__ import annotations
import platform
import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont
import customtkinter as ctk


# =============================================================================
# ÚNICA FONTE DE CORES DA TABELA (por tema)
# =============================================================================
_THEME_COLORS: dict[str, dict[str, str]] = {
    "light": {
        "bg": "#F3F3F3",
        "fg": "#111111",
        # Grid (borda, luz, sombra)
        "grid_border": "#BCBCBC",
        "grid_light": "#9F9F9F",
        "grid_dark": "#678892",
        # Cabeçalho (um pouco mais cinza que o corpo)
        "header_bg": "#C4C4C4",
        "header_hover_bg": "#ADADAD",
        # Hover de linha
        "row_hover_bg": "#DAEBFF",
        # Zebra
        "odd_bg": "#ffffff",
        "even_bg": "#E5E2E2",
        # Seleção
        "sel_bg": "#3b82f6",
        "sel_fg": "#ffffff",
    },
    "dark": {
        "bg": "#1f1f1f",
        "fg": "#eaeaea",
        "grid_border": "#3a3a3a",
        "grid_light": "#4a4a4a",
        "grid_dark": "#252525",
        "header_bg": "#2a2a2a",
        "header_hover_bg": "#323232",
        "row_hover_bg": "#2b3648",
        "odd_bg": "#232323",
        "even_bg": "#1b1b1b",
        "sel_bg": "#3b82f6",
        "sel_fg": "#ffffff",
    },
}


class ColumnToggleTree(ctk.CTkFrame):
    """Treeview com menu de colunas e estilo responsivo ao tema persistido.
    Mudança mínima: apenas cores em `_colors_for_mode()` e aplicação no `apply_style()`.
    """

    DEFAULT_FONT_SIZE = 12

    def __init__(self, master, columns, height=12, font_size: int | None = None):
        super().__init__(master)
        # ---- normaliza colunas ----
        norm_columns = []
        self._all_cols = []
        self._col_anchor = {}
        self._col_widths = {}
        self._visible = {}

        for c in columns:
            if isinstance(c, dict):
                name = c.get("key") or c.get("name") or c.get("id")
                width = int(c.get("width", 120))
                anchor = str(c.get("anchor") or c.get("align") or "center").lower()
                vis = bool(c.get("visible", True))
            elif isinstance(c, (tuple, list)) and len(c) >= 2:
                name, width = c[0], int(c[1])
                anchor = "center"
                vis = True
            else:
                name, width = str(c), 120
                anchor = "center"
                vis = True
            name = str(name)
            norm_columns.append((name, width, anchor, vis))
            self._all_cols.append(name)
            self._col_anchor[name] = anchor
            self._col_widths[name] = width
            self._visible[name] = vis

        # ---------- tema/estilo ----------
        self._style = ttk.Style(self)
        self._style_tv = "Ilfx.Treeview"
        self._style_hd = "Ilfx.Treeview.Heading"
        self._current_theme = None

        # fonte configurável por instância (ou global via DEFAULT_FONT_SIZE)
        self._font_size = int(font_size) if font_size is not None else int(self.DEFAULT_FONT_SIZE)

        # widget
        self.tree = ttk.Treeview(self, columns=self._all_cols, show="headings", height=height, style=self._style_tv)
        for col, width, anchor, _vis in norm_columns:
            # centraliza cabeçalho e células por padrão (ou usa anchor fornecido)
            self.tree.heading(col, text=col, anchor=anchor, command=lambda c=col: self._on_heading_click(c))
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

        # menu de colunas (mantém padrão com checkmarks)
        self._menu = tk.Menu(self, tearoff=0)
        self._col_vars = {}
        for col, _w, _a, _vis in norm_columns:
            var = tk.BooleanVar(value=self._visible[col])
            self._col_vars[col] = var
            self._menu.add_checkbutton(label=col, variable=var, onvalue=True, offvalue=False,
                                       command=lambda c=col: self._toggle_col(c))

        # estilo inicial
        self.apply_style()

        # aplicar visibilidade inicial (não mostrar todas ao abrir)
        for col, _w, _a, vis in norm_columns:
            if not vis:
                self._apply_hide(col)

        # bind de clique direito para abrir menu
        self.tree.bind("<Button-3>", self._maybe_open_menu)

        # suporte a ordenação por cabeçalho (opcional)
        self._auto_sort_col = None
        self._auto_sort_asc = True

    # ---------- API de fonte ----------
    @classmethod
    def set_default_font_size(cls, size: int) -> None:
        """Define o tamanho padrão usado por novas instâncias."""
        cls.DEFAULT_FONT_SIZE = int(size)

    def set_font_size(self, size: int) -> None:
        """Atualiza o tamanho desta instância e re-aplica o estilo."""
        self._font_size = int(size)
        self.apply_style()

    # ---------- helpers de tema ----------
    def _pick_ttk_theme(self) -> str:
        # Mantém lógica próxima ao original (vista no Windows claro; clam no demais/escuro)
        # O tema "vista" ignora cores do Treeview.Heading no Windows.
        # Use "clam" para permitir personalização real.
        return "clam"
        sys = platform.system().lower()
        try:
            mode = ctk.get_appearance_mode()
        except Exception:
            mode = "Light"
        if sys == "windows":
            return "clam" if str(mode) == "Dark" else "vista"
        return "clam"

    def _colors_for_mode(self) -> dict[str, str]:
        try:
            mode = ctk.get_appearance_mode()
        except Exception:
            mode = "Light"
        key = "dark" if str(mode).lower().startswith("dark") else "light"
        return dict(_THEME_COLORS.get(key, _THEME_COLORS["light"]))

    def apply_style(self):  # pode ser chamado no on_theme_changed
        desired = self._pick_ttk_theme()
        if desired != self._current_theme:
            try:
                self._style.theme_use(desired)
                self._current_theme = desired
            except Exception:
                self._style.theme_use("clam")
                self._current_theme = "clam"

        pal = self._colors_for_mode()

        # --- Fonte e altura derivadas do tamanho configurado ---
        try:
            base_font = tkfont.nametofont("TkDefaultFont")
            family = base_font.cget("family")
            fsize = int(getattr(self, "_font_size", 10))
            row_font = tkfont.Font(family=family, size=fsize)
            head_font = tkfont.Font(family=family, size=fsize, weight="bold")
            row_h = max(14, row_font.metrics("linespace") + 4)
        except Exception:
            row_font = None
            head_font = None
            row_h = 24

        # corpo (aplica grid refinado)
        tv_kwargs = dict(
            background=pal["bg"],
            fieldbackground=pal["bg"],
            foreground=pal["fg"],
            rowheight=row_h,
            bordercolor=pal["grid_border"],
            lightcolor=pal["grid_light"],
            darkcolor=pal["grid_dark"],
            borderwidth=2,
        )
        if row_font is not None:
            tv_kwargs["font"] = row_font
        self._style.configure(self._style_tv, **tv_kwargs)
        self._style.map(
            self._style_tv,
            background=[("selected", pal["sel_bg"])],
            foreground=[("selected", pal["sel_fg"])],
        )

        # cabeçalho (mais cinza que o corpo + hover)
        hd_kwargs = dict(
            background=pal["header_bg"],
            foreground=pal["fg"],
            relief="flat",
            bordercolor=pal["grid_border"],
            lightcolor=pal["grid_light"],
            darkcolor=pal["grid_dark"],
        )
        if head_font is not None:
            hd_kwargs["font"] = head_font
        self._style.configure(self._style_hd, **hd_kwargs)
        self._style.map(
            self._style_hd,
            background=[("active", pal["header_hover_bg"])],
            relief=[("pressed", "flat"), ("!pressed", "flat")],
        )
        # fallback no estilo padrão
        fb_hd = {"background": pal["header_bg"], "foreground": pal["fg"], "relief": "flat"}
        if head_font is not None:
            fb_hd["font"] = head_font
        self._style.configure("Treeview.Heading", **fb_hd)

        # tags (hover/zebra)
        try:
            self.tree.tag_configure("hover", background=pal["row_hover_bg"], foreground=pal["fg"])  # feedback visual rápido
            self.tree.tag_configure("odd", background=pal["odd_bg"], foreground=pal["fg"])         # zebra
            self.tree.tag_configure("even", background=pal["even_bg"], foreground=pal["fg"])       # zebra
            # ---- STATUS (cores de negócio) ----
            self.tree.tag_configure("edited",   background="#7f1d1d", foreground="#ffffff")
            self.tree.tag_configure("last",     background="#939393", foreground=pal["fg"])
            self.tree.tag_configure("dup_sid",  background="#FAE467", foreground="#111111")
            self.tree.tag_configure("sid_zero", background="#FAE467", foreground="#111111")
            self.tree.tag_configure("uniq_sid", background="#89E889", foreground="#111111")
        except Exception:
            pass

        self.update_idletasks()
        try:
            self._ensure_hover_binding()
        except Exception:
            pass

    # ---------- hover ----------
    def _ensure_hover_binding(self) -> None:
        if getattr(self, "_hover_bound", False):
            return
        tv = self.tree
        tv.bind("<Motion>", self._on_motion, add="+")
        tv.bind("<Leave>", self._on_leave, add="+")
        self._hover_iid = None
        self._hover_bound = True

    def _on_motion(self, event) -> None:
        tv = self.tree
        iid = tv.identify_row(event.y)
        if not iid:
            self._clear_hover(); return
        if self._hover_iid == iid:
            return
        self._clear_hover()
        if iid in set(tv.selection()):  # não sobrepor seleção
            return
        tags = set(tv.item(iid, "tags") or ())
        tags.add("hover")
        tv.item(iid, tags=tuple(tags))
        self._hover_iid = iid

    def _on_leave(self, _event) -> None:
        self._clear_hover()

    def _clear_hover(self) -> None:
        if not getattr(self, "_hover_iid", None):
            return
        tv = self.tree
        try:
            tags = set(tv.item(self._hover_iid, "tags") or ())
            if "hover" in tags:
                tags.remove("hover")
                tv.item(self._hover_iid, tags=tuple(tags))
        finally:
            self._hover_iid = None

    # ---------- utilidades ----------
    def _maybe_open_menu(self, event) -> None:
        if self.tree.identify_region(event.x, event.y) == "heading":
            # sincroniza checkmarks com estado atual de visibilidade
            for col in self._all_cols:
                var = self._col_vars.get(col)
                if var is not None:
                    var.set(bool(self._visible.get(col, True)))
            try:
                self._menu.tk_popup(event.x_root, event.y_root)
            finally:
                self._menu.grab_release()

    def _apply_hide(self, name: str) -> None:
        self.tree.heading(name, text="")
        self.tree.column(name, width=0, stretch=False)

    def _apply_show(self, name: str) -> None:
        self.tree.heading(name, text=name, anchor=self._col_anchor.get(name, "center"))
        self.tree.column(name, width=self._col_widths.get(name, 120), anchor=self._col_anchor.get(name, "center"), stretch=True)

    def _toggle_col(self, name: str) -> None:
        # **Mantido simples como o original: alterna visibilidade**
        vis = self._visible.get(name, True)
        nvis = not vis
        self._visible[name] = nvis
        if nvis:
            self._apply_show(name)
        else:
            self._apply_hide(name)
        # refaz zebra
        for i, iid in enumerate(self.tree.get_children("")):
            self.tree.item(iid, tags=(("even" if i % 2 == 0 else "odd"),))

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

    def upsert_row(self, row, key_cols=("MAC",)) -> None:
        key = tuple(row.get(k, "") for k in key_cols)
        target = None
        for iid in self.tree.get_children(""):
            vals = self.tree.item(iid, "values")
            cur_key = tuple(
                vals[self._all_cols.index(k)] if k in self._all_cols else None for k in key_cols
            )
            if cur_key == key:
                target = iid
                break
        values = [row.get(col, "") for col in self._all_cols]
        if target is None:
            i = len(self.tree.get_children(""))
            tag = "even" if i % 2 == 0 else "odd"
            self.tree.insert("", "end", values=values, tags=(tag,))
        else:
            self.tree.item(target, values=values)
        self._auto_sort_if_needed()

    def get_selected_row(self):
        sel = self.tree.selection()
        if not sel:
            return None
        vals = self.tree.item(sel[0], "values")
        return {col: vals[i] for i, col in enumerate(self._all_cols)}

    # ---------- ordenação por cabeçalho ----------
    def _on_heading_click(self, col: str) -> None:
        if getattr(self, "_auto_sort_col", None) == col:
            self._auto_sort_asc = not self._auto_sort_asc
        else:
            self._auto_sort_col = col
            self._auto_sort_asc = True
        self._sort_by(col, toggle=False)

    def sort_by(self, col: str, ascending: bool | None = None) -> None:
        self._auto_sort_col = col
        if ascending is not None:
            self._auto_sort_asc = bool(ascending)
        self._sort_by(col, toggle=False)

    def _sort_by(self, col: str, toggle: bool = True) -> None:
        try:
            idx = self._all_cols.index(col)
        except ValueError:
            return
        children = list(self.tree.get_children(""))

        def _key(iid):
            vals = self.tree.item(iid, "values")
            v = vals[idx] if idx < len(vals) else ""
            try:
                return (0, float(v))                # numéricos juntos
            except Exception:
                return (1, str(v).strip().lower())  # textos juntos


        reverse = not getattr(self, "_auto_sort_asc", True)
        children.sort(key=_key, reverse=reverse)
        for i, iid in enumerate(children):
            self.tree.move(iid, "", i)
        for i, iid in enumerate(self.tree.get_children("")):
            self.tree.item(iid, tags=(("even" if i % 2 == 0 else "odd"),))
        if toggle:
            self._auto_sort_asc = not self._auto_sort_asc

    def _auto_sort_if_needed(self) -> None:
        if getattr(self, "_auto_sort_col", None):
            self._sort_by(self._auto_sort_col, toggle=False)
            

"""
# Plano (cores em **um único lugar**: `_colors_for_mode` no `ColumnToggleTree`)
- `_colors_for_mode()` retorna **um `dict`** com **todas** as cores do tema.
- `apply_style()` consome esse `dict`.
- `set_table_colors(theme, **cores)` permite overrides em runtime.
- Chaves: `bg`, `fg`, `header_bg`, `header_hover_bg`, `row_hover_bg`, `odd_bg`, `even_bg`, `sel_bg`, `sel_fg`, `grid_border`, `grid_light`, `grid_dark`.

**Como customizar (neste arquivo)**
- Edite `_THEME_COLORS["light"|"dark"]` com os hex desejados.
- Agora o grid tem 3 tons: `grid_border`, `grid_light`, `grid_dark` (mapeados para `bordercolor`, `lightcolor`, `darkcolor`).
- Ou chame `set_table_colors("dark", grid_border="#444", grid_light="#555", grid_dark="#222")` antes de criar a tabela.
- `_colors_for_mode()` continua sendo a **única fonte** e retorna um `dict` usado por todo o widget.
"""