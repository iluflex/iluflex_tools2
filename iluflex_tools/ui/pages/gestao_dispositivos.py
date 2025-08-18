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
from iluflex_tools.core.settings import load_settings, save_settings
import time
import re

TABLE_FONT_SIZE = 12

class GestaoDispositivosPage(ctk.CTkFrame):
    """Página de gestão de *dispositivos* (rede 485/mesh)."""

    def __init__(self, master, send_func=None, conn=None, settings=None):
        super().__init__(master)
        self._send = send_func  # função para enviar comandos TCP
        self._conn = conn       # ConnectionService para ouvir RX
        self._settings = settings or load_settings()

        # controle da barra de progresso do botão "Procurar Dispositivos"
        self._discover_after: str | None = None
        self._discover_end_time: float = 0.0
        self._discover_timeout: int = 0

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

        
        self.auto_reconnect = ctk.CTkSwitch(bar, text="Auto reconectar", command=self._on_toggle_auto_reconnect)
        self.auto_reconnect.pack(side="right", padx=6)
        # refletir estado real do serviço
        try:
            if self._conn is not None and hasattr(self._conn, "is_auto_reconnect_enabled") and self._conn.is_auto_reconnect_enabled():
                self.auto_reconnect.select()
            else:
                self.auto_reconnect.deselect()
        except Exception:
            self.auto_reconnect.deselect()

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
        self.listUpdateBtn.grid(row=0, column=0, padx=6, pady=6)

        # botão "Procurar Dispositivos" com barra de progresso
        self.discover_frame = ctk.CTkFrame(bottom_frame)
        self.discover_frame.grid(row=0, column=1, padx=6, pady=6, sticky="ew")
        self.discover_frame.grid_columnconfigure(0, weight=1)

        self.discoverDevicesBtn = ctk.CTkButton(
            self.discover_frame,
            text="Procurar Dispositivos",
            command=self._on_click_discover,
        )
        self.discoverDevicesBtn.grid(row=0, column=0, sticky="ew")

        self.discover_progress = ctk.CTkProgressBar(self.discover_frame)
        self.discover_progress.set(0)
        # coloca progress bar abaixo do botão ocupando a mesma largura
        self.discover_progress.grid(row=1, column=0, sticky="ew")

        self._style_discover_progress()

        self.stopDiscoverBtn = ctk.CTkButton(bottom_frame,  text="Parar Busca", command=self._on_click_stop_discover)
        self.stopDiscoverBtn.grid(row=0, column=2, padx=6, pady=6)
        self.stopDiscoverBtn.grid_remove()  # oculto inicialmente

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

        # --- Restaurar progresso persistido ---
        try:
            started = getattr(self._settings, "discovery_started_at", None)
            timeout = int(getattr(self._settings, "mesh_discovery_timeout_sec", 30))
            if started:
                end_ts = float(started) + float(max(timeout, 1))
                remaining = end_ts - time.time()
                if remaining > 0:
                    self.discoverDevicesBtn.configure(text="Procurando…")
                    try:
                        self.stopDiscoverBtn.grid()
                    except Exception:
                        pass
                    self._discover_timeout = max(timeout, 1)
                    self._discover_end_time = end_ts
                    self._discover_after = self.after(100, self._update_discover_progress)
                else:
                    # expirado → limpar persistência
                    self._settings.discovery_started_at = None
                    save_settings(self._settings)
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
            
            # --- ACK do comando SRF,15,9,<tempo> ---
            if "RRF,15,9," in text:
                for m in re.finditer(r"RRF,15,9,(\d+)", text):
                    try:
                        secs = int(m.group(1))
                    except Exception:
                        continue
                    self.after(0, self._handle_rrf_15_1, secs)
            
            devices = parse_rrf10_lines(text)
            if not devices:
                return
            self.after(0, self.ingest_rrf10, devices)
        except Exception:
            pass

    def _handle_rrf_15_1(self, seconds: int) -> None:
        """
        Confirmação da interface para SRF,15,9,<status>.
        1 -> está na rede pública, avisa slaves, volta para privada em 2 segundos.
        0 -> já está na rede privada, não faz mais nada
        Em ambos: o comando foi aceito, e logo estará na rede privada.
        """
        # se foi parar (2s), cancelar o loop de progresso e resetar UI
        try:
            if getattr(self, "_discover_after", None):
                try: self.after_cancel(self._discover_after)
                except Exception: pass
                self._discover_after = None
            self.discover_progress.set(0)
            self.discoverDevicesBtn.configure(text="Procurar Dispositivos")
            # esconder botão de parar a busca
            self.stopDiscoverBtn.grid_remove()
        except Exception:
            pass

        # agenda reconexão: após a troca de rede + 10s para a interface aceitar nova conexão
        delay = 10 
        self._schedule_reconnect_after(delay)
 
    def _schedule_reconnect_after(self, delay_sec: int, window_sec: int = 20) -> None:
        """Agenda tentativa de reconexão após 'delay_sec'. Se o switch de auto-reconnect
        estiver desligado, ativa temporariamente por 'window_sec' segundos."""
        try:
            was_on = False
            try:
                was_on = bool(self.auto_reconnect.get())
            except Exception:
                was_on = False

            def _start():
                try:
                    self._conn.auto_reconnect()
                except Exception:
                    pass
                # se não estava ligado, para depois da janela
                if not was_on:
                    try:
                        self.after(window_sec * 1000, lambda: self._conn.stop_auto_reconnect())
                    except Exception:
                        pass

            self.after(int(delay_sec * 1000), _start)
        except Exception:
            pass


    # ------------------------------------------------------------------
    # Ações
    # ------------------------------------------------------------------
        
    def _on_toggle_auto_reconnect(self):
        if self._conn is None:
            print("[GestaoDispositivosPage] _on_toggle_auto_reconnect: self._conn é None")
            return
        enabled = bool(self.auto_reconnect.get())
        # print(f"[ConexaoPage] toggle auto -> {enabled}")
        try:
            if hasattr(self._conn, "enable_auto_reconnect"):
                self._conn.enable_auto_reconnect(enabled)
            else:
                (self._conn.auto_reconnect() if enabled else self._conn.stop_auto_reconnect())
        except Exception as e:
            print("[GestaoDispositivosPage] Erro ao alternar auto-reconnect:", e)



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
            self._dataset.clear()
            try:
                self.table.set_rows([])
            except Exception:
                pass
            if callable(self._send):
                self._send(f"SRF,15,1,{timeout}\r")
        except Exception as e:
            print("Procurar Dispositivos Error: ", e)

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

        # mostrar botão Parar Busca ao iniciar
        self.stopDiscoverBtn.grid()



    def _update_discover_progress(self):
        remaining = self._discover_end_time - time.time()
        progress = 1.0 - max(remaining, 0) / float(self._discover_timeout)
        self.discover_progress.set(progress)
        if remaining <= 0:
            self.discover_progress.set(0)
            self.discoverDevicesBtn.configure(text="Procurar Dispositivos")
            self._discover_after = None
            # esconder ao concluir automaticamente
            self.stopDiscoverBtn.grid_remove()
        else:
            self._discover_after = self.after(100, self._update_discover_progress)

    def _style_discover_progress(self):
        try:
            fg = self.discoverDevicesBtn.cget("fg_color")
            self.discover_progress.configure(fg_color=fg, progress_color=self.discoverDevicesBtn.cget("text_color"), border_width=0)
        except Exception:
            pass

    def _on_click_stop_discover(self):
        """Solicita parar a busca (SRF,15,9). Esconde o botão apenas após RRF,15,9"""
        try:
            # feedback imediato; aguardamos o ACK para esconder botão/zerar UI
            try:
                self.discoverDevicesBtn.configure(text="Parando…")
            except Exception:
                pass
            if callable(self._send):
                self._send("SRF,15,9\r")
        except Exception:
            pass


    # ---- Tema ----
    def on_theme_changed(self):
        self._style_discover_progress()
        if hasattr(self.table, "apply_style"):
            try:
                self.table.apply_style()
            except Exception:
                pass
