
from typing import List

# Configuracao
PAUSE_THRESHOLD_US = 15000
TOLERANCE = 0.2
DEBUG = False
max_pause_before_cut = 0  # variável global

class CompressError(Exception):
    """Exceção mínima para reportar erros específicos de compressão (sir,4).
    Mantém o código enxuto e permite captura no nível superior."""
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code

class IrCodeLib:

    @staticmethod
    def preProcessIrCmd(irCmd: str, pause_threshold: int, max_frames: int, normalize: bool):
        """ Faz pré processamento de comandos no formato sir,2 
            Parametros:  irCmd: str, pause_threshold: int, max_frames: int, normalize: bool
            return: dict {"returned_frames", "equal_frames_detected", "pairs_preserved", "total_frames_received", "new_sir2", "pulses_normalized" }
        """
        if irCmd.startswith("sir,2,"):
            ircmd = irCmd.strip()
            pause_threshold = pause_threshold if pause_threshold > 1000 and pause_threshold < 80000 else 40000
            max_frames = max_frames if max_frames >= 1 and max_frames <= 4 else 3

            try: 
                out = extract_optimized_frame(ircmd, pause_threshold, max_frames, normalize)
                # sir2_str = out.get("new_sir2", "")
                return out
            except Exception as conv_err:
                    error = f"Erro em conversão {conv_err}"
                    print (error)
                    return {
                        "error": error
                    }
                    

    @staticmethod
    def convertIRCmd(ircmd: str, tipo: str, repeat: int, channel: int):
        """ Converte comandos de IR aceitando formatos sir,2 sir,3 e sir,4.
            tipo: 'Iluflex Long' ou 'Iluflex Short'
            repeat: número de repetições
        """
        trimmed = ircmd.strip()
        rep = repeat if (repeat is not None and repeat > 0 and repeat < 4) else 1
        chan = channel if (repeat is not None and repeat > 0 and repeat < 127) else 1
        error = ""
        plot_data = ""
        out = ""
        try:
            if tipo == "Iluflex Long":
                # Saída precisa ser sir,2
                if trimmed.startswith("sir,3") or trimmed.startswith("sir,4"):
                    out = sir34tosir2(trimmed)
                    out = update_rep_channel_fields(out, rep, chan)
                    plot_data = out

                elif trimmed.startswith("sir,2"):
                    out = trimmed  # já está em Long; apenas replica
                    out = update_rep_channel_fields(out, rep, chan)
                    plot_data = out
                else:
                    return {
                        "converted": "",
                        "plot_data": "",
                        "error": "Erro: Formato desconhecido. Esperado sir,2 ou sir,3/sir,4."
                    }

                # convertou, retorna
                return {
                    "converted": out,
                    "plot_data": plot_data,
                    "error": error
                }
            
            else:
                # Iluflex Short: saída precisa ser sir,3/sir,4
                if trimmed.startswith("sir,2"):
                    # Adiciona \r só para a função que necessita, sem modificar o editor
                    cmd_for_conv = trimmed + '\r'
                    pulsos = conversion(cmd_for_conv)
                    if not isinstance(pulsos, list) or len(pulsos) == 0:
                        return {
                            "converted": "",
                            "plot_data": "",
                            "error": "Erro: Falha interna ao converter para pulsos"
                        }
                    if pulsos[0] > (len(pulsos) - 6):
                        return {
                            "converted": "",
                            "plot_data": "",
                            "error": f"Erro: Dados insuficientes para número de pulsos = {pulsos[0]} len pulsos = {len(pulsos)}"
                        }
                    converted = None
                    try:
                        converted = compatibility_to_compressed(pulsos.copy())
                    except Exception as e:
                        converted = None
                        print(f"CompatibilityToCompressed exception:", e)
                        error = e
                    if not converted:
                        try:
                            converted = CompatibilityToCompressII(pulsos)
                        except Exception as e:
                            print(f"CompatibilityToCompressII exception:", e)
                            error = e
                            converted = None
                    if not converted or not error == "":
                        return {
                            "converted": "",
                            "plot_data": "",
                            "error": f"Error: Não foi possível compactar (sir,3/sir,4). {error}"
                        }
                    
                    out = converted.strip()
                    out = update_rep_channel_fields(out, rep, chan)  # só troca o header (campo 6), sem recompactar, para atualizar nr de repetições
                    # para o gráfico "convertido", reconstituímos sir,2
                    try:
                        plot_data = sir34tosir2(out).strip()
                    except Exception:
                        plot_data = ""

                elif trimmed.startswith("sir,3") or trimmed.startswith("sir,4"):
                    out = trimmed  # já está em Short; apenas replica
                    out = update_rep_channel_fields(out, rep, chan)  # só troca o header (campo 6), sem recompactar, para atualizar nr de repetições
                    try:
                        plot_data = sir34tosir2(out).strip()
                    except Exception:
                        plot_data = ""
                else:
                    return {
                        "converted": "",
                        "plot_data": "",
                        "error": "Error: Formato desconhecido. Esperado sir,2 ou sir,3/sir,4."
                    }
                
                # Se nada falhou, retorna dados.
                return {
                    "converted": out,
                    "plot_data": plot_data,
                    "error": ""
                }
            
        except Exception as e:
            error = e
            if DEBUG: print(f"Erro de exception: {error}")
            return {
                "converted": "",
                "plot_data": "",
                "error": f"Erro de exception: {error}"
            }

        finally:
            pass



