import customtkinter as ctk
import threading
from iluflex_tools.widgets.page_title import PageTitle
from iluflex_tools.core.validators import get_safe_int
from iluflex_tools.core.protocols import IPv4Config, IPv4ConfigValidator, build_srf16_sequence
from iluflex_tools.core.protocols.rrf16 import RRF16_6Parser, RRF16_9Parser
from iluflex_tools.core.settings import save_settings

DEBUG = True

class ConfigurarMasterPage(ctk.CTkFrame):

    def __init__(self, master, conn):
        super().__init__(master)
        self.conn = conn
        # listener will be attached when the page is activated
        self._listener_attached = False
        self._mesh_ssid = None
        self._mesh_pass = None

        # Estado do worker de envio/verificação
        self._worker_running = False           # evita 2 workers em paralelo
        self._ack_event = None                 # threading.Event criado por operação
        self._verify_target = None             # dicionário do que vamos conferir no RRF,16,9
        self._pending_summary = ""             # texto curto do que está sendo salvo

        # parsers RRF,16
        self._p16_6 = RRF16_6Parser()
        self._p16_9 = RRF16_9Parser()

        PageTitle(self, "Configurar Master")

        self._build()

    def destroy(self):
        # remove listener ao sair
        try:
            self.conn.remove_listener(self._on_conn_event)
        except Exception:
            pass
        return super().destroy()

    # called by main_app.navigate when the page becomes visible
    def on_page_activated(self):
        if not self._listener_attached:
            self.conn.add_listener(self._on_conn_event)
            self._listener_attached = True
        # MOSTRA/OCULTA o card conforme o estado atual
        self._update_cards_visibility()
        # já pede os dados (se estiver conectado, envia; senão mostra aviso)
        self._request_all()

    # called by main_app.navigate when the page is hidden
    def on_page_deactivated(self):
        if self._listener_attached:
            try:
                self.conn.remove_listener(self._on_conn_event)
            finally:
                self._listener_attached = False

    # compatível com o mecanismo de mudar tema
    def on_theme_changed(self):
        pass



    def _build(self):
        # Layout base da página
        self.grid_columnconfigure(0, weight=1)

        # Cartão principal
        self.card_main = ctk.CTkFrame(self, corner_radius=10)
        self.card_main.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        for col in (0, 1, 2):
            self.card_main.grid_columnconfigure(col, weight=1)

        # Texto introdutório
        ctk.CTkLabel(
            self.card_main,
            text="Configuração de IP da IC. Os dados preenchidos foram lidos da IC conectada.",
            justify="left",
            anchor="w",
            wraplength=820,
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=12, pady=(12, 4))

        ctk.CTkLabel(
            self.card_main,
            text=("Lembre-se: é melhor fixar o IP da IC no roteador via DHCP. "
                "Se houver mudanças na rede, fica mais fácil achar a IC novamente."),
            justify="left",
            anchor="w",
            wraplength=820,
        ).grid(row=1, column=0, columnspan=3, sticky="w", padx=12, pady=(0, 10))

        # Linha DHCP
        ctk.CTkLabel(self.card_main, text="Modo DHCP (marque para obter IP automático via DHCP)", anchor="w")\
            .grid(row=2, column=1, columnspan=2, sticky="w", padx=12, pady=(0, 6))
        self.dhcp_field = ctk.CTkCheckBox(self.card_main, text="", command=self._on_toggle_dhcp)
        self.dhcp_field.grid(row=2, column=0, sticky="e", padx=12, pady=(0, 6))

        # Linha: IP / Gateway / Netmask
        ctk.CTkLabel(self.card_main, text="Endereço IP v4", anchor="w").grid(row=3, column=0, sticky="w", padx=12)
        self.ip_field = ctk.CTkEntry(self.card_main, placeholder_text="192.168.15.51")
        self.ip_field.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 10))

        ctk.CTkLabel(self.card_main, text="Gateway", anchor="w").grid(row=3, column=1, sticky="w", padx=12)
        self.gateway_field = ctk.CTkEntry(self.card_main, placeholder_text="192.168.15.1")
        self.gateway_field.grid(row=4, column=1, sticky="ew", padx=12, pady=(0, 10))

        ctk.CTkLabel(self.card_main, text="Net Mask", anchor="w").grid(row=3, column=2, sticky="w", padx=12)
        self.netmask_field = ctk.CTkEntry(self.card_main, placeholder_text="255.255.255.0")
        self.netmask_field.grid(row=4, column=2, sticky="ew", padx=12, pady=(0, 10))

        # Linha: DNS1 / DNS2
        ctk.CTkLabel(self.card_main, text="DNS 1", anchor="w").grid(row=5, column=0, sticky="w", padx=12)
        self.dns1_field = ctk.CTkEntry(self.card_main, placeholder_text="8.8.8.8")
        self.dns1_field.grid(row=6, column=0, sticky="ew", padx=12, pady=(0, 10))

        ctk.CTkLabel(self.card_main, text="DNS 2", anchor="w").grid(row=5, column=1, sticky="w", padx=12)
        self.dns2_field = ctk.CTkEntry(self.card_main, placeholder_text="8.8.4.4")
        self.dns2_field.grid(row=6, column=1, sticky="ew", padx=12, pady=(0, 10))

        # Espaço para manter a malha de 3 colunas alinhada
        ctk.CTkLabel(self.card_main, text="").grid(row=5, column=2, padx=12)

        # Linha: Hostname / MAC / Canal Mesh
        ctk.CTkLabel(self.card_main, text="Nome da IC na rede (Hostname)", anchor="w")\
            .grid(row=7, column=0, sticky="w", padx=12)
        self.hostname_field = ctk.CTkEntry(self.card_main, placeholder_text="IC-315")
        self.hostname_field.grid(row=8, column=0, sticky="ew", padx=12, pady=(0, 10))

        ctk.CTkLabel(self.card_main, text="Mac Address", anchor="w").grid(row=7, column=1, sticky="w", padx=12)
        self.mac_field = ctk.CTkEntry(self.card_main, placeholder_text="94:e6:86:80:fb:10", state="disabled")
        self.mac_field.grid(row=8, column=1, sticky="ew", padx=12, pady=(0, 10))

        ctk.CTkLabel(self.card_main, text="Canal da Rede Mesh", anchor="w").grid(row=9, column=0, sticky="w", padx=12)
        self.mesh_channel_field = ctk.CTkEntry(self.card_main, placeholder_text="ex.: 20")
        self.mesh_channel_field.grid(row=10, column=0, sticky="ew", padx=12, pady=(0, 10))

        # Linha de botões
        btn_row = ctk.CTkFrame(self.card_main, fg_color="transparent")
        btn_row.grid(row=11, column=0, columnspan=3, sticky="w", padx=12, pady=(4, 12))
        btn_row.grid_columnconfigure(0, weight=0)
        btn_row.grid_columnconfigure(1, weight=0)
        btn_row.grid_columnconfigure(2, weight=1)

        self.btn_save = ctk.CTkButton(btn_row, text="Salvar Configuração e reiniciar a IC:", command=self._apply_save)
        self.btn_save.grid(row=0, column=1, padx=(0, 8))

        self.btn_refresh = ctk.CTkButton(btn_row, text="Atualizar", width=110, command=self._request_all)
        self.btn_refresh.grid(row=0, column=2)

        # Status e avisos
        self.status = ctk.CTkLabel(self.card_main, text="", anchor="w")
        self.status.grid(row=12, column=0, sticky="ew", padx=10, pady=12)

        # Card “conecte primeiro”
        self.card_hint = ctk.CTkFrame(self, corner_radius=10)
        self.card_hint.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        ctk.CTkLabel(
            self.card_hint,
            text="Conecte-se a uma Interface Master para visualizar e editar as configurações.",
            anchor="w", justify="left", wraplength=820
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 12))

        # Estado inicial
        self._on_toggle_dhcp()
        self._update_cards_visibility()


    #-------------------------------------------------
    #       Comandos e ações
    #-------------------------------------------------
   
    def _on_toggle_dhcp(self):
        """Habilita/desabilita campos conforme checkbox DHCP."""
        dyn = bool(self.dhcp_field.get())  # True => DHCP dinâmico
        state = "disabled" if dyn else "normal"
        for w in (self.ip_field, self.gateway_field, self.netmask_field,
                self.dns1_field, self.dns2_field):
            try:
                w.configure(state=state)
            except Exception:
                pass

    def _request_all(self):
        # atualiza o card antes de qualquer coisa
        self._update_cards_visibility()

        if not getattr(self.conn, "get_is_connected", lambda: False)():
            self.status.configure(text="Não conectado. Conecte-se para ler configurações.", text_color="red")
            return

        # envia primeiro o 16,6
        self.conn.send("SRF,15,10\r")

        # agenda o 15,10 após 200 ms para separar as respostas
        self.after(500, lambda: self.conn.send("SRF,16,6\r"))

        self.status.configure(text="Solicitando configurações à interface…")


    def _apply_save(self):
        if not getattr(self.conn, "get_is_connected", lambda: False)():
            self.status.configure(text="Não conectado. Conecte-se para salvar.", text_color="red"); self._update_cards_visibility(); return
        
        cfg = IPv4Config(
            dhcp=bool(self.dhcp_field.get()),
            ip=self.ip_field.get().strip(),
            netmask=self.netmask_field.get().strip(),
            gateway=self.gateway_field.get().strip(),
            dns1=self.dns1_field.get().strip(),
            dns2=self.dns2_field.get().strip(),
            hostname=self.hostname_field.get().strip(),
        )
        ok, err, cfg = IPv4ConfigValidator.validate(cfg)
        if not ok:
            self.status.configure(text=f"Erro: {err}", text_color="red"); return
        try: mesh_channel = get_safe_int(self.mesh_channel_field.get())
        except Exception: mesh_channel = None
        cmds = build_srf16_sequence(cfg, mesh_ssid=self._mesh_ssid, mesh_pass=self._mesh_pass, mesh_channel=mesh_channel)
        self._pending_summary = "; ".join(filter(None, [
            "DHCP=on" if cfg.dhcp else f"IP fixo {cfg.ip}/{cfg.netmask} gw {cfg.gateway}",
            f"DNS1 {cfg.dns1}" if cfg.dns1 else "",
            f"DNS2 {cfg.dns2}" if cfg.dns2 else "",
            f"host {cfg.hostname}" if cfg.hostname else "",
            f"mesh canal {mesh_channel}" if mesh_channel else "",
        ]))
        if self._worker_running:
            self.status.configure(text="Já existe um salvamento em andamento… aguarde."); return
        self._verify_target = ({k: getattr(cfg, k) for k in ("ip","netmask","gateway","dns1","dns2","hostname") if getattr(cfg, k)} | {"dhcp": "0" if cfg.dhcp else "1"})
        self._ack_event = threading.Event(); self._worker_running = True
        self.status.configure(text=f"Salvando configurações… {self._pending_summary}")
        threading.Thread(target=self._send_worker, args=(cmds,), daemon=True).start()

    def _send_worker(self, commands: list[str]):
        import time
        min_gap = 0.22
        timeout = 3.0
        last_ts = 0.0
        try:
            for raw in commands:
                dt = time.monotonic() - last_ts
                if dt < min_gap:
                    time.sleep(min_gap - dt)
                cmd = raw.rstrip("\r\n") + "\r"
                if DEBUG: print(f"[CONFIG_MASTER] TX -> {cmd!r}")
                ok = self.conn.send(cmd)
                last_ts = time.monotonic()
                if not ok:
                    self.after(0, lambda: self.status.configure(text="Falha ao enviar. Verifique a conexão.", text_color="red"))
                    break
                if self._ack_event:
                    got = self._ack_event.wait(timeout)
                    self._ack_event.clear()
                    if not got and DEBUG:
                        print("[CONFIG_MASTER] timeout aguardando RRF para", raw)
            # terminou a fila
            self.after(0, lambda: self.status.configure(text="Comandos enviados. Aguardando verificação (16,9)…"))
        finally:
            self._worker_running = False



    def _update_cards_visibility(self):
        """Mostra o card correto conforme estado da conexão."""
        connected = False
        try:
            connected = bool(self.conn.get_is_connected())
        except Exception:
            connected = False
        if connected:
            self.card_hint.grid_remove()
            self.card_main.grid()
        else:
            self.card_main.grid_remove()
            self.card_hint.grid()


    #-------------------------------------------------
    #       EVENTOS DE CONEXÃO
    #-------------------------------------------------
   
    def _on_conn_event(self, ev: dict):
        # garantir thread-safe
        self.after(0, lambda e=ev: self._handle_ev(e))

    def _handle_ev(self, ev: dict):
        typ = ev.get("type")  # connect, disconnect, tx, rx, error
        buffer = str(ev.get("text") or "").strip()

        if typ in ("connect", "disconnect"):
            self._update_cards_visibility()
            if typ == "connect":
                self.after(200, self._request_all)
            return

        if typ == "rx" and buffer:
            if buffer.startswith("RRF,15") or buffer.startswith("RRF,16"):
                self._parse_SRF_income(buffer)


    def _send(self):
        msg = self.send_cmd_entry.get()
        if not msg:
            return
        
        # mantém espaços; só normaliza quebras de linha
        msgr = msg.rstrip("\r\n") + "\r"

        if self.conn.send(msgr):
            # comando enviado com sucesso
            self.status.configure(text=f"Enviado: {msg}", text_color=ctk.ThemeManager.theme["CTkLabel"]["text_color"])
            if DEBUG: print(f">> {repr(msg)}")  # log TX simples
        else:
            self.status.configure(text= "Erro no envio, tente conectar primeiro.", text_color="red")
                 

    def _parse_SRF_income(self, message: str) -> None:
        if DEBUG: print(f"[CONFIG_MASTER] RX: {message}")

        # ACK para o worker (RRF,15/16 liberam próximo envio)
        if (message.startswith("RRF,15,") or message.startswith("RRF,16,")) and self._ack_event is not None:
            try: self._ack_event.set()
            except Exception: pass

        # 16,6 => estado atual de rede
        if self._p16_6.match(message):
            snap = self._p16_6.parse(message)
            if not snap: return
            self.ip_field.delete(0,"end");      self.ip_field.insert(0, snap.ip)
            self.netmask_field.delete(0,"end"); self.netmask_field.insert(0, snap.netmask)
            self.gateway_field.delete(0,"end"); self.gateway_field.insert(0, snap.gateway)
            self.dns1_field.delete(0,"end");    self.dns1_field.insert(0, snap.dns1)
            self.dns2_field.delete(0,"end");    self.dns2_field.insert(0, snap.dns2)
            self.mac_field.configure(state="normal")
            self.mac_field.delete(0,"end");     self.mac_field.insert(0, snap.mac)
            self.mac_field.configure(state="disabled")
            self.dhcp_field.select() if snap.dhcp_flag == "0" else self.dhcp_field.deselect()
            self._on_toggle_dhcp()
            self.hostname_field.delete(0,"end"); self.hostname_field.insert(0, snap.hostname)
            self.status.configure(text="Dados de rede carregados.")
            return

        # 16,9 => preview próximo boot (confere e reinicia)
        if self._p16_9.match(message) and self._verify_target:
            snap = self._p16_9.parse(message)
            if snap:
                got = {"ip":snap.ip,"netmask":snap.netmask,"gateway":snap.gateway,
                    "dns1":snap.dns1,"dns2":snap.dns2,"dhcp":snap.dhcp_flag,"hostname":snap.hostname}
                ok = all(str(got.get(k,"")) == str(v) for k,v in self._verify_target.items() if v not in (None,""))
                if ok:
                    summary = self._pending_summary or "configurações"
                    self.status.configure(text=f"Configurações salvas: {summary}. Reiniciando a master…")
                    self.conn.send("SRF,16,8\r")
                    # a master vai reiniciar em breve.
                    self.conn.enable_auto_reconnect(True)


                else:
                    self.status.configure(text="Aviso: 16,9 diferente do solicitado. Confira IP/DHCP/Host.", text_color="red")
            self._verify_target = None
            return

        # 15,10 => dados da mesh
        if message.startswith("RRF,15,10,"):
            parts = [p.strip() for p in message.split(",")]
            if len(parts) >= 6:
                canal, ssid, senha = parts[3:6]
                self.mesh_channel_field.delete(0,"end"); self.mesh_channel_field.insert(0, canal)
                self._mesh_ssid, self._mesh_pass = ssid, senha
                self.status.configure(text="Configuração da rede Mesh carregada.")
            return



