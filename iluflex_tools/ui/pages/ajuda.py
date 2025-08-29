# file: iluflex_tools/ui/pages/ajuda.py
from __future__ import annotations
import tkinter as tk
from tkhtmlview import HTMLLabel, HTMLScrolledText
import customtkinter as ctk
from iluflex_tools.widgets.page_title import PageTitle

ONLINE_HELP = (
    "https://www.iluflex.com.br/downloads/iluflextools/help/index.html"
)


class AjudaPage(ctk.CTkFrame):
    """Ajuda simples e nativo (HTML local). """

    def __init__(self, master) -> None:
        super().__init__(master)

        # Layout
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._htmltxt = self.htmlcontent()

        PageTitle(self, text="Ajuda").grid(row=0, column=0, sticky="w", padx=12, pady=(10, 6))

        hframe = ctk.CTkFrame(self, fg_color="white")
        hframe.grid(row=1, column=0, padx=5, pady=5, sticky=("nsew"))
        # 2) HTML ocupa todo o espaço do frame
        hframe.grid_rowconfigure(0, weight=1)
        hframe.grid_columnconfigure(0, weight=1)

        self.helphtmllabel = HTMLScrolledText(
            hframe,
            html=self._htmltxt,
            background="white",
            borderwidth=0,
            relief="flat",
            highlightthickness=0,
        )
        self.helphtmllabel.grid(row=0, column=0, padx=(20,2), pady=20, sticky="nsew")




    def htmlcontent(self) -> str:
        # CSS margin/padding não é suportado aqui; usamos tag_config acima.
        return """<div>
    <h2 style='text-align:center'>iluflex Tools V 2.0 — Ajuda</h2>
    <p>Este help local e suscinto. Para o conteúdo mais completo, use o link “Help completo online”.</p>
    <ul>
        <li>Conexão (onde tudo começa...)</li>
        <li>Gestão de Dispositivos - Cadastro rede Mesh</li>
        <li>IR Learner </li>
        <li>Configurar Interface Master IC-315 ou IC-215</li>
        <li><a href='https://www.iluflex.com.br/downloads/iluflextools/help/index.html' target='_blank'>Help completo online</a></li>
    </ul>
    <div>
        <h3>Conexão</h3>
        <p><strong>Busca automática de interfaces master na rede LAN. </strong><br>
        No campo endereço também são aceitos url´s. Permite trocar a porta padrão 4999 para permitir acesso a portas mapeadas
        com Portforwarder na ic-421, viabilizando o acesso remoto a interface master dentro da rede local.</p>
        <p>O Menu também contém campos adicionais como 'Mascara' e 'Gateway'. Clique com botão da direita do mouse sobre o título da tabela para exibir ou ocultar colunas.</p>

        <h3>Gestão de Dispositivos</h3>
        <p><strong>Permite cadastrar módulos slave da rede mesh e rede 485.</strong> <br>
        O botão 'Procurar Dispositivos' é usado para entrar no modo de procura de módulos slave da rede mesh. Módulos slave da 485 não precisam fazer descoberta.<br>
        O tempo de procura pode ser ajustado em Preferências: Tempo padrão para procura por novos dispositivos na rede mesh.<br>
        Ao iniciar e terminar a procura, é normal a interface master reiniciar. A reconexão automática é ligada para ajudar a reconeção.</p>
        <p>Clique duas vezes no campo Slave ID e nome para editar. Clique Enter para confirmar a edição.
        O botão 'salvar' ficará vermelho e então permite enviar o comando para o cadastro do módulo.<br>
        Evite usar nomes muito longs ou caracteres especiais no nome dos dispositivos !</p>

        <h3>IR Learner</h3>
        <p><strong>Permite a Captura de Comandos de IR (infra vermelho).</strong> <br>
        Para capturar comandos de IR, ligue o Modo Lerner (primeiro do menu de comandos), com a interface master conectada.<br>
        Aponte o controle remoto para o sensor de IR, localizado no centro da ic-315. Mantenha uma distância curta de 2 a 5 cm do controle remoto para a ic-315.<br>
        Os comandos capturados são recebidos no campo 'Entrada', que não é editável.<br>
        Assim que um comando de captura é recebido (sir,2) ele é pré-processado e este resultado colocado no campo 'pré processado'.
        O pré-processamento dos comandos permite normalizar os dados, isto é, usar os tempos médios dos pulsos, permite detectar a repetição de frames,
        permite limitar o número de frames. Ao mudar os parâmetros o resultado é atualizado automaticamente.<br>
        O gráfico ajuda e ver o resultado do pré-processamento e conversão dos comandos, permitindo ajustar os parâmetros para obter um resultado ideal.<p>
        O tempo da pausa é um parâmetro que ajuda a identificar o fim da transmissão e ajuda a dividir os frames. 
        Para poder capturar vários frames, deixe este valor maior que o tempo de intervalo entre frames e menor que a última pausa.<br>
        Observe o texto que informa se frames iguais foram encontrados, se foi feita a média deles, e quantos pulsos foram usados.<br>
        Com o pré-processamento bem ajustado, pode ser dado o início à conversão dos comandos, e captura de novos comandos. </p>
        A <strong>Conversão dos comandos</strong> tem 2 formatos de saída. O 'iluflex long' são os dados do pré-processamento, isto é, sem compatação e começam com sir,2.<br>
        O formato 'iluflex short' é um formato especial da iluflex que consegue reduzir siginificativamente o tamanho dos comandos usando técnicas de compatação de dados.<br>
        Prefira o 'iluflex short' por 2 razões importantes: comandos menores são mais rápidos de transmitir e processar, e segundo, os formatos compactados geram comandos com 
        tempos uniformes, melhorando a qualidade da transmissão e consequentemente o reconhecimento do aparelho.</p>

        <h3>Configurar Interface Master IC-315 ou IC-215</h3>
        <p><strong>Permite fixar endereço IP e trocar canal do WiFi.</strong> <br>
        Conecte antes de querer mudar as configurações da interface master ic-315 ou ic-215. Outros modelos não são compatíveis com essa configuração.</p>
        <p>Fixe o endereço IP desmarcando a opção de conexão modo DHCP.</p>
        <p><strong>Troca do canal do Wifi</strong></p>
        <p>Embora a rede mesh use um protocolo diferente da rede WiFi, o meio físico é o mesmo, isto é, compartilha o mesmo espectro de frequências de 2.4 GHz. 
        Se experimentar problemas como desconexão de módulos da rede mesh ou instabilidade, pode ser indício de problema de congestionamento de canal do WiFi. 
        Neste caso vale a pena trocar o canal da rede mesh. <br> 
        Os módulos slaves cadastrados irão primeiro tentar se conectar com o canal com o qual foram cadastrados. Se não acharem a interface master, irão tentar outros canais.
        Então a troca de canal em si não prejudica o funcionamento do sistema, mas é aconselhável recadastrar ao menos alguns módulos da rede, para ajudar na reconexão da rede mesh.</p>

    </div></div>"""
