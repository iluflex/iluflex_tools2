import threading
import customtkinter as ctk
from iluflex_tools.widgets.column_tree import ColumnToggleTree

class ConexaoPage(ctk.CTkFrame):
    def __init__(self, master, on_connect, on_disconnect, get_state, scan_func=None, get_discovery_timeout=None):
        super().__init__(master)
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        self.get_state = get_state
        self.scan_func = scan_func or (lambda timeout_ms: [])
        self.get_discovery_timeout = get_discovery_timeout or (lambda: 2000)
        self._scan_thread = None
        self._build()

    def _build(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(self, text="Conexão de Rede", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, columnspan=3, pady=(10, 12), sticky="w"
        )

        ctk.CTkLabel(self, text="IP MASTER").grid(row=1, column=0, sticky="e", padx=6, pady=6)
        self.ip_entry = ctk.CTkEntry(self)
        self.ip_entry.insert(0, self.get_state().ip)
        self.ip_entry.grid(row=1, column=1, sticky="ew", padx=6, pady=6)

        ctk.CTkLabel(self, text="Porta").grid(row=2, column=0, sticky="e", padx=6, pady=6)
        self.port_entry = ctk.CTkEntry(self)
        self.port_entry.insert(0, str(self.get_state().port))
        self.port_entry.grid(row=2, column=1, sticky="ew", padx=6, pady=6)

        self.btn_buscar = ctk.CTkButton(self, text="Buscar master na rede", command=self._buscar)
        self.btn_buscar.grid(row=1, column=2, rowspan=2, padx=6, pady=6)

        cols = [("NAME", 220), ("MAC", 160), ("IP", 140), ("MASCARA", 140), ("GATEWAY", 140), ("DHCP", 100)]
        self.table = ColumnToggleTree(self, columns=cols, height=10)
        self.table.grid(row=3, column=0, columnspan=3, sticky="nsew", padx=6, pady=(6, 10))


        # duplo clique: conecta no IP da linha
        self.table.tree.bind("<Double-1>", self._on_row_double_click)
        # sorting default by NAME
        try:
            self.table.set_auto_sort("NAME", ascending=True)
        except Exception:
            pass

        btns = ctk.CTkFrame(self)
        btns.grid(row=4, column=0, columnspan=3, pady=8)
        ctk.CTkButton(btns, text="Conectar", command=self._connect).pack(side="left", padx=6)
        ctk.CTkButton(btns, text="Desconectar", command=self._disconnect).pack(side="left", padx=6)

        self.status = ctk.CTkLabel(self, text="Pronto.")
        self.status.grid(row=5, column=0, columnspan=3, pady=6)

    # ---- Ações ----
    def _on_row_double_click(self, _event=None):
        row = self._get_selected_row()
        if not row:
            return
        ip = (row.get("IP") or "").strip()
        if ip:
            self.ip_entry.delete(0, "end")
            self.ip_entry.insert(0, ip)
            self._connect()

    def _connect(self):
        ip = self.ip_entry.get().strip()
        port = int(self.port_entry.get().strip() or 0)
        ok = self.on_connect(ip, port)
        self.status.configure(text=f"Conectado a {ip}:{port}" if ok else "Falha na conexão")

    def _disconnect(self):
        self.on_disconnect()
        self.status.configure(text="Desconectado.")

    def _buscar(self):
        if self._scan_thread and self._scan_thread.is_alive():
            return
        timeout = int(self.get_discovery_timeout())
        self.btn_buscar.configure(state="disabled", text="Aguarde…")
        self.status.configure(text=f"Procurando (timeout={timeout}ms)…")

        def worker():
            try:
                data = self.scan_func(timeout)
            except Exception:
                data = []
            self.after(0, lambda d=data, t=timeout: self._on_scan_done(d, t))

        self._scan_thread = threading.Thread(target=worker, daemon=True)
        self._scan_thread.start()

    def _on_scan_done(self, data, timeout):
        rows = []
        for item in data:
            rows.append({
                "NAME": item.get("NAME", ""),
                "MAC": item.get("MAC", ""),
                "IP": item.get("IP", ""),
                "MASCARA": item.get("MASCARA", ""),
                "GATEWAY": item.get("GATEWAY", ""),
                "DHCP": item.get("DHCP", "")
            })
        self.table.set_rows(rows)
        self.table.set_font_size(12)
        self.btn_buscar.configure(state="normal", text="Buscar master na rede")
        self.status.configure(text=f"{len(rows)} dispositivo(s) encontrados (timeout={timeout}ms)")

    # ---- Tema ----
    def on_theme_changed(self):
        if hasattr(self, "table"):
            self.table.apply_style()


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
        except Exception:
            # fallback: rebuild all rows
            cur = getattr(self, "_rows", [])
            cur.append(row)
            self.table.set_rows(cur)