# Conversor fiel do comando sir (2, 3, 4, 5, 6, 7) para vetor de pulsos em Python
# Lembrar que precisa ter \r ou \n no final do comandos !
def conversion(buffer: str) -> list[int]:
    pulso = [0] * 1000
    pulsosfinal = [0] * 1000
    buf = [0] * 6
    state = 0
    contBuf = 0
    contPulso = 0
    formato = None

    if len(buffer) < 5:
        if (DEBUG): print("[Debug] Buffer muito curto")
        return []

    pos = 0
    while pos < len(buffer):
        x = buffer[pos]
        pos += 1

        # print(f"[Debug] State: {state}, Char: {x}, Pos: {pos}")

        match state:
            case 0:
                state = 1 if x == 's' else 0
            case 1:
                state = 2 if x == 'i' else 0
            case 2:
                state = 3 if x == 'r' else 0
            case 3:
                state = 4
            case 4:
                if x == '2':
                    state = 5
                    formato = '2'
                elif x == '3':
                    state = 20
                    formato = '3'
                elif x == '4':
                    state = 10
                    formato = '4'
                elif x == '5':
                    state = 5
                    formato = '5'
                elif x == '6':
                    state = 5
                    formato = '6'
                elif x == '7':
                    state = 15
                    formato = '7'
                if (DEBUG): print(f"[Debug] Detected formato: {formato}")
            case 5:
                if x == ',':
                    state = 6
                    buf = [0] * 6
                    contBuf = contPulso = 0
            case 6:
                if x in ('\r', '\n', ' ', '\\'):
                    valor = int(''.join([chr(b) for b in buf if b != 0]))
                    if (DEBUG): print(f"[Debug] Fim de pulsos [{contPulso}]: {valor}")
                    pulso[contPulso] = valor
                    if pulso[contPulso] > 65500:
                        if (DEBUG): print("[Debug] Valor de pulso acima do permitido")
                        return []
                    if formato == '2':
                        pulsosfinal = iluflex_to_compatibility(pulso)
                        # print(f"pulsosfinal ({pulsosfinal[0]}):", ",".join(map(str, pulsosfinal[0:])))
                        return pulsosfinal[0:(pulsosfinal[0]+6)]
                    state = 30
                elif x == ',':
                    valor = int(''.join([chr(b) for b in buf if b != 0]))
                    # if (DEBUG): print(f"[Debug] Novo pulso[{contPulso}]: {valor}")
                    pulso[contPulso] = valor
                    if pulso[contPulso] > 65500:
                        if (DEBUG): print("[Debug] Valor de pulso acima do permitido")
                        return []
                    contPulso += 1
                    if contPulso > 900:
                        if (DEBUG): print("[Debug] pulso excede limite")
                        return []
                    buf = [0] * 6
                    contBuf = 0
                elif '0' <= x <= '9':
                    buf[contBuf] = ord(x)
                    contBuf += 1
                    if contBuf > 5:
                        if (DEBUG): print("[Debug] contBuf excede 5")
                        return []
                else:
                    if (DEBUG): print("[Debug] Caractere inválido no estado 6")
                    return []
            
            # monitorar mensagem sir,4
            case 10:
                if x == ',':
                    state = 11
                    buf = [0] * 6
                    contBuf = 0
                    contPulso = 0
                else:
                    if (DEBUG): print('[Debug] Falha no estado 10 (esperava vírgula)')
                    return []


            case 11:
                if x == ',':
                    # normaliza para convASCIIToInt (direita→esquerda)
                    tmp = [0] * 6
                    for i in range(contBuf):
                        tmp[i] = buf[6 - contBuf + i]
                    for i in range(contBuf, 6):
                        tmp[i] = 48
                    valor = convASCIIToInt(tmp)
                    if (DEBUG): print(f"[sir4][header] pulso[{contPulso}] = {valor}")
                    if valor > 65500 or valor <= 0:
                        return []
                    pulso[contPulso] = valor
                    contPulso += 1
                    if contPulso > 900:
                        return []
                    buf = [0] * 6
                    contBuf = 0
                    if contPulso == 8:
                        state = 12
                elif '0' <= x <= '9':
                    # direita→esquerda
                    if contBuf > 5:
                        return []
                    buf[5 - contBuf] = ord(x)
                    contBuf += 1
                else:
                    return []
            case 12:
                if x == ',':
                    buf = [0] * 6
                    contBuf = 0
                    state = 13
                else:
                    ox = ord(x)
                    if 65 <= ox <= 90:  # A-Z
                        pulso[contPulso] = ox
                        contPulso += 1
                        if contPulso > 900:
                            return []
                    elif 97 <= ox <= 122:  # a-z (4x)
                        for _ in range(4):
                            pulso[contPulso] = ox
                            contPulso += 1
                            if contPulso > 900:
                                return []
                    else:
                        return []
            case 13: # inicio da recepcao do buffer footer
                if x == ',':
                    tmp = [0] * 6
                    for i in range(contBuf):
                        tmp[i] = buf[6 - contBuf + i]
                    for i in range(contBuf, 6):
                        tmp[i] = 48
                    valor = convASCIIToInt(tmp)
                    if (DEBUG): print(f"[sir4][footer] pulso[{contPulso}] = {valor}")
                    if valor > 65500 or valor <= 0:
                        return []
                    pulso[contPulso] = valor
                    contPulso += 1
                    if contPulso > 900:
                        return []
                    buf = [0] * 6
                    contBuf = 0
                elif '0' <= x <= '9':
                    if contBuf > 5:
                        return []
                    buf[5 - contBuf] = ord(x)
                    contBuf += 1
                else:
                    # fim (0x0d ou ponto)
                    tmp = [0] * 6
                    for i in range(contBuf):
                        tmp[i] = buf[6 - contBuf + i]
                    for i in range(contBuf, 6):
                        tmp[i] = 48
                    valor = convASCIIToInt(tmp)
                    if valor > 65500 or valor <= 0:
                        return []
                    pulso[contPulso] = valor
                    contPulso += 1
                    if contPulso > 900:
                        return []
                    pulso[contPulso] = 0
                    contPulso += 1
                    state = 30

            # ---------------- sir,7 ----------------
            case 15:
                if x == ',':
                    state = 16
                    buf = [0] * 6
                    contBuf = 0
                    contPulso = 0
                else:
                    return []
            case 16:
                if x == ',':
                    tmp = [0] * 6
                    for i in range(contBuf):
                        tmp[i] = buf[6 - contBuf + i]
                    for i in range(contBuf, 6):
                        tmp[i] = 48
                    valor = convASCIIToInt(tmp)
                    if valor > 65500:
                        return []
                    pulso[contPulso] = valor
                    contPulso += 1
                    if contPulso > 900:
                        return []
                    buf = [0] * 6
                    contBuf = 0
                    if contPulso == 6:
                        state = 17
                elif '0' <= x <= '9':
                    if contBuf > 5:
                        return []
                    buf[5 - contBuf] = ord(x)
                    contBuf += 1
                else:
                    return []
            case 17:
                ox = ord(x)
                if (97 <= ox <= 122) or (48 <= ox <= 57):
                    pulso[contPulso] = ox
                    contPulso += 1
                    if contPulso > 900:
                        return []
                else:
                    if contPulso == 26:
                        state = 30
                    else:
                        return []

            # ---------------- sir,3 ----------------
            case 20:
                if x == ',':
                    state = 21
                else:
                    return []
                buf = [0] * 6
                contBuf = 0
                contPulso = 0
                zip = 0
            case 21:
                ox = ord(x)
                if x in ('\r', '\n', ' ', '\\'):
                    valor = int(''.join([chr(b) for b in buf if b != 0])) if contBuf > 0 else 0
                    pulso[contPulso] = valor
                    state = 30
                elif x == ',' and zip == 0:
                    valor = int(''.join([chr(b) for b in buf if b != 0])) if contBuf > 0 else 0
                    pulso[contPulso] = valor
                    if pulso[contPulso] > 65500 or pulso[contPulso] <= 0:
                        return []
                    contPulso += 1
                    if contPulso > 900:
                        return []
                    if contPulso == 12:
                        zip = 1
                        msbByte = 1
                    buf = [0] * 6
                    contBuf = 0
                elif x == ',' and zip == 1:
                    zip = 0
                    contBuf = 0
                elif zip == 1 and msbByte == 1:
                    pulso[contPulso] = ox << 8
                    msbByte = 0
                elif zip == 1 and msbByte == 0:
                    pulso[contPulso] = pulso[contPulso] + ox
                    contPulso += 1
                    if contPulso > 900:
                        return []
                    msbByte = 1
                else:
                    if not (33 <= ox <= 126):
                        return []
                    buf[contBuf] = ox
                    contBuf += 1
                    if contBuf > 5:
                        return []

            case 30:
                break

    if state == 30:
        if contPulso > 900:
            if (DEBUG): print("[Debug] pulso excede 900 no final")
            return []
        if (DEBUG): print(f"[Debug] Conversão finalizada com {contPulso} pulsos")
        return pulso[:contPulso + 1]

    if (DEBUG): print("[Debug] Estado final não chegou a 30")
    return []

