# iluflex_learner.py
import socket
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk
import customtkinter as ctk
import os
import sys
import json
import tempfile
from buttontags import BUTTON_TAGS
import ircode
import ir_decode  # mantido para compatibilidade futura

# ========================= NOVA LÓGICA (RESUMO) ==============================
"""
- Pré-processamento SEMPRE parte de `raw_sir2_data` (entrada capturada/read-only).
- O editor (`toConvert`) é livre; use o botão "Copiar para entrada" para promover um `sir,2`
  do editor a `raw_sir2_data` e então reprocessar com os parâmetros atuais.
- Alterar parâmetros (`pause_threshold`, `max_frames`, `normalize`) reprocessa **apenas** se
  houver `raw_sir2_data` (mantém previsibilidade e evita sobrescrever edições do editor).
- Converter SEMPRE lê do editor atual (`toConvert`). O seletor "Tipo de código" define o
  formato da saída:
    * Iluflex Short → saída compactada (`sir,3` preferível; fallback `sir,4`) quando a
      entrada é `sir,2`. Se já for `sir,3/4`, apenas replica.
    * Iluflex Long  → saída expandida (`sir,2`) quando a entrada é `sir,3/4`. Se já for
      `sir,2`, apenas replica.
- Gráficos: "recebido" = `raw_sir2_data`; "otimizado" = `toConvert`; "convertido" = um
  `sir,2` derivado (ex.: reconstituição de `sir,3/4`).
- Importante: preservar exatamente `
` e `
` recebidos; só adicionar `
` temporário
  ao chamar funções que exigem, sem alterar o conteúdo exibido ao usuário.
"""
# ============================================================================

# ------------------------- ESTADO GLOBAL ------------------------------------
client_socket = None
listener_thread = None
connected = False
learner_on = False
DEBUG = True

# buffers/dados
raw_sir2_data: str = ""  # último sir,2 recebido cru do learner (ou copiado via botão)
last_converted_sir2: str = ""  # sir,2 reconstituído a partir de sir,3/sir,4 (para plot)

# widgets/controls globais (inicializados no main)
canvas_overlay: tk.Canvas | None = None
canvas_label_overlay: tk.Label | None = None
output_convert_field: scrolledtext.ScrolledText | None = None
toConvert_text: scrolledtext.ScrolledText | None = None
input_field: scrolledtext.ScrolledText | None = None
tag_select: ttk.Combobox | None = None
pre_process_result_label: ctk.CTkLabel | None = None
pan_slider: ctk.CTkSlider | None = None

# variáveis Tk
pause_threshold_var: tk.StringVar | None = None
max_frames_var: tk.StringVar | None = None
normalize_var: tk.BooleanVar | None = None
toConvert_var: tk.StringVar | None = None
x_scale_var: tk.DoubleVar | None = None
tipo_codigo_var: tk.StringVar | None = None  # Iluflex Short/Long
repeat_var: tk.StringVar | None = None

# ------------------------- CONFIG -------------------------------------------
temp_dir = tempfile.gettempdir()
config_file = os.path.join(temp_dir, 'iluflexToolsConfig.json')

def load_config(parameter: str):
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config_data = json.load(f)
            return config_data.get(parameter, '')
    return ''

def save_config(parameter: str, value):
    config_data = {}
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config_data = json.load(f)
    config_data[parameter] = value
    with open(config_file, 'w') as f:
        json.dump(config_data, f, indent=4)

def resource_path(relative_path: str):
    # compatível com PyInstaller
    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ------------------------- REDE/LEARNER -------------------------------------

def listen(input_field, status_label, connect_button, learner_var, learner_switch):
    global client_socket, connected, learner_on, raw_sir2_data, pause_threshold_var, toConvert_text

    try:
        buffer = ""
        while connected:
            data = client_socket.recv(4096)
            if not data:
                break
            # preserva bytes recebidos; decode ignorando inválidos
            buffer += data.decode(errors="ignore")
            while "\r" in buffer:
                message, buffer = buffer.split("\r", 1)
                if message:
                    input_field.config(state=tk.NORMAL)
                    input_field.insert(tk.END, message + "\n")
                    # Mantém apenas as 10 últimas linhas (não altera conteúdo crú)
                    lines = input_field.get("1.0", tk.END).splitlines()
                    if len(lines) > 10:
                        lines = lines[-10:]
                        input_field.delete("1.0", tk.END)
                        input_field.insert(tk.END, "\n".join(lines) + "\n")
                    input_field.see(tk.END)
                    input_field.config(state=tk.DISABLED)

                # estados do learner
                if "RIR,LEARNER,ON" in message:
                    learner_on = True
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

    except Exception as e:
        status_label.config(text=f"Erro: {e}", fg="red")
    finally:
        connected = False
        client_socket = None
        connect_button.configure(text="Conectar")
        status_label.config(text="Desconectado", fg="red")

