import customtkinter as ctk
from iluflex_tools.core.services import ConnectionService

class StatusLed(ctk.CTkFrame):
    """Pequeno indicador em forma de LED para status de conexão."""
    def __init__(self, master, conn: ConnectionService | None = None, size: int = 12, **kwargs):
        super().__init__(master, width=size, height=size, **kwargs)
        self._size = size
        self._conn: ConnectionService | None = None
        self._listener = lambda ev: self._on_event(ev)
        self.canvas = ctk.CTkCanvas(self, width=size, height=size, highlightthickness=0)
        self.canvas.pack()
        self._set_color("#666666")
        if conn is not None:
            self.bind_conn(conn)

    def _set_color(self, color: str):
        s = self._size
        self.canvas.delete("all")
        self.canvas.create_oval(1, 1, s - 1, s - 1, fill=color, outline="")

    def _on_event(self, ev: dict):
        typ = ev.get("type")
        if typ == "connect":
            self._set_color("#2ecc71")  # verde
        elif typ == "disconnect":
            self._set_color("#e74c3c")  # vermelho
        elif typ == "error":
            self._set_color("#E622C5")  # laranja
        elif typ in ("connecting", "reconnecting"):
            self._set_color("#f1c40f")  # amarelo

    def bind_conn(self, conn: ConnectionService | None):
        if self._conn is not None:
            try:
                self._conn.remove_listener(self._listener)
            except Exception:
                pass
        self._conn = conn
        if conn is not None:
            try:
                conn.add_listener(self._listener)
                self._set_color("#2ecc71" if conn.connected else "#e74c3c")
            except Exception:
                pass

    def destroy(self):
        try:
            if self._conn is not None:
                self._conn.remove_listener(self._listener)
        except Exception:
            pass
        return super().destroy()
