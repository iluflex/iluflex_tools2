import customtkinter as ctk
from iluflex_tools.core.services import ConnectionService



class StatusLed(ctk.CTkFrame):
    """Indicador de status de conexão com fundo transparente usando um label "●".
    `size` controla o tamanho da fonte do ponto.
    """
    def __init__(self, master, conn: ConnectionService | None = None, size: int = 12, **kwargs):
        # fundo transparente por padrão
        fg = kwargs.pop("fg_color", "transparent")
        super().__init__(master, fg_color=fg, **kwargs)
        self._size = int(size)
        self._conn: ConnectionService | None = None
        self._listener = lambda ev: self._on_event(ev)
        # usa label com ponto para herdar transparência do CTk
        self._font = ctk.CTkFont(size=self._size)
        self._lbl = ctk.CTkLabel(self, text="●", font=self._font, text_color="#666666", fg_color="transparent")
        self._lbl.pack(padx=0, pady=0)
        if conn is not None:
            self.bind_conn(conn)

    def _set_color(self, color: str):
        self._lbl.configure(text_color=color)


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
