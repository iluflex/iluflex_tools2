import customtkinter as ctk
from iluflex_tools.widgets.waveform_canvas import WaveformCanvas
from iluflex_tools.widgets.cards import DropDownCard as dpc
from iluflex_tools.core.ircode import IrCodeLib
from iluflex_tools.widgets.buttontags import ButtonTagsWidget

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
        
        # escuta eventos da conexão para receber dados.
        self.conn.add_listener(self._on_conn_event)

        # --- Controles de zoom/pan (espelhando o learner) ---
        self.x_scale_var = ctk.DoubleVar(value=0.005)  # pixels por tick (1 tick ≈ 1.6 µs)
        self.x_scroll = None
        self.zoom_slider = None

        # comandos de IR guardados do Learner
        self.received_cmd_raw = ""
        self.ir_command_pre_process = ""
        self.ir_command_converterd = ""
        self.ir_command_converted_plot = ""
        self.learner_on = False

        # gera a página
        self._build()

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
        
        # Pause threshold (ms)
        self.pause_treshold_label = ctk.CTkLabel(pre_content, text="Pause (ms)")
        self.pause_treshold_label.grid(row=0, column=0, sticky="w", padx=0, pady=(0, 2))
        self.pause_treshold_entry = ctk.CTkEntry(pre_content, width=60)
        self.pause_treshold_entry.insert(0, "40")
        self.pause_treshold_entry.grid(row=0, column=0, sticky="e", padx=0, pady=(0, 8))

        # Max frames (DEFAULT = 3)
        self.max_frames_label = ctk.CTkLabel(pre_content, text="Max Frames:")
        self.max_frames_label.grid(row=1, column=0, sticky="w", padx=0, pady=(0, 2)        )
        self.max_frames_cbox = ctk.CTkComboBox( pre_content, values=["1","2","3","4"], width=60, command=self._max_frames_change)
        self.max_frames_cbox.grid(row=1, column=0, sticky="e", padx=0, pady=(0, 8))
        self.max_frames_cbox.set("3")

        # Normalizar
        self.normalize_switch_label = ctk.CTkLabel(pre_content, text="Normalizar:")
        self.normalize_switch_label.grid(row=2, column=0, sticky="w", padx=0, pady=(0, 2))
        self.normalize_switch = ctk.CTkSwitch(pre_content, text="", width=60, command=self._process_from_raw)
        self.normalize_switch.select()
        self.normalize_switch.grid(row=2, column=0, sticky="e", padx=0, pady=(0, 8))

        # Botões Pré-processar + Copiar
        self.btn_pre = ctk.CTkButton(pre_content, text="Pré-processar", command=self._process_from_raw)
        self.btn_pre.grid(row=3, column=0, sticky="ew", padx=0, pady=2)

        self.btn_copiar = ctk.CTkButton(pre_content, text="Copiar para Entrada:", command=self._copiar_para_entrada)
        self.btn_copiar.grid(row=4, column=0, sticky="ew", padx=0, pady=2)

        # Bindings
        self.pause_treshold_entry.bind("<FocusOut>", lambda e: self._process_from_raw())
        self.pause_treshold_entry.bind("<Return>", lambda e: self._process_from_raw())
        #self.max_frames_cbox.bind("<<ComboboxSelected>>", lambda e: self._process_from_raw())
        #self.max_frames_cbox.bind("<FocusOut>", lambda e: self._process_from_raw())

        # Card: Conversão (linha 3)
        conv_content = dpc.make_card(leftpanel, "Conversão", 3)
        self.tag_picker = ButtonTagsWidget(conv_content, combo_width=160, cols=3, checkbox_size=14, font_size=12)
        self.tag_picker.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 6))

        self.cmd_repeat_label = ctk.CTkLabel(conv_content, text="Repetições:")
        self.cmd_repeat_label.grid(row=1, column=0, sticky="w", padx=0, pady=(0, 2)        )
        self.cmd_repeat_cbox = ctk.CTkComboBox(conv_content, values=["1", "2", "3", "4"], width=60)
        self.cmd_repeat_cbox.grid(row=1, column=0, sticky="e", padx=0, pady=(0, 8))

        self.btn_conv = ctk.CTkButton(conv_content, text="Converter (sir,3/sir,4)", command=self._convert)
        self.btn_conv.grid(row=2, column=0, sticky="ew", padx=0, pady=(0, 0))

        # Card: Enviar comando (linha 4)
        send_content = dpc.make_card(leftpanel, "Enviar comando", 4)
        self.entry = ctk.CTkEntry(send_content, placeholder_text="Digite o comando a enviar...")
        self.entry.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 8))
        ctk.CTkButton(send_content, text="Enviar", command=self._send).grid(
            row=1, column=0, sticky="ew", padx=0, pady=(0, 0)
        )

        # ========= MAINPANEL: textos e canvas =========
        self.CANVAS_H = 124          # altura fixa do gráfico
        self.CANVAS_CTRL_H = 28      # altura da régua/controles abaixo do gráfico

        mainpanel.grid_columnconfigure(0, weight=1)
        mainpanel.grid_rowconfigure(1, weight=1)  # txt_raw
        mainpanel.grid_rowconfigure(3, weight=1)  # txt_pre
        mainpanel.grid_rowconfigure(4, weight=0, minsize=self.CANVAS_H + self.CANVAS_CTRL_H + 8)
        mainpanel.grid_rowconfigure(6, weight=1)  # txt_out

        # Campo 1: capturado
        ctk.CTkLabel(mainpanel, text="Entrada (capturado sir,2)").grid(row=0, column=0, sticky="w", padx=10, pady=(0, 4))
        self.txt_raw = ctk.CTkTextbox(mainpanel, height=100)
        self.txt_raw.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))
        self.txt_raw.configure(state=ctk.DISABLED)

        # Campo 2: pré-processado
        ctk.CTkLabel(mainpanel, text="Pré-processado").grid(row=2, column=0, sticky="w", padx=10, pady=(0, 4))
        self.txt_pre = ctk.CTkTextbox(mainpanel, height=80)
        self.txt_pre.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 8))

        # Canvas (waveform)
        self.wave_wrap = ctk.CTkFrame(mainpanel)
        self.wave_wrap.grid(row=4, column=0, sticky="nsew", padx=10, pady=4)
        self.wave_wrap.grid_rowconfigure(0, weight=0, minsize=self.CANVAS_H)
        self.wave_wrap.grid_rowconfigure(1, weight=0, minsize=self.CANVAS_CTRL_H)  # linha da régua/scroll
        self.wave_wrap.grid_columnconfigure(0, weight=1)
        # Cria o gráfico dos comandos em forma de osciloscópio.
        self.wave = WaveformCanvas(self.wave_wrap, height=self.CANVAS_H)
        self.wave.grid(row=0, column=0, sticky="ew")
        # zoom inicial definido no init
        self.wave.set_zoom(self.x_scale_var.get())

        # Permite que o Canvas reporte scroll horizontal (para manter o slider de pan sincronizado)
        # self.wave.configure(xscrollcommand=self._on_canvas_xscroll)

        # Barra de controles (Zoom / Pan)
        ctrl = ctk.CTkFrame(self.wave_wrap)
        ctrl.grid(row=1, column=0, sticky="ew", padx=0, pady=(6, 0))
        ctrl.grid_columnconfigure(1, weight=1)  # pan ocupa o espaço

        # Zoom (0.005 .. 0.5 px/tick) – igual ao learner (0.05 default)
        ctk.CTkLabel(ctrl, text="Zoom").grid(row=0, column=0, padx=(6, 6), pady=2, sticky="w")
        self.zoom_slider = ctk.CTkSlider(
            ctrl, from_=0.002, to=0.05, number_of_steps=100, command=self._on_zoom_changed, width=160
        )
        self.zoom_slider.set(self.x_scale_var.get())
        self.zoom_slider.grid(row=0, column=0, padx=(54, 16), pady=2, sticky="w")
        
        # régua/scrollbar horizontal de pan (mostra fração visível)
        self.x_scroll = ctk.CTkScrollbar(ctrl, orientation="horizontal", command=self.wave.xview        )
        self.x_scroll.grid(row=0, column=1, padx=(6, 8), pady=2, sticky="ew")

        # Conecta o Canvas para atualizar o “thumb” da régua automaticamente
        self.wave.configure(xscrollcommand=self.x_scroll.set)


        # Campo 3: saída (sir,3/sir,4)
        ctk.CTkLabel(mainpanel, text="Saída (comandos convertidos sir,3/sir,4)").grid(
            row=5, column=0, sticky="w", padx=10, pady=(10, 4)
        )
        self.txt_out = ctk.CTkTextbox(mainpanel, height=120)
        self.txt_out.grid(row=6, column=0, sticky="nsew", padx=10, pady=(0, 8))
  

        # Para comentários e avisos e resultado de conversões.
        self.status = ctk.CTkLabel(mainpanel, text="", anchor="w")
        self.status.grid(row=7, column=0, sticky="ew", padx=10, pady=(0, 6))

    # --- Ações ---

    def _convert(self):
        src = self.txt_pre.get("1.0", "end").strip() or self.txt_raw.get("1.0", "end").strip()
        sir3 = self.ir.to_sir3(src)
        sir4 = self.ir.to_sir4(src)
        self.txt_out.delete("1.0", "end")
        self.txt_out.insert("1.0", f"[sir,3]\n{sir3}\n\n[sir,4]\n{sir4}\n")
        self.status.configure(text="Conversão concluída.")

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

    def _max_frames_change(self, choice):
        maxf = self.max_frames_cbox.get()
        print(f"max frames changed to {maxf} and choice is {choice}")
        self._process_from_raw()
        

    # ---- eventos da conexão ----
    def _on_conn_event(self, ev: dict):
        # garantir thread-safe
        self.after(0, lambda e=ev: self._handle_ev(e))

    def _handle_ev(self, ev: dict):
        # t = ev.get("ts", "--:--:--.---")
        typ = ev.get("type") # event types: connect, disconnect, tx, rx, error
        buffer = ev.get("text")
        buffer = str(buffer).strip()
        if typ == "rx" and buffer:
            # chegou dados, vamos colocar no campo 'Entrada'
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
            # Processa dados recebidos.
            self._parse_raw_income(buffer)

        
    def _parse_raw_income(self, message: str)-> None:    
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
            self.received_cmd_raw = message
            self._process_from_raw()

    def _process_from_raw(self):
        """Reexecuta o pré-processamento a partir do `raw_sir2_data` usando os parâmetros atuais."""
        print(f"raw = {self.received_cmd_raw}")
        if not self.received_cmd_raw or self.received_cmd_raw == "":
            self.status.configure(text= "Erro: Nenhuma entrada capturada. Use 'Copiar para entrada' ou capture um comando.")
            return
        if not self.received_cmd_raw.startswith("sir,2,"):
            self.status.configure(text= "Erro: dado de entrada não inválido (precisa começar com sir,2...).")
            self.received_cmd_raw = ""
            return
        try:
            pause_threshold_ms = int(self.pause_treshold_entry.get().strip())
            if 1 <= pause_threshold_ms < 80:
                pause_threshold = int(pause_threshold_ms) * 1000 # converte para µs
            else: pause_threshold = 40000
            max_frames = int(self.max_frames_cbox.get()) if self.max_frames_cbox else 3
            normalize = bool(self.normalize_switch.get()) if self.normalize_switch else True

            normalizedCmd = IrCodeLib.preProcessIrCmd(self.received_cmd_raw, pause_threshold, max_frames, normalize)
            
            new_sir2 = normalizedCmd.get("new_sir2", "")
            if new_sir2:
                print("Reproces Pre-Process: Temos new_sir2")
                self.txt_pre.delete("1.0", "end")
                self.txt_pre.insert("1.0", new_sir2)

                # [+] manter variável e atualizar o canvas com auto-zoom
                self.ir_command_pre_process = new_sir2
                #atualizar_grafico()
                
                self.update_preproc_overlay(normalizedCmd)
            else:
                self.status.configure(text="Captura inválida ou falha na conversão", text_color="orange")
        except Exception as e:
            print("Pré-processamento", f"Erro ao reprocessar: {e}", fg="red")
            self.status.configure(text=f"Erro ao reprocessar: {e}", text_color="red")
        finally:
            self._update_waveform()

    # compatível com o mecanismo de mudar tema
    def on_theme_changed(self):
        pass


    def update_preproc_overlay(self, meta: dict | None = None):
        """
        meta: dicionário retornado por ircode.extract_optimized_frame
            chaves usadas: equal_frames_detected, pairs_preserved, new_sir2
        sir2_opt: string 'sir,2,...' otimizada (fallback para calcular duração/pulsos)
        """

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
            self.status.configure(text=f"Falha no processamento dos dados")
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
        self.status.configure(text=f"{text1} \n {text2}")



    def _update_waveform(self):
        """Reflete os três sinais no widget WaveformCanvas."""
        try:
            self.wave.set_commands(
                received=self.received_cmd_raw or "",
                pre=self.ir_command_pre_process or "",
                converted=self.ir_command_converted_plot or "",
            )
        except Exception as e:
            print("update waveform error:", e)




    # ---------------------- ZOOM E PAN ------------------
    # ---- Zoom/Pan (mesmos nomes e papel do learner) ----
    # ----------------------------------------------------
    def _on_zoom_changed(self, val):
        """Atualiza a escala horizontal do WaveformCanvas e preserva a posição de pan."""
        try:
            z = max(0.001, float(val))
        except Exception:
            z = 0.05
        # lembrar a posição atual antes do redraw
        try:
            first, _last = self.wave.xview()
        except Exception:
            first = float(self.pan_var.get() or 0.0)

        self.x_scale_var.set(z)
        self.wave.set_zoom(z)  # isto dispara redraw e recalcula a scrollregion

        # reposiciona o pan na mesma fração após mudar o zoom
        self.wave.xview_moveto(first)

        #--------------- Actions ----------------------


    def _copiar_para_entrada(self):
        """Promove um `sir,2` do editor para a entrada crua (`raw_sir2_data`) e reprocessa.
        - Só aceita `sir,2`. Para `sir,3/4` mostra aviso e não altera a entrada.
        """

        texto = self.txt_pre.get("1.0", "end-1c")  # preservar tal como está; não strip para manter finais se houver
        trimmed = str(texto).strip()
        if not trimmed:
            self.status.configure(text="Erro: copiar para entrada falhou, campo vaziu !", color="#FF0000")
            return
        if not trimmed.startswith("sir,2,"):
            self.status.configure(text= "Erro: Apenas formato Long é aceito aqui (sir,2). Para sir,3/sir,4 use Converter → Iluflex Long.",color="#FF0000")
            return
        # Define a nova entrada crua EXATAMENTE como no editor (não adicionar/criar aqui)
        self.received_cmd_raw = trimmed
        # Atualiza campo de entrada com o comando copiado.
        self.txt_raw.configure(state=ctk.NORMAL)
        self.txt_raw.delete("1.0", ctk.END)
        self.txt_raw.insert("1.0", trimmed + '\n')
        self.txt_raw.configure(state=ctk.DISABLED)

        self._reprocess_from_raw()


