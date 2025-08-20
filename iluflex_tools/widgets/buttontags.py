# buttontags.py
# Widget de seleção/filtragem de Button Tags para uso em painéis estreitos (ex.: leftpanel).
# - Combobox acima; filtros logo abaixo (podem quebrar em 2–3 linhas).
# - API:
#     picker = ButtonTagsWidget(parent, on_change=callable)
#     picker.get_selected_tag() -> str
#     picker.set_selected_tag(tag: str) -> None
#     picker.get_values() -> list[str]   # lista atual filtrada
#
# Mantém funções no topo e constantes no fim, como solicitado.

import customtkinter as ctk


class ButtonTags:
    """Regras de agrupamento + utilitários de filtro (sem UI)."""

    @staticmethod
    def _match_prefix_or_token(tag: str, token: str) -> bool:
        """token com '_' = prefixo; sem '_' = termo exato OU prefixo seguido de '_'."""
        if token.endswith("_"):
            return tag.startswith(token)
        return (tag == token) or tag.startswith(token + "_")

    @classmethod
    def _in_any_category(cls, tag: str) -> bool:
        for cat, prefs in cls.category_prefixes.items():
            if cat == "Outros":
                continue
            if any(cls._match_prefix_or_token(tag, p) for p in prefs):
                return True
        return False

    @classmethod
    def _outros_tags(cls):
        """Calcula cache de 'Outros' (tudo que não bate nos grupos)."""
        if cls._OUTROS_CACHE is None:
            cls._OUTROS_CACHE = sorted([t for t in cls.BUTTON_TAGS if not cls._in_any_category(t)])
        return cls._OUTROS_CACHE

    # ---- API lógica (usada pelo widget) ----
    @classmethod
    def filtered_values(
        cls,
        ac: bool, tv: bool, rx: bool, md: bool,
        comuns: bool, outros: bool
    ) -> list[str]:
        selected = set()

        # Agrupa por categorias
        if ac or tv or rx or md:
            selected_prefixes = []
            if ac: selected_prefixes += cls.category_prefixes.get("AC", [])
            if tv: selected_prefixes += cls.category_prefixes.get("TV", [])
            if rx: selected_prefixes += cls.category_prefixes.get("Receiver", [])
            if md: selected_prefixes += cls.category_prefixes.get("Midia", [])
            for tag in cls.BUTTON_TAGS:
                if any(cls._match_prefix_or_token(tag, p) for p in selected_prefixes):
                    selected.add(tag)

        if comuns:
            for tag in cls.BUTTON_TAGS:
                if any(cls._match_prefix_or_token(tag, p) for p in cls.category_prefixes["Comuns"]):
                    selected.add(tag)

        if outros:
            selected.update(cls._outros_tags())

        return sorted(selected) if selected else []


