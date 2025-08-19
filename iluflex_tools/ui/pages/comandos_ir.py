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
        self.received_cmd_raw = ""
        self.ir_command_pre_process = ""
        self.ir_command_converterd = ""
        self.learner_on = False
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
        
        self.pagetitle = ctk.CTkLabel(self, text="IR Learner - Captura de comandos de Infra Vermelho (IR)", font=ctk.CTkFont(size=16, weight="bold"))
        self.pagetitle.grid(row=0, column=0, padx=12, pady=6, sticky='w')


        self.grid_rowconfigure(2, weight=1)   # entrada cresce
        self.grid_columnconfigure(0, weight=1)

        # Campo 1: capturado
        ctk.CTkLabel(self, text="Entrada:").grid(row=1, column=0, sticky="w", padx=10, pady=2)
        self.txt_raw = ctk.CTkTextbox(self, height=80)
        self.txt_raw.grid(row=2, column=0, sticky="ew", padx=10)

        # Campo 2: pré-processado
        ctk.CTkLabel(self, text="Pré-processado:").grid(row=3, column=0, sticky="w", padx=10, pady=(10,4))
        self.txt_pre = ctk.CTkTextbox(self, height=80)
        self.txt_pre.grid(row=4, column=0, sticky="ew", padx=10, pady=(0,8))

        # Canvas para gráfico
        self.wave_wrap = ctk.CTkFrame(self)
        self.wave_wrap.grid(row=5, column=0, sticky="nsew", padx=10, pady=4)
        self.grid_rowconfigure(5, weight=1)
        self.wave_wrap.grid_rowconfigure(0, weight=1)
        self.wave_wrap.grid_columnconfigure(0, weight=1)
        self.wave = WaveformCanvas(self.wave_wrap)
        self.wave.grid(row=0, column=0, sticky="nsew")

        # Campo 3: saída (sir,3 + sir,4)
        ctk.CTkLabel(self, text="Saída: (comandos convertidos com button tag)").grid(row=6, column=0, sticky="w", padx=10, pady=(10,4))
        self.txt_out = ctk.CTkTextbox(self, height=100)
        self.txt_out.grid(row=7, column=0, sticky="nsew", padx=10)
        self.grid_rowconfigure(7, weight=1)

        #  opções + botões
        foot = ctk.CTkFrame(self)
        foot.grid(row=8, column=0, sticky="ew", padx=10, pady=(8,10))
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
        self.learner_status_sw = ctk.CTkSwitch(sendcmd_frame, text="Learner Status", command=self._toggle_learner_status)
        self.learner_status_sw.pack(side="left", padx=(0, 8))
        self.entry = ctk.CTkEntry(sendcmd_frame, placeholder_text="Digite o comando a enviar...", width=600)
        self.entry.pack(side="left", padx=(0, 8))
        ctk.CTkButton(sendcmd_frame, text="Enviar", command=self._send).pack(side="left", padx=(0, 8))


    # --- Ações ---
    def _capturar(self):
        # aqui você pode pegar do hardware / socket; por enquanto usa received_cmd_raw
        self.txt_raw.delete("1.0", "end")
        self.txt_raw.insert("1.0", self.received_cmd_raw)
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

    def _toggle_learner_status(self):
        """ Apenas envia o comando e o toggle faz na resposta"""
        try:
            if self.learner_on:
                # Leaner está ligado, manda desligar
                ok = self.conn.send("sir,l,0\r")
            else:
                # Leaner está desligado, manda ligar
                ok = self.conn.send("sir,l,1\r")
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
        typ = ev.get("type") # event types: connect, disconnect, tx, rx, error
        buffer = ev.get("text")
        buffer = str(buffer).strip()
        if typ == "rx" and buffer:
            self.received_cmd_raw = buffer
            self.txt_raw.configure(state=ctk.NORMAL)
            self.txt_raw.insert(ctk.END, buffer + "\n")
            # Mantém apenas as 10 últimas linhas (não altera conteúdo crú)
            lines = self.txt_raw.get("1.0", ctk.END).splitlines()
            if len(lines) > 10:
                lines = lines[-10:]
                self.txt_raw.delete("1.0", ctk.END)
                self.txt_raw.insert(ctk.END, "\n".join(lines) + "\n")
            self.txt_raw.see(ctk.END)
            self.txt_raw.configure(state=ctk.DISABLED)

            self._process_raw_income(buffer)

        
    def _process_raw_income(self, message: str)-> None:    
        """ Recebe mensagens e faz o pre processamento. """
        """
        # estados do learner
        if "RIR,LEARNER,ON" in message:
            self.learner_on = True
            if learner_var is not None:
                learner_var.set(True)
            try:
                learner_switch.set("ON")
            except Exception:
                pass
            status_label.config(text="Modo Learner Ativado", fg="green")
            continue
        if "RIR,LEARNER,OFF" in message:
            learner_on = False
            if learner_var is not None:
                learner_var.set(False)
            try:
                learner_switch.set("OFF")
            except Exception:
                pass
            status_label.config(text="Modo Learner Desativado", fg="black")
            continue

                # comando IR cru capturado
                if message.startswith("sir,2,"):
                    try:
                        # 1) Guarda recebido CRU exatamente como veio
                        raw_sir2_data = message  # NÃO alterar \n aqui
                        # 2) Pré-processa a partir do CRU com parâmetros atuais
                        pause_threshold = int(pause_threshold_var.get().strip())
                        max_frames = int(max_frames_var.get()) if max_frames_var else 3
                        normalize = bool(normalize_var.get()) if normalize_var else True
                        normalizedCmd = ircode.extract_optimized_frame(raw_sir2_data, pause_threshold, max_frames, normalize)
                        sir2_str = normalizedCmd.get("new_sir2", "")
                        # 3) Espelha no editor/var e atualiza gráfico
                        if sir2_str and toConvert_var is not None:
                            toConvert_var.set(sir2_str)
                            if toConvert_text is not None:
                                toConvert_text.delete("1.0", tk.END)
                                toConvert_text.insert("1.0", sir2_str)
                                atualizar_grafico()
                            update_preproc_overlay(normalizedCmd)
                        else:
                            status_label.config(text="Captura inválida ou falha na conversão", fg="orange")
                    except Exception as conv_err:
                        status_label.config(text=f"Erro conversão: {conv_err}", fg="red")
            """

    # compatível com o mecanismo de mudar tema
    def on_theme_changed(self):
        pass
