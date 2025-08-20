# buttontags.py
# Widget CTk com seletor + filtros para Button Tags.
# - Dropdown custom com scrollbar visível (CTkToplevel + CTkScrollableFrame)
# - Select acima; filtros abaixo (2–3 por linha, configurável)
# - API:
#     picker = ButtonTagsWidget(parent, on_change=None,
#                               combo_width=160, cols=3,
#                               checkbox_size=14, font_size=12,
#                               dropdown_height=260)
#     picker.get_selected_tag() -> str
#     picker.set_selected_tag(tag: str) -> None
#     picker.get_values() -> list[str]

import customtkinter as ctk

# ----------------- Lógica (match e filtros) -----------------

def _match_prefix_or_token(tag: str, token: str) -> bool:
    # token com '_' = prefixo; sem '_' = termo exato OU prefixo seguido de '_'
    if token.endswith("_"):
        return tag.startswith(token)
    return (tag == token) or tag.startswith(token + "_")

def _in_any_category(tag: str) -> bool:
    for cat, prefs in category_prefixes.items():
        if cat == "Outros":
            continue
        if any(_match_prefix_or_token(tag, p) for p in prefs):
            return True
    return False

_OUTROS_CACHE = None
def _outros_tags():
    global _OUTROS_CACHE
    if _OUTROS_CACHE is None:
        _OUTROS_CACHE = sorted([t for t in BUTTON_TAGS if not _in_any_category(t)])
    return _OUTROS_CACHE

def filtered_values(ac: bool, tv: bool, rx: bool, md: bool, comuns: bool, outros: bool):
    selected = set()

    if ac or tv or rx or md:
        selected_prefixes = []
        if ac: selected_prefixes += category_prefixes.get("AC", [])
        if tv: selected_prefixes += category_prefixes.get("TV", [])
        if rx: selected_prefixes += category_prefixes.get("Receiver", [])
        if md: selected_prefixes += category_prefixes.get("Midia", [])
        for tag in BUTTON_TAGS:
            if any(_match_prefix_or_token(tag, p) for p in selected_prefixes):
                selected.add(tag)

    if comuns:
        for tag in BUTTON_TAGS:
            if any(_match_prefix_or_token(tag, p) for p in category_prefixes["Comuns"]):
                selected.add(tag)

    if outros:
        selected.update(_outros_tags())

    return sorted(selected) if selected else []


# ----------------- Widget com dropdown scrollável -----------------

