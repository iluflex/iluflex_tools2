# waveform_canvas.py
import tkinter as tk
import math
from typing import List, Dict, Optional
import customtkinter as ctk

# --------------------------------------------------------------------
# Paleta alinhada ao table_tree (mantém line1/line2/line3 e contraste)
# --------------------------------------------------------------------
_THEME_COLORS = {
    "light": {
        "bg":   "#D9D9D9",
        "fg":   "#111111",
        "text": "#494949",
        "line1": "#1F7605",   # capturado
        "line2": "#16499D",   # otimizado
        "line3": "#6C0259",   # convertido
        "sel_bg": "#3b82f6",
        "sel_fg": "#ffffff",
    },
    "dark": {
        "bg":   "#4A4A4A",
        "fg":   "#eaeaea",
        "text": "#C8C8C8",
        "line1": "#4BD022",
        "line2": "#8AD0FF",
        "line3": "#D025B1",
        "sel_bg": "#3b82f6",
        "sel_fg": "#ffffff",
    },
}

def _palette() -> dict:
    try:
        mode = ctk.get_appearance_mode()
    except Exception:
        mode = "Light"
    key = "dark" if str(mode).lower().startswith("dark") else "light"
    return dict(_THEME_COLORS.get(key, _THEME_COLORS["light"]))

# Conversão de ticks x tempo (fidelidade com o learner)
TICKS_PER_MS = 625.0  # 1 ms ≈ 625 ticks (1.6 µs por tick)

# --------------------------------------------------------------------
# Funções com MESMOS NOMES do learner (para comparação 1:1)
# --------------------------------------------------------------------
def extract_pulses_from_sir2(sir2_str: str) -> List[int]:
    """
    Extrai lista de pulsos (tempos) de um comando sir,2.
    Tenta índices de início diferentes (6 e 8) para tolerar variações de cabeçalho.
    Retorna [] quando não for possível.
    """
    if not sir2_str or not sir2_str.startswith("sir,2,"):
        return []
    body = sir2_str[6:]  # remove 'sir,2,'
    parts = [p for p in body.strip().split(',') if p != ""]

    candidates: List[List[int]] = []
    for start in (6, 8):
        try:
            pulses = [int(tok) for tok in parts[start:]]
            if pulses:
                candidates.append(pulses)
        except Exception:
            pass
    if candidates:
        # escolhe o que tiver mais dados
        return max(candidates, key=len)

    # última tentativa: tentar converter tudo em int e usar a partir de 6
    try:
        ints = [int(tok) for tok in parts]
        return ints[6:] if len(ints) > 6 else []
    except Exception:
        return []

def repeat_pulses(pulses: List[int], rep: int) -> List[int]:
    """Repete a sequência completa de pulsos 'rep' vezes (mantém pausa longa entre frames)."""
    if rep is None or rep <= 1 or not pulses:
        return pulses
    return pulses * int(rep)

def get_rep_from_cmd(cmd: Optional[str]) -> int:
    """Lê o campo 'Rep' (posição 6) de um comando 'sir,*'. Retorna 1 se não conseguir."""
    try:
        if not cmd or not cmd.startswith("sir,"):
            return 1
        parts = cmd.strip().split(",")
        return int(parts[6]) if len(parts) > 6 else 1
    except Exception:
        return 1

