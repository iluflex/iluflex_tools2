import tkinter as tk
import math
from typing import List, Dict, Optional
import customtkinter as ctk

# Paleta alinhada ao table_tree (cores idênticas por tema)
_THEME_COLORS = {
    "light": {
        "bg": "#7A7A7A", "fg": "#111111",
        "grid_border": "#d0d0d0", "grid_light": "#e6e6e6", "grid_dark": "#c0c0c0",
        "header_bg": "#A8A8A8", "header_hover_bg": "#d9d9d9",
        "row_hover_bg": "#DAEBFF", "odd_bg": "#ffffff", "even_bg": "#E5E2E2",
        "sel_bg": "#3b82f6", "sel_fg": "#ffffff",
    },
    "dark": {
        "bg": "#1f1f1f", "fg": "#eaeaea",
        "grid_border": "#3a3a3a", "grid_light": "#4a4a4a", "grid_dark": "#252525",
        "header_bg": "#2a2a2a", "header_hover_bg": "#323232",
        "row_hover_bg": "#2b3648", "odd_bg": "#232323", "even_bg": "#1b1b1b",
        "sel_bg": "#3b82f6", "sel_fg": "#ffffff",
    },
}

def _palette() -> dict:
    try:
        mode = ctk.get_appearance_mode()
    except Exception:
        mode = "Light"
    key = "dark" if str(mode).lower().startswith("dark") else "light"
    return dict(_THEME_COLORS.get(key, _THEME_COLORS["light"]))


TICKS_PER_MS = 625.0  # 1 ms ≈ 625 ticks (1.6 µs por tick)

def _extract_pulses_from_sir2(sir2_str: str) -> List[int]:
    """
    Extrai a lista de pulsos (em 'ticks' de 1.6 µs) de um comando em formato sir,2.
    Tenta diferentes offsets de início (6 e 8) para tolerar cabeçalhos variantes.
    Retorna [] quando inválido.
    """
    if not sir2_str or not isinstance(sir2_str, str):
        return []
    s = sir2_str.strip()
    if not s.startswith("sir,2,"):
        return []
    body = s[6:]
    parts = [p for p in body.strip().split(",") if p != ""]
    # offsets comuns após o cabeçalho: 6 ou 8
    for start in (6, 8):
        try:
            arr = [int(tok) for tok in parts[start:]]
            # precisa ter pelo menos 2 pulsos (on/off)
            if len(arr) >= 2:
                return arr
        except Exception:
            pass
    return []

def _repeat_pulses(pulses: List[int], rep: int) -> List[int]:
    """Repete a sequência completa de pulsos 'rep' vezes (mantém pausa longa entre frames)."""
    if rep is None or rep <= 1 or not pulses:
        return pulses
    return pulses * int(rep)

def _get_rep_from_cmd(cmd: Optional[str]) -> int:
    """Lê o campo 'Rep' (posição 6) de um comando 'sir,*'. Retorna 1 se não conseguir."""
    try:
        if not cmd or not cmd.startswith("sir,"):
            return 1
        parts = cmd.strip().split(",")
        return int(parts[6]) if len(parts) > 6 else 1
    except Exception:
        return 1

