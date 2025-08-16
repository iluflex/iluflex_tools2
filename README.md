# iluflex_tools (CustomTkinter Scaffold v4)

- **Gestão de Dispositivos** (Mesh + 485 **na mesma tabela**), com colunas:
  `Rede`, `Endereço/MAC`, `Node ID`, `Modelo`, `Nome`, `FW`, `HW`, `Conectado a`.
- **Menu de cabeçalho com clique direito** para **ocultar/exibir colunas**.
- **Sidebar colapsável** (texto ↔ ícones) via botão "≡" no topo.
- **Topologia Mesh**: botão "Ver Topologia" abre um gráfico simples (stub) com nós e ligações.
- **Tema**: `system` (herda do Windows).

## Rodar (sem mexer no PATH/ESP-IDF)
Abra um PowerShell nesta pasta e rode UM dos comandos abaixo (escolha o seu `python.exe`):

# 2) sem venv, apontando direto para o seu python.exe
C:/Users/SEUUSER/AppData/Local/Programs/Python/Python313/python.exe -m pip install -r requirements.txt --user
C:/Users/SEUUSER/AppData/Local/Programs/Python/Python313/python.exe main.py
```
## Comandos para gerar executável com Installer