def draw_waveform_overlay(canvas: tk.Canvas, series: List[Dict], height: int, x_scale: float):
    """Desenha múltiplas trilhas no canvas (fiel ao learner).
    series: lista de dicts { 'pulses': list[int], 'label': str, 'color': str }
    """
    if canvas is None:
        return

    canvas.delete("all")
    valid_series = [s for s in series if s.get('pulses')]
    if not valid_series:
        return

    # comprimento total (para scroll)
    lengths = [sum(s['pulses']) for s in valid_series]
    if not lengths:
        return

    max_len = max(lengths)
    content_width = max_len * x_scale + 20
    canvas.config(scrollregion=(0, 0, content_width, height))

    # Desenha trilhas (osciloscópio)
    def draw_oscilloscope(pulses: List[int], base_y: int, color: str):
        x = 10.0
        high = base_y - 10
        low  = base_y + 10
        is_on = True
        for duration in pulses:
            length = duration * x_scale
            if is_on:
                # vertical + horizontal em "alto" com espessura 2 (como no learner)
                canvas.create_line(x, low, x, high, fill=color, width=2)
                canvas.create_line(x, high, x + length, high, fill=color, width=2)
                canvas.create_line(x + length, high, x + length, low, fill=color, width=2)
            else:
                # trilha baixa mais fina (width=1)
                canvas.create_line(x, low, x + length, low, fill=color, width=1)
            x += length
            is_on = not is_on

    base = 22
    gap  = 28
    for idx, s in enumerate(valid_series):
        draw_oscilloscope(s['pulses'], base_y=base + idx * gap, color=s.get('color', 'black'))

    # ---------------- Régua de tempo (ms) no rodapé -------------------
    def _choose_steps(px_per_ms: float) -> tuple[float, float]:
        # devolve (major_ms, minor_ms)
        if px_per_ms >= 80:  return 1.0, 0.5
        if px_per_ms >= 40:  return 2.0, 1.0
        if px_per_ms >= 20:  return 5.0, 1.0
        if px_per_ms >= 10:  return 10.0, 5.0
        return 20.0, 10.0

    # total em ticks e ms
    max_len_ticks = max_len
    total_ms = max_len_ticks / TICKS_PER_MS
    px_per_ms = x_scale * TICKS_PER_MS

    base_y = height - 15
    left_x = 10.0
    right_x = 10.0 + max_len_ticks * x_scale

    # linha base da régua (colada embaixo)
    canvas.create_line(left_x, base_y, right_x, base_y, fill="#888", width=1)

    major_ms, minor_ms = _choose_steps(px_per_ms)

    # "0 ms"
    canvas.create_text(left_x, base_y + 2, text="0",   anchor="n",
                       font=("TkDefaultFont", 9), fill="#666")
    canvas.create_text(left_x + 14, base_y + 2, text="ms", anchor="n",
                       font=("TkDefaultFont", 9), fill="#666")

    # major ticks + labels
    n_major = int(math.floor(total_ms / major_ms)) + 1 if major_ms > 0 else 0
    for k in range(1, n_major + 1):
        ms = k * major_ms
        x = left_x + ms * px_per_ms
        if x > right_x:
            break
        canvas.create_line(x, base_y, x, base_y - 6, fill="#777", width=1)
        canvas.create_text(x, base_y + 2, text=f"{int(ms)}", anchor="n",
                           font=("TkDefaultFont", 9), fill="#666")

    # minor ticks (sem rótulo; pula se coincide com major)
    if minor_ms > 0:
        n_minor = int(math.floor(total_ms / minor_ms)) + 1
        for j in range(n_minor + 1):
            ms = j * minor_ms
            if abs((ms / major_ms) - round(ms / major_ms)) < 1e-6:
                continue
            x = left_x + ms * px_per_ms
            if x > right_x:
                break
            canvas.create_line(x, base_y, x, base_y - 4, fill="#bbb", width=1)

# --------------------------------------------------------------------
# Widget: prepara as séries e chama draw_waveform_overlay (learner-like)
# --------------------------------------------------------------------
class WaveformCanvas(tk.Canvas):
    """
    Canvas especializado para até TRÊS trilhas de ondas, a partir de:
      - received_cmd_raw            (sir,2 capturado)
      - ir_command_pre_process      (sir,2 otimizado / pré-processado)
      - ir_command_converted_plot   (sir,2 equivalente de conversão sir,3/sir,4)

    Uso:
        wf = WaveformCanvas(parent, height=110)
        wf.set_commands(received=..., pre=..., converted=...)
        # ou:
        wf.set_received(...); wf.set_preprocessed(...); wf.set_converted(...)

    O eixo X usa pixels por TICK (1 tick ≈ 1.6 µs). Padrão = 0.05 (igual ao learner).
    """
    def __init__(self, master, **kwargs):
        pal = _palette()
        self._pal = pal
        super().__init__(master, bg=pal["bg"], highlightthickness=0, **kwargs)

        # strings fonte
        self.received_cmd_raw: str = ""
        self.ir_command_pre_process: str = ""
        self.ir_command_converted_plot: str = ""

        # caches
        self._pulses_received: List[int] = []
        self._pulses_pre: List[int] = []
        self._pulses_conv: List[int] = []

        # escala horizontal (px por TICK)
        self._x_scale: float = 0.05

        # redraw ao redimensionar
        self.bind("<Configure>", lambda e: self.redraw())

    # -------- API pública ------------------------------------------------
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

    # -------- Implementação ---------------------------------------------
    def _rebuild_pulse_cache(self) -> None:
        """Extrai/atualiza as três listas de pulsos para desenho."""
        self._pulses_received = extract_pulses_from_sir2(self.received_cmd_raw)
        self._pulses_pre      = extract_pulses_from_sir2(self.ir_command_pre_process)

        self._pulses_conv = extract_pulses_from_sir2(self.ir_command_converted_plot)
        if self._pulses_conv:
            rep = get_rep_from_cmd(self.ir_command_converted_plot)
            self._pulses_conv = repeat_pulses(self._pulses_conv, rep)

    def redraw(self) -> None:
        """Redesenha o canvas com as trilhas disponíveis (usa draw_waveform_overlay)."""
        # monta séries (ordem: capturado, otimizado, convertido)
        series: List[Dict] = []
        if self._pulses_received:
            series.append({"pulses": self._pulses_received, "label": "capturado", "color": self._pal["line1"]})
        if self._pulses_pre:
            series.append({"pulses": self._pulses_pre, "label": "otimizado", "color": self._pal["line2"]})
        if self._pulses_conv:
            series.append({"pulses": self._pulses_conv, "label": "convertido", "color": self._pal["line3"]})

        if not series:
            self.delete("all")
            self.create_text(8, 8, text="Waveform (sem dados)", anchor="nw", fill=self._pal["text"])
            return

        h = self.winfo_height() or 110
        draw_waveform_overlay(self, series=series, height=h, x_scale=float(self._x_scale))
