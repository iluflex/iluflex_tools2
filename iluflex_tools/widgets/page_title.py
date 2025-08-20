import customtkinter as ctk

class PageTitle(ctk.CTkLabel):
    """Helper label for page titles with consistent style and placement."""
    def __init__(self, master, text: str, **grid_kwargs):
        super().__init__(master, text=text, font=ctk.CTkFont(size=18, weight="bold"))
        opts = {"row": 0, "column": 0, "padx": 12, "pady": (10, 6), "sticky": "w"}
        opts.update(grid_kwargs)
        self.grid(**opts)