def toggle_connection(ip_entry, port_entry, input_field, status_label, connect_button, learner_var, learner_switch):
    global client_socket, connected, listener_thread, pause_threshold_var, toConvert_text
    if connected:
        connected = False
        if client_socket:
            try:
                client_socket.close()
            finally:
                client_socket = None
        connect_button.configure(text="Conectar")
        status_label.config(text="Desconectado", fg="red")
        return

    # conectar
    ip = ip_entry.get().strip()
    try:
        port = int(port_entry.get().strip())
    except ValueError:
        messagebox.showerror("Erro", "Porta inválida")
        return
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((ip, port))
        connected = True
        connect_button.configure(text="Desconectar")
        status_label.config(text=f"Conectado a {ip}:{port}", fg="green")
        save_config("last_host", ip)
        save_config("last_port", port)
        listener_thread = threading.Thread(
            target=listen,
            args=(input_field, status_label, connect_button, learner_var, learner_switch),
            daemon=True,
        )
        listener_thread.start()
    except Exception as e:
        messagebox.showerror("Erro", f"Não foi possível conectar: {e}")
        connected = False
        client_socket = None

def toggle_learner():
    global client_socket, connected, learner_on
    if not connected or not client_socket:
        return
    if learner_on:
        client_socket.sendall(b"sir,l,0\r")
    else:
        client_socket.sendall(b"sir,l,1\r")

def send_message(entry):
    global client_socket, connected
    if connected and client_socket:
        msg = entry.get().strip()
        if msg:
            client_socket.sendall((msg + "\r").encode())
            save_config("last_message", msg)

# ----------------------- Filtro de Button Tag -----------------------------
            
# Grupo "Comuns" (sem ac_* e sem z2_*; esses ficam nos grupos AC/Receiver)
category_prefixes = {
    "Comuns":   ["channel_", "volume_", "menu", "power_", "cursor_", "back_return", "exit_cancel"],

    # grupos já existentes
    "AC":       ["ac_"],
    "TV":       ["channel_", "volume_", "func_", "menu", "home", "guide", "digit_", "cursor_", "pip_"],
    "Receiver": ["input_", "preset_", "surround_", "bass_", "treble_", "z2_", "matrix_", "audio_"],
    "Midia":    ["tr_", "skip", "open_close_eject",
                 "netflix", "youtube", "youtube_music", "primevideo", "globoplay", "disneyplus"],
    # "Outros" é dinâmico (calculado abaixo)
}

def _match_prefix_or_token(tag: str, token: str) -> bool:
    # token com '_' = prefixo; sem '_' = termo exato OU prefixo seguido de '_'
    if token.endswith("_"):
        return tag.startswith(token)
    return (tag == token) or tag.startswith(token + "_")

def _in_any_category(tag: str) -> bool:
    for cat, prefs in category_prefixes.items():
        if cat == "Outros":
            continue
        if any(_match_prefix_or_token(tag, p) for p in prefs):
            return True
    return False

# Tudo que não bateu nos grupos acima vai para "Outros"
OUTROS_TAGS = sorted([t for t in BUTTON_TAGS if not _in_any_category(t)])



def filter_tags(var_list, tag_select_widget, var_todos=None, var_comuns=None, var_outros=None):
    """
    var_list = [var_ac, var_tv, var_rx, var_md] (StringVar: "AC"/"" etc.)
    var_comuns = BooleanVar (True/False)
    var_outros = BooleanVar (True/False)
    var_todos  = BooleanVar  (True/False) -> master (marca/desmarca todos)
    """
    # 1) Reflete no "Todos" se de fato TODOS estão marcados
    all_selected = (
        (var_comuns.get() if var_comuns else False) and
        (var_outros.get() if var_outros else False) and
        (var_list[0].get() == "AC") and
        (var_list[1].get() == "TV") and
        (var_list[2].get() == "Receiver") and
        (var_list[3].get() == "Midia")
    )
    if var_todos is not None and var_todos.get() != all_selected:
        var_todos.set(all_selected)

    # 2) Monta união dos grupos marcados
    selected = set()

    # AC/TV/Receiver/Midia por prefixos
    selected_prefixes = []
    category_order = ["AC", "TV", "Receiver", "Midia"]
    for cat, var in zip(category_order, var_list):
        if var.get():
            selected_prefixes += category_prefixes.get(cat, [])
    for tag in BUTTON_TAGS:
        if any(_match_prefix_or_token(tag, p) for p in selected_prefixes):
            selected.add(tag)

    # Comuns (sem ac_* e sem z2_* por definição dos tokens usados)
    if var_comuns and var_comuns.get():
        for tag in BUTTON_TAGS:
            if any(_match_prefix_or_token(tag, p) for p in category_prefixes["Comuns"]):
                selected.add(tag)

    # Outros (tudo que sobrou)
    if var_outros and var_outros.get():
        selected.update(OUTROS_TAGS)

    filtered = sorted(selected)
    tag_select_widget["values"] = filtered
    if filtered:
        tag_select_widget.current(0)
    else:
        tag_select_widget.set("")

# ------------------------- PRÉ-PROCESSO E BOTÕES ----------------------------

