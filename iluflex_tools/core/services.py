import socket
import threading
from datetime import datetime
from typing import Callable, List, Dict, Any
import time
import re

# --------- Conexão TCP ---------
class ConnectionService:
    """
    Cliente TCP simples com:
      - connect(ip, port), disconnect()
      - send(data) (str ou bytes)
      - listener em thread que dispara callbacks para eventos:
          { "type": "connect"|"disconnect"|"tx"|"rx"|"error",
            "ts": "HH:MM:SS.mmm",
            "remote": (ip,port),
            "text": "...",       # quando couber (utf-8)
            "raw": b"..."}       # bytes brutos (tx/rx)
    """
    def __init__(self):
        self.connected = False
        self._sock: socket.socket | None = None
        self._rx_thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._remote = ("", 0)
        self._listeners: List[Callable[[Dict[str, Any]], None]] = []
        self._auto_thread: threading.Thread | None = None
        self._auto_stop = threading.Event()
        self._auto_interval = 5.0
        self._listener_lock = threading.Lock()
        self._auto_reconnect_enabled = False  # quando True, desconexões disparam auto‑reconnect
        self._rx_buffer = bytearray()

    # ---- listeners ----
    def add_listener(self, cb: Callable[[Dict[str, Any]], None]):
        with self._listener_lock:
            if cb not in self._listeners:
                self._listeners.append(cb)

    def remove_listener(self, cb: Callable[[Dict[str, Any]], None]):
        with self._listener_lock:
            if cb in self._listeners:
                self._listeners.remove(cb)

    def _emit(self, ev: Dict[str, Any]):
        with self._listener_lock:
            listeners = list(self._listeners)
        for cb in listeners:
            try:
                cb(ev)
            except Exception:
                pass  # não derruba o loop de eventos

    # ---- conexão ----
    def connect(self, ip: str, port: int, timeout: float = 3.0) -> bool:
        self.disconnect()  # encerra conexão anterior, se houver
        self._remote = (ip, port)
        try:
            # notifica UI que vamos tentar conectar
            ts0 = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            self._emit({"type": "connecting", "ts": ts0, "remote": self._remote})

            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            print(f"[CONNECT] tentando {ip}:{port} ...")
            s.connect((ip, port))
            s.settimeout(0.5)
            self._sock = s
            self.connected = True
            self._stop.clear()
            self._rx_thread = threading.Thread(target=self._recv_loop, daemon=True)
            self._rx_thread.start()
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            self._emit({"type": "connect", "ts": ts, "remote": self._remote})
            print(f"[CONNECT] OK -> {ip}:{port}")
            return True
        except Exception as e:
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"{ts} [CONNECT] falhou: {e}")
            self._emit({"type": "error", "ts": ts, "remote": self._remote, "text": f"connect failed: {e}"})
            self._sock = None
            self.connected = False
            return False

    def auto_reconnect(self, interval: float = 5.0):
        """Tenta reconectar periodicamente após desconexão."""
        self._auto_interval = max(1.0, interval)
        # encerra thread anterior, se houver
        self._auto_stop.set()
        if self._auto_thread and self._auto_thread.is_alive():
            try:
                self._auto_thread.join(timeout=0)
            except Exception:
                pass
        self._auto_stop.clear()
        self._auto_thread = threading.Thread(target=self._auto_loop, daemon=True)
        self._auto_thread.start()

    def enable_auto_reconnect(self, enabled: bool = True, interval: float = 5.0):
        """Liga/desliga auto‑reconnect sem a UI precisar escutar eventos."""
        self._auto_reconnect_enabled = bool(enabled)
        if enabled:
            self.auto_reconnect(interval)
        else:
            self.stop_auto_reconnect()

    def stop_auto_reconnect(self):
        self._auto_stop.set()

    def _auto_loop(self):
        while not self._auto_stop.wait(self._auto_interval):
            if self.connected:
                continue
            ip, port = self._remote
            if ip and port:
                # avisa UI que estamos tentando reconectar
                ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                self._emit({"type": "reconnecting", "ts": ts, "remote": self._remote})
                self.connect(ip, port)


    def disconnect(self):
        if self._sock:
            try:
                print("[DISCONNECT] encerrando conexão ...")
                self._stop.set()
                try:
                    self._sock.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                self._sock.close()
            except Exception:
                pass
        self._sock = None
        if self.connected:
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            self._emit({"type": "disconnect", "ts": ts, "remote": self._remote})
        self.connected = False
        # se o modo auto estiver habilitado e a thread não estiver ativa, (re)inicia
        if self._auto_reconnect_enabled and not (self._auto_thread and self._auto_thread.is_alive()):
            try:
                self.auto_reconnect(self._auto_interval)
            except Exception:
                pass


    def _recv_loop(self):
        assert self._sock is not None
        while not self._stop.is_set():
            try:
                data = self._sock.recv(4096)
                if not data:
                    print("[RX] conexão encerrada pelo remoto")
                    break
                self._rx_buffer.extend(data)
                while True:
                    if not self._rx_buffer:
                        break
                    if self._rx_buffer[0] == 0xA5:
                        # Binary frame: A5 <opcode> <len> <payload...> <checksum>
                        if len(self._rx_buffer) < 3:
                            break
                        payload_len = self._rx_buffer[2]
                        total_len = 4 + payload_len
                        if len(self._rx_buffer) < total_len:
                            break
                        msg = bytes(self._rx_buffer[:total_len])
                        del self._rx_buffer[:total_len]
                    else:
                        idx = self._rx_buffer.find(b"\r")
                        if idx == -1:
                            break
                        msg = bytes(self._rx_buffer[:idx + 1])
                        del self._rx_buffer[:idx + 1]
                    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    text = msg.decode("utf-8", errors="replace")
                    print(f"[{ts}] RX {self._remote[0]}:{self._remote[1]} -> {text}")
                    self._emit({"type": "rx", "ts": ts, "remote": self._remote, "text": text, "raw": msg})
            except socket.timeout:
                continue
            except OSError:
                break
            except Exception as e:
                ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                self._emit({"type": "error", "ts": ts, "remote": self._remote, "text": f"rx error: {e}"})
                break
        self.disconnect()

    # ---- envio ----
    def send(self, data) -> bool:
        if not self.connected or not self._sock:
            print("[TX] não conectado.")
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            self._emit({"type": "error", "ts": ts, "remote": self._remote, "text": "send while not connected"})
            return False
        try:
            payload = data.encode("utf-8") if isinstance(data, str) else bytes(data)
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            dbg = payload.decode("utf-8", errors="replace")
            print(f"[{ts}] TX -> {dbg}")
            self._sock.sendall(payload)
            self._emit({"type": "tx", "ts": ts, "remote": self._remote, "text": dbg, "raw": payload})
            return True
        except (BrokenPipeError, ConnectionResetError, OSError) as e:
            print(f"[TX] erro: {e}")
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            self._emit({"type": "error", "ts": ts, "remote": self._remote, "text": f"tx error: {e}"})
            # garantir que listeners recebam o evento de disconnect
            self.disconnect()
            return False
        except Exception as e:
            print(f"[TX] erro: {e}")
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            self._emit({"type": "error", "ts": ts, "remote": self._remote, "text": f"tx error: {e}"})
            self.disconnect()
            return False
        
    # ---- util ----
    def get_remote(self) -> tuple[str, int]:
        return self._remote

