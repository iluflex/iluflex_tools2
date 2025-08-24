Iluflex Menu Icons (simple line set)
====================================

Sizes: 20px, 24px
Variants:
- *_light.png  -> use in LIGHT themes (dark strokes)
- *_dark.png   -> use in DARK themes (light strokes)

Suggested mappings for your MENU_ITEMS:
- INICIO -> home / dashboard
- CONEXÃO -> plug / network / router
- GESTÃO DE DISPOSITIVOS -> folders / network
- COMANDOS IR -> radio-tower
- CONFIGURAR MASTER -> server-cog / router
- PREFERÊNCIAS -> sliders / settings-gear
- AJUDA -> help-circle
- (extras) firmware-upload, terminal

Usage (CustomTkinter):
----------------------
from PIL import Image
import customtkinter as ctk

def icon(path, size):
    img = Image.open(path)
    return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))

# Example:
# icon_light = icon("assets/icons/server-cog_24px_light.png", 24)
# icon_dark  = icon("assets/icons/server-cog_24px_dark.png", 24)
# Choose based on current theme.
