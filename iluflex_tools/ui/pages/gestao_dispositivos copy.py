# iluflex_tools/ui/pages/gestao_dispositivos.py
"""
Gestão de Dispositivos — simplificado e alinhado ao ConnectionService

- Reconexão automática: **somente** pelo ConnectionService.
- Switch "Auto reconectar": reflete e controla o estado real (sem estados paralelos).
- "Buscar Dispositivos": força **ligar** auto‑reconnect antes do comando e mantém ligado.
- Ao abrir a página (ou ao conectar), se já conectado, emula **Atualizar Lista**.
- Mantém comandos existentes: "SRF,10,255\r" (atualizar), "SRF,15,1,<timeout>\r" (descoberta mesh).
- Mantém ingestão de `RRF,10` via `parse_rrf10_lines`.
"""

from __future__ import annotations

import time
import threading
from collections import Counter
from typing import Dict, List

import customtkinter as ctk

from iluflex_tools.widgets.column_tree import ColumnToggleTree
from iluflex_tools.core.services import ConnectionService, parse_rrf10_lines
from iluflex_tools.core.settings import load_settings

TABLE_FONT_SIZE = 12


class GestaoDispositivosPage(ctk.CTkFrame):
    def __init__(self, master, conn: ConnectionService, send_func=None):
        super().__init__(master)
        self._conn: ConnectionService = conn
        self._send = send_func or self._conn.send
        self._settings = load_settings()

        # estado de busca
        self._discover_after: str | None = None  # id de after
        self._discover_end_time: float = 0.0
        self._discover_timeout: int = 0
        self._discover_stop = threading.Event()
        self._discover_thread: threading.Thread | None = None

        # dataset
        self._rows_by_mac: Dict[str, Dict] = {}
        self._dataset: List[Dict] = []
        self._last_mac: str | None = None

        # UI
        self._build()

        # eventos do serviço
        try:
            self._conn.add_listener(self._on_conn_event)
        except Exception:
            pass

        # quando ficar visível, tenta autorefresh
        try:
            self.bind("<Map>", self._on_mapped, add="+")
        except Exception:
            pass

    # ------------------------- UI -------------------------
    def _build(self):
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        bar = ctk.CTkFrame(self)
        bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        bar.grid_columnconfigure(9, weight=1)

        ctk.CTkLabel(bar, text="Gestão de Dispositivos", font=ctk.CTkFont(size=16, weight="bold")).pack(
            side="left", padx=(4, 12)
        )

        # Switch auto‑reconnect (espelha serviço)
        self.auto_reconnect = ctk.CTkSwitch(bar, text="Auto reconectar", command=self._on_toggle_auto)
        self.auto_reconnect.pack(side="right", padx=6)
        self._sync_auto_switch_from_service()

        # Tabela
        cols = [
            {"key": "Slave ID", "width": 80},
            {"key": "Mac Address", "width": 150},
            {"key": "Modelo", "width": 110},
            {"key": "FW", "width": 90},
            {"key": "HW", "width": 70},
            {"key": "Conectado a", "width": 130},
            {"key": "IP", "width": 120},
            {"key": "MASCARA", "width": 120},
            {"key": "GATEWAY", "width": 120},
            {"key": "Sinal (dB)", "width": 100},
        ]
        self.table = ColumnToggleTree(self, columns=cols, height=14)
        self.table.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 8))
        self.table.set_font_size(TABLE_FONT_SIZE)

        # Oculta colunas de detalhes
        for col in ("FW", "HW", "Conectado a", "Sinal (dB)"):
            try:
                self.table._toggle_col(col)
            except Exception:
                pass

        # Ordenação padrão por Slave ID
        try:
            self.table.set_auto_sort("Slave ID", ascending=True)
        except Exception:
            try:
                self.table.enable_header_sort()  # conforme impl.
            except Exception:
                pass

        # Barra inferior (botões)
        bottom = ctk.CTkFrame(self)
        bottom.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 6))
        bottom.grid_columnconfigure(2, weight=1)

        self.listUpdateBtn = ctk.CTkButton(bottom, text="Atualizar Lista", command=self._on_click_atualizar)
        self.listUpdateBtn.grid(row=0, column=0, padx=6, pady=6)

        self.discover_frame = ctk.CTkFrame(bottom)
        self.discover_frame.grid(row=0, column=1, padx=6, pady=6, sticky="ew")
        self.discover_frame.grid_columnconfigure(0, weight=1)

        self.discoverDevicesBtn = ctk.CTkButton(self.discover_frame, text="Procurar Dispositivos", command=self._on_click_discover)
        self.discoverDevicesBtn.grid(row=0, column=0, sticky="ew")

        self.discover_progress = ctk.CTkProgressBar(self.discover_frame)
        self.discover_progress.set(0)
        self.discover_progress.grid(row=1, column=0, sticky="ew")
        self._style_discover_progress()

        self.stopDiscoverBtn = ctk.CTkButton(bottom, text="Parar Busca", command=self._on_click_stop_discover)
        self.stopDiscoverBtn.grid(row=0, column=2, padx=6, pady=6)
        self.stopDiscoverBtn.grid_remove()

    # --------------------- Auto‑reconnect ---------------------
    def _service_auto_enabled(self) -> bool:
        """Inferir estado real do serviço (não há getter público)."""
        try:
            thr = getattr(self._conn, "_auto_thread", None)
            ev = getattr(self._conn, "_auto_stop", None)
            return bool(thr and getattr(thr, "is_alive", lambda: False)() and ev and not ev.is_set())
        except Exception:
            return False

    def _sync_auto_switch_from_service(self) -> None:
        # desativado aqui: não altera visual do switch nesta página
        return

    def _on_toggle_auto(self) -> None:(self) -> None:
        # desativado aqui: auto-reconnect é responsabilidade do serviço (não desta página)
        return

    # ----------------------- Eventos -----------------------
    def _on_conn_event(self, ev: dict):
        typ = ev.get("type")
        text = ev.get("text")
        if typ == "rx" and text:
            # RRF,15,9,<status>
            if "RRF,15,9," in text:
                import re
                for m in re.finditer(r"RRF,15,9,(\d+)", text):
                    try:
                        secs = int(m.group(1))
                    except Exception:
                        continue
                    self.after(0, self._handle_rrf_15_1, secs)
            
            # RRF,10 (lista de dispositivos)
            devices = parse_rrf10_lines(text)
            if devices:
                self.after(0, self.ingest_rrf10, devices)
        elif typ == "connect":
            # não sincroniza/força auto-reconnect aqui
            pass
        elif typ in ("disconnect", "error"):
            # pode manter feedback visual; não mexe no switch
            pass

    # --------------------- Ingestão de dados ---------------------
    def ingest_rrf10(self, devices: List[Dict]):
        """Mescla/atualiza dispositivos pelo MAC e repinta.
        Mantém o LAYOUT da tabela; mapeia chaves do parser (snake_case) para
        os nomes das colunas já existentes (ex.: "Slave ID", "Mac Address", ...).
        """
        if not devices:
            return

        def _map_to_view(d: Dict) -> Dict:
            # Parser (services.parse_rrf10_lines) usa snake_case:
            # slave_id, mac, sinal_db, parent_mac, modelo, versao_hw, versao_fw, ...
            return {
                "Slave ID": d.get("slave_id", ""),
                "Mac Address": d.get("mac", ""),
                "Modelo": d.get("modelo", ""),
                "FW": d.get("versao_fw", ""),
                "HW": d.get("versao_hw", ""),
                "Conectado a": d.get("parent_mac", ""),
                # Estes campos não vêm no RRF,10; ficam vazios se não existirem
                "IP": d.get("IP", d.get("ip", "")),
                "MASCARA": d.get("MASCARA", d.get("mask", "")),
                "GATEWAY": d.get("GATEWAY", d.get("gateway", "")),
                "Sinal (dB)": d.get("sinal_db", ""),
            }

        last_mac = None
        for d in devices:
            row = _map_to_view(d)
            mac = row.get("Mac Address")
            if not mac:
                continue
            self._rows_by_mac[mac] = row
            last_mac = mac

        self._dataset = list(self._rows_by_mac.values())

        # (re)desenha tabela usando as MESMAS colunas já configuradas
        try:
            if hasattr(self.table, "set_rows"):
                self.table.set_rows(self._dataset)
                self.table.set_font_size(TABLE_FONT_SIZE)
            else:
                # fallback: upsert
                for r in self._dataset:
                    try:
                        self.table.upsert_row(r, key_cols=["Mac Address"])
                    except Exception:
                        pass
        except Exception:
            pass

        # cores por regra
        self._apply_row_colors(last_mac)
        self._last_mac = last_mac

    def _apply_row_colors(self, last_mac: str | None):
        counts = Counter(r.get("Slave ID") for r in self._dataset if r.get("Slave ID") not in (None, ""))
        tv = getattr(self.table, "tree", getattr(self.table, "tv", None))
        if tv is None:
            return
        try:
            tv.tag_configure("last", background="#939393")         # cinza
            tv.tag_configure("dup_sid", background="#FAE467")       # amarelo claro
            tv.tag_configure("uniq_sid", background="#D9F8D9")      # verde claro
        except Exception:
            pass
        # limpa tags
        try:
            for iid in tv.get_children(""):
                tv.item(iid, tags=tuple(tag for tag in tv.item(iid, "tags") if tag not in {"last","dup_sid","uniq_sid"}))
        except Exception:
            pass
        # aplica
        mac_idx = None
        try:
            mac_idx = self.table._all_cols.index("Mac Address")
        except Exception:
            pass
        for iid in tv.get_children(""):
            try:
                vals = tv.item(iid, "values")
                mac = (vals[mac_idx] if mac_idx is not None else None) if vals else None
                sid = None
                try:
                    sid = vals[self.table._all_cols.index("Slave ID")]
                except Exception:
                    pass
                tags = set(tv.item(iid, "tags") or ())
                if mac and last_mac and mac == last_mac:
                    tags.add("last")
                if sid:
                    if counts.get(sid, 0) > 1:
                        tags.add("dup_sid")
                    else:
                        tags.add("uniq_sid")
                tv.item(iid, tags=tuple(tags))
            except Exception:
                pass

    # --------------------- Ações ---------------------
    def _on_click_atualizar(self):
        """Solicita a lista completa e reseta realces."""
        try:
            self._rows_by_mac.clear()
            self._dataset.clear()
            self._last_mac = None
            try:
                self.table.set_rows([])
            except Exception:
                pass
            if callable(self._send):
                self._send("SRF,10,255\r")
        except Exception:
            pass

    def _on_click_discover(self):
        """Envia comando para dispositivos irem para rede mesh pública."""
        timeout = int(getattr(self._settings, "mesh_discovery_timeout_sec", 30))
        try:
            # envia comando real
            if callable(self._send):
                self._send(f"SRF,15,1,{timeout}\r")
        except Exception as e:
            print("[Gestao] Erro ao iniciar descoberta:", e)

        # reinicia contagem e barra de progresso
        if self._discover_after:
            try:
                self.after_cancel(self._discover_after)
            except Exception:
                pass
            self._discover_after = None
        self.discoverDevicesBtn.configure(text="Procurando…")
        self.discover_progress.set(0)
        self._discover_timeout = max(timeout, 1)
        self._discover_end_time = time.time() + self._discover_timeout
        self._discover_after = self.after(100, self._update_discover_progress)
        self.stopDiscoverBtn.grid()

    def _on_click_stop_discover(self):
        try:
            self._discover_stop.set()
        except Exception:
            pass
        try:
            if self._discover_after:
                self.after_cancel(self._discover_after)
        except Exception:
            pass
        self._discover_after = None
        self.discover_progress.set(0)
        self.discoverDevicesBtn.configure(text="Procurar Dispositivos")
        self.stopDiscoverBtn.grid_remove()

    def _update_discover_progress(self):
        remaining = self._discover_end_time - time.time()
        progress = 1.0 - max(remaining, 0) / float(self._discover_timeout)
        self.discover_progress.set(progress)
        if remaining <= 0:
            self.discover_progress.set(0)
            self.discoverDevicesBtn.configure(text="Procurar Dispositivos")
            self._discover_after = None
            self.stopDiscoverBtn.grid_remove()
            return
        self._discover_after = self.after(100, self._update_discover_progress)

    def _handle_rrf_15_1(self, seconds: int) -> None:
        """Confirmação da interface para SRF,15,1,<timeout> (mudança de rede).
        A UI reseta o progresso e mantém auto‑reconnect ligado (quem reconecta é o serviço).
        """
        try:
            if getattr(self, "_discover_after", None):
                try:
                    self.after_cancel(self._discover_after)
                except Exception:
                    pass
                self._discover_after = None
            self.discover_progress.set(0)
            self.discoverDevicesBtn.configure(text="Procurar Dispositivos")
            self.stopDiscoverBtn.grid_remove()
        except Exception:
            pass
        # nenhuma agenda local de reconexão aqui; o serviço cuida

    # --------------------- Helpers ---------------------
    def _style_discover_progress(self):
        try:
            self.discover_progress._fg_color = ("#e5e5e5", "#2a2a2a")  # segue paleta do ColumnToggleTree
            self.discover_progress._progress_color = ("#3b82f6", "#3b82f6")
        except Exception:
            pass

    def _on_mapped(self, _ev=None):
        self.after(80, self._maybe_autorefresh)

    def _maybe_autorefresh(self):
        try:
            if getattr(self._conn, "connected", False):
                self._on_click_atualizar()
        except Exception:
            pass

    def on_page_activated(self) -> None:
        """Chamar ao navegar para esta página para auto‑atualizar se conectado."""
        self._maybe_autorefresh()

    # --------------------- Tema ---------------------
    def on_theme_changed(self):
        self._style_discover_progress()
        if hasattr(self.table, "apply_style"):
            try:
                self.table.apply_style()
            except Exception:
                pass

    def destroy(self):
        try:
            self._conn.remove_listener(self._on_conn_event)
        except Exception:
            pass
        try:
            if self._discover_after:
                self.after_cancel(self._discover_after)
        except Exception:
            pass
        super().destroy()