# --------- OTA Services ---------
class OtaService:
    def run_fw_upgrade(self, firmware_path: str) -> str:
        return f"OTA iniciado com {firmware_path}"


class IrService:
    def preprocess(self, raw_sir2: str, pause_us: int, max_frames: int, normalize: bool) -> str:
        return "Resumo do pré-processo (stub)"

    def to_sir3(self, data: str) -> str:
        return "sir,3,... (stub)"

    def to_sir4(self, data: str) -> str:
        return "sir,4,... (stub)"


# --------- Descoberta de dispositivos na rede (UDP broadcast) ---------

class NetworkService:
    """Descoberta via UDP dos masters IC-315/IC-215."
    - Envia broadcast para 255.255.255.255:30303 a string:
        "Discovery: Who is out there?"
    - Recebe respostas em múltiplas linhas. Aceita **somente** payloads cujo
      PRIMEIRA linha começa com "Found:" ou "FOUND:".
    - Espera, no mínimo, as linhas (após a linha Found:):
        Nome, MAC, IP, Máscara, Gateway, DHCP[, Flag]
    - Retorna dicionários com chaves: NAME, MAC, IP, MASCARA, GATEWAY, DHCP, FLAG
    """

    def _get_local_ip(self) -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(('8.8.8.8', 80))
                return s.getsockname()[0]
            finally:
                s.close()
        except Exception:
            return '0.0.0.0'

    def _parse_response(self, payload: bytes) -> dict | None:
        try:
            text = payload.decode(errors="ignore").replace("\r", "")
            lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
            if not lines:
                return None
            # aceitar SOMENTE se a primeira linha começar com Found:
            first = lines[0]
            if not (first.startswith("Found:") or first.startswith("FOUND:")):
                return None

            # os demais campos são por posição; toleramos faltantes
            name    = lines[1] if len(lines) > 1 else ""
            mac     = lines[2] if len(lines) > 2 else ""
            ip      = lines[3] if len(lines) > 3 else ""
            mask    = lines[4] if len(lines) > 4 else ""
            gateway = lines[5] if len(lines) > 5 else ""
            dhcp    = lines[6] if len(lines) > 6 else ""
            flag    = lines[7] if len(lines) > 7 else ""

            # normalizações leves
            mac = mac.strip().lower()
            ip = ip.strip()
            mask = mask.strip()
            gateway = gateway.strip()
            dhcp = dhcp.strip()
            flag = flag.strip()

            return {
                "NAME": name,
                "MAC": mac,
                "IP": ip,
                "MASCARA": mask,
                "GATEWAY": gateway,
                "DHCP": dhcp,
                "FLAG": flag,
            }
        except Exception:
            return None

    def scan_masters(self, timeout_ms: int, on_found=None) -> list[dict]:
        """Varredura síncrona com deduplicação. Se `on_found` for fornecido,
        chama esse callback a cada dispositivo válido encontrado.
        """
        timeout_s = max(0.2, float(timeout_ms) / 1000.0)
        deadline = time.time() + timeout_s

        results: list[dict] = []
        seen: set[str] = set()   # chave: MAC ou IP

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            # Vincular ajuda em ambientes multi-homed (respostas unicast)
            local_ip = self._get_local_ip()
            try:
                sock.bind((local_ip, 0))
            except Exception:
                # fallback: deixa SO escolher
                pass

            sock.settimeout(0.2)
            # envia broadcast
            try:
                sock.sendto(b"Discovery: Who is out there?", ("255.255.255.255", 30303))
            except Exception:
                pass

            while time.time() < deadline:
                try:
                    data, addr = sock.recvfrom(4096)
                except socket.timeout:
                    continue
                except Exception:
                    break
                parsed = self._parse_response(data)
                if not parsed:
                    continue
                key = parsed.get("MAC") or parsed.get("IP") or repr(parsed)
                if key in seen:
                    continue
                seen.add(key)
                results.append(parsed)
                if on_found:
                    try:
                        on_found(parsed)
                    except Exception:
                        pass
        finally:
            try:
                sock.close()
            except Exception:
                pass

        return results