def copiar_para_entrada():
    """Promove um `sir,2` do editor para a entrada crua (`raw_sir2_data`) e reprocessa.
    - Só aceita `sir,2`. Para `sir,3/4` mostra aviso e não altera a entrada.
    """
    global raw_sir2_data, input_field, toConvert_text
    if toConvert_text is None:
        return
    texto = toConvert_text.get("1.0", "end-1c")  # preservar tal como está; não strip para manter finais se houver
    trimmed = texto.strip()
    if not trimmed:
        messagebox.showinfo("Copiar para entrada", "Campo está vazio.")
        return
    if not trimmed.startswith("sir,2,"):
        messagebox.showwarning("Copiar para entrada", "Apenas formato Long é aceito aqui (sir,2). Para sir,3/sir,4 use Converter → Iluflex Long.")
        return
    # Define a nova entrada crua EXATAMENTE como no editor (não adicionar/criar aqui)
    raw_sir2_data = trimmed
    # Atualiza campo de entrada com o comando copiado.
    input_field.config(state=tk.NORMAL)
    input_field.delete("1.0", tk.END)
    input_field.insert("1.0", trimmed + '\n')
    input_field.config(state=tk.DISABLED)

    reprocess_from_raw()


def reprocess_from_raw():
    """Reexecuta o pré-processamento a partir do `raw_sir2_data` usando os parâmetros atuais."""
    if not raw_sir2_data:
        messagebox.showinfo("Pré-processamento", "Nenhuma entrada capturada. Use 'Copiar para entrada' ou capture um comando.")
        return
    try:
        pause_threshold = int(pause_threshold_var.get().strip()) if pause_threshold_var else 40000
        max_frames = int(max_frames_var.get()) if max_frames_var else 3
        normalize = bool(normalize_var.get()) if normalize_var else True
        normalized = ircode.extract_optimized_frame(raw_sir2_data, pause_threshold, max_frames, normalize)
        new_sir2 = normalized.get("new_sir2", "")
        if new_sir2:
            if toConvert_text is not None:
                toConvert_text.delete("1.0", tk.END)
                toConvert_text.insert("1.0", new_sir2)
            if toConvert_var is not None:
                toConvert_var.set(new_sir2)
            update_preproc_overlay(normalized)
    except Exception as e:
        messagebox.showerror("Pré-processamento", f"Erro ao reprocessar: {e}")
    finally:
        atualizar_grafico()

# ------------------------- GRÁFICOS -----------------------------------------

def extract_pulses_from_sir2(sir2_str: str) -> list[int]:
    """Extrai lista de pulsos (tempos) de um comando sir,2.
    Tenta índices de início diferentes (6 e 8) para tolerar variações de cabeçalho.
    Retorna [] quando não for possível.
    """
    if not sir2_str or not sir2_str.startswith("sir,2,"):
        return []
    body = sir2_str[6:]  # remove 'sir,2,'
    parts = [p for p in body.strip().split(',') if p != ""]

    candidates: list[list[int]] = []
    for start in (6, 8):
        try:
            pulses = [int(tok) for tok in parts[start:]]
            if pulses:
                candidates.append(pulses)
        except Exception:
            pass
    if candidates:
        # escolhe o que tiver mais dados
        return max(candidates, key=len)

    # última tentativa: tentar converter tudo em int e usar a partir de 6
    try:
        ints = [int(tok) for tok in parts]
        return ints[6:] if len(ints) > 6 else []
    except Exception:
        return []



def draw_waveform_overlay(canvas: tk.Canvas, series: list[dict], height: int, x_scale: float):
    """Desenha múltiplas trilhas no canvas.
    series: lista de dicts { 'pulses': list[int], 'label': str, 'color': str }
    """
    if canvas is None:
        return

    canvas.delete("all")
    valid_series = [s for s in series if s.get('pulses')]
    if not valid_series:
        return

    # comprimento total em micros (para scroll)
    lengths = [sum(s['pulses']) for s in valid_series]
    if not lengths:
        return

    max_len = max(lengths)
    content_width = max_len * x_scale + 20
    canvas.config(scrollregion=(0, 0, content_width, height))
    # --- sincroniza o CTkSlider de Pan com a posição atual do Canvas ---
    try:
        if pan_slider is not None:
            first, _last = canvas.xview()
            pan_slider.set(first)
    except Exception:
        pass

    def draw_oscilloscope(pulses: list[int], base_y: int, color: str):
        x = 10.0
        high = base_y - 10
        low = base_y + 10
        is_on = True
        for duration in pulses:
            length = duration * x_scale
            if is_on:
                canvas.create_line(x, low, x, high, fill=color, width=2)
                canvas.create_line(x, high, x + length, high, fill=color, width=2)
                canvas.create_line(x + length, high, x + length, low, fill=color, width=2)
            else:
                canvas.create_line(x, low, x + length, low, fill=color, width=1)
            x += length
            is_on = not is_on

    base = 22
    gap = 28
    for idx, s in enumerate(valid_series):
        draw_oscilloscope(s['pulses'], base_y=base + idx * gap, color=s.get('color', 'black'))

    # --- RÉGUA DE TEMPO (ms) ---
    def _choose_steps(px_per_ms: float) -> tuple[float, float]:
        # devolve (major_ms, minor_ms)
        if px_per_ms >= 80:
            return 1.0, 0.5
        elif px_per_ms >= 40:
            return 2.0, 1.0
        elif px_per_ms >= 20:
            return 5.0, 1.0
        elif px_per_ms >= 10:
            return 10.0, 5.0
        else:
            return 20.0, 10.0

    # total em ticks e ms
    max_len = max(lengths)                     # já calculado acima
    TICKS_PER_MS = 625.0                       # 1000 / 1.6
    total_ms = max_len / TICKS_PER_MS
    px_per_ms = x_scale * TICKS_PER_MS

    base_y = height - 15
    left_x = 10.0
    right_x = 10.0 + max_len * x_scale

    # linha base
    canvas.create_line(left_x, base_y, right_x, base_y, fill="#999", width=1)

    major_ms, minor_ms = _choose_steps(px_per_ms)

    # rótulo "0 ms" discreto à esquerda
    canvas.create_text(left_x, base_y + 2, text="0", anchor="n",
                       font=("TkDefaultFont", 7), fill="#666")
    canvas.create_text(left_x + 14, base_y + 2, text="ms", anchor="n",
                       font=("TkDefaultFont", 7), fill="#666")

    # major ticks + labels
    import math
    n_major = int(math.floor(total_ms / major_ms)) + 1
    for k in range(1, n_major + 1):  # começa em 1 para não duplicar o "0"
        ms = k * major_ms
        x = left_x + ms * px_per_ms
        if x > right_x: break
        canvas.create_line(x, base_y, x, base_y - 6, fill="#777", width=1)
        canvas.create_text(x, base_y + 2, text=f"{int(ms)}", anchor="n",
                           font=("TkDefaultFont", 7), fill="#666")

    # minor ticks entre majors (sem rótulo)
    if minor_ms > 0:
        n_minor = int(math.floor(total_ms / minor_ms)) + 1
        for j in range(n_minor + 1):
            ms = j * minor_ms
            # pula se coincide com major (evita duplicar)
            if abs((ms / major_ms) - round(ms / major_ms)) < 1e-6:
                continue
            x = left_x + ms * px_per_ms
            if x > right_x: break
            canvas.create_line(x, base_y, x, base_y - 4, fill="#bbb", width=1)

