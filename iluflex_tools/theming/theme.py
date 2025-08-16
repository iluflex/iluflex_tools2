import customtkinter as ctk

def apply_theme(mode: str = "system"):
    """
    Aplica o tema escolhido em Preferências: "system", "dark" ou "light".
    """
    if mode not in ("system", "dark", "light"):
        mode = "system"
    ctk.set_appearance_mode(mode)
    # Paleta neutra/escura moderna
    ctk.set_default_color_theme("dark-blue")