class WaveformCanvas(tk.Canvas):
    """
    Canvas especializado para desenhar até TRÊS trilhas de ondas, a partir de:
      - received_cmd_raw        (sir,2 capturado)
      - ir_command_pre_process  (sir,2 otimizado / pré-processado)
      - ir_command_converted_plot (sir,2 equivalente gerado de uma conversão sir,3/sir,4)

    Uso:
        wf = WaveformCanvas(parent, height=110)
        wf.set_commands(received=..., pre=..., converted=...)
        # ou atualizar separadamente:
        wf.set_received(...); wf.set_preprocessed(...); wf.set_converted(...)

    O eixo X é proporcional aos 'ticks' (1 tick ≈ 1.6 µs).
    """

    def __init__(self, master, **kwargs):
        pal = _palette()
        self._pal = _palette()
        super().__init__(master, bg=pal["bg"], highlightthickness=0, **kwargs)

        self.received_cmd_raw: str = ""
        self.ir_command_pre_process: str = ""
        self.ir_command_converted_plot: str = ""

        # cache de pulsos já extraídos
        self._pulses_received: List[int] = []
        self._pulses_pre: List[int] = []
        self._pulses_conv: List[int] = []

        # fator de escala horizontal: pixels por TICK
        # (no iluflex_learner era ~0.05 padrão; mantenho)
        self._x_scale: float = 0.05

        # redesenha quando o canvas ganha tamanho
        self.bind("<Configure>", lambda e: self.redraw())

    # --------------------------- API pública ---------------------------
        

    def set_zoom(self, px_per_tick: float) -> None:
        """Define a escala horizontal (pixels por 'tick')."""
        try:
            self._x_scale = max(0.001, float(px_per_tick))
        except Exception:
            self._x_scale = 0.05
        self.redraw()

    def set_commands(self, received: Optional[str] = None,
                     pre: Optional[str] = None,
                     converted: Optional[str] = None) -> None:
        """Atualiza quaisquer dos três comandos e redesenha."""
        if received is not None:
            self.received_cmd_raw = received or ""
        if pre is not None:
            self.ir_command_pre_process = pre or ""
        if converted is not None:
            self.ir_command_converted_plot = converted or ""
        self._rebuild_pulse_cache()
        self.redraw()

    def set_received(self, s: Optional[str]) -> None:
        self.received_cmd_raw = s or ""
        self._rebuild_pulse_cache()
        self.redraw()

    def set_preprocessed(self, s: Optional[str]) -> None:
        self.ir_command_pre_process = s or ""
        self._rebuild_pulse_cache()
        self.redraw()

    def set_converted(self, s: Optional[str]) -> None:
        self.ir_command_converted_plot = s or ""
        self._rebuild_pulse_cache()
        self.redraw()

    # ------------------------ Implementação ---------------------------
    def _rebuild_pulse_cache(self) -> None:
        """Extrai e normaliza as três listas de pulsos que serão desenhadas."""
        # capturado (sir,2)
        self._pulses_received = _extract_pulses_from_sir2(self.received_cmd_raw)

        # pré-processado (sir,2)
        self._pulses_pre = _extract_pulses_from_sir2(self.ir_command_pre_process)

        # convertido: já deve ser sir,2 para plot; respeita o 'rep' do header
        self._pulses_conv = _extract_pulses_from_sir2(self.ir_command_converted_plot)
        if self._pulses_conv:
            rep = _get_rep_from_cmd(self.ir_command_converted_plot)
            self._pulses_conv = _repeat_pulses(self._pulses_conv, rep)

    def _draw_single_series(self, pulses: List[int], base_y: int,
                            color: str = "#cccccc") -> None:
        """Desenha uma série do 'osciloscópio' (linhas horizontais com bordas verticais)."""
        if not pulses:
            return
        x = 10.0
        high = base_y - 10
        low = base_y + 10
        is_on = True
        scale = float(self._x_scale)

        for dur in pulses:
            length = max(1.0, float(dur) * scale)  # px
            # borda vertical
            self.create_line(x, low, x, high, fill=color, width=1)
            # segmento horizontal
            y = high if is_on else low
            self.create_line(x, y, x + length, y, fill=color, width=2 if is_on else 1)
            x += length
            is_on = not is_on

    def _draw_time_ruler(self, height: int, left_x: float, right_x: float,
                         base_y: int = 100) -> None:
        """Desenha a régua de tempo (ms) com ticks maiores/menores."""
        total_width = right_x - left_x
        if total_width <= 0:
            return

        px_per_ms = self._x_scale * TICKS_PER_MS  # px por ms
        total_ms = total_width / px_per_ms if px_per_ms > 0 else 0.0

        def _choose_steps(pxms: float) -> tuple[float, float]:
            # devolve (major_ms, minor_ms)
            if pxms >= 80:   return 1.0, 0.5
            if pxms >= 40:   return 2.0, 1.0
            if pxms >= 20:   return 5.0, 1.0
            if pxms >= 10:   return 10.0, 5.0
            return 20.0, 10.0

        major_ms, minor_ms = _choose_steps(px_per_ms)

        # linha base
        self.create_line(left_x, base_y, right_x, base_y, fill="#888", width=1)

        # ticks principais com rótulo
        if major_ms > 0:
            n_major = int(math.floor(total_ms / major_ms)) + 1
            for i in range(n_major + 1):
                ms = i * major_ms
                x = left_x + ms * px_per_ms
                if x > right_x:
                    break
                self.create_line(x, base_y, x, base_y - 6, fill="#777", width=1)
                self.create_text(x, base_y + 2, text=f"{int(ms)}",
                                 anchor="n", font=("TkDefaultFont", 7), fill="#666")

        # ticks menores (sem rótulo), evitando sobrepor majors
        if minor_ms > 0:
            n_minor = int(math.floor(total_ms / minor_ms)) + 1
            for j in range(n_minor + 1):
                ms = j * minor_ms
                # pula se coincide com major
                if abs((ms / major_ms) - round(ms / major_ms)) < 1e-6:
                    continue
                x = left_x + ms * px_per_ms
                if x > right_x:
                    break
                self.create_line(x, base_y, x, base_y - 4, fill="#bbb", width=1)

        # legenda
        self.create_text(left_x, base_y - 12, text="tempo (ms)",
                         anchor="w", font=("TkDefaultFont", 8), fill="#aaa")

    def _on_resize(self):
        #self._pal = _palette()
        try:
            self.configure(bg=self._pal["bg"])
        except Exception:
            pass
        self.redraw()


    def redraw(self) -> None:
        """Redesenha o canvas com as trilhas disponíveis."""
        self.delete("all")

        # monta séries a desenhar (ordem: capturado, otimizado, convertido)
        #pal = self._pal
        series: List[Dict] = []
        if self._pulses_received:
            series.append({"pulses": self._pulses_received, "label": "capturado", "color": self._pal["fg"]})
        if self._pulses_pre:
            series.append({"pulses": self._pulses_pre, "label": "otimizado", "color": self._pal["sel_bg"]})
        if self._pulses_conv:
            series.append({"pulses": self._pulses_conv, "label": "convertido", "color": "#fbbf24"})

        if not series:
            # placeholder
            w = self.winfo_width() or 400
            self.create_text(8, 8, text="Waveform (sem dados)",
                             anchor="nw", fill="#b3b3b3")
            return

        # altura disponível
        h = self.winfo_height() or 110
        self.configure(scrollregion=(0, 0, 0, h))

        # desenha trilhas
        base_top = 22
        row_gap = 28
        for idx, s in enumerate(series):
            base_y = base_top + idx * row_gap
            self._draw_single_series(s["pulses"], base_y=base_y, color=s.get("color", "#cccccc"))

        # régua de tempo no rodapé da última trilha
        right_x = max(20.0, sum(max(s["pulses"], default=0) for s in series)) * float(self._x_scale) + 20.0
        # melhor usar total máximo por série
        max_len_ticks = max((sum(s["pulses"]) for s in series), default=0)
        right_x = max(20.0, max_len_ticks * float(self._x_scale) + 20.0)
        left_x = 10.0
        ruler_y = base_top + (len(series)) * row_gap + 8
        ruler_y = min(ruler_y, h - 6)
        self._draw_time_ruler(h, left_x, right_x, base_y=ruler_y)

        # legenda (nomes)
        labels = ", ".join([s["label"] for s in series])
        self.create_text(8, 8, text=labels, anchor="nw", fill="#c4c4c4")