class ButtonTagsWidget(ctk.CTkFrame):
    """
    Widget compacto: Combobox (tags) + filtros (check-boxes em múltiplas colunas).
    Pensado para caber direto no conv_content do Card 'Conversão'
    (select acima, filtros abaixo).
    """

    def __init__(self, parent, on_change=None, combo_width=180, cols=3, checkbox_size=16, font_size=12):
        super().__init__(parent, fg_color="transparent")
        self._on_change_cb = on_change

        # --- Linha 0: label + OptionMenu (dropdown rolável) ---
        lbl = ctk.CTkLabel(self, text="Button Tag:")
        lbl.grid(row=0, column=0, sticky="w", padx=(0, 6), pady=(0, 4))

        self._option = ctk.CTkOptionMenu(
            self,
            values=list(ButtonTags.BUTTON_TAGS),  # mesma lista
            width=combo_width,                    # pixels, mantém estreito
            anchor="w",
            command=lambda _sel=None: self._notify_change()
        )
        self._option.grid(row=0, column=1, sticky="w", padx=(0, 0), pady=(0, 4))
        if ButtonTags.BUTTON_TAGS:
            self._option.set(ButtonTags.BUTTON_TAGS[0])

        # --- Linha 1+: filtros empilhando em múltiplas colunas (quebra natural) ---
        self._filter_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._filter_frame.grid(row=1, column=0, columnspan=2, sticky="w")
        for i in range(cols):                    # N colunas fixas, não expansivas
            self._filter_frame.grid_columnconfigure(i, weight=0)
        self._chk_font = ctk.CTkFont(size=font_size)

        # Vars
        self.var_comuns  = ctk.BooleanVar(value=True)
        self.var_outros  = ctk.BooleanVar(value=False)
        self.var_todos   = ctk.BooleanVar(value=False)

        self.var_ac = ctk.BooleanVar(value=False)
        self.var_tv = ctk.BooleanVar(value=False)
        self.var_rx = ctk.BooleanVar(value=False)
        self.var_md = ctk.BooleanVar(value=False)

        # Ordem: Comuns | AC | TV | Receiver | Midia | Outros | Todos
        r, c = 0, 0
        def add_chk(text, var, cmd):
            nonlocal r, c
            cb = ctk.CTkCheckBox(
                self._filter_frame,
                text=text,
                variable=var,
                command=cmd,
                width=0,                          # não forçar 100px
                checkbox_width=checkbox_size,
                checkbox_height=checkbox_size,
                font=self._chk_font
            )
            cb.grid(row=r, column=c, sticky="w", padx=(0, 6), pady=(0, 2))
            c += 1
            if c >= cols:                         # 2 ou 3 por linha, ajustável
                c = 0; r += 1

        add_chk("Comuns",   self.var_comuns,   self._apply_filter)
        add_chk("AC",       self.var_ac,       self._apply_filter)
        add_chk("TV",       self.var_tv,       self._apply_filter)
        add_chk("Receiver", self.var_rx,       self._apply_filter)
        add_chk("Midia",    self.var_md,       self._apply_filter)
        add_chk("Outros",   self.var_outros,   self._apply_filter)
        add_chk("Todos",    self.var_todos,    self._on_todos)

        # Inicializa lista conforme filtros atuais
        self._apply_filter()

    # ---------------- API externa ----------------
    def get_selected_tag(self) -> str:
        return (self._option.get() or "").strip()

    def set_selected_tag(self, tag: str) -> None:
        vals = list(self._option.cget("values"))
        if tag in vals:
            self._option.set(tag)
            self._notify_change()

    def get_values(self) -> list[str]:
        return list(self._option.cget("values"))

    def set_on_change(self, cb) -> None:
        self._on_change_cb = cb

    # ---------------- Internos -------------------
    def _notify_change(self, *_):
        if callable(self._on_change_cb):
            try:
                self._on_change_cb(self.get_selected_tag())
            except Exception:
                pass

    def _on_todos(self):
        """Marca/desmarca TODOS e reaplica filtro."""
        state = bool(self.var_todos.get())
        # espelha nos demais
        self.var_comuns.set(state)
        self.var_outros.set(state)
        self.var_ac.set(state)
        self.var_tv.set(state)
        self.var_rx.set(state)
        self.var_md.set(state)
        self._apply_filter()

    def _reflect_master_toggle(self):
        """Atualiza 'Todos' conforme estado dos demais."""
        all_selected = (
            self.var_comuns.get() and self.var_outros.get() and
            self.var_ac.get() and self.var_tv.get() and self.var_rx.get() and self.var_md.get()
        )
        if self.var_todos.get() != all_selected:
            self.var_todos.set(all_selected)

    def _apply_filter(self):
        """Recalcula valores do combobox conforme filtros e notifica mudança."""
        self._reflect_master_toggle()
        filtered = ButtonTags.filtered_values(
            ac=self.var_ac.get(),
            tv=self.var_tv.get(),
            rx=self.var_rx.get(),
            md=self.var_md.get(),
            comuns=self.var_comuns.get(),
            outros=self.var_outros.get(),
        )
        # fallback para "todos" quando vazio (evita combobox sem opções)
        if not filtered:
            filtered = list(ButtonTags.BUTTON_TAGS)

        current = self._option.get().strip()
        self._option.configure(values=filtered)

        # mantém tag antiga se ainda existir; senão seleciona a primeira
        if current in filtered:
            self._option.set(current)
        else:
            self._option.set(filtered[0] if filtered else "")

        self._notify_change()