""" protocolo comandos iluflex para configuração da master 



5.9	COMANDOS PARA CADASTRAMENTO DE REDE MESH (OPCODE 15)
Na rede 485, o payload de todos comandos com opcode >= 10 é em ascii.
5.9.1	Configuração da Interface Master (Root) (opcode 15,0)
O comando configura a rede mesh privada da interface master. A master utiliza essas informações para configurar as interfaces slaves que forem cadastradas na rede mesh da master usando Opcode 15,10.
Comando: SRF,15,0,0,<SSID>,<senha>,<canalWiFi><cr>
Respsta: RRF,15,0,<canalWiFi><cr>

5.9.2	Descoberta de Módulos Slave Novos (opcode 15,1)
O comando coloca todos os módulos slave da rede mesh e a master para se comunicarem na rede mesh pública por determinado período de tempo. Esse tempo é definido em segundos.
Comando: SRF,15,1,<tempo><cr>
Respsta: RRF,15,1,<tempo><cr>
O tempo pode ser entre 1 e 255 segundos. O tempo ideal é entre 15 e 60 segundos.
Esse comando é enviado da master (root) para todos os módulos da rede mesh e rede 485.
O módulo slave novo, que não está cadastrado, responde com seu status complete usando opcode 10.



5.9.3	Recadastro de Módulo da rede mesh (opcode 15,3)
Este comando só é válido na rede mesh. O módulo da rede mesh irá aceitar o comando sem precisar confirmar, pois ele já estava cadastrado em uma rede mesh. Serve para permitir mudar a master da rede mesh do módulo, ou mudar o módulo de uma rede mesh para outra. 
Comando: SRF,15,3,<macAddress>,<slaveID>,<nome>,<SSID>,<senha>,<canal><cr>
Respsta: RRF,15,3,<nome><cr>
•	MacAddress destino do slave que será cadastrado ou atualizado
•	Slave ID único
•	SSID da rede Mesh privada;
•	Senha da rede Mesh privada;
•	Canal do WiFi da rede mesh privada
•	Nome do módulo, para facilitar identificação (somente a-zA-Z0-9_-)
Na rede mesh, a master recebe esse comando e envia como recebeu. 


5.9.4	Cadastramento ou Atualização de Módulo Slave (opcode 15,5)
Este comando é válido tanto na rede mesh quanto na rede 485 para efetivamente cadastrar novos módulos na rede mesh e na rede 485. O módulo da rede mesh irá entrar em modo de confirmação, que é aguardar alguma tecla ser pressionada. Somente após concluir a confirmação a resposta é enviada. Se a tecla não for pressionada dentro de 30 segundos, o módulo não salva as novas configurações e volta para modo stand-alone. Durante este período piscar led de status e backlight para facilitar a localização do módulo.
Na rede 485 não precisa confirmar com pressionar com uma tecla, pois como é uma rede cabeada, já existe uma camada de comunicação segura para os módulos.
Esse comando é aceito tanto para módulos novos quanto para módulos já cadastrados, permitindo alterar parâmetros gravados. Mesmo no recadastro na rede mesh, precisa confirmar novamente para aceitar a programação.
Comando: SRF,15,5,<macAddress>,<slaveID>,<nome><cr>
Respsta: RRF,15,5,1<cr>
•	MacAddress destino do slave que será cadastrado ou atualizado
•	Slave ID único
•	SSID da rede Mesh privada;
•	Senha da rede Mesh privada;
•	Canal do WiFi da rede mesh privada
•	Nome do módulo, para facilitar identificação (somente a-zA-Z0-9_-)
Módulos Slave novos, aceitam todos parâmetros. 
Módulos da rede 485 utilizam somente os 3 primeiros parâmetros e nome.

Na rede mesh, a master recebe esse comando e acrescenta seus dados para o slave saber o SSID, senha e canal da rede mesh. O comando completo enviado para os módulos da rede mesh é:

Para os módulos da rede mesh, envia comando com dados da rede mesh.
Comando: SRF,15,5,<macAddress>,<slaveID>,<nome>,<SSID>,<senha>,<canal><cr>
5.9.5	Localizar Módulo informando slave_id (opcode 15,7)
O comando para identificar ou localizar módulo slave da rede. Irá piscar teclado, no caso de touch ou piscar led de status. O comando informa número de slave do módulo.
Comando: SRF,15,7,<slave_id><cr>
Respsta: RRF,15,7,<cr>

5.9.6	Localizar Módulo informando Mac Address  (opcode 15,8)
O comando para identificar ou localizar módulo slave da rede. Irá piscar teclado, no caso de touch ou piscar led de status. O comando informa Mac Address do módulo.
Comando: SRF,15,8,<Mac Address><cr>
Respsta: RRF,15,8,<slave>,1<cr>

5.9.7	Força reinicialização em 2 segundos (opcode 15,9)
O comando programa slave para reiniciar em 2 segundos. É útil para antecipar volta dos módulos para rede privada
Comando: SRF,15,9<cr>
Respsta: RRF,15,9,1<cr> quando está na rede pública, avisa os slaves e reinicia em 2 segundos.
Respsta: RRF,15,9,0<cr> quando já está na rede privada, não avisa slaves.



5.9.8	Ler Configuração da Interface Master (Root) (opcode 15,10)
O comando para ler os parâmetros da master, evitando de ter que desmontar o produto e ligar o gravador.
Comando: SRF,15,10<cr>
Respsta: RRF,15,10,<canalWiFi>,<SSID>,<senha><cr>



5.10	COMANDOS PARA CONFIGURAÇÃO DE IP (OPCODE 16)

5.10.1	Envio do IP Fixo Slave (opcode 16,0)

Comando: 	SRF,16,0,<IP><cr>
Resposta  OK:     RRF,16,0,<IP><cr> 
Resposta ERRO : RRF,16,0,0<cr>

5.10.2	Envio do IP do GateWay Padrão (opcode 16,1)

Comando: 	SRF,16,1,<defaul_gateway><cr>
Resposta  OK:     RRF,16,1,< defaul_gateway ><cr> 
Resposta ERRO : RRF,16,1,0<cr>

5.10.3	Envio da Máscara de Rede (opcode 16,2)

Comando: 	SRF,16,2,< netmask><cr>
Resposta  OK:     RRF,16,2,< netmask><cr> 
Resposta ERRO : RRF,16,2,0<cr>

5.10.4	Envio do IP DNS1 (opcode 16,3)

Comando: 	SRF,16,3,< dns1><cr>
Resposta  OK:     RRF,16,3,< dns1><cr> 
Resposta ERRO : RRF,16,3,0<cr>
5.10.5	Envio do IP DNS2 (opcode 16,4)

Comando: 	SRF,16,4,< dns2><cr>
Resposta  OK:     RRF,16,4,< dns2><cr> 
Resposta ERRO : RRF,16,4,0<cr>
5.10.6	Fixar IP Fixo (opcode 16,5)

DHCP = 0 (IP DINAMICO) 
DHCP = 1 (IP FIXO) 
Comando: 	SRF,16,5,< DHCP><cr>
Resposta  OK:     RRF,16,5,< DHCP><cr> 
Resposta ERRO : RRF,16,5,0<cr>

5.10.7	Solicitar dados da Rede (opcode 16,6)

Comando: 	SRF,16,6<cr>
Resposta OK:   RRF,16,6,{IP},{NETMASK},{GATEWAY},{DNS1},{DNS2},{MAC},{DHCP},{NAME_HOST}<cr> 
Resposta ERRO : RRF,16,6,0<cr>

5.10.8	Troca Nome Host (opcode 16,7)

Comando: 		SRF,16,7,{Host}<cr>
Resposta OK:   		RRF,16,7,{Host}cr> 
Resposta ERRO : 	RRF,16,7,0<cr>
5.10.9	Restart o Dispositivo (opcode 16,8)

Comando: 		SRF,16,8<cr>
Resposta OK:   		RRF,16,8,1<cr> 
Resposta ERRO : 	RRF,16,8,0<cr>

5.10.10	Solicitar dados da Rede Configurado para IP Fixo (opcode 16,9)

Comando: 	SRF,16,9<cr>
Resposta OK:   RRF,16,9,{IP},{NETMASK},{GATEWAY},{DNS1},{DNS2},{MAC},{DHCP},{NAME_HOST}<cr> 
Resposta ERRO : RRF,16,9,0<cr>



"""