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
import tkinter as tk  # local, para não mexer nos imports do arquivo

from iluflex_tools.widgets.column_tree import ColumnToggleTree
from iluflex_tools.core.services import ConnectionService, parse_rrf10_lines
from iluflex_tools.core.settings import load_settings, save_settings
import time
import re

TABLE_FONT_SIZE = 12

class GestaoDispositivosPage(ctk.CTkFrame):
    """Página de gestão de *dispositivos* (rede 485/mesh)."""

    def __init__(self, master, conn: ConnectionService, send_func=None):
        super().__init__(master)
        self._conn = conn       # ConnectionService para ouvir RX
        self._send = send_func or self._conn.send  # função para enviar comandos TCP
        self._settings = load_settings()

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

        self.sinalizarModuloBtn = ctk.CTkButton(bottom_frame,  text="Sinalizar Modulo", command=self._on_click_sinalizarModulo)
        self.sinalizarModuloBtn.grid(row=0, column=3, padx=6, pady=6)

        self.salvarModuloBtn = ctk.CTkButton(bottom_frame,  text="Salvar", command=self._on_click_salvarModulo)
        self.salvarModuloBtn.grid(row=0, column=4, padx=6, pady=6)        

        # Configurações da pagina

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

        # Recurso para edição da tabela
        self._init_editing_features()


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
                    self.after(0, self._handle_rrf_15_9, secs)

            timeout = int(getattr(self._settings, "mesh_discovery_timeout_sec", 120))
            if text.strip() == f"RRF,15,1,{timeout}":
                print("vai atualizar em 15 seg")
                self.after(15000, self._on_click_atualizar)
            
            devices = parse_rrf10_lines(text)
            if not devices:
                return
            self.after(0, self.ingest_rrf10, devices)
        except Exception:
            pass

    def _handle_rrf_15_9(self, seconds: int) -> None:
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
        print("atualizar lista")
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
            else:
                print("no callable")
        except Exception as e:
            print(["GestaoDispositivos Erro:", e])
            pass

    def _on_click_discover(self):
        """Envia comando para dispositivos irem para rede mesh pública."""
        timeout = int(getattr(self._settings, "mesh_discovery_timeout_sec", 120))
        print(f"Busca Dispositivos por {timeout} seg")
        try:
            self._dataset.clear()
            self.table.set_rows([])
            if callable(self._send):
                self._send(f"SRF,15,1,{timeout}\r")
            else:
                print("Erro não fez send SRF,15,1 ")
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

        # força ligar auto‑reconnect **antes** do comando e mantém ligado
        self.auto_reconnect.select()
        
        try:
            self._conn.auto_reconnect()
        except Exception as e:
            print("[Pagina Gestao Dispositivos] Erro ao ativar auto_reconnect", e)
            pass


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

    def _on_toggle_auto(self) -> None:
        enabled = bool(self.auto_reconnect.get())
        try:
            if enabled:
                self._conn.auto_reconnect()
            else:
                self._conn.stop_auto_reconnect()
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

    #------------ Navegação para essa página ----------------
    def _maybe_autorefresh(self):
        try:
            if getattr(self._conn, "connected", False):
                self._on_click_atualizar()
        except Exception:
            pass

    def on_page_activated(self) -> None:
        """Chamar ao navegar para esta página para auto‑atualizar se conectado."""
        self._maybe_autorefresh()        
        # refletir estado real do serviço de reconecção
        try:
            if self._conn is not None and hasattr(self._conn, "is_auto_reconnect_enabled") and self._conn.is_auto_reconnect_enabled():
                self.auto_reconnect.select()
            else:
                self.auto_reconnect.deselect()
        except Exception:
            self.auto_reconnect.deselect()




    # --------------------------------------------------------
    #  NOVOS COMANDOS PARA EDIÇÃO E SINALIZAÇÃO DOS MÓDULOS
    # --------------------------------------------------------

    def _init_editing_features(self) -> None:
        """Inicializa estado de edição/seleção e faz os binds necessários."""
        # Estado de edição por MAC: { mac: {"__baseline": {..}, "Slave ID": <novo>, "Nome": <novo>} }
        self._edited_rows: dict[str, dict] = {}
        # Editor in-place
        self._cell_editor = None
        self._cell_editor_info: dict | None = None

        # Seleção atual (MAC)
        self._selected_mac: str | None = None

        # Estados iniciais dos botões
        try:
            self.salvarModuloBtn.configure(state="disabled")
        except Exception:
            pass
        try:
            self.sinalizarModuloBtn.configure(state="disabled")
        except Exception:
            pass

        # Binds: seleção e duplo‑clique para edição
        try:
            self.table.tree.bind("<<TreeviewSelect>>", self._on_table_select, add="+")
            self.table.tree.bind("<Double-1>", self._on_table_double_click, add="+")
            #self.table.tree.bind("<Double-Button-1>", self._on_table_double_click, add="+")
        except Exception:
            pass


    def _on_table_select(self, _evt=None) -> None:
        """Atualiza MAC selecionado e habilita/desabilita o botão Sinalizar."""
        try:
            row = self.table.get_selected_row()
        except Exception:
            row = None
        self._selected_mac = (row or {}).get("Mac Address") if row else None
        self._refresh_signal_button_state()


    def _refresh_signal_button_state(self) -> None:
        try:
            state = "normal" if self._selected_mac else "disabled"
            self.sinalizarModuloBtn.configure(state=state)
        except Exception:
            pass





 
    def _tree_columns(self) -> list[str]:
        try:
            return list(self.table.tree.cget("columns") or ())
        except Exception:
            try:
                return list(getattr(self.table, "_all_cols", []) or [])
            except Exception:
                return []


    def _on_table_double_click(self, event):
        """Edita apenas 'Slave ID' e 'Nome'. Retorna 'break' para parar outros binds."""
        try:
            # Se já existe editor aberto, comita antes de abrir outro (permite re-editar a mesma linha)
            if getattr(self, "_cell_editor", None) is not None:
                try:
                    self._commit_cell_edit()
                except Exception:
                    self._cancel_cell_edit()
            tree = getattr(event, "widget", None) or self.table.tree
            region = getattr(tree, "identify_region", lambda x, y: tree.identify("region", x, y))(event.x, event.y)
            if region != "cell":
                return "break"
            row_iid = tree.identify_row(event.y)
            col_token = tree.identify_column(event.x)
            if not row_iid or not col_token:
                return "break"
            idx0 = int(col_token[1:]) - 1
            columns = list(tree.cget("columns") or ())
            if idx0 < 0 or idx0 >= len(columns):
                return "break"
            col_name = columns[idx0]  # exatamente as keys definidas
            if col_name not in ("Slave ID", "Nome"):
                return "break"
            self._start_cell_edit(tree, row_iid, idx0, col_name)
            return "break"
        except Exception:
            return "break"


    # --- editor in-place simples e confiável (tk.Entry como filho do Treeview) ---
    def _start_cell_edit(self, tree, row_iid: str, col_idx: int, col_name: str) -> None:
        import tkinter as tk

        # Fecha editor anterior, se houver
        if self._cell_editor is not None:
            try:
                self._commit_cell_edit()
            except Exception:
                try:
                    self._cancel_cell_edit()
                except Exception:
                    pass

        # Garante visibilidade e mede bbox
        try:
            tree.see(row_iid)
            x, y, w, h = tree.bbox(row_iid, f"#{col_idx+1}")
        except Exception:
            return
        if not w or not h:
            return

        current_value = tree.set(row_iid, col_name)
        mac_value = tree.set(row_iid, "Mac Address")

        # Baseline
        if mac_value and mac_value not in self._edited_rows:
            self._edited_rows[mac_value] = {
                "__baseline": {
                    "Slave ID": tree.set(row_iid, "Slave ID"),
                    "Nome": tree.set(row_iid, "Nome"),
                }
            }

        # tk.Entry é compatível com todos os temas
        editor = tk.Entry(tree, relief="flat", borderwidth=1, highlightthickness=1)
        editor.insert(0, str(current_value))
        editor.select_range(0, "end")
        editor.place(x=x, y=y, width=w, height=h)

        # Foco confiável (após pipeline do duplo clique)
        tree.after_idle(editor.focus_force)

        # Guarda contexto
        self._cell_editor = editor
        self._cell_editor_info = {
            "tree": tree,
            "iid": row_iid,
            "col_idx": col_idx,
            "col_name": col_name,
            "mac": mac_value,
            "old": current_value,
        }

        # Binds do editor
        editor.bind("<Return>", lambda e: self._commit_cell_edit())
        editor.bind("<KP_Enter>", lambda e: self._commit_cell_edit())
        editor.bind("<Escape>", lambda e: self._cancel_cell_edit())
        editor.bind("<FocusOut>", lambda e: self._commit_cell_edit())
        


    # --- commit/cancel + destaque visual + estado do botão Salvar ---
    def _commit_cell_edit(self) -> None:
        if not self._cell_editor or not self._cell_editor_info:
            return
        try:
            editor = self._cell_editor
            info = self._cell_editor_info
            new_val = editor.get()
            col_name = info["col_name"]
            row_iid = info["iid"]
            mac = info.get("mac")

            if col_name == "Slave ID":
                try:
                    new_val = self._sanitize_slave_id(new_val)
                except Exception:
                    v = (new_val or "").strip()
                    new_val = str(max(0, min(255, int(v)))) if v.isdigit() else ""
                if new_val == "":
                    # inválido: cancela e não marca edição
                    self._cancel_cell_edit()
                    return

            # Aplica na UI
            self.table.tree.set(row_iid, col_name, new_val)

            # Atualiza estado por MAC
            if mac:
                # Atualiza cache
                try:
                    if mac in getattr(self, "_rows_by_mac", {}):
                        self._rows_by_mac[mac][col_name] = new_val
                except Exception:
                    pass

                # Baseline & diff
                try:
                    b = self._edited_rows.get(mac, {}).get("__baseline", {})
                    cur_slave = self.table.tree.set(row_iid, "Slave ID")
                    cur_nome = self.table.tree.set(row_iid, "Nome")
                    changes = {}
                    if cur_slave != b.get("Slave ID"):
                        changes["Slave ID"] = cur_slave
                    if cur_nome != b.get("Nome"):
                        changes["Nome"] = cur_nome
                    if changes:
                        self._edited_rows.setdefault(mac, {"__baseline": b})
                        # Limpa chaves anteriores (exceto baseline) e grava atuais
                        for k in list(self._edited_rows[mac].keys()):
                            if k != "__baseline":
                                self._edited_rows[mac].pop(k, None)
                        self._edited_rows[mac].update(changes)
                    else:
                        self._edited_rows.pop(mac, None)
                except Exception:
                    pass

                # Destaque visual
                try:
                    self._update_row_edit_tag(mac)
                except Exception:
                    pass

            # Encerra editor
            try:
                editor.destroy()
            finally:
                self._cell_editor = None
                self._cell_editor_info = None

            # Estado do botão Salvar
            self._refresh_save_button_state()
        except Exception:
            try:
                self._cancel_cell_edit()
            except Exception:
                pass

    def _cancel_cell_edit(self) -> None:
        try:
            if self._cell_editor is not None:
                self._cell_editor.destroy()
        finally:
            self._cell_editor = None
            self._cell_editor_info = None


    def _ensure_edit_tag_style(self) -> None:
        """Configura a tag 'edited' com destaque VERMELHO (linha inteira)."""
        try:
            t = self.table.tree
            t.tag_configure("edited", background="#7f1d1d", foreground="#ffffff")
        except Exception:
            pass


    def _row_iid_by_mac(self, mac: str | None):
        if not mac:
            return None
        try:
            for iid in self.table.tree.get_children(""):
                if self.table.tree.set(iid, "Mac Address") == mac:
                    return iid
        except Exception:
            return None
        return None





    def _sanitize_slave_id(self, value: str) -> str:
        """Normaliza Slave ID. Mantém simples e defensivo."""
        v = (value or "").strip()
        if not v.isdigit():
            return ""  # inválido -> ignora alteração
        n = int(v)
        if n < 0:
            n = 0
        if n > 255:
            n = 255
        return str(n)


    def _mac_compact(self, mac: str | None) -> str:
        """Remove separadores (ex.: ':', '-', '.') e mantém apenas [0-9A-Za-z]."""
        try:
            return re.sub(r"[^0-9A-Za-z]", "", mac or "")
        except Exception:
            return (mac or "").replace(":", "").replace("-", "").replace(".", "")



    #------------------- atualização XXXX ------------------------
        

    def _update_row_edit_tag(self, mac: str) -> None:
        self._ensure_edit_tag_style()
        iid = self._row_iid_by_mac(mac)
        if not iid:
            return
        d = self._edited_rows.get(mac, {})
        has_changes = any(k != "__baseline" for k in d.keys())
        try:
            tags = set(self.table.tree.item(iid, "tags") or [])
            if has_changes:
                tags.add("edited")
            else:
                tags.discard("edited")
            self.table.tree.item(iid, tags=tuple(tags))
        except Exception:
            pass


    def _clear_all_edit_tags(self) -> None:
        try:
            for iid in self.table.tree.get_children(""):
                tags = set(self.table.tree.item(iid, "tags") or [])
                if "edited" in tags:
                    tags.discard("edited")
                    self.table.tree.item(iid, tags=tuple(tags))
        except Exception:
            pass


    def _apply_save_button_red(self, active: bool) -> None:
        """Muda a cor do botão Salvar para vermelho quando ativo; restaura quando inativo."""
        try:
            if active:
                self.salvarModuloBtn.configure(fg_color="#b91c1c", hover_color="#dc2626", text_color="#ffffff")
            else:
                if getattr(self, "_salvar_default_colors", None):
                    self.salvarModuloBtn.configure(**self._salvar_default_colors)
        except Exception:
            pass


    def _refresh_save_button_state(self) -> None:
        try:
            has_changes = any(any(k != "__baseline" for k in d.keys()) for d in self._edited_rows.values())
            if not hasattr(self, "_salvar_default_colors"):
                try:
                    self._salvar_default_colors = {
                        "fg_color": self.salvarModuloBtn.cget("fg_color"),
                        "hover_color": self.salvarModuloBtn.cget("hover_color"),
                        "text_color": self.salvarModuloBtn.cget("text_color"),
                    }
                except Exception:
                    self._salvar_default_colors = None
            if has_changes:
                self.salvarModuloBtn.configure(state="normal")
                self._apply_save_button_red(True)
            else:
                self.salvarModuloBtn.configure(state="disabled")
                self._apply_save_button_red(False)
        except Exception:
            pass





    # -------------------- COMANDOS --------------------

    def _on_click_sinalizarModulo(self) -> None:
        """ 
        Obtem a linha selecionada, obtem o mac do modulo, constroi comando, envia para modulo ocomando 
        para identificar ou localizar módulo slave da rede. Irá piscar teclado e ou led. 
        O comando usa Mac Address do módulo pois podem ter módulos com mesmo slave_id.
        Comando: SRF,15,8,<Mac Address><cr>
        Ação: Obtem a linha selecionada, obtem o mac do modulo, constroi comando, envia para modulo
        """
        try:
            mac = self._selected_mac
            mac = self._mac_compact(mac)
            if not mac:
                return
            cmd = f"SRF,15,8,{mac}\r"
            if callable(self._send):
                self._send(cmd)
        except Exception:
            pass


    def _on_click_salvarModulo(self) -> None:
        """
        Este comando é válido tanto na rede mesh quanto na rede 485 para efetivamente cadastrar 
        novos módulos na rede mesh e na rede 485. Esse comando é aceito tanto para módulos novos quanto 
        para módulos já cadastrados, permitindo alterar parâmetros gravados. 
        Comando: SRF,15,5,<macAddress>,<slaveID>,<nome><cr>
        Ação: Obter a linha selecionada, obtem o mac do modulo, constroi comando, envia para modulo
        Envia SRF,15,5,<mac>,<slave_id>,<nome> para CADA módulo com alterações.
        """
    def _on_click_salvarModulo(self) -> None:
        """Envia SRF,15,5,<mac>,<slave_id>,<nome> para CADA módulo com alterações."""
        try:
            if not self._edited_rows:
                return
            # Só MACs com mudanças além do baseline
            changed_macs = [mac for mac, d in self._edited_rows.items() if any(k != "__baseline" for k in d.keys())]
            if not changed_macs:
                return
            for mac in changed_macs:
                safe_mac = self._mac_compact(mac)
                if not safe_mac:
                    continue
                iid_match = None
                try:
                    for iid in self.table.tree.get_children(""):
                        if self.table.tree.set(iid, "Mac Address") == mac:
                            iid_match = iid
                            break
                except Exception:
                    iid_match = None

                if iid_match:
                    slave_id = self.table.tree.set(iid_match, "Slave ID")
                    nome = self.table.tree.set(iid_match, "Nome")
                else:
                    row = self._rows_by_mac.get(mac, {})
                    slave_id = str(row.get("Slave ID", ""))
                    nome = str(row.get("Nome", ""))

                cmd = f"SRF,15,5,{safe_mac},{slave_id},{nome}\r"
                if callable(self._send):
                    self._send(cmd)

            # Pós-salvamento
            self._clear_all_edit_tags()
            self._edited_rows.clear()
            self._refresh_save_button_state()
        except Exception:
            pass





 