class ButtonTagsWidget(ctk.CTkFrame):
    def __init__(
        self, parent, on_change=None,
        combo_width=160,    # largura do "campo" (px)
        cols=3,             # checkboxes por linha
        checkbox_size=14,   # tamanho do quadradinho
        font_size=12,       # fonte dos checkboxes
        dropdown_height=260, # altura máxima do dropdown (px)
        item_font_size=12,          # NOVO: fonte dos itens do dropdown
        item_height=22              # NOVO: altura de cada linha do dropdown
    ):
        super().__init__(parent, fg_color="transparent")
        self._on_change_cb = on_change
        self._cols = max(1, int(cols))
        self._combo_width = int(combo_width)
        self._dropdown_height = int(dropdown_height)
        self._item_font   = ctk.CTkFont(size=item_font_size)  # NOVO
        self._item_height = int(item_height)                  # NOVO
        self._dropdown = None        # CTkToplevel aberto
        self._values = list(BUTTON_TAGS)
        self._item_buttons = []  # <- NOVO: guarda os CTkButton dos itens do dropdown

        # ---- Linha 0: label + botão que abre o dropdown ----
        ctk.CTkLabel(self, text="Button Tag:").grid(row=0, column=0, sticky="w",
                                                    padx=(0, 6), pady=(0, 4))

        self._sel_var = ctk.StringVar(value=self._values[0] if self._values else "")
        self._select_btn = ctk.CTkButton(
            self,
            textvariable=self._sel_var,
            width=self._combo_width,
            height=32,
            anchor="w",
            command=self._toggle_dropdown,
            # estilo "entrada de texto":
            fg_color=("white", "#2b2b2b"),
            text_color=("black", "white"),
            hover_color=("white", "#2b2b2b"),
            border_width=2,
            border_color=("#C4C7CF", "#3A3A3A"),
            corner_radius=6,
        )
        self._select_btn.grid(row=0, column=1, sticky="w", padx=(0, 0), pady=(0, 4))

        # Navegação por teclado quando o foco está no "select"
        self._select_btn.bind("<Up>",   self._on_key_up)
        self._select_btn.bind("<Down>", self._on_key_down)
        self._select_btn.bind("<Prior>", self._on_page_up)   # PageUp
        self._select_btn.bind("<Next>",  self._on_page_down) # PageDown
        self._select_btn.bind("<Home>",  self._on_home)
        self._select_btn.bind("<End>",   self._on_end)
        self._select_btn.bind("<Return>", lambda e: self._toggle_dropdown())

        # ---- Linha 1+: filtros compactos ----
        self._filter_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._filter_frame.grid(row=1, column=0, columnspan=2, sticky="w")
        self._chk_font = ctk.CTkFont(size=font_size)
        for i in range(self._cols):
            self._filter_frame.grid_columnconfigure(i, weight=0)

        # Vars
        self.var_comuns  = ctk.BooleanVar(value=True)
        self.var_outros  = ctk.BooleanVar(value=False)
        self.var_todos   = ctk.BooleanVar(value=True)

        self.var_ac = ctk.BooleanVar(value=True)
        self.var_tv = ctk.BooleanVar(value=True)
        self.var_rx = ctk.BooleanVar(value=True)
        self.var_md = ctk.BooleanVar(value=True)

        # Ordem / criação
        r = c = 0
        def add_chk(text, var, cmd):
            nonlocal r, c
            cb = ctk.CTkCheckBox(
                self._filter_frame, text=text, variable=var, command=cmd,
                width=0, checkbox_width=checkbox_size, checkbox_height=checkbox_size,
                font=self._chk_font
            )
            cb.grid(row=r, column=c, sticky="w", padx=(0, 6), pady=(0, 2))
            c += 1
            if c >= self._cols:
                c = 0; r += 1

        add_chk("Comuns",   self.var_comuns,   self._apply_filter)
        add_chk("AC",       self.var_ac,       self._apply_filter)
        add_chk("TV",       self.var_tv,       self._apply_filter)
        add_chk("Receiver", self.var_rx,       self._apply_filter)
        add_chk("Midia",    self.var_md,       self._apply_filter)
        add_chk("Outros",   self.var_outros,   self._apply_filter)
        add_chk("Todos",    self.var_todos,    self._on_todos)

        # Inicializa a lista
        self._apply_filter()

        # Fecha dropdown ao destruir o widget
        self.bind("<Destroy>", lambda e: self._close_dropdown())

    # -------- API pública --------
    def get_selected_tag(self) -> str:
        return (self._sel_var.get() or "").strip()

    def set_selected_tag(self, tag: str) -> None:
        if tag in self._values:
            self._sel_var.set(tag)
            self._notify_change()

    def get_values(self) -> list[str]:
        return list(self._values)

    def set_on_change(self, cb) -> None:
        self._on_change_cb = cb

    # -------- Internos --------
    def _notify_change(self):
        if callable(self._on_change_cb):
            try:
                self._on_change_cb(self.get_selected_tag())
            except Exception:
                pass

    def _on_todos(self):
        state = bool(self.var_todos.get())
        self.var_comuns.set(state)
        self.var_outros.set(state)
        self.var_ac.set(state)
        self.var_tv.set(state)
        self.var_rx.set(state)
        self.var_md.set(state)
        self._apply_filter()

    def _reflect_master_toggle(self):
        all_selected = (
            self.var_comuns.get() and self.var_outros.get() and
            self.var_ac.get() and self.var_tv.get() and self.var_rx.get() and self.var_md.get()
        )
        if self.var_todos.get() != all_selected:
            self.var_todos.set(all_selected)

    def _apply_filter(self):
        self._reflect_master_toggle()
        filtered = filtered_values(
            ac=self.var_ac.get(),
            tv=self.var_tv.get(),
            rx=self.var_rx.get(),
            md=self.var_md.get(),
            comuns=self.var_comuns.get(),
            outros=self.var_outros.get(),
        )
        self._values = filtered

        current = self._sel_var.get().strip()
        if current in self._values:
            self._sel_var.set(current)
        else:
            # quando vazio, deixa o “campo” sem texto
            self._sel_var.set(self._values[0] if self._values else "")
        self._notify_change()

        # Se o dropdown estiver aberto, atualiza o conteúdo
        if self._dropdown:
            self._fill_dropdown(self._values)

    # ---- Dropdown custom com scrollbar visível ----
    def _toggle_dropdown(self):
        if self._dropdown:
            self._close_dropdown()
        else:
            self._open_dropdown()

    def _open_dropdown(self):
        if self._dropdown:
            return

        # cria o popup toplevel
        self._dropdown = ctk.CTkToplevel(self)
        self._dropdown.overrideredirect(True)
        self._dropdown.attributes("-topmost", True)
        # fecha com ESC (mas não em FocusOut, para poder clicar nos filtros)
        self._dropdown.bind("<Escape>", lambda e: self._close_dropdown())

        # posiciona logo abaixo do botão
        self._dropdown.update_idletasks()
        bx = self._select_btn.winfo_rootx()
        by = self._select_btn.winfo_rooty() + self._select_btn.winfo_height()
        self._dropdown.geometry(f"+{bx}+{by}")

        # conteúdo com borda e fundo claro/escuro
        container = ctk.CTkFrame(
            self._dropdown,
            fg_color=("white", "#2b2b2b"),
            border_width=2,
            border_color=("#C4C7CF", "#3A3A3A"),
            corner_radius=6,
        )
        container.pack(fill="both", expand=True)

        self._scroll = ctk.CTkScrollableFrame(
            container,
            width=self._combo_width + 18,
            height=self._dropdown_height,
            fg_color=("white", "#2b2b2b"),
        )
        self._scroll.pack(fill="both", expand=True, padx=2, pady=2)

        # binds de navegação de teclado também no popup
        for w in (self._dropdown, self._scroll):
            w.bind("<Up>",     self._on_key_up)
            w.bind("<Down>",   self._on_key_down)
            w.bind("<Prior>",  self._on_page_up)   # PageUp
            w.bind("<Next>",   self._on_page_down) # PageDown
            w.bind("<Home>",   self._on_home)
            w.bind("<End>",    self._on_end)
            w.bind("<Return>", lambda e: self._choose(self._sel_var.get()))

        # popula e foca
        self._fill_dropdown(self._values)
        self._dropdown.focus_force()

        # rola e destaca o item atual
        idx = self._index_of_current()
        if idx >= 0:
            self.after(10, lambda: (self._highlight_item(idx), self._ensure_visible(idx)))


    def _fill_dropdown(self, values):
        # limpa itens antigos
        for w in self._scroll.winfo_children():
            w.destroy()
        self._item_buttons = []

        # itens “flat”, com hover e clique
        for idx, v in enumerate(values):
            btn = ctk.CTkButton(
                self._scroll,
                text=v,
                width=self._combo_width - 4,
                height=self._item_height,
                anchor="w",
                fg_color=("white", "#2b2b2b"),   # fundo
                text_color=("black", "white"),   # texto
                hover=True,
                border_width=0,
                corner_radius=0,
                font=self._item_font,
                cursor="hand2",
                command=lambda _v=v: self._choose(_v),
            )
            btn.pack(fill="x", padx=2, pady=0)
            self._item_buttons.append(btn)

        # aplica highlight ao item atual, se existir
        cur = self._index_of_current()
        if 0 <= cur < len(self._item_buttons):
            self._highlight_item(cur)



    def _choose(self, value: str):
        self._sel_var.set(value)
        self._close_dropdown()
        self._notify_change()

    def _close_dropdown(self):
        if self._dropdown:
            try:
                self._dropdown.destroy()
            except Exception:
                pass

            try:
                self._select_btn.focus_set()
            except Exception:
                pass
            self._dropdown = None


    def _index_of_current(self) -> int:
        try:
            return self._values.index(self._sel_var.get())
        except Exception:
            return -1

    def _select_index(self, idx: int, announce: bool = True, ensure_visible: bool = True):
        if not self._values:
            self._sel_var.set("")
            return
        idx = max(0, min(idx, len(self._values) - 1))
        self._sel_var.set(self._values[idx])
        if self._dropdown and ensure_visible:
            self._highlight_item(idx)   # NOVO
            self._ensure_visible(idx)
        if announce:
            self._notify_change()

    def _ensure_visible(self, idx: int):
        """Tenta rolar o dropdown para tornar o item idx visível."""
        try:
            # child alvo
            child = self._scroll.winfo_children()[idx]
            self._scroll.update_idletasks()
            y = child.winfo_y()
            # tenta usar a canvas interna do ScrollableFrame (API interna, por isso try/except)
            canvas = getattr(self._scroll, "_parent_canvas", None)
            if canvas is not None and hasattr(canvas, "bbox") and hasattr(canvas, "yview_moveto"):
                bbox = canvas.bbox("all")
                if bbox:
                    total_h = max(1, bbox[3] - bbox[1])
                    frac = max(0.0, min(1.0, y / total_h))
                    canvas.yview_moveto(frac)
        except Exception:
            pass

    # ---- Teclas ----
    def _on_key_down(self, event=None):
        i = self._index_of_current()
        if i < 0: i = -1
        self._select_index(i + 1)
        return "break"

    def _on_key_up(self, event=None):
        i = self._index_of_current()
        if i < 0: i = len(self._values)
        self._select_index(i - 1)
        return "break"

    def _on_page_down(self, event=None):
        i = self._index_of_current()
        if i < 0: i = -1
        self._select_index(i + 10)
        return "break"

    def _on_page_up(self, event=None):
        i = self._index_of_current()
        if i < 0: i = len(self._values)
        self._select_index(i - 10)
        return "break"

    def _on_home(self, event=None):
        self._select_index(0)
        return "break"

    def _on_end(self, event=None):
        self._select_index(len(self._values) - 1)
        return "break"



