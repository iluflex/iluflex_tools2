# Arquivo: iluflex_tools_scaffold/iluflex_tools/ui/pages/gestao_dispositivos.py
# Objetivo: manter lista sempre atualizada (upsert por MAC), reordenar, e colorir linhas:
#  - Cinza: último dispositivo que enviou mensagem
#  - Amarelo claro: slave_id duplicado (há >1 com o mesmo id)
#  - Verde claro: slave_id único
#  - Aumentar fonte da tabela

from __future__ import annotations

import customtkinter as ctk
from collections import Counter
from typing import Dict, List

from iluflex_tools.widgets.column_tree import ColumnToggleTree
from iluflex_tools.core.services import parse_rrf10_lines

TABLE_FONT_SIZE = 12

class GestaoDispositivosPage(ctk.CTkFrame):
    """Página de gestão de *dispositivos* (rede 485/mesh)."""

    def __init__(self, master, send_func=None, conn=None):
        super().__init__(master)
        self._send = send_func  # função para enviar comandos TCP
        self._conn = conn       # ConnectionService para ouvir RX

        # Estado local indexado por MAC
        self._rows_by_mac: Dict[str, Dict] = {}
        self._dataset: List[Dict] = []
        self._last_mac: str | None = None

        self._build()

        # Inscrição nos eventos de RX
        try:
            if self._conn is not None:
                self._conn.add_listener(self._on_conn_event)
        except Exception:
            pass

    def destroy(self):
        try:
            if self._conn is not None:
                self._conn.remove_listener(self._on_conn_event)
        except Exception:
            pass
        return super().destroy()

    def _build(self):
        # Barra
        bar = ctk.CTkFrame(self)
        bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        bar.grid_columnconfigure(9, weight=1)

        ctk.CTkLabel(
            bar,
            text="Gestão de Dispositivos",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(side="left", padx=(4, 12))

        
        self.auto_reconnect = ctk.CTkSwitch(bar, text="Auto reconectar", command=self._toggle_auto_reconnect)
        self.auto_reconnect.pack(side="left", padx=6)

        # Tabela
        cols = [
            {"key": "Slave ID", "width": 80},
            {"key": "Mac Address", "width": 150},
            {"key": "Modelo", "width": 110},
            {"key": "Nome", "width": 220},
            {"key": "FW", "width": 70},
            {"key": "HW", "width": 70},
            {"key": "Conectado a", "width": 170},
            {"key": "Sinal (dB)", "width": 90},
        ]
        self.table = ColumnToggleTree(self, columns=[(c["key"], c["width"]) for c in cols], height=16)
        self.table.grid(row=1, column=0, sticky="nsew", padx=10, pady=(6, 10))
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.table.set_font_size(TABLE_FONT_SIZE)

        bottom_frame = ctk.CTkFrame(self)
        bottom_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(4, 20))
        self.listUpdateBtn = ctk.CTkButton(bottom_frame, text="Atualizar Lista", command=self._on_click_atualizar)
        self.listUpdateBtn.grid(row=0, column = 0, padx=6, pady=6)
        self.discoverDevicesBtn = ctk.CTkButton(bottom_frame, text="Procurar Dispositivos", command=self._on_click_discover)
        self.discoverDevicesBtn.grid(row=0, column = 1, padx=6, pady=6)

        # Oculta colunas de detalhes
        for col in ("FW", "HW", "Conectado a", "Sinal (dB)"):
            try:
                self.table._toggle_col(col)
            except Exception:
                pass

        # Ordenação por Slave ID
        try:
            self.table.set_auto_sort("Slave ID", ascending=True)
        except Exception:
            try:
                self.table.enable_header_sort()
            except Exception:
                pass

    def _toggle_auto_reconnect(self):
        try:
            if self.auto_reconnect.get():
                self._conn.auto_reconnect()
            else:
                self._conn.stop_auto_reconnect()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Ingestão de RRF,10
    # ------------------------------------------------------------------
    def ingest_rrf10(self, devices: list[dict]):
        """Upsert por MAC + reordenar e colorir linhas."""
        if not devices:
            return

        last_mac: str | None = None
        for d in devices:
            mac = (d.get("mac") or "").lower()
            if not mac:
                continue  # ignoramos sem MAC
            last_mac = mac
            parent_mac = (d.get("parent_mac") or "").lower()
            row = {
                "Slave ID": d.get("slave_id", ""),
                "Mac Address": mac,
                "Modelo": d.get("modelo", ""),
                "Nome": d.get("nome", ""),
                "FW": d.get("versao_fw", ""),
                "HW": d.get("versao_hw", ""),
                "Conectado a": parent_mac,
                "Sinal (dB)": d.get("sinal_db", ""),
            }
            # upsert por MAC no estado local
            self._rows_by_mac[mac] = row

        # Recria dataset ordenado (estável p/ UI)
        self._dataset = sorted(
            self._rows_by_mac.values(),
            key=lambda r: (
                int(r.get("Slave ID") or 0),
                str(r.get("Nome") or "").lower(),
                str(r.get("Mac Address") or ""),
            ),
        )
        try:
            self.table.set_rows(self._dataset)
            self.table.set_font_size(TABLE_FONT_SIZE)
        except Exception:
            # fallback: insere/atualiza linha-a-linha
            for r in self._dataset:
                try:
                    self.table.upsert_row(r, key_cols=["Mac Address"])  # chave por MAC
                except Exception:
                    pass

        # Aplica cores
        self._apply_row_colors(last_mac)
        self._last_mac = last_mac

    # ------------------------------------------------------------------
    # Cores por regra
    # ------------------------------------------------------------------
    def _apply_row_colors(self, last_mac: str | None):
        # Conta duplicidades de slave_id
        counts = Counter(r.get("Slave ID") for r in self._dataset if r.get("Slave ID") != "")

        # Acessa Treeview interno (ColumnToggleTree deve expor como .tree ou .tv)
        tv = getattr(self.table, "tree", getattr(self.table, "tv", None))
        if tv is None:
            return  # sem como aplicar cor, não quebra

        # Define tags (não falhar se já existir)
        try:
            tv.tag_configure("last", background="#939393")       # cinza
            tv.tag_configure("dup_sid", background="#FAE467")     # amarelo claro
            tv.tag_configure("uniq_sid", background="#7FD37F")    # verde claro
        except Exception:
            pass

        # Descobre índices das colunas
        headers = []
        try:
            headers = [h for (h, _w) in getattr(self.table, "columns", [])]
        except Exception:
            pass
        if not headers:
            headers = ["Slave ID", "Mac Address"]  # suposição segura
        try:
            idx_sid = headers.index("Slave ID")
            idx_mac = headers.index("Mac Address")
        except ValueError:
            return

        # Limpa tags e reaplica
        for iid in tv.get_children(""):
            try:
                vals = tv.item(iid, "values")
                sid = vals[idx_sid]
                mac = str(vals[idx_mac]).lower()
                tags = []
                if last_mac and mac == last_mac:
                    tags.append("last")  # última mensagem tem prioridade visual
                # grupo por slave_id
                n = counts.get(sid, 0)
                if n > 1:
                    tags.append("dup_sid")
                else:
                    tags.append("uniq_sid")
                tv.item(iid, tags=tuple(tags))
            except Exception:
                continue

    # ------------------------------------------------------------------
    # Eventos de conexão
    # ------------------------------------------------------------------
    def _on_conn_event(self, ev: dict):
        try:
            if ev.get("type") != "rx":
                return
            text = ev.get("text") or ""
            devices = parse_rrf10_lines(text)
            if not devices:
                return
            self.after(0, self.ingest_rrf10, devices)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Ações
    # ------------------------------------------------------------------
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
        try:
            self._dataset.clear()


        except Exception as e:
            print("Procurar Dispositivos Error: ", e)