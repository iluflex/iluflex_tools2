import customtkinter as ctk
from iluflex_tools.widgets.waveform_canvas import WaveformCanvas
from iluflex_tools.widgets.status_led import StatusLed

class ComandosIRPage(ctk.CTkFrame):
    """
    - Campo 1: Capturado (sir,2)
    - Campo 2: Pré-processado
    - Canvas de waveform
    - Campo 3: Saída (inclui sir,3 e sir,4 juntos)
    - Rodapé: opções + botões (sem popups/overlays)
    """
    def __init__(self, master, ir_service, conn):
        super().__init__(master)
        self.conn = conn
        self.ir = ir_service
        self._last_raw = "sir,2,126,1,1,258,1,1,1888,6163,236,1052,236,408,236,408,236,"
        self._build()
        # escuta eventos da conexão para logar no console
        self.conn.add_listener(self._on_conn_event)

    def destroy(self):
        # remove listener ao sair
        try:
            self.conn.remove_listener(self._on_conn_event)
        except Exception:
            pass
        return super().destroy()

    def _build(self):
        self.grid_rowconfigure(3, weight=1)   # waveform cresce
        self.grid_columnconfigure(0, weight=1)

        # Campo 1: capturado
        ctk.CTkLabel(self, text="Capturado (sir,2)").grid(row=0, column=0, sticky="w", padx=10, pady=(10,4))
        self.txt_raw = ctk.CTkTextbox(self, height=80)
        self.txt_raw.grid(row=1, column=0, sticky="ew", padx=10)
        self.txt_raw.insert("1.0", self._last_raw)

        # Campo 2: pré-processado
        ctk.CTkLabel(self, text="Pré-processado").grid(row=2, column=0, sticky="w", padx=10, pady=(10,4))
        self.txt_pre = ctk.CTkTextbox(self, height=80)
        self.txt_pre.grid(row=3, column=0, sticky="ew", padx=10, pady=(0,8))

        # Canvas entre 2º e 3º campo
        self.wave_wrap = ctk.CTkFrame(self)
        self.wave_wrap.grid(row=4, column=0, sticky="nsew", padx=10, pady=4)
        self.grid_rowconfigure(4, weight=1)
        self.wave_wrap.grid_rowconfigure(0, weight=1)
        self.wave_wrap.grid_columnconfigure(0, weight=1)
        self.wave = WaveformCanvas(self.wave_wrap)
        self.wave.grid(row=0, column=0, sticky="nsew")
        self.wave.set_pulses([500, 500, 2500, 5000, 250, 1100, 250, 400, 250, 400, 250])

        # Campo 3: saída (sir,3 + sir,4)
        ctk.CTkLabel(self, text="Saída (sir,3 e sir,4)").grid(row=5, column=0, sticky="w", padx=10, pady=(10,4))
        self.txt_out = ctk.CTkTextbox(self, height=100)
        self.txt_out.grid(row=6, column=0, sticky="nsew", padx=10)
        self.grid_rowconfigure(6, weight=1)

        #  opções + botões
        foot = ctk.CTkFrame(self)
        foot.grid(row=7, column=0, sticky="ew", padx=10, pady=(8,10))
        foot.grid_columnconfigure(5, weight=1)

        self.normalize = ctk.CTkSwitch(foot, text="Normalize"); self.normalize.select()
        self.pause = ctk.CTkEntry(foot, width=120); self.pause.insert(0, "15000")
        self.frames = ctk.CTkEntry(foot, width=80); self.frames.insert(0, "3")
        ctk.CTkLabel(foot, text="Pause (µs)").grid(row=0, column=0, padx=6)
        self.pause.grid(row=0, column=1)
        ctk.CTkLabel(foot, text="Max Frames").grid(row=0, column=2, padx=(12,6))
        self.frames.grid(row=0, column=3)
        self.normalize.grid(row=0, column=4, padx=(12,6))

        self.btn_capturar = ctk.CTkButton(foot, text="Capturar", command=self._capturar)
        self.btn_pre = ctk.CTkButton(foot, text="Pré-processar", command=self._preprocess)
        self.btn_conv = ctk.CTkButton(foot, text="Converter (sir,3/sir,4)", command=self._convert)
        self.btn_capturar.grid(row=0, column=6, padx=6)
        self.btn_pre.grid(row=0, column=7, padx=6)
        self.btn_conv.grid(row=0, column=8, padx=6)

        # envio de comandos frame
        sendcmd_frame = ctk.CTkFrame(self)
        sendcmd_frame.grid(row=8, column=0, sticky="ew", padx=10, pady=(8,10))
        sendcmd_frame.grid_columnconfigure(5, weight=1)
        self.auto_reconnect = ctk.CTkSwitch(sendcmd_frame, text="Auto reconectar", command=self._toggle_auto_reconnect)
        self.auto_reconnect.pack(side="left", padx=(0, 8))
        self.entry = ctk.CTkEntry(sendcmd_frame, placeholder_text="Digite o comando a enviar...", width=600)
        self.entry.pack(side="left", padx=(0, 8))
        ctk.CTkButton(sendcmd_frame, text="Enviar", command=self._send).pack(side="left", padx=(0, 8))

        status_frame = ctk.CTkFrame(self)
        status_frame.grid(row=9, column=0, sticky="w", padx=10, pady=(0,10))
        self.status_led = StatusLed(status_frame, conn=self.conn)
        self.status_led.pack(side="left", padx=(0,6))
        self.status = ctk.CTkLabel(status_frame, text="")
        self.status.pack(side="left")




    # --- Ações ---
    def _capturar(self):
        # aqui você pode pegar do hardware / socket; por enquanto usa _last_raw
        self.txt_raw.delete("1.0", "end")
        self.txt_raw.insert("1.0", self._last_raw)
        self.status.configure(text="Captura copiada.")

    def _preprocess(self):
        try:
            pause = int(self.pause.get() or 0)
            frames = int(self.frames.get() or 0)
            norm = bool(self.normalize.get())
        except Exception:
            pause, frames, norm = 15000, 3, True
        src = self.txt_raw.get("1.0", "end").strip()
        pre = self.ir.preprocess(src, pause, frames, norm)
        self.txt_pre.delete("1.0", "end")
        self.txt_pre.insert("1.0", pre)
        self.status.configure(text="Pré-processo concluído.")

    def _convert(self):
        src = self.txt_pre.get("1.0", "end").strip() or self.txt_raw.get("1.0", "end").strip()
        sir3 = self.ir.to_sir3(src)
        sir4 = self.ir.to_sir4(src)
        self.txt_out.delete("1.0", "end")
        self.txt_out.insert("1.0", f"[sir,3]\n{sir3}\n\n[sir,4]\n{sir4}\n")
        self.status.configure(text="Conversão concluída.")

    # ---- ações ----
    def _send(self):
        msg = self.entry.get()
        if not msg:
            return
        
        # mantém espaços; só normaliza quebras de linha
        msg = msg.rstrip("\r\n") + "\r"

        ok = self.conn.send(msg)
        print(f">> {repr(msg)}")  # log TX simples
        if not ok:
            self._append("[warn] não conectado; mensagem não enviada.\n")

    def _toggle_auto_reconnect(self):
        try:
            if self.auto_reconnect.get():
                self.conn.auto_reconnect()
            else:
                self.conn.stop_auto_reconnect()
        except Exception:
            pass

    def _clear(self):
        self.status.configure(text="")

    # ---- eventos da conexão ----
    def _on_conn_event(self, ev: dict):
        # garantir thread-safe
        self.after(0, lambda e=ev: self._handle_ev(e))

    def _handle_ev(self, ev: dict):
        t = ev.get("ts", "--:--:--.---")
        typ = ev.get("type")
        if typ == "connect":
            self._append(f"[{t}] CONNECT {ev.get('remote')}\n")
        elif typ == "disconnect":
            self._append(f"[{t}] DISCONNECT\n")
        elif typ == "tx":
            self._append(f"[{t}] TX: {ev.get('text','')}")  # já vem com \n se você mandar
        elif typ == "rx":
            self._append(f"[{t}] RX: {ev.get('text','')}")
        elif typ == "error":
            self._append(f"[{t}] ERROR: {ev.get('text','')}\n")

    def _append(self, text: str):
        print(text)


    # compatível com o mecanismo de mudar tema
    def on_theme_changed(self):
        pass
