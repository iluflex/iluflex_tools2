import customtkinter as ctk
from iluflex_tools.widgets.waveform_canvas import WaveformCanvas
from iluflex_tools.widgets.status_led import StatusLed
from iluflex_tools.widgets.cards import DropDownCard as dpc
from iluflex_tools.core.ircode import IrCodeLib

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
        self.ir_command_converted_plot = ""
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
        # Título
        self.pagetitle = ctk.CTkLabel(
            self,
            text="IR Learner - Captura de comandos de Infra Vermelho (IR)",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self.pagetitle.grid(row=0, column=0, columnspan=2, padx=12, pady=6, sticky="w")

        # Painéis
        leftpanel = ctk.CTkFrame(self)
        leftpanel.grid(row=1, column=0, padx=(10, 6), pady=6, sticky="nsw")

        mainpanel = ctk.CTkFrame(self)
        mainpanel.grid(row=1, column=1, padx=(6, 10), pady=6, sticky="nsew")

        # Expansão do painel direito
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ========= LEFTPANEL (estreito): 1 elemento por linha =========
        leftpanel.grid_columnconfigure(0, weight=1)

        # Switch Learner (linha 0)
        self.learner_status_var = ctk.BooleanVar(value=False)
        self.learner_status_sw = ctk.CTkSwitch(
            leftpanel, text="Modo Learner", command=self._toggle_learner_status,
            variable=self.learner_status_var, onvalue=True, offvalue=False,
        )
        self.learner_status_sw.grid(row=0, column=0, sticky="w", padx=4, pady=(0, 8))

        # Card: Pré-processamento (linha 2)
        pre_content = dpc.make_card(leftpanel, "Pré-processamento", 2)
        # 1 elemento por linha: label em uma, entry na próxima
        ctk.CTkLabel(pre_content, text="Pause (ms)").grid(
            row=0, column=0, sticky="w", padx=0, pady=(0, 2)
        )
        self.pause_treshold_entry = ctk.CTkEntry(pre_content)
        self.pause_treshold_entry.insert(0, "15")
        self.pause_treshold_entry.grid(row=1, column=0, sticky="ew", padx=0, pady=(0, 8))

        ctk.CTkLabel(pre_content, text="Max Frames").grid(
            row=2, column=0, sticky="w", padx=0, pady=(0, 2)
        )
        self.max_frames_entry = ctk.CTkEntry(pre_content)
        self.max_frames_entry.insert(0, "3")
        self.max_frames_entry.grid(row=3, column=0, sticky="ew", padx=0, pady=(0, 8))

        self.normalize_switch = ctk.CTkSwitch(pre_content, text="Normalize")
        self.normalize_switch.select()
        self.normalize_switch.grid(row=4, column=0, sticky="w", padx=0, pady=(0, 8))

        self.btn_pre = ctk.CTkButton(pre_content, text="Pré-processar", command=self._preprocess)
        self.btn_pre.grid(row=5, column=0, sticky="ew", padx=0, pady=2)

        # Botão Copiar para Entrada (linha 6)
        self.btn_capturar = ctk.CTkButton(pre_content, text="Copiar para Entrada:", command=self._capturar)
        self.btn_capturar.grid(row=6, column=0, sticky="ew", padx=0, pady=2)

        # Card: Conversão (linha 3)
        conv_content = dpc.make_card(leftpanel, "Conversão", 3)
        self.btn_conv = ctk.CTkButton(conv_content, text="Converter (sir,3/sir,4)", command=self._convert)
        self.btn_conv.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 0))

        # Card: Enviar comando (linha 4)
        send_content = dpc.make_card(leftpanel, "Enviar comando", 4)
        self.entry = ctk.CTkEntry(send_content, placeholder_text="Digite o comando a enviar...")
        self.entry.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 8))
        ctk.CTkButton(send_content, text="Enviar", command=self._send).grid(
            row=1, column=0, sticky="ew", padx=0, pady=(0, 0)
        )

        # ========= MAINPANEL: textos e canvas =========
        mainpanel.grid_columnconfigure(0, weight=1)
        mainpanel.grid_rowconfigure(1, weight=1)  # txt_raw
        mainpanel.grid_rowconfigure(3, weight=1)  # txt_pre
        mainpanel.grid_rowconfigure(4, weight=2)  # canvas
        mainpanel.grid_rowconfigure(6, weight=1)  # txt_out

        # Campo 1: capturado
        ctk.CTkLabel(mainpanel, text="Entrada (capturado sir,2)").grid(
            row=0, column=0, sticky="w", padx=10, pady=(0, 4)
        )
        self.txt_raw = ctk.CTkTextbox(mainpanel, height=80)
        self.txt_raw.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))
        self.txt_raw.configure(state=ctk.DISABLED)

        # Campo 2: pré-processado
        ctk.CTkLabel(mainpanel, text="Pré-processado").grid(
            row=2, column=0, sticky="w", padx=10, pady=(0, 4)
        )
        self.txt_pre = ctk.CTkTextbox(mainpanel, height=100)
        self.txt_pre.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 8))

        # Canvas (waveform)
        self.wave_wrap = ctk.CTkFrame(mainpanel)
        self.wave_wrap.grid(row=4, column=0, sticky="nsew", padx=10, pady=4)
        self.wave_wrap.grid_rowconfigure(0, weight=1)
        self.wave_wrap.grid_columnconfigure(0, weight=1)
        self.wave = WaveformCanvas(self.wave_wrap)
        self.wave.grid(row=0, column=0, sticky="nsew")

        # Campo 3: saída (sir,3/sir,4)
        ctk.CTkLabel(mainpanel, text="Saída (comandos convertidos sir,3/sir,4)").grid(
            row=5, column=0, sticky="w", padx=10, pady=(10, 4)
        )
        self.txt_out = ctk.CTkTextbox(mainpanel, height=100)
        self.txt_out.grid(row=6, column=0, sticky="nsew", padx=10, pady=(0, 8))
        self.txt_out.configure(state=ctk.DISABLED)

    # --- Ações ---
    def _capturar(self):
        # aqui você pode pegar do hardware / socket; por enquanto usa received_cmd_raw
        self.txt_raw.delete("1.0", "end")
        self.txt_raw.insert("1.0", self.received_cmd_raw)
        self.status.configure(text="Captura copiada.")

    def _preprocess(self):
        try:
            pause = int(self.pause_treshold_entry.get() or 40)
            frames = int(self.max_frames_entry.get() or 1)
            norm = bool(self.normalize_switch.get())
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
        # estados do learner
        if  message.startswith("RIR,LEARNER,ON"):
            self.learner_on = True
            self.learner_status_var.set(True)
        
        elif message.startswith("RIR,LEARNER,OFF"):
            self.learner_on = False
            self.learner_status_var.set(False)
        elif message.startswith("sir,2,"):
            # comando IR cru capturado
            try:
                # 1) Guarda recebido CRU exatamente como veio
                self.received_cmd_raw = message  # NÃO alterar \n aqui
                # 2) Pré-processa a partir do CRU com parâmetros atuais
                pause_threshold_ms = int(self.pause_treshold_entry.get().strip())
                if 1 <= pause_threshold_ms < 80:
                    pause_threshold = int(pause_threshold_ms) * 1000 # converte para µs
                else: pause_threshold = 40
                max_frames = int(self.max_frames_entry.get()) if self.max_frames_entry else 3
                normalize = bool(self.normalize_switch.get()) if self.normalize_switch else True
                normalizedCmd = IrCodeLib.preProcessIrCmd(message, pause_threshold, max_frames, normalize)
                
                sir2_str = normalizedCmd.get("new_sir2", "")
                # 3) Espelha no editor/var e atualiza gráfico
                if sir2_str:
                    print("Pre-Process: Temos sir2")
                    self.txt_pre.delete("1.0", "end")
                    self.txt_pre.insert("1.0", sir2_str)
                    #atualizar_grafico()
                    #update_preproc_overlay(normalizedCmd)
                else:
                    #status_label.config(text="Captura inválida ou falha na conversão", fg="orange")
                    print("Captura inválida ou falha na conversão")
            except Exception as conv_err:
                #status_label.config(text=f"Erro conversão: {conv_err}", fg="red")
                print(f"Erro conversão: {conv_err}")


    # compatível com o mecanismo de mudar tema
    def on_theme_changed(self):
        pass


    def update_preproc_overlay(meta: dict | None = None):
        """
        meta: dicionário retornado por ircode.extract_optimized_frame
            chaves usadas: equal_frames_detected, pairs_preserved, new_sir2
        sir2_opt: string 'sir,2,...' otimizada (fallback para calcular duração/pulsos)
        """
        global pre_process_result_label
        if pre_process_result_label is None:
            return

        iguais = 0
        pares = 0
        sir2 = None

        if meta:
            returned_frames = meta.get("returned_frames", 0)
            equal_frames_detected = meta.get("equal_frames_detected", 0)
            pairs_preserved = meta.get("pairs_preserved", 0) 
            total_frames_received = meta.get("total_frames_received", 0)
            pulses_normalized = meta.get("pulses_normalized", False)
            sir2 = meta.get("new_sir2") or None
        else:
            pre_process_result_label.config(text=f"Falha no processamento dos dados")
            return

        # duração total (soma dos ticks * 1.6 µs)
        dur_str = ""
        if isinstance(sir2, str) and sir2.startswith("sir,2,"):
            try:
                parts = [p.strip() for p in sir2.split(",")]
                ticks = list(map(int, parts[8:]))  # sir,2,<NT>,<Canal>,<Id>,<Per>,<Rep>,<Offset>,<Pulses…>
                dur_ms = (sum(ticks) * 1.6) / 1000.0
                dur_str = f"{dur_ms:.1f} ms"
            except Exception:
                dur_str = ""
        # apresenta resultados        
        if pulses_normalized: 
            pulses_normalized_txt = "sim"
        else:
            pulses_normalized_txt = "não"

        text1 = f"Frames detectados recebidos: {total_frames_received} Frames retornados: {returned_frames}  Frames iguais encontrados: {equal_frames_detected} "
        text2 = f"Pulsos Normalizados: {pulses_normalized_txt}  Pulsos preservados: {pairs_preserved}  Duração: {dur_str}"
        print(f"{text1} {text2}")
        pre_process_result_label.config(text=f"{text1} {text2}")