# ----------------- Constantes (no fim) -----------------

category_prefixes = {
    "Comuns":   ["channel_", "volume_", "menu", "power_", "cursor_", "back_return", "exit_cancel"],
    "AC":       ["ac_"],
    "TV":       ["channel_", "volume_", "func_", "menu", "home", "guide", "digit_", "cursor_", "pip_"],
    "Receiver": ["input_", "preset_", "surround_", "bass_", "treble_", "z2_", "matrix_", "audio_"],
    "Midia":    ["tr_", "skip", "open_close_eject",
                 "netflix", "youtube", "youtube_music", "primevideo", "globoplay", "disneyplus"],
    # "Outros" é dinâmico (_outros_tags)
}

BUTTON_TAGS = [
"3D",
"A-B",
"A.F.D",
"ac_16graus",
"ac_17graus",
"ac_18graus",
"ac_19graus",
"ac_20graus",
"ac_21graus",
"ac_22graus",
"ac_23graus",
"ac_24graus",
"ac_25graus",
"ac_26graus",
"ac_27graus",
"ac_28graus",
"ac_29graus",
"ac_30graus",
"ac_31graus",
"ac_desliga",
"ac_direcao",
"ac_fan_auto_17graus",
"ac_fan_auto_18graus",
"ac_fan_auto_19graus",
"ac_fan_auto_20graus",
"ac_fan_auto_21graus",
"ac_fan_auto_22graus",
"ac_fan_auto_23graus",
"ac_fan_auto_24graus",
"ac_fan_auto_25graus",
"ac_fan_auto_26graus",
"ac_fan_auto_27graus",
"ac_fan_auto_28graus",
"ac_fan_max_17graus",
"ac_fan_max_18graus",
"ac_fan_max_19graus",
"ac_fan_max_20graus",
"ac_fan_max_21graus",
"ac_fan_max_22graus",
"ac_fan_max_23graus",
"ac_fan_max_24graus",
"ac_fan_max_25graus",
"ac_fan_max_26graus",
"ac_fan_max_27graus",
"ac_fan_max_28graus",
"ac_fan_max_29graus",
"ac_fan_max_30graus",
"ac_fan_med_17graus",
"ac_fan_med_18graus",
"ac_fan_med_19graus",
"ac_fan_med_20graus",
"ac_fan_med_21graus",
"ac_fan_med_22graus",
"ac_fan_med_23graus",
"ac_fan_med_24graus",
"ac_fan_med_25graus",
"ac_fan_med_26graus",
"ac_fan_med_27graus",
"ac_fan_med_28graus",
"ac_fan_med_29graus",
"ac_fan_med_30graus",
"ac_fan_min_17graus",
"ac_fan_min_18graus",
"ac_fan_min_19graus",
"ac_fan_min_20graus",
"ac_fan_min_21graus",
"ac_fan_min_22graus",
"ac_fan_min_23graus",
"ac_fan_min_24graus",
"ac_fan_min_25graus",
"ac_fan_min_26graus",
"ac_fan_min_27graus",
"ac_fan_min_28graus",
"ac_fan_min_29graus",
"ac_fan_min_30graus",
"ac_fan_speed",
"ac_liga",
"ac_light",
"ac_swing",
"ac_swing_h",
"ac_swing_off",
"ac_swing_on",
"ac_swing_v",
"alexa",
"angle",
"audio",
"audiodelay_minus",
"audiodelay_plus",
"audio_adjust",
"audio_effects",
"audio_hdmi",
"audio_sync_down",
"audio_sync_up",
"back_return",
"band",
"bass_down",
"bass_up",
"cena_1",
"cena_2",
"cena_3",
"cena_4",
"channel_down",
"channel_enter",
"channel_last",
"channel_next",
"channel_prev",
"channel_up",
"ch_level",
"clear",
"cursor_down",
"cursor_left",
"cursor_ok_select",
"cursor_right",
"cursor_up",
"digit_0",
"digit_1",
"digit_100",
"digit_2",
"digit_3",
"digit_4",
"digit_5",
"digit_6",
"digit_7",
"digit_8",
"digit_9",
"digit_dash",
"disneyplus",
"display",
"display_dimmer",
"exit_cancel",
"favorite",
"format_wide",
"func_blue",
"func_green",
"func_red",
"func_yellow",
"globoplay",
"google",
"guide",
"home",
"info",
"input_audio",
"input_audio_1",
"input_audio_2",
"input_audio_3",
"input_aux",
"input_av1",
"input_av2",
"input_av3",
"input_av4",
"input_av5",
"input_av6",
"input_bd",
"input_bt",
"input_cd",
"input_cdr_tape",
"input_comp1",
"input_comp2",
"input_comp3",
"input_dock",
"input_down",
"input_dvd",
"input_game",
"input_game2",
"input_hdmi_1",
"input_hdmi_2",
"input_hdmi_3",
"input_hdmi_4",
"input_hdmi_5",
"input_media_player",
"input_mhl",
"input_movie",
"input_music",
"input_net",
"input_phono",
"input_photo",
"input_rgb_pc",
"input_sat_cbl",
"input_scroll",
"input_tuner",
"input_tv",
"input_up",
"input_usb",
"input_vcr",
"internet",
"L/R",
"matrix_outA_in1",
"matrix_outA_in2",
"matrix_outA_in3",
"matrix_outA_in4",
"matrix_outB_in1",
"matrix_outB_in2",
"matrix_outB_in3",
"matrix_outB_in4",
"matrix_outC_in1",
"matrix_outC_in2",
"matrix_outC_in3",
"matrix_outC_in4",
"matrix_outD_in1",
"matrix_outD_in2",
"matrix_outD_in3",
"matrix_outD_in4",
"media_player",
"memory",
"menu",
"menu_3d",
"menu_disc",
"menu_popup",
"menu_position",
"menu_system",
"menu_top",
"microphone",
"mode",
"mosaico",
"most",
"Movie",
"Music",
"Mute",
"N/P",
"netflix",
"next",
"now",
"open_close_eject",
"OPT",
"optoma",
"OSD",
"page_down",
"page_up",
"PBC",
"Photo",
"picture",
"PIP",
"pip_channel_down",
"pip_channel_up",
"pip_freeze",
"pip_input",
"pip_move",
"pip_multi",
"pip_off",
"pip_on",
"pip_swap",
"play",
"portal",
"power_off_discr",
"power_on_discr",
"power_on_off",
"preset_minus",
"preset_plus",
"preset_quickselect_1",
"preset_quickselect_2",
"preset_quickselect_3",
"preset_quickselect_4",
"preset_quickselect_5",
"preset_quickselect_6",
"preset_quickselect_7",
"prev",
"primevideo",
"Prog",
"radio",
"repeat",
"reset",
"restorer",
"return",
"ripping",
"sap",
"search",
"setup_function",
"shift",
"sleep",
"slow",
"smart",
"sound_edit",
"source",
"status",
"step",
"subtitle",
"surround_down",
"surround_on_off",
"surround_up",
"time",
"title",
"tone",
"tools",
"treble_down",
"treble_up",
"trilho_direita",
"trilho_esquerda",
"trilho_girar_antihorario",
"trilho_girar_horario",
"trilho_preset_1",
"trilho_preset_2",
"trilho_preset_3",
"trilho_preset_4",
"tr_back",
"tr_fast_forward",
"tr_pause",
"tr_play",
"tr_random",
"tr_record",
"tr_repeat",
"tr_rewind",
"tr_skip_next",
"tr_skip_prev",
"tr_stop",
"tuning_down",
"tuning_up",
"tv",
"video",
"voice",
"volume_down",
"volume_mute",
"volume_night",
"volume_up",
"Wifi",
"youtube",
"youtube_music",
"z2_back_return",
"z2_cena_1",
"z2_cena_2",
"z2_cena_3",
"z2_cena_4",
"z2_cursor_down",
"z2_cursor_enter",
"z2_cursor_left",
"z2_cursor_right",
"z2_cursor_up",
"z2_input_bt",
"z2_input_down",
"z2_input_net",
"z2_input_tuner",
"z2_input_up",
"z2_input_usb",
"z2_power_on_off",
"z2_volume_down",
"z2_volume_mute",
"z2_volume_up",
"zona2",
"zoom"
]