def iluflex_to_compatibility(pulso: List[int]) -> List[int]:
    """Converte vetor sir,2 (pulsos em ticks 1,6 µs) para vetor "compatível"
    usado na compactação (tempos em N ciclos, como sir,3/sir,4).

    - Campo 3 do header é convertido de Per (0,1 µs) para freq (Hz) com
      divisão inteira, espelhando o C (1e7 // Per).
    - Cada tempo t2 (>= índice 6) vira N = round_half_up(16*t2/Per).
    """
    if len(pulso) < 7:
        return []
    if pulso[3] == 0:
        return []

    buffer_out = [0] * max(len(pulso), pulso[0] + 6)

    # Copia campos de header 0..5
    for i in range(0, 6):
        buffer_out[i] = pulso[i]

    periodo = pulso[3]  # Per em 0,1 µs
    # ESP usa divisão inteira aqui (no C: 10000000 / Per)
    buffer_out[3] = 10_000_000 // periodo

    # Converte todos os tempos após o header para N (ciclos)
    plen = pulso[0] + 6
    for i in range(6, plen):
        ti = pulso[i]
        buffer_out[i] = sir2_to_sir34_per(ti, periodo) if ti > 0 else 0

    return buffer_out


def add_bit_stateful(pulso: list[int], bit_pos: int, bit_state: int, word_store_map: dict[int, int]) -> int:
    pulso_loc = (bit_pos // 8) + 12
    bit_loc = bit_pos % 8

    if bit_loc == 0:
        word_store_map[pulso_loc] = 0x4141

    word_store = word_store_map.get(pulso_loc, 0x4141)

    if bit_loc == 0 and bit_state:
        word_store |= 0x2000
    elif bit_loc == 1 and bit_state:
        word_store |= 0x1000
    elif bit_loc == 2 and bit_state:
        word_store |= 0x0800
    elif bit_loc == 3 and bit_state:
        word_store |= 0x0200
        word_store &= 0xFEFF
    elif bit_loc == 4 and bit_state:
        word_store |= 0x0020
    elif bit_loc == 5 and bit_state:
        word_store |= 0x0010
    elif bit_loc == 6 and bit_state:
        word_store |= 0x0008
    elif bit_loc == 7 and bit_state:
        word_store |= 0x0002
        word_store &= 0xFFFE

    word_store_map[pulso_loc] = word_store

    if bit_pos >= 7:
        if pulso_loc >= len(pulso):
            pulso.extend([0] * (pulso_loc - len(pulso) + 1))
        pulso[pulso_loc] = word_store

    # if (DEBUG): print(f"[Debug Add Bit] bit: {bit_state} bit_pos: {bit_pos} pulso_loc: {pulso_loc} bit_loc: {bit_loc} word_store: {word_store} ")

    return pulso_loc

# Converte pulsos em formato sir,3
def compatibility_to_compressed(pulso: list[int]) -> str | int:
    if pulso[0] < 26:
        raise CompressError("PULSE_COUNT_TOO_SMALL", f"Quantidade de pulsos < 26 (valor: {pulso[0]})")
    
    if pulso[8] < 2 or pulso[9] < 2:
        raise CompressError("PULSE_TIME_TOO_SMALL", f"Tempo pulso muito curto < 2 (valores {pulso[8]}:{pulso[9]})")

    on0, off0 = pulso[8], pulso[9]
    cont_bit = 0
    word_store_map = {}

    pos = add_bit_stateful(pulso, cont_bit, 0, word_store_map)
    cont_bit += 1
    on1 = off1 = 0

    for i in range(10, pulso[0] - 2, 2):
        if pulso[i] < 2 or pulso[i+1] < 2:
            raise CompressError("PULSE_TIME_TOO_SMALL", f"Tempo pulso muito curto < 2 (valor: {pulso[i]})")
        
        p_on, p_off = pulso[i], pulso[i + 1]
        if (on0 - 5 <= p_on <= on0 + 5) and (off0 - 5 <= p_off <= off0 + 5):
            pos = add_bit_stateful(pulso, cont_bit, 0, word_store_map)
            cont_bit += 1
        elif on1 == 0:
            on1, off1 = p_on, p_off
            pos = add_bit_stateful(pulso, cont_bit, 1, word_store_map)
            cont_bit += 1
        elif (on1 - 5 <= p_on <= on1 + 5) and (off1 - 5 <= p_off <= off1 + 5):
            pos = add_bit_stateful(pulso, cont_bit, 1, word_store_map)
            cont_bit += 1
        else:
            return 0

    if on1 == 0:
        on1, off1 = on0, off0

    pulso[10] = on1
    pulso[11] = off1


    # guarda o último pulso no formato original, permitindo guardar terminações diferentes.
    pulso[pos + 1] = pulso[pulso[0]-2]
    pulso[pos + 2] = pulso[pulso[0]-1]

    total_bit = (pulso[0] - 10) // 2    # 106 - 10 // 2 = 96 / 2 = 48
    pulso_loc = ((total_bit - 1) // 8) + 12

    buffer_str = "sir,3"
    for i in range(12):
        buffer_str += "," + str(pulso[i])

    buffer_str += ","

    for i in range(12, pulso_loc + 1):
        high_byte = (pulso[i] >> 8) & 0xFF
        low_byte = pulso[i] & 0xFF
        buffer_str += chr(high_byte)
        buffer_str += chr(low_byte)

    for i in range(pulso_loc + 1, pulso_loc + 3):
        if pulso[i] < 2:
            raise CompressError("PULSE_TIME_TOO_SMALL", f"Tempo pulso muito curto < 2 (valor: {pulso[i]})")
        
        buffer_str += "," + str(pulso[i])

    return buffer_str

# Converte pulsos em formato sir,4
def CompatibilityToCompressII(pulso: list[int]) -> str | int:

    # if (DEBUG): print(f"Pulsos recebidos ({pulso[0]}):", ",".join(map(str, pulso[0:])))

    if pulso[0] < 12:
        raise CompressError("PULSE_COUNT_TOO_SMALL", f"Quantidade de pulsos < 12 (valor: {pulso[0]})")

    different_times_arr = [0] * 20
    number_of_different_times = 0
    out_buffer = "sir,4"

    # Header: pulso[0] is the count, then next 7 elements
    for i in range(8):
        out_buffer += f",{pulso[i]}"
    
    out_buffer += ","

    # Identify different pulse lengths
    # starting position 8 keep 2 first pulses and 2 last out
    for i in range(8, pulso[0] - 2):
        if pulso[i] < 2:
            raise CompressError("PULSE_TIME_TOO_SMALL", f"Tempo pulso muito curto < 2 (valor: {pulso[i]})")

        number_of_different_times += 1
        different_times_arr[number_of_different_times] = pulso[i]
        if (DEBUG): print(f"[DEBUG] Scan pulse {i}: {pulso[i]} at index {number_of_different_times}, array: {different_times_arr[:20]}")

        # Find other pulses with similar time
        number_of_equal_times = 0
        for j in range(8, pulso[0] - 2):
            toln = pulso[j] - (2 + 0.01 * pulso[j])
            tolp = pulso[j] + (2 + 0.01 * pulso[j])
            if toln < pulso[i] < tolp:
                number_of_equal_times += 1
              
        #  Verify if pulse time is already stored in DifferentTimesArr
        if number_of_equal_times > 1:
            rp = 0
            for j in range(1, number_of_different_times + 1):
                toln = different_times_arr[j] - (2 + 0.01 * different_times_arr[j])
                tolp = different_times_arr[j] + (2 + 0.01 * different_times_arr[j])
                if toln < pulso[i] < tolp:
                    rp += 1
            if rp > 1:
                number_of_different_times -= 1

        if number_of_different_times > 17:
            print(f"Erro, ultrapassou 16 references, numberOfDifferentTimes = {number_of_different_times}, numberOfEqualTimes = {number_of_equal_times}")
            return 0

    # Compression
    buffer3 = ['\0'] * 10
    char_position = 0
    cp = 0

    for i in range(8, pulso[0] - 2):
        c = chr(0x58)  # default 'X'
        # compress level I
        for j in range(1, number_of_different_times + 1):
            toln = different_times_arr[j] - (2 + 0.01 * different_times_arr[j])
            tolp = different_times_arr[j] + (2 + 0.01 * different_times_arr[j])
            if toln < pulso[i] < tolp:
                c = chr(0x40 + j)  # '@'+j from ascii: 0x40 = @ , 0x41 = A , 0x42 = B ...

        # compress level II
        # cp guarda a posição sendo bit 0 para A e bit 1 para B
        buffer3[char_position] = c
        char_position += 1

        if c == 'A':
            cp = cp & 0xFF
        elif c == 'B':
            cp = cp | (0x01 << (char_position - 1))
        else:
            # Adiciona os caracteres quando tiver tempo diferente do A ou B
            for j in range(char_position):
                out_buffer += buffer3[j]
            char_position = 0
            cp = 0

        if char_position > 3:
            out_buffer += chr(0x61 + cp) # 0x61 = 'a'
            char_position = 0
            cp = 0
    
    # guarda as poisções finais se ainda tiver.
    if char_position > 0:
        for j in range(char_position):
            out_buffer += buffer3[j]

    # Last two pulses
    for i in range(pulso[0] - 2, pulso[0]):
        if pulso[i] < 2:
            raise CompressError("PULSE_TIME_TOO_SMALL", f"Tempo pulso muito curto < 2 (valor: {pulso[i]})")
        
        out_buffer += f",{pulso[i]}"

    # add reference values to the end of command.
    for i in range(1, number_of_different_times + 1):
        out_buffer += f",{different_times_arr[i]}"

    return out_buffer



# Verifica se dois blocos de pares sao similares com tolerancia percentual
def blocks_are_similar(block1, block2, tolerance=TOLERANCE):
    if len(block1) != len(block2):
        return False
    for (a1, b1), (a2, b2) in zip(block1, block2):
        if abs(a1 - a2) > max(a1, a2) * tolerance or abs(b1 - b2) > max(b1, b2) * tolerance:
            return False
    return True

# Faz a media de varios blocos de pares
def average_multiple_blocks(blocks):
    averaged = []
    for i in range(len(blocks[0])):
        ons = [frame[i][0] for frame in blocks]
        offs = [frame[i][1] for frame in blocks]
        averaged.append([int(round(sum(ons)/len(ons))), int(round(sum(offs)/len(offs)))])
    return averaged

# Trunca após primeira pausa longa e retorna apenas o primeiro frame,
# usando o maior tempo de pausa anterior como pausa final
def truncate_after_first_pause(pairs, pause_threshold):
    print(f"pause_threshold = {pause_threshold}")
    global max_pause_before_cut
    cut_index = None
    max_pause_before_cut = 0
    for idx, pair in enumerate(pairs):
        if len(pair) == 2:
            if pair[1] >= pause_threshold:
                cut_index = idx
                break
            max_pause_before_cut = max(max_pause_before_cut, pair[1])

    if cut_index is not None:
        trimmed = pairs[:cut_index]  # até antes da pausa longa
        trimmed.append([pairs[cut_index][0], max_pause_before_cut])  # adiciona pulso com pausa ajustada
        return trimmed
    return pairs




# Detecta repetição de frames dentro do bloco já truncado com logs detalhados
def detect_multiple_repetitions(pairs, max_frames, normalizar):
    global max_pause_before_cut
    if DEBUG: print(f"max_pause before cut: {max_pause_before_cut}")
  
    pause_indexes = []
    pause_indexes.append(0)  # Começa no início para capturar o primeiro frame

    # Detecta pausas significativas
    for idx, pair in enumerate(pairs):
        if (pair[1] > max_pause_before_cut * 0.95) and idx > 3:
            pause_indexes.append(idx + 1)
            if DEBUG: print(f"Achou pausa no pair idx: {idx}")

    # Só adiciona o final se a última pausa não for exatamente no final
    if pause_indexes[-1] < (len(pairs) - 1):
        pause_indexes.append(len(pairs) - 1)

    # Extrai os frames com base nas pausas
    all_frames = []
    for i in range(len(pause_indexes) - 1):
        start = pause_indexes[i]
        end = pause_indexes[i + 1]
        frame = pairs[start:end]
        if frame:
            all_frames.append(frame)
            if DEBUG: print(f"Frame {i}: {frame}")

    if DEBUG: print(f"Total de frames detectados: {len(all_frames)}")

    # Remove frames com tamanhos diferentes
    base_length = len(all_frames[0])
    frames = []

    for f in all_frames:
        if (not normalizar) or (len(f) == base_length):
            frames.append(f)
        if len(frames) >= max_frames:
            break

    
    # se por algum motivo frames ficou vazio, faz fallback seguro
    if not frames:
        # tenta usar todos os frames detectados antes de prosseguir
        frames = all_frames[:max_frames]
        if DEBUG: print(f"Frames não tinham retornado, vai usar all_frames até o limite de {max_frames}), novo len: {len(frames)}")

    else: 
        if DEBUG: print(f"Frames com mesmo comprimento (até o limite de {max_frames}): {len(frames)}")
    
    ref_frame = frames[0]
    similar_frames = [ref_frame]

    for f in frames[1:]:
        if blocks_are_similar(ref_frame, f):
            similar_frames.append(f)

    if len(similar_frames) > 1:
        if DEBUG: print(f"Frames semelhantes encontrados: {len(similar_frames)}. Retornando a média.")
        if normalizar:
            averaged_pairs = average_multiple_blocks(similar_frames)
            return {
                "equal_frames_detected": len(similar_frames),
                "returned_frames": 1,
                "total_frames_received": len(all_frames),
                "pairs": averaged_pairs
            }
        else:
            flattened_pairs = [pair for frame in frames for pair in frame]
            return {
                "equal_frames_detected": len(similar_frames),
                "returned_frames":len(frames),
                "total_frames_received": len(all_frames),
                "pairs": flattened_pairs
            }
    else:
        if DEBUG: print(f"Frames diferentes. Retornando todos os {len(frames)} frames.")
        flattened_pairs = [pair for frame in frames for pair in frame]
        return {
            "equal_frames_detected": 0,
            "returned_frames": len(frames),
            "total_frames_received": len(all_frames),
            "pairs": flattened_pairs
        }    


def normalize_bit_pulses(pairs, tolerance=0.2):
    """
    Normaliza pulsos IR, garantindo que só os pulsos válidos (bit 0 e bit 1) entram na média.
    Usa threshold inicial para classificar OFF0 e OFF1 e depois calcula médias.
    """
    if len(pairs) <= 1:
        return pairs

    data_pairs = pairs[1:-1]  # Ignorar start burst e final pulse com pausa longa

    # ---  detectar ON inicial  ---
    on_times = [on for (on, off) in data_pairs if on > 0]
    if not on_times:
        print("Erro ao normalizar dados, não achou on_times")
        return pairs
    
    avg_on = sum(on_times) / len(on_times)
    on_low, on_high = avg_on * (1 - tolerance), avg_on * (1 + tolerance)
    
    # --- Threshold usando somente pausas válidas ---
    valid_offs = [off for (on, off) in data_pairs if off < avg_on * 5]
    if not valid_offs:
        print("Erro ao normalizar dados, não achou off_times adequado")
        return pairs

    threshold = sum(valid_offs) / len(valid_offs)
    print(f"threshold inicial = {threshold}")

    # --- 1ª Passagem: classificar OFF0 e OFF1 com base no threshold ---
    off0_list = []
    off1_list = []
    on_list = []

    for idx, (on_time, off_time) in enumerate(data_pairs):
        if (not (on_low <= on_time <= on_high)) or (off_time > avg_on * 5):
            continue

        if off_time <= threshold:
            off0_list.append(off_time)
        else:
            off1_list.append(off_time)
        on_list.append(on_time)

    if len(off0_list) == 0 or len(off1_list) == 0:
        print(f"Erro: não achou off0 ou off1 - off0={len(off0_list)}, off1={len(off1_list)}")
        return pairs
    
    if len(on_list) < 2:
        print(f"Erro: não achou tempos on suficientes")
        return pairs
    
    avg_on = sum(on_list) / len(on_list)
    avg_off0 = sum(off0_list) / len(off0_list)
    avg_off1 = sum(off1_list) / len(off1_list)

    on_low, on_high = avg_on * (1 - tolerance), avg_on * (1 + tolerance)
    off0_low, off0_high = avg_off0 * (1 - tolerance), avg_off0 * (1 + tolerance)
    off1_low, off1_high = avg_off1 * (1 - tolerance), avg_off1 * (1 + tolerance)

    print(f"Médias iniciais: ON={avg_on:.1f}, OFF0={avg_off0:.1f}, OFF1={avg_off1:.1f}")
    print(f"Quantidade dados das médias: ON={len(on_list)}, OFF0={len(off0_list)}, OFF1={len(off1_list)}")

    # --- 2ª Passagem: com médias iniciais para filtrar dados válidos.

    off0_list = []
    off1_list = []
    on_list = []

    for idx, (on_time, off_time) in enumerate(data_pairs):
        if (on_low <= on_time <= on_high) and (off_time <= off1_high) :
            if off0_low <= off_time <= off0_high:
                off0_list.append(off_time)
            elif off1_low <= off_time <= off1_high:
                off1_list.append(off_time)
            on_list.append(on_time)
  
    if len(off0_list) < 2 or len(off1_list) < 2 :
        print(f"Erro: não achou off0 ou off1 suficientes - off0={len(off0_list)}, off1={len(off1_list)}")
        return pairs
    
    if len(on_list) < 2:
        print(f"Erro: não achou tempos on suficientes")
        return pairs

    avg_on = sum(on_list) / len(on_list)
    avg_off0 = sum(off0_list) / len(off0_list)
    avg_off1 = sum(off1_list) / len(off1_list)

    tolerance = 0.3

    on_low, on_high = avg_on * (1 - tolerance), avg_on * (1 + tolerance)
    off0_low, off0_high = avg_off0 * (1 - tolerance), avg_off0 * (1 + tolerance)
    off1_low, off1_high = avg_off1 * (1 - tolerance), avg_off1 * (1 + tolerance)

    print(f"Médias finais: ON={avg_on:.1f}, OFF0={avg_off0:.1f}, OFF1={avg_off1:.1f}")
    print(f"Quantidade dados das médias finais: ON={len(on_list)}, OFF0={len(off0_list)}, OFF1={len(off1_list)}")
  
    # --- 3ª Passagem: normalizar apenas válidos ---
    normalized_pairs = [pairs[0]]

    for idx, (on_time, off_time) in enumerate(data_pairs):
        if (on_low <= on_time <= on_high) and (off_time <= off1_high) :
            if off0_low <= off_time <= off0_high:
                normalized_pairs.append([int(avg_on), int(avg_off0)])
            elif off1_low <= off_time <= off1_high:
                normalized_pairs.append([int(avg_on), int(avg_off1)])
            else:
                print(f"[IDX {idx}] OFF fora no par {on_time},{off_time}")
                normalized_pairs.append([on_time, off_time])
        else:
            print(f"[IDX {idx}] ON fora no par {on_time},{off_time}")
            normalized_pairs.append([on_time, off_time])

    #adicionar o último pulso com pausa longa
    normalized_pairs.append(pairs[-1])

    return normalized_pairs



# Funcao principal para extrair o primeiro frame baseado em pausa longa
def extract_optimized_frame(sir2_str, pause_threshold , max_frames, normalize):
    if not sir2_str.startswith("sir,2,"):
        raise ValueError("Comando deve começar com 'sir,2,'")

    if DEBUG: print(f"pause_threshold: {pause_threshold} , max_frames: {max_frames}, normalize: {normalize}")
    prefix = "sir,2,"
    parts = sir2_str[len(prefix):].split(',')
    header_fields = parts[:6]  # tamanho, porta, id, periodo, repeat, offset
    pulse_values = list(map(int, parts[6:]))

    # Agrupar pulsos em pares (ON/OFF)
    pairs = [pulse_values[i:i+2] for i in range(0, len(pulse_values)-1, 2)]

    # Truncar o comando após primeira pausa longa
    truncated = truncate_after_first_pause(pairs, pause_threshold)

    if normalize:
           # Verificar repetição dentro do primeiro bloco
        result = detect_multiple_repetitions(truncated, max_frames, normalize)
        averaged_pairs1 = result['pairs']
        equal_frames_detected = result['equal_frames_detected']
        returned_frames = result["returned_frames"]
        total_frames_received = result['total_frames_received']
        
        # Normaliza valores de bit 0 e 1
        averaged_pairs = normalize_bit_pulses(averaged_pairs1)
        pulses_normalized = 1
    else:
        result = detect_multiple_repetitions(truncated, max_frames, normalize)
        averaged_pairs = result['pairs']
        equal_frames_detected = result['equal_frames_detected']
        returned_frames = result["returned_frames"]
        total_frames_received = result['total_frames_received']
        pulses_normalized = 0

    # Recalcular tamanho
    total_pulses = len(averaged_pairs) * 2
    # Ajuste artifical, para na conversão para sir,3 ou sir,4 para que seja incluso os últimos 6 pulsos
    total_pulses += 6
    header_fields[0] = str(total_pulses)

    # Reconstruir a sequencia
    flattened_trimmed = [str(p) for pair in averaged_pairs for p in pair]
    new_sir2 = prefix + ",".join(header_fields + flattened_trimmed)

    return {
        "returned_frames": returned_frames,
        "equal_frames_detected": equal_frames_detected,
        "pairs_preserved": len(averaged_pairs),
        "total_frames_received": total_frames_received,
        "new_sir2": new_sir2,
        "pulses_normalized": pulses_normalized
    }


# --- helper fiel ao C -------------------------------------------------------
def convASCIIToInt(num1: list[int]) -> int:
    return (
        (num1[0] - 48)
        + 10 * (num1[1] - 48)
        + 100 * (num1[2] - 48)
        + 1000 * (num1[3] - 48)
        + 10000 * (num1[4] - 48)
        + 100000 * (num1[5] - 48)
    )

def sir34tosir2(sirin):
    # sir,4,126,1,1,38760,1,1,117,382,ABACA
    # sir,2,126,1,1,258,1,1,1888,6163,236,1052,236,408,236,408,236,
    splited = sirin.split(',')
    resultsir2 = ""
    freq = 1

    # fator de conversão do iluflex_learner do Ciro
    # converte tempos da unidade do sir,2 (1.6 x µs) para pulsos do sir,3 ou sir,4 ou GC
    def timePulseConversion(strnum) -> int:
        # return round(((625000 * int(strnum)) - 312500) / freq) usa half round up com inteiros  
        return round((625000 * int(strnum)) / freq)


    if splited[1] == '4':  # conversão de sir,4 para sir,2
        freq = int(splited[5])
        resultsir2 = f"sir,2,{splited[2]},{splited[3]},{splited[4]},"
        periodo = round(10000000 / int(splited[5]))
        resultsir2 += f"{periodo},{splited[6]},{splited[7]}"
        resultsir2 += f",{timePulseConversion(splited[8])},{timePulseConversion(splited[9])}"

        #mapear tempos
        timearr = [timePulseConversion(tok) for tok in splited[13:] if tok.strip()]

        if DEBUG: print(f"Timer Arr: {timearr}")

        #converter char payload em pulsos
        for ch in splited[10]:
            #print(f"char: {ch}")
            charVal = ord(ch) # converte caractere em número ascii
            if (64 < charVal < 81 ): # caracteres maiúsculos
                resultsir2 += f",{timearr[charVal - 65]}"
            elif (96 < charVal < 118): # caracteres mínúsculos
                #precisamos extrair os bits das letras
                bytechar = ord(ch) - 97
                # print(f"bytechar = {bytechar}")
                n = bytechar & 0xF  # garante só 4 bits
                # extrai bits do nibble na sequencia dos tempos: b0,b1,b2,b3
                for bit in (n & 1, (n >> 1) & 1, (n >> 2) & 1, (n >> 3) & 1):
                    #print(f"bit = {bit} que corresponde a {timearr[bit]}")
                    resultsir2 += f",{timearr[bit]}"

        # por fim, os dois pulsos finais
        resultsir2 += f",{timePulseConversion(splited[11])},{timePulseConversion(splited[12])}"


    elif splited[1] == '3':
        # sir,3,74,1,1,37878,1,1,169,169,18,65,18,23,BzBzjzQA,18,3792
        freq = int(splited[5])
        resultsir2 = f"sir,2,{splited[2]},{splited[3]},{splited[4]},"
        periodo = round(10000000 / int(splited[5]))
        resultsir2 += f"{periodo},{splited[6]},{splited[7]}"
        resultsir2 += f",{timePulseConversion(splited[8])},{timePulseConversion(splited[9])}"

        # adição da parte das letras
        on0 = timePulseConversion(splited[10])
        off0 = timePulseConversion(splited[11])
        on1 = timePulseConversion(splited[12])
        off1 = timePulseConversion(splited[13])

        totalBit = (int(splited[2]) - 10) // 2 # len sempre tem 6 a mais, 2 primeiros pulsos são start burst e 2 final burst ; // divide e retorna inteiro, melhor que / que retorna float

        letras = splited[14]
        totalLetras = len(letras)

        if len(letras) % 2 != 0:
            raise ValueError("payload ímpar em sir,3")
        
        if (len(letras) // 2 ) * 8 < totalBit:
            raise ValueError(f"payload erro: número de pulsos {totalBit} em sir,3")

        # print(f"Letras = {letras} e totalbit = {totalBit}")

        # a cada 2 letras temos que converter em int

        intBuffer = [0] * (totalLetras // 2 + 1)
        idx = 0
        for i in range(0, totalLetras, 2):
            msb = ord(letras[i])
            lsb = ord(letras[i+1])
            intBuffer[idx] = (msb << 8) | lsb
            idx += 1

        for i in range(totalBit):
            pulsoLoc = int(i / 8)
            bitLoc = int(i / 8)
            bitLoc = i - (bitLoc * 8)
            # print(f"for {i}: BitLoc = {bitLoc} e pulsoLoc = {pulsoLoc} ")
            match bitLoc:
                case 0:  # bit 13
                    if intBuffer[pulsoLoc] & 0x2000:
                        resultsir2 += f",{on1},{off1}"
                    else:
                        resultsir2 += f",{on0},{off0}"
                case 1:  # bit 12
                    if intBuffer[pulsoLoc] & 0x1000:
                        resultsir2 += f",{on1},{off1}"
                    else:
                        resultsir2 += f",{on0},{off0}"
                case 2:  # bit 11
                    if intBuffer[pulsoLoc] & 0x0800:
                        resultsir2 += f",{on1},{off1}"
                    else:
                        resultsir2 += f",{on0},{off0}"
                case 3:  # bit 9
                    if intBuffer[pulsoLoc] & 0x0200:
                        resultsir2 += f",{on1},{off1}"
                    else:
                        resultsir2 += f",{on0},{off0}"
                case 4:  # bit 5
                    if intBuffer[pulsoLoc] & 0x0020:
                        resultsir2 += f",{on1},{off1}"
                    else:
                        resultsir2 += f",{on0},{off0}"
                case 5:  # bit 4
                    if intBuffer[pulsoLoc] & 0x0010:
                        resultsir2 += f",{on1},{off1}"
                    else:
                        resultsir2 += f",{on0},{off0}"
                case 6:  # bit 3
                    if intBuffer[pulsoLoc] & 0x0008:
                        resultsir2 += f",{on1},{off1}"
                    else:
                        resultsir2 += f",{on0},{off0}"
                case 7:  # bit 1
                    if intBuffer[pulsoLoc] & 0x0002:
                        resultsir2 += f",{on1},{off1}"
                    else:
                        resultsir2 += f",{on0},{off0}"

        # adição do último pulso e pausa final
        resultsir2 +=f",{timePulseConversion(splited[15])},{timePulseConversion(splited[16])}"
                        
    return resultsir2


# ----------------------------------------------------------------------------
#  Conversões CANÔNICAS entre unidades usadas pelo firmware
#  - t2 (sir,2): ticks de 1,6 µs (us/1.6)
#  - N  (sir,3/4): número de ciclos da portadora
#  - us: microssegundos
#  - Per (0,1 µs): período da portadora em décimos de µs (campo 5 do sir,2)
#  Observação:
#  A reprodução do ESP converte N → µs com multiplicador = 1e6/freq e depois
#  µs → RMT ticks (10 µs). Portanto, a relação correta é:
#      N  = round_half_up(t2 * freq / 625000)
#      t2 = round_half_up(N  * 625000 / freq)
#  e, usando Per diretamente (freq = 10_000_000 / Per):
#      N  = round_half_up(16 * t2 / Per)
#      t2 = round_half_up(N  * Per / 16)
# ----------------------------------------------------------------------------

def sir34_to_sir2(N: int, freq: int) -> int:
    """Converte ciclos (sir,3/4) para ticks 1,6 µs (sir,2).
    t2 = round_half_up(N * 625000 / freq)
    """
    return _div_round_half_up(N * 625000, freq)


def sir2_to_sir34(t2: int, freq: int) -> int:
    """Converte ticks 1,6 µs (sir,2) para ciclos (sir,3/4).
    N = round_half_up(t2 * freq / 625000)
    """
    return _div_round_half_up(t2 * freq, 625000)


def sir34_to_us(N: int, freq: int) -> int:
    """Converte ciclos (sir,3/4) diretamente para microssegundos.
    us = round_half_up(N * 1_000_000 / freq)
    """
    return _div_round_half_up(N * 1_000_000, freq)


def us_to_sir2(us: int) -> int:
    """Converte microssegundos para ticks 1,6 µs (sir,2): round_half_up(us/1.6)."""
    return _div_round_half_up(us * 10, 16)


def sir2_to_us(t2: int) -> int:
    """Converte ticks 1,6 µs (sir,2) para microssegundos: round_half_up(t2*1.6)."""
    return _div_round_half_up(t2 * 16, 10)

# --- Versões usando período Per em décimos de µs (0,1 µs) -------------------

def sir2_to_sir34_per(t2: int, Per: int) -> int:
    """N = round_half_up(16 * t2 / Per)."""
    return _div_round_half_up(16 * t2, Per)


def sir34_to_sir2_per(N: int, Per: int) -> int:
    """t2 = round_half_up(N * Per / 16)."""
    return _div_round_half_up(N * Per, 16)


def sir34_to_us_per(N: int, Per: int) -> int:
    """us = round_half_up(N * (Per/10))."""
    return _div_round_half_up(N * Per, 10)


# ------------------------- EDITOR/CONVERSOR ---------------------------------
def update_rep_channel_fields(cmd: str, rep: int, channel: int) -> str:
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
        parts[3] = str(channel)
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


# ----------------------------------------------------------------------------
#  Arredondamento idêntico ao usado no C (half-up): (num + den/2) / den
# ----------------------------------------------------------------------------

def _div_round_half_up(num: int, den: int) -> int:
    if den == 0:
        raise ZeroDivisionError("Denominador zero em divisão com arredondamento")
    return (num + den // 2) // den