_MAC = re.compile(r'^[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}$')

def parse_rrf10_line(line: str) -> dict | None:
    """
    Converte UMA linha 'RRF,10,...' no dicionário com todos os campos.
    Campos:
      slave_id (int)
      mac (str)
      sinal_db (int)
      parent_mac (str)
      modelo (str)
      versao_hw (int)
      versao_fw (int)
      data_producao (str, ex.: '20250814')
      n_saidas (int)
      n_entradas (int)
      nome (str)
      raw (str)
    """
    if not line:
        return None
    line = line.strip()
    if not line.startswith("RRF,10,"):
        return None

    parts = [p.strip() for p in line.split(",")]
    # layout mínimo: 13 campos
    if len(parts) < 13:
        print(f"parse_rrf10_line faltou elementos, tem só {len(parts)}")
        return None

    try:
        # índices fixos pelo protocolo
        # 0:'RRF' 1:'10'
        slave_id      = int(parts[2])
        mac           = parts[3]
        sinal_db      = int(parts[4])   # pode ser negativo (RSSI) ou positivo
        parent_mac    = parts[5]
        modelo        = parts[6]
        versao_hw     = int(parts[7])
        versao_fw     = int(parts[8])
        data_producao = parts[9]
        n_saidas      = int(parts[10])
        n_entradas    = int(parts[11])
        # nome pode conter vírgulas? por segurança, junta o resto:
        nome          = ",".join(parts[12:]).strip()

        # valida MACs quando possível (não reprova; só corrige se inválido)
        if not _MAC.match(mac):
            # às vezes vem em minúsculas/sem padding — normalizamos pra minúsculas
            mac = mac.lower()
        if not _MAC.match(parent_mac):
            parent_mac = parent_mac.lower()

        return {
            "slave_id": slave_id,
            "mac": mac,
            "sinal_db": sinal_db,
            "parent_mac": parent_mac,
            "modelo": modelo,
            "versao_hw": versao_hw,
            "versao_fw": versao_fw,
            "data_producao": data_producao,
            "n_saidas": n_saidas,
            "n_entradas": n_entradas,
            "nome": nome,
            "raw": line,
        }
    except Exception as e:
        print("parse_rrf10_line error:", e)
        return None


def parse_rrf10_lines(texto: str) -> list[dict]:
    """Aceita um blob com várias linhas e retorna só as válidas RRF,10."""
    dispositivos = []
    if not texto:
        return dispositivos
    for raw in texto.splitlines():
        # print(f"services.parse_rrf10_lines line: {raw} !") # até aqui vem bem
        d = parse_rrf10_line(raw)
        if d:
            dispositivos.append(d)
    return dispositivos