def show_waveform_multi():
    """Monta e plota as trilhas disponíveis: recebido, otimizado e convertido."""
    global canvas_overlay, canvas_label_overlay

    series: list[dict] = []

    # recebido (cru)
    raw_pulses = extract_pulses_from_sir2(raw_sir2_data)
    if raw_pulses:
        series.append({"pulses": raw_pulses, "label": "recebido", "color": "green"})

    # otimizado (prioriza conteúdo do editor)
    optimized_cmd = ""
    try:
        if toConvert_text is not None:
            optimized_cmd = toConvert_text.get("1.0", "end-1c").strip()
    except Exception:
        optimized_cmd = ""
    if not optimized_cmd and toConvert_var is not None:
        try:
            optimized_cmd = toConvert_var.get().strip()
        except Exception:
            optimized_cmd = ""

    opt_pulses = extract_pulses_from_sir2(optimized_cmd)
    if opt_pulses:
        series.append({"pulses": opt_pulses, "label": "otimizado", "color": "darkblue"})

    # convertido (sir3/sir4 -> sir2)
    conv_pulses = extract_pulses_from_sir2(last_converted_sir2)
    if conv_pulses:
        rep_count = get_rep_from_cmd(last_converted_sir2)  # lê do header (campo 6)
        conv_pulses = repeat_pulses(conv_pulses, rep_count)
        series.append({"pulses": conv_pulses, "label": "convertido", "color": "darkgoldenrod"})

    # desenha
    scale = float(x_scale_var.get()) / 10.0 if x_scale_var is not None else 0.05
    draw_waveform_overlay(canvas_overlay, series=series, height=110, x_scale=scale)

    # legenda
    if canvas_label_overlay is not None:
        labels = ", ".join([s['label'] for s in series]) if series else "(nenhum dado disponível)"
        canvas_label_overlay.config(text=f"Forma de onda: {labels}")



# ------------------------- AUX UI -------------------------------------------
        
def on_canvas_xscroll(*args):
    """Mantém o CTkSlider de pan sincronizado com a posição horizontal do Canvas."""
    try:
        # Tk chama com dois args: (first, last) como strings.
        if pan_slider is not None and len(args) >= 2:
            first = float(args[0])
            pan_slider.set(first)
    except Exception as e:
        print("xscroll sync err:", e)

def atualizar_grafico():
    try:
        show_waveform_multi()
    except Exception as e:
        print("Erro ao atualizar gráfico:", e)

def _sync_from_editor(update_plot: bool = True):
    """Mantém `toConvert_var` espelhando o editor e prepara `last_converted_sir2` para o
    gráfico se o editor tiver sir,3/4. Não promove automaticamente ao `raw_sir2_data`.
    """
    global last_converted_sir2, toConvert_text
    if toConvert_text is None:
        return
    text = toConvert_text.get("1.0", "end-1c").strip()
    if toConvert_var is not None:
        toConvert_var.set(text)
    if text.startswith("sir,3") or text.startswith("sir,4"):
        try:
            last_converted_sir2 = ircode.sir34tosir2(text).strip()
        except Exception:
            last_converted_sir2 = ""
    if update_plot:
        atualizar_grafico()


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