# ----------------------- Constantes (por último) -----------------------

# Grupo "Comuns" (sem ac_* e sem z2_*; esses ficam nos grupos AC/Receiver)
ButtonTags.category_prefixes = {
    "Comuns":   ["channel_", "volume_", "menu", "power_", "cursor_", "back_return", "exit_cancel"],
    "AC":       ["ac_"],
    "TV":       ["channel_", "volume_", "func_", "menu", "home", "guide", "digit_", "cursor_", "pip_"],
    "Receiver": ["input_", "preset_", "surround_", "bass_", "treble_", "z2_", "matrix_", "audio_"],
    "Midia":    ["tr_", "skip", "open_close_eject",
                 "netflix", "youtube", "youtube_music", "primevideo", "globoplay", "disneyplus"],
    # "Outros" é dinâmico (calculado via _outros_tags)
}

# --- Lista completa de tags (mesma base usada no Learner) ---
ButtonTags.BUTTON_TAGS = [
    "3D","A-B","A.F.D","ac_16graus","ac_17graus","ac_18graus","ac_19graus","ac_20graus","ac_21graus","ac_22graus",
    "ac_23graus","ac_24graus","ac_25graus","ac_26graus","ac_27graus","ac_28graus","ac_29graus","ac_30graus",
    "ac_31graus","ac_desliga","ac_direcao","ac_fan_auto_17graus","ac_fan_auto_18graus","ac_fan_auto_19graus",
    "ac_fan_auto_20graus","ac_fan_auto_21graus","ac_fan_auto_22graus","ac_fan_auto_23graus","ac_fan_auto_24graus",
    "ac_fan_auto_25graus","ac_fan_auto_26graus","ac_fan_auto_27graus","ac_fan_auto_28graus","ac_fan_auto_29graus",
    "ac_fan_auto_30graus","ac_fan_max_17graus","ac_fan_max_18graus","ac_fan_max_19graus","ac_fan_max_20graus",
    "ac_fan_max_21graus","ac_fan_max_22graus","ac_fan_max_23graus","ac_fan_max_24graus","ac_fan_max_25graus",
    "ac_fan_max_26graus","ac_fan_max_27graus","ac_fan_max_28graus","ac_fan_max_29graus","ac_fan_max_30graus",
    "ac_fan_med_17graus","ac_fan_med_18graus","ac_fan_med_19graus","ac_fan_med_20graus","ac_fan_med_21graus",
    "ac_fan_med_22graus","ac_fan_med_23graus","ac_fan_med_24graus","ac_fan_med_25graus","ac_fan_med_26graus",
    "ac_fan_med_27graus","ac_fan_med_28graus","ac_fan_med_29graus","ac_fan_med_30graus","ac_fan_min_17graus",
    "ac_fan_min_18graus","ac_fan_min_19graus","ac_fan_min_20graus","ac_fan_min_21graus","ac_fan_min_22graus",
    "ac_fan_min_23graus","ac_fan_min_24graus","ac_fan_min_25graus","ac_fan_min_26graus","ac_fan_min_27graus",
    "ac_fan_min_28graus","ac_fan_min_29graus","ac_fan_min_30graus","ac_fan_speed","ac_liga","ac_light","ac_swing",
    "ac_swing_h","ac_swing_off","ac_swing_on","ac_swing_v","alexa","angle","audio","audiodelay_minus","audiodelay_plus",
    "audio_adjust","audio_effects","audio_hdmi","audio_sync_down","audio_sync_up","back_return","band","bass_down",
    "bass_up","cena_1","cena_2","cena_3","cena_4","channel_down","channel_enter","channel_last","channel_next",
    "channel_prev","channel_up","ch_level","clear","cursor_down","cursor_left","cursor_ok_select","cursor_right",
    "cursor_up","digit_0","digit_1","digit_100","digit_2","digit_3","digit_4","digit_5","digit_6","digit_7",
    "digit_8","digit_9","digit_dash","disneyplus","display","display_dimmer","exit_cancel","favorite","format_wide",
    "func_blue","func_green","func_red","func_yellow","globoplay","google","guide","home","info","input_audio",
    "input_audio_1","input_audio_2","input_audio_3","input_aux","input_av1","input_av2","input_av3","input_av4",
    "input_av5","input_av6","input_bd","input_bt","input_cd","input_cdr_tape","input_comp1","input_comp2",
    "input_comp3","input_dock","input_down","input_dvd","input_game","input_game2","input_hdmi_1","input_hdmi_2",
    "input_hdmi_3","input_hdmi_4","input_hdmi_5","input_media_player","input_mhl","input_movie","input_music",
    "input_net","input_phono","input_photo","input_rgb_pc","input_sat_cbl","input_scroll","input_tuner","input_tv",
    "input_up","input_usb","input_vcr","internet","L/R","matrix_outA_in1","matrix_outA_in2","matrix_outA_in3",
    "matrix_outA_in4","matrix_outB_in1","matrix_outB_in2","matrix_outB_in3","matrix_outB_in4","matrix_outC_in1",
    "matrix_outC_in2","matrix_outC_in3","matrix_outC_in4","matrix_outD_in1","matrix_outD_in2","matrix_outD_in3",
    "matrix_outD_in4","media_player","memory","menu","menu_3d","menu_disc","menu_popup","menu_position","menu_system",
    "menu_top","microphone","mode","mosaico","most","Movie","Music","Mute","N/P","netflix","next","now",
    "open_close_eject","OPT","optoma","OSD","page_down","page_up","PBC","Photo","picture","PIP","pip_channel_down",
    "pip_channel_up","pip_freeze","pip_input","pip_move","pip_multi","pip_off","pip_on","pip_swap","play","portal",
    "power_off_discr","power_on_discr","power_on_off","preset_minus","preset_plus","preset_quickselect_1",
    "preset_quickselect_2","preset_quickselect_3","preset_quickselect_4","preset_quickselect_5","preset_quickselect_6",
    "preset_quickselect_7","prev","primevideo","Prog","radio","repeat","reset","restorer","return","ripping","sap",
    "search","setup_function","shift","sleep","slow","smart","sound_edit","source","status","step","subtitle",
    "surround_down","surround_on_off","surround_up","time","title","tone","tools","treble_down","treble_up",
    "trilho_direita","trilho_esquerda","trilho_girar_antihorario","trilho_girar_horario","trilho_preset_1",
    "trilho_preset_2","trilho_preset_3","trilho_preset_4","tr_back","tr_fast_forward","tr_pause","tr_play","tr_random",
    "tr_record","tr_repeat","tr_rewind","tr_skip_next","tr_skip_prev","tr_stop","tuning_down","tuning_up","tv","video",
    "voice","volume_down","volume_mute","volume_night","volume_up","Wifi","youtube","youtube_music","z2_back_return",
    "z2_cena_1","z2_cena_2","z2_cena_3","z2_cena_4","z2_cursor_down","z2_cursor_enter","z2_cursor_left",
    "z2_cursor_right","z2_cursor_up","z2_input_bt","z2_input_down","z2_input_net","z2_input_tuner","z2_input_up",
    "z2_input_usb","z2_power_on_off","z2_volume_down","z2_volume_mute","z2_volume_up","zona2","zoom"
]

# cache para OUTROS (preenchido no primeiro uso)
ButtonTags._OUTROS_CACHE = None

# Export de compatibilidade opcional
BUTTON_TAGS = ButtonTags.BUTTON_TAGS
