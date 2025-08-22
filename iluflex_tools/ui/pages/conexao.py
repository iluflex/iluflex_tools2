import threading
import customtkinter as ctk
from iluflex_tools.widgets.table_tree import ColumnToggleTree
from iluflex_tools.core.services import ConnectionService
from iluflex_tools.widgets.status_led import StatusLed
from iluflex_tools.widgets.page_title import PageTitle
from iluflex_tools.core.validators import get_safe_int

DEBUG = True

TABLE_FONT_SIZE = 12

class ConexaoPage(ctk.CTkFrame):
    def __init__(
        self,
        master,
        get_state,
        scan_func=None,
        get_discovery_timeout=None,
        conn: ConnectionService | None = None,
    ):
        super().__init__(master)
        self.get_state = get_state
        self.scan_func = scan_func or (lambda timeout_ms: [])
        self.get_discovery_timeout = get_discovery_timeout or (lambda: 2000)
        self._scan_thread = None
        self._conn = conn
        self._build()

    def _build(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(3, weight=1)

        PageTitle(self, "Conexão de Rede", columnspan=3)

        conn_frame = ctk.CTkFrame(self)
        conn_frame.grid(row=1, column=0, columnspan=3, padx = 6, pady=10, sticky="ew")

        # colunas do conn_frame: 0,1 (IP), 3,4 (Porta), 5 (spacer), 6 (botão)
        conn_frame.grid_columnconfigure(1, weight=1)   # entry IP expande
        conn_frame.grid_columnconfigure(3, weight=1)   # entry Porta expande
        conn_frame.grid_columnconfigure(5, weight=1)   # spacer que empurra o botão
  
        ctk.CTkLabel(conn_frame, text="IP Master:").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        self.ip_entry = ctk.CTkEntry(conn_frame)
        self.ip_entry.insert(0, self.get_state().ip)
        self.ip_entry.grid(row=0, column=1, sticky="ew", padx=6, pady=6)

        ctk.CTkLabel(conn_frame, text="Porta:").grid(row=0, column=3, sticky="e", padx=6, pady=6)
        self.port_entry = ctk.CTkEntry(conn_frame)
        self.port_entry.insert(0, str(self.get_state().port))
        self.port_entry.grid(row=0, column=4, sticky="w", padx=6, pady=6)

        self.btn_buscar = ctk.CTkButton(conn_frame, text="Buscar master na rede", command=self._buscar)
        self.btn_buscar.grid(row=0, column=6, padx=6, pady=6, sticky="e")

        cols = [("NAME", 220), ("MAC", 160), ("IP", 140), ("MASCARA", 140), ("GATEWAY", 140), ("DHCP", 100)]
        self.table = ColumnToggleTree(self, columns=cols, height=10)
        self.table.grid(row=3, column=0, columnspan=3, sticky="nsew", padx=6, pady=(6, 10))
        self.table.set_font_size(TABLE_FONT_SIZE)

        # Oculta colunas desnecessárias por padrão
        for col in ("MASCARA", "GATEWAY"):
            try:
                self.table._toggle_col(col)
            except Exception:
                pass

        # duplo clique: conecta no IP da linha
        self.table.tree.bind("<Double-1>", self._on_row_double_click)
        # click na linha atualiza IP
        self.table.tree.bind("<<TreeviewSelect>>", self._on_row_select)
        # sorting default by NAME
        try:
            self.table.set_auto_sort("NAME", ascending=True)
        except Exception:
            pass

        btns = ctk.CTkFrame(self)
        btns.grid(row=4, column=0, columnspan=3, pady=8)
        self.auto_reconnect = ctk.CTkSwitch(btns, text="Auto reconectar", command=self._on_toggle_auto)
        self.auto_reconnect.pack(side="left", padx=6)
        
        ctk.CTkButton(btns, text="Conectar", command=self._connect).pack(side="left", padx=6)
        ctk.CTkButton(btns, text="Desconectar", command=self._disconnect).pack(side="left", padx=6)

        status_frame = ctk.CTkFrame(self)
        status_frame.grid(row=5, column=0, columnspan=3, pady=6)
        self.status = ctk.CTkLabel(status_frame, text="Pronto.")
        self.status.pack(side="left")

        # refletir estado real do serviço
        try:
            if self._conn is not None and hasattr(self._conn, "is_auto_reconnect_enabled") and self._conn.is_auto_reconnect_enabled():
                self.auto_reconnect.select()
            else:
                self.auto_reconnect.deselect()
        except Exception:
            self.auto_reconnect.deselect()

    # ---- Ações ----
            
    def _on_row_select(self, _event=None):
        row = self._get_selected_row()
        if not row:
            return
        ip = (row.get("IP") or "").strip()
        port = get_safe_int(self.port_entry.get(), 1, 65000, 4999)

        if ip:
            self.ip_entry.delete(0, "end")
            self.ip_entry.insert(0, ip)
            # valida porta também.
            self.port_entry.delete(0, "end")
            self.port_entry.insert(0, str(port))


    def _on_row_double_click(self, _event=None):
        row = self._get_selected_row()
        if not row:
            return
        ip = (row.get("IP") or "").strip()
        port = get_safe_int(self.port_entry.get(), 1, 65000, 4999)

        if ip:
            self.ip_entry.delete(0, "end")
            self.ip_entry.insert(0, ip)
            # valida porta também.
            self.port_entry.delete(0, "end")
            self.port_entry.insert(0, str(port))
            self._connect()

    def _connect(self):
        # Verifica se tem alguma linha selecionada.

        ip = self.ip_entry.get().strip()
        port = get_safe_int(self.port_entry.get(), 1, 65000, 4999)
        desired_auto = bool(self.auto_reconnect.get())
        if self._conn is None:
            if DEBUG: print("[ConexaoPage] _connect: self._conn é None — verifique a injeção em main_app.py")
            return
        # evitar corrida: desliga auto enquanto troca de conexão (inclui duplo clique já conectado)
        try:
            if hasattr(self._conn, "enable_auto_reconnect"):
                self._conn.enable_auto_reconnect(False)
            else:
                self._conn.stop_auto_reconnect()
        except Exception:
            pass

        if self._conn.get_is_connected:
            # se já está conectado em outro host, não reconecta.
            if DEBUG: print(f"[ConexaoPage] no _connect detectou conexão anterior")
            # precisa desconectar, esperar um pouco, e reconectar.

        def worker():
            if DEBUG: print("[ConexaoPage worker] start worker")
            ok = self._conn.connect(ip, port)
            # se precisar atualizar a UI após terminar:
            self.after(0, lambda: print(f"[ConexaoPage worker] end: ({ip}:{port}) -> ok: {ok}"))

        threading.Thread(target=worker, daemon=True).start()

        # aplica estado desejado do switch após conectar (ou manter tentando, se falhou)
        try:
            self._conn.enable_auto_reconnect(desired_auto)
            if DEBUG: print(f"[ConexaoPage worker] desired auto reconnect: ({desired_auto})")
        except Exception as e:
            if DEBUG: print("[ConexaoPage] Erro ao aplicar estado do auto-reconnect:", e)




    def _disconnect(self):
        if self._conn is None:
            if DEBUG: print("[ConexaoPage] _disconnect: self._conn é None")
            return
        # usuário pediu desconectar => NUNCA ficar tentando reconectar
        try:
            if hasattr(self._conn, "enable_auto_reconnect"):
                self._conn.enable_auto_reconnect(False)
            else:
                self._conn.stop_auto_reconnect()
        except Exception:
            pass
        try:
            self._conn.disconnect()
        finally:
            self.auto_reconnect.deselect()


    def _on_toggle_auto(self):
        if self._conn is None:
            if DEBUG: print("[ConexaoPage] _on_toggle_auto: self._conn é None")
            return
        enabled = bool(self.auto_reconnect.get())
        # print(f"[ConexaoPage] toggle auto -> {enabled}")
        try:
            if hasattr(self._conn, "enable_auto_reconnect"):
                self._conn.enable_auto_reconnect(enabled)
            else:
                (self._conn.auto_reconnect() if enabled else self._conn.stop_auto_reconnect())
        except Exception as e:
            if DEBUG: print("[ConexaoPage] Erro ao alternar auto-reconnect:", e)


    def _buscar(self):
        if self._scan_thread and self._scan_thread.is_alive():
            return
        timeout = int(self.get_discovery_timeout())
        self.table.set_rows([])
        self.table.set_font_size(TABLE_FONT_SIZE)
        self.btn_buscar.configure(state="disabled", text="Aguarde…")
        self.status.configure(text=f"Procurando (timeout={timeout}ms)…")

        def worker():
            items = self.scan_func(
                timeout_ms=timeout,
                on_found=lambda d: self.after(0, self._append_row, d)
            )
            self.after(0, self._on_scan_finished, items, timeout)

        self._scan_thread = threading.Thread(target=worker, daemon=True)
        self._scan_thread.start()

    def _on_scan_finished(self, items, timeout):
        self._scan_thread = None
        self.btn_buscar.configure(state="normal", text="Buscar master na rede")
        self.status.configure(text=f"{len(items)} Interfaces encontradas (timeout={timeout}ms)")

    # ---- Tema ----
    def on_theme_changed(self):
        if hasattr(self, "table"):
            self.table.apply_style()
            self.table.set_font_size(TABLE_FONT_SIZE)


    def _get_selected_row(self):
        # Prefer ColumnToggleTree helper; fallback to raw Treeview
        if hasattr(self.table, "get_selected_row"):
            try:
                return self.table.get_selected_row()
            except Exception:
                pass
        sel = self.table.tree.selection()
        if not sel:
            return None
        item = sel[0]
        vals = self.table.tree.item(item, "values")
        return {self.table._all_cols[i]: vals[i] for i in range(len(self.table._all_cols))}


    def _do_scan(self):
        timeout = int(self.get_discovery_timeout())
        self.table.set_rows([])
        def on_found(item: dict):
            self.after(0, self._append_row, item)
        items = self.scan_func(timeout_ms=timeout, on_found=on_found)
        self.after(0, lambda: self.status.configure(text=f"{len(items)} dispositivo(s) encontrados (timeout={timeout}ms)"))


    def _append_row(self, item: dict):
        row = {
            "NAME": item.get("NAME",""),
            "MAC": item.get("MAC",""),
            "IP": item.get("IP",""),
            "MASCARA": item.get("MASCARA",""),
            "GATEWAY": item.get("GATEWAY",""),
            "DHCP": item.get("DHCP",""),
        }
        try:
            # upsert by IP (stable in same scan); fallback to MAC
            key_cols = ["IP"] if "IP" in self.table._all_cols else ["MAC"]
            self.table.upsert_row(row, key_cols=key_cols)
            self.table.set_font_size(TABLE_FONT_SIZE)
        except Exception:
            # fallback: rebuild all rows
            cur = getattr(self, "_rows", [])
            cur.append(row)
            self.table.set_rows(cur)

    def destroy(self):
        return super().destroy()