# ------------------------- EDITOR/CONVERSOR ---------------------------------
def update_rep_field(cmd: str, rep: int) -> str:
    """Atualiza o campo 6 (Repeat) do header em sir,2/sir,3/sir,4 — sem alterar o restante."""
    if not cmd or not cmd.startswith("sir,"):
        return cmd
    # rep = max(1, min(int(rep), 3))  # limita 1..3 não vamos limitar aqui !
    s = cmd.strip()
    # preserva \r/\n finais, se existirem
    trailer = ""
    while s and s[-1] in "\r\n":
        trailer = s[-1] + trailer
        s = s[:-1]
    parts = s.split(",")
    if len(parts) > 6 and parts[0] == "sir" and parts[1] in ("2", "3", "4"):
        parts[6] = str(rep)
        return ",".join(parts) + trailer
    return cmd

def get_rep_from_cmd(cmd: str) -> int:
    """Lê o campo Rep (índice 6) de um sir,2/3/4. Retorna 1 se não conseguir."""
    try:
        if not cmd or not cmd.startswith("sir,"):
            return 1
        parts = cmd.strip().split(",")
        return int(parts[6]) if len(parts) > 6 else 1
    except Exception:
        return 1

def repeat_pulses(pulses: list[int], rep: int) -> list[int]:
    """Repete a sequência completa de pulsos rep vezes (mantém a pausa longa final entre frames)."""
    if rep <= 1 or not pulses:
        return pulses
    return pulses * rep    

def converter_comando():
    """Converte conforme o tipo selecionado, usando SEMPRE o texto atual do editor.
    - Iluflex Short: se entrada é sir,2 → compacta (sir,3 preferível, senão sir,4). Se já for sir,3/4, replica.
    - Iluflex Long:  se entrada é sir,3/4 → expande para sir,2. Se já for sir,2, replica.
    Preserva `\n e \r do editor; apenas adiciona `\r` temporário quando APIs exigirem.
    """
    global last_converted_sir2
    global toConvert_text, output_convert_field, tag_select, tipo_codigo_var

    if toConvert_text is None:
        return
    cmd = toConvert_text.get("1.0", "end-1c")  # preservar tal como está
    trimmed = cmd.strip()
    if not trimmed:
        messagebox.showinfo("Converter", "Nada para converter.")
        return

    tipo = tipo_codigo_var.get() if tipo_codigo_var is not None else "Iluflex Short"

    out = None
    try:
        if tipo == "Iluflex Long":
            # Saída precisa ser sir,2
            if trimmed.startswith("sir,3") or trimmed.startswith("sir,4"):
                out = ircode.sir34tosir2(trimmed).strip()
                rep = int(repeat_var.get()) if repeat_var is not None else 1
                out = update_rep_field(out, rep)
                last_converted_sir2 = out  # gráfico "convertido"
            elif trimmed.startswith("sir,2"):
                out = trimmed  # já está em Long; apenas replica
                rep = int(repeat_var.get()) if repeat_var is not None else 1
                out = update_rep_field(out, rep)
                last_converted_sir2 = out
            else:
                messagebox.showwarning("Converter", "Formato desconhecido. Esperado sir,2 ou sir,3/sir,4.")
                return
        else:
            # Iluflex Short: saída precisa ser sir,3/sir,4
            if trimmed.startswith("sir,2"):
                # Adiciona \r só para a função que necessita, sem modificar o editor
                cmd_for_conv = trimmed + '\r'
                pulsos = ircode.conversion(cmd_for_conv)
                if not isinstance(pulsos, list) or len(pulsos) == 0:
                    messagebox.showerror("Converter", "Falha ao converter para pulsos.")
                    return
                converted = None
                try:
                    converted = ircode.compatibility_to_compressed(pulsos.copy())
                except Exception:
                    converted = None
                if not converted:
                    try:
                        converted = ircode.CompatibilityToCompressII(pulsos)
                    except Exception:
                        converted = None
                if not converted:
                    messagebox.showerror("Converter", "Não foi possível compactar (sir,3/sir,4).")
                    return
                out = converted.strip()
                rep = int(repeat_var.get()) if repeat_var is not None else 1
                out = update_rep_field(out, rep)  # só troca o header (campo 6), sem recompactar, para atualizar nr de repetições
                # para o gráfico "convertido", reconstituímos sir,2
                try:
                    last_converted_sir2 = ircode.sir34tosir2(out).strip()
                except Exception:
                    last_converted_sir2 = ""
            elif trimmed.startswith("sir,3") or trimmed.startswith("sir,4"):
                out = trimmed  # já está em Short; apenas replica
                rep = int(repeat_var.get()) if repeat_var is not None else 1
                out = update_rep_field(out, rep)  # só troca o header (campo 6), sem recompactar, para atualizar nr de repetições
                try:
                    last_converted_sir2 = ircode.sir34tosir2(out).strip()
                except Exception:
                    last_converted_sir2 = ""
            else:
                messagebox.showwarning("Converter", "Formato desconhecido. Esperado sir,2 ou sir,3/sir,4.")
                return
    finally:
        pass

    # escreve na saída
    if output_convert_field is not None and tag_select is not None and out is not None:
        tag = tag_select.get().strip()
        output_convert_field.insert("end", f"{tag}	{out} \n")
        output_convert_field.see("end")
        atualizar_grafico()


# ------------------------- MAIN (UI) ----------------------------------------

