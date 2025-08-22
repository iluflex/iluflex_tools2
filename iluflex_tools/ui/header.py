import customtkinter as ctk
from iluflex_tools.widgets.status_led import StatusLed

class Header(ctk.CTkFrame):
    def __init__(self, master, conn, on_toggle_collapse=None):
        super().__init__(master, corner_radius=0, fg_color=("gray85","gray14"))
        self.conn = conn
        self._listener = lambda ev: self._on_conn_event(ev)

        self.toggle_collapse = on_toggle_collapse
        self._build()
        # assina eventos de conexão
        try:
            self.conn.add_listener(self._listener)
        except Exception as e:
            print("Header Error", e )
            pass


    def _build(self):

        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0)

        self.toggle_btn = ctk.CTkButton(self, text="≡", width=36, command=self.toggle_collapse)
        self.toggle_btn.grid(row=0, column=0, padx=8, pady=6)

        self.title = ctk.CTkLabel(self, text="iluflex Tools - v 2.0", font=ctk.CTkFont(size=18, weight="bold"))
        self.title.grid(row=0, column=1, sticky="w")

        # self.status_led = ctk.CTkLabel(self, text="●", font=ctk.CTkFont(size=20))
        self.status_led = StatusLed(self, conn=self.conn, size=24)
        self.status_led.grid(row=0, column=2, padx=(0,6))
        self.status_text = ctk.CTkLabel(self, text="Desconectado")
        self.status_text.grid(row=0, column=3, padx=(0,12), pady = 8)

    # ---- eventos da conexão ----
    def _on_conn_event(self, ev: dict):
        print(f"[HEADER] Connect event => {ev}")
        typ = ev.get("type")
        ip, port = ev.get("remote", ("", 0))
        if typ == "connect":
            self.status_text.configure(text=f"Conectado a {ip}:{port}")

        elif typ == "reconnecting":
            self.status_text.configure(text=f"Reconectando... {ip}:{port}")

        elif typ == 'connecting':
            self.status_text.configure(text=f"Conectando... {ip}:{port}")

        elif typ == "disconnect":
            # mantém info do último remoto, útil para o usuário
            suffix = f" {ip}:{port}" if ip else ""
            self.status_text.configure(text=f"Desconectado")
        elif typ == "error":
            self.status_text.configure(text=f"Erro: {ev.get("text")}")
        else:
            print(f"[HEADER] Connect event desconhecido => {typ}")

    def destroy(self):
        try:
            self.conn.remove_listener(self._listener)
        except Exception:
            pass