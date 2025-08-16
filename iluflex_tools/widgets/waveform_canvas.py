import tkinter as tk

class WaveformCanvas(tk.Canvas):
    def __init__(self, master, **kwargs):
        super().__init__(master, bg="#111111", highlightthickness=0, **kwargs)
        self.pulses = []

    def set_pulses(self, pulses):
        self.pulses = pulses or []
        self.redraw(1.0)

    def redraw(self, zoom_x: float = 1.0):
        self.delete("all")
        if not self.pulses:
            return
        h = self.winfo_height() or 260
        baseline1 = int(h * 0.35)
        baseline2 = int(h * 0.70)
        y_high_1, y_low_1 = baseline1 - 24, baseline1 + 24
        y_high_2, y_low_2 = baseline2 - 24, baseline2 + 24
        scale_x = float(zoom_x) * 0.05
        def draw_line(y_high, y_low):
            x = 20; level_high = True
            for dur in self.pulses:
                dx = max(1, int(dur * scale_x / 100.0))
                self.create_line(x, y_low, x, y_high)
                y = y_high if level_high else y_low
                self.create_line(x, y, x + dx, y)
                x += dx; level_high = not level_high
        draw_line(y_high_1, y_low_1); draw_line(y_high_2, y_low_2)
        self.create_text(8, 8, text="Waveform", anchor="nw", fill="#cccccc")