def main():
    global pause_threshold_var, max_frames_var, normalize_var, toConvert_var, x_scale_var, tipo_codigo_var
    global canvas_overlay, canvas_label_overlay, output_convert_field, toConvert_text, tag_select
    global last_converted_sir2, input_field
    global pre_process_result_label, pan_slider, repeat_var

    root = tk.Tk()
    root.title("Iluflex Learner para IC-315 v.2.2.0")
    root.geometry("960x740")
    try:
        root.iconbitmap(resource_path('iluflex-Learner-icon.ico'))
    except Exception:
        pass  # ícone é opcional

    # ----- Vars: Inicialização de valores -----
    pause_threshold_var = tk.StringVar(value="40000")
    max_frames_var = tk.StringVar(value="3")
    normalize_var = tk.BooleanVar(value=True)
    toConvert_var = tk.StringVar()
    learner_var = tk.BooleanVar()
    x_scale_var = tk.DoubleVar(value=0.05)
    tipo_codigo_var = tk.StringVar(value="Iluflex Short")
    repeat_var = tk.StringVar(value="1")

    # tema/escala (opcional)
    ctk.set_appearance_mode("system")          # "light" | "dark" | "system"
    ctk.set_default_color_theme("dark-blue")   # ou "dark-blue", "green" ou tema custom
    # ctk.set_widget_scaling(1.0)              # ajuste se quiser botões maiores

    # ----- Helpers -----

    def CButton(parent, text, command=None, variant="primary", **kw):
        # cores neutras que ficam boas no claro/escuro; ajuste se quiser
        palette = {
            "primary":   dict(fg_color="#ACC1ED", hover_color="#8091C0", text_color="#161616"),
            "secondary": dict(fg_color="#e5e7eb", hover_color="#d1d5db", text_color="#111827"),
            "danger":    dict(fg_color="#dc2626", hover_color="#b91c1c", text_color="white"),
        }
        style = palette.get(variant, palette["primary"])
        # tamanhos padrão — pode sobrescrever via kwargs
        defaults = dict(width=50, height=24, corner_radius=4, font=("Segoe UI", 12, "bold"),
                        border_width=1, border_color="#223146")
        defaults.update(style)
        defaults.update(kw)
        return ctk.CTkButton(parent, text=text, command=command, **defaults)

    def validate_pause_threshold_on_focus_out(event=None):
        try:
            value = int(pause_threshold_var.get())
            if value < 1000:
                pause_threshold_var.set("1000")
            elif value > 50000:
                pause_threshold_var.set("50000")
        except ValueError:
            pause_threshold_var.set("40000")

    def clear_output():
        global last_converted_sir2, raw_sir2_data

        if input_field is not None:
            input_field.config(state=tk.NORMAL)
            input_field.delete("1.0", tk.END)
            input_field.config(state=tk.DISABLED)

        if output_convert_field is not None:
            output_convert_field.delete("1.0", tk.END)
        if toConvert_text is not None:
            toConvert_text.delete("1.0", tk.END)
        if toConvert_var is not None:
            toConvert_var.set("")
        last_converted_sir2 = ""
        raw_sir2_data = ""
        update_preproc_overlay(None)
        atualizar_grafico()

    def on_close():
        global client_socket, connected
        try:
            if connected and client_socket:
                client_socket.close()
        finally:
            connected = False
            root.destroy()



    # ----- Top bar -----
    top_frame = tk.Frame(root)
    top_frame.pack(fill="x", padx=10, pady=5)

    tk.Label(top_frame, text="IP:").grid(row=0, column=0, padx=5)
    ip_entry = tk.Entry(top_frame, width=20)
    ip_entry.insert(0, load_config("last_host"))
    ip_entry.grid(row=0, column=1, padx=5)

    tk.Label(top_frame, text="Porta:").grid(row=0, column=2, padx=5)
    port_entry = tk.Entry(top_frame, width=8)
    port_entry.insert(0, load_config("last_port") or "4999")
    port_entry.grid(row=0, column=3, padx=5)

    connect_button = CButton(top_frame, text="Conectar")
    connect_button.grid(row=0, column=4, padx=5)
    connect_button.configure(command=lambda: toggle_connection(
        ip_entry, port_entry, input_field, status_label, connect_button, learner_var, learner_switch ))
    
    learner_switch_label = tk.Label(top_frame, text="Modo Learner:")
    learner_switch_label.grid(row=0, column=5, padx=(10,2), pady=2)

    def on_learner_segment_change(val: str):
        # val é "OFF" ou "ON"; só envia comando se realmente mudou
        desired = (val == "ON")
        if connected and (desired != learner_on):
            toggle_learner()  # envia sir,l,1 ou sir,l,0 conforme estado atual

    learner_switch = ctk.CTkSegmentedButton(
        top_frame,
        values=["OFF", "ON"],
        command=on_learner_segment_change,
        # estética compatível com seu Primary (pílula com borda)
        corner_radius=6, border_width=1,
        width=100, height=24,
        selected_color="#ACC1ED",           # ON
        selected_hover_color="#8091C0",
        unselected_color="#E5E7EB",         # OFF
        unselected_hover_color="#D1D5DB",
        text_color="#161616",
    )
    learner_switch.grid(row=0, column=6, padx=5)
    learner_switch.set("OFF")

    status_label = tk.Label(top_frame, text="Desconectado", fg="red")
    status_label.grid(row=0, column=7, padx=10, pady=2)

    # botão conectar
    input_field = scrolledtext.ScrolledText(root, wrap=tk.WORD, height=3, font=("Consolas", 10))
    input_field.pack(fill="both", expand=True, padx=10, pady=5)
    input_field.config(state=tk.DISABLED)



    # ----- Pré-processo -----
    pre_process_frame = tk.Frame(root)
    pre_process_frame.pack(fill="x", padx=10, pady=5)

    tk.Label(pre_process_frame, text="Comando otimizado para conversão:").grid(row=0, column=0, padx=2, pady=2, sticky="w")

    tk.Label(pre_process_frame, text="pause_threshold:").grid(row=0, column=1, padx=(20, 1), pady=2, sticky="w")
    pause_entry = tk.Entry(pre_process_frame, textvariable=pause_threshold_var, width=10)
    pause_entry.grid(row=0, column=2, padx=(1, 2), pady=2)
    pause_entry.bind("<FocusOut>", validate_pause_threshold_on_focus_out)
    pause_entry.bind("<FocusOut>", lambda e: reprocess_from_raw())

    tk.Label(pre_process_frame, text="max_frames:").grid(row=0, column=3, padx=(20, 1), pady=2, sticky="w")
    maxframes_select = ttk.Combobox(pre_process_frame, textvariable=max_frames_var, values=["1", "2", "3", "4"], width=8)
    maxframes_select.grid(row=0, column=4, padx=(1, 2), pady=2)
    maxframes_select.bind("<<ComboboxSelected>>", lambda e: reprocess_from_raw())
    maxframes_select.bind("<FocusOut>", lambda e: reprocess_from_raw())

    tk.Label(pre_process_frame, text="normalizar dados:").grid(row=0, column=5, padx=(20, 1), pady=2, sticky="w")
    normalize_check = tk.Checkbutton(pre_process_frame, text="Sim", variable=normalize_var, command=reprocess_from_raw)
    normalize_check.grid(row=0, column=6, padx=(1, 10), pady=2)

    # Botão Copiar para entrada (promove sir,2 do editor para raw_sir2_data e reprocessa)
    copiar_btn = CButton(pre_process_frame, text="Copiar para entrada", command=copiar_para_entrada)
    copiar_btn.grid(row=0, column=7, sticky="w", padx=10, pady=2)

    toConvert_text = scrolledtext.ScrolledText(pre_process_frame, height=3, font=("Consolas", 10), wrap=tk.WORD)
    toConvert_text.grid(row=1, column=0, columnspan=8, sticky="we", padx=5, pady=4)
    pre_process_frame.grid_columnconfigure(0, weight=1)

    pre_process_result_label = tk.Label(pre_process_frame, text="Pré processamento:")
    pre_process_result_label.grid(row=2, column=0, columnspan=8, padx=10, pady=2, sticky="w")

    # Eventos de edição: apenas sincroniza espelho/plot (NÃO promove para entrada)
    def _on_editor_change(_event=None):
        _sync_from_editor(update_plot=True)
    toConvert_text.bind("<KeyRelease>", _on_editor_change)

    # ----- Canvas -----
    canvas_frame = tk.Frame(root)
    canvas_frame.pack(fill="both", expand=False, padx=10, pady=(4, 8))

    canvas_overlay = tk.Canvas(canvas_frame, height=110, bg="white")
    canvas_overlay.pack(fill="x", padx=5, pady=(2, 0))

    canvas_label_overlay = tk.Label(canvas_frame, text="Forma de onda: (aguardando dados)")
    canvas_label_overlay.pack(anchor="w", padx=5, pady=(0, 2))

    zoom_row_frame = tk.Frame(root)
    zoom_row_frame.pack(fill="x", padx=10, pady=(0, 2))

    ctk.CTkLabel(zoom_row_frame, text="Zoom horizontal:").pack(side="left", padx=(5, 4))

    def _on_zoom_change(val):
        try:
            x_scale_var.set(float(val))
            atualizar_grafico()
        except Exception as e:
            print("zoom slider error:", e)

    zoom_slider = ctk.CTkSlider(
        zoom_row_frame,
        from_=0.01, to=1.0, number_of_steps=200,
        width=240, height=14,  # ↑ altura deixa a trilha visível
        command=_on_zoom_change,
    )
    zoom_slider.set(x_scale_var.get())
    zoom_slider.pack(side="left", padx=(6, 10), pady=(2, 2))

    ctk.CTkLabel(zoom_row_frame, text="Pan:").pack(side="left", padx=(4, 4))

    # Slider que “anda” o canvas horizontalmente (0.0 à esquerda, 1.0 à direita)
    pan_slider = ctk.CTkSlider(
        zoom_row_frame,
        from_=0.0, to=1.0, number_of_steps=1000,
        width=420, height=14,
        command=lambda v: canvas_overlay.xview_moveto(float(v)),
    )
    pan_slider.pack(side="left", fill="x", expand=True, padx=(6, 10), pady=(2, 2))

    # Faz o Canvas avisar o slider quando a posição mudar (mouse, teclas, etc.)
    canvas_overlay.config(xscrollcommand=on_canvas_xscroll)


    # ----- Tags/Filters -----
    btag_frame = tk.Frame(root)
    btag_frame.pack(fill="x", padx=10, pady=5)

    tk.Label(btag_frame, text="Button Tag:").grid(row=0, column=2, padx=5, pady=2, sticky="w")
    tag_select = ttk.Combobox(btag_frame, values=BUTTON_TAGS, width=20)
    tag_select.grid(row=0, column=3, padx=5, pady=2)
    tag_select.current(0)

    var_ac = tk.StringVar(value="AC")
    var_tv = tk.StringVar(value="TV")
    var_rx = tk.StringVar(value="Receiver")
    var_md = tk.StringVar(value="Midia")

    var_comuns = tk.BooleanVar(value=True)   # Comuns ligado por padrão
    var_outros = tk.BooleanVar(value=False)  # Outros desligado por padrão
    var_todos  = tk.BooleanVar(value=True)   # Master ligado por padrão (mostra tudo)

    cb_frame = tk.Frame(btag_frame)
    cb_frame.grid(row=0, column=5, padx=5)

    def _apply_filter():
        filter_tags([var_ac, var_tv, var_rx, var_md],
                    tag_select,
                    var_todos=var_todos,
                    var_comuns=var_comuns,
                    var_outros=var_outros)

    def on_todos_change():
        state = var_todos.get()
        # "Todos" marca/desmarca TODOS os grupos
        var_comuns.set(state)
        var_outros.set(state)
        var_ac.set("AC" if state else "")
        var_tv.set("TV" if state else "")
        var_rx.set("Receiver" if state else "")
        var_md.set("Midia" if state else "")
        _apply_filter()

    # Checkboxes (na ordem desejada)
    tk.Checkbutton(cb_frame, text="Comuns",  variable=var_comuns,
                onvalue=True, offvalue=False, command=_apply_filter).pack(side="left")

    tk.Checkbutton(cb_frame, text="AC",       variable=var_ac,
                onvalue="AC", offvalue="", command=_apply_filter).pack(side="left")
    tk.Checkbutton(cb_frame, text="TV",       variable=var_tv,
                onvalue="TV", offvalue="", command=_apply_filter).pack(side="left")
    tk.Checkbutton(cb_frame, text="Receiver", variable=var_rx,
                onvalue="Receiver", offvalue="", command=_apply_filter).pack(side="left")
    tk.Checkbutton(cb_frame, text="Midia",    variable=var_md,
                onvalue="Midia", offvalue="", command=_apply_filter).pack(side="left")

    tk.Checkbutton(cb_frame, text="Outros",   variable=var_outros,
                onvalue=True, offvalue=False, command=_apply_filter).pack(side="left")

    tk.Checkbutton(cb_frame, text="Todos",    variable=var_todos,
                onvalue=True, offvalue=False, command=on_todos_change).pack(side="left")

    # Popular a combobox inicialmente
    _apply_filter()


    # ----- Conversor -----
    converter_frame = tk.Frame(root)
    converter_frame.pack(fill="x", padx=10, pady=5)

    tk.Label(converter_frame, text="Parâmetros para conversão: Tipo Código:").grid(row=2, column=0, padx=5, pady=2, sticky="w")
    tipo_select = ttk.Combobox(converter_frame, textvariable=tipo_codigo_var, values=["Iluflex Short", "Iluflex Long"], width=15)
    tipo_select.grid(row=2, column=1, padx=5, pady=2)
    tipo_select.current(0)

    tk.Label(converter_frame, text="Repetições:").grid(row=2, column=2, padx=5, pady=2, sticky="w")
    repeat_var = tk.StringVar(value="1")
    repeat_select = ttk.Combobox(
        converter_frame, textvariable=repeat_var,
        values=["1", "2", "3", "4"], width=3, state="readonly"
    )
    repeat_select.grid(row=2, column=3, padx=5, pady=2)

    converter_button = CButton(converter_frame, text="Converter", command=lambda: ( _sync_from_editor(update_plot=False), converter_comando()))
    converter_button.grid(row=2, column=5, padx=5, pady=2)

    atualizar_grafico_button = CButton(converter_frame, text="Atualizar Gráfico", command=lambda: _sync_from_editor(update_plot=True))
    atualizar_grafico_button.grid(row=2, column=6, padx=5, pady=2)

    # ----- Saída -----
    tk.Label(root, text="Comandos Convertidos:").pack(anchor="w", padx=10)
    output_convert_field = scrolledtext.ScrolledText(root, wrap=tk.WORD, height=3, font=("Consolas", 10))
    output_convert_field.pack(fill="both", expand=True, padx=10, pady=5)

    # ----- Envio/limpeza -----
    send_frame = tk.Frame(root)
    send_frame.pack(fill="x", padx=10, pady=20)

    msg_entry = tk.Entry(send_frame)
    msg_entry.insert(0, load_config("last_message"))
    msg_entry.pack(side="left", fill="x", expand=True, padx=5)

    clear_button = CButton(send_frame, text="Limpar mensagens", width=15, command=clear_output)
    clear_button.pack(side="right", padx=10)

    send_button = CButton(send_frame, text="Enviar", command=lambda: send_message(msg_entry))
    send_button.pack(side="right", padx=5)

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
