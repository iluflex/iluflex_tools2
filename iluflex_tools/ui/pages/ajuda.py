import customtkinter as ctk
from iluflex_tools.widgets.page_title import PageTitle

# Dependências: pip install tkinterweb markdown
try:
    from tkinterweb import HtmlFrame
    import markdown
except Exception as e:
    HtmlFrame = None
    markdown = None

import pathlib

class AjudaPage(ctk.CTkFrame):
    def __init__(self, master, md_path: str = "docs/index.md"):
        super().__init__(master)
        PageTitle(self, "Ajuda")
        self._md_path = pathlib.Path(md_path)
        self._build()

    def _build(self):
        if HtmlFrame is None or markdown is None:
            msg = (
                "Dependências ausentes: instale 'tkinterweb' e 'markdown'\n"
                "Ex.: pip install tkinterweb markdown"
            )
            ctk.CTkLabel(self, text=msg, justify="left").grid(row=1, column=0, padx=12, pady=6, sticky="w")
            return

        # Toolbar simples
        bar = ctk.CTkFrame(self)
        bar.grid(row=1, column=0, padx=10, pady=(6, 4), sticky="ew")
        ctk.CTkButton(bar, text="Recarregar (F5)", width=130, command=self.reload).pack(side="left")
        self.search_entry = ctk.CTkEntry(bar, placeholder_text="Buscar...")
        self.search_entry.pack(side="left", padx=6, fill="x", expand=True)
        ctk.CTkButton(bar, text="Ir", width=80, command=self._search).pack(side="left")

        # Viewer
        self.viewer = HtmlFrame(self, messages_enabled=False)
        self.viewer.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Atalhos
        #self.bind_all("<F5>", lambda e: self.reload())
        #self.bind_all("<Control-f>", lambda e: self._search())

        self.reload()

    def _search(self):
        term = (self.search_entry.get() or "").strip()
        if not term:
            return
        try:
            self.viewer.search(term)
        except Exception:
            pass

    def reload(self):
        if not self._md_path.exists():
            html = (
                f"<h3>Arquivo não encontrado</h3>"
                f"<p>Crie <code>{self._md_path}</code> com o conteúdo do help em Markdown.</p>"
            )
            try:
                self.viewer.load_html(html)
            except Exception:
                pass
            return
        try:
            md_text = self._md_path.read_text(encoding="utf-8")
            html_body = markdown.markdown(md_text, extensions=["fenced_code", "tables", "toc", "admonition"])
            # base_uri = self._md_path.parent.as_uri()
            html = f"""
            <html>
              <head>
                <meta charset="utf-8">
                <style>
                  body {{ font-family: 'Segoe UI', Arial, sans-serif; padding: 12px; line-height: 1.55; }}
                  h1, h2, h3 {{ margin-top: 1.1em; }}
                  code, pre {{ font-family: Consolas, monospace; }}
                  pre {{ padding: 10px; border: 1px solid #ddd; border-radius: 8px; overflow-x:auto; }}
                  table {{ border-collapse: collapse; width: 100%; }}
                  th, td {{ border: 1px solid #ddd; padding: 6px 8px; text-align: left; }}
                  .admonition {{ border-left: 4px solid #888; padding: 8px 10px; margin: 10px 0; background:#f7f7f7; }}
                  a {{ text-decoration: none; }}
                </style>
              </head>
              <body>
                {html_body}
              </body>
            </html>
            """
            self.viewer.load_html(html)
        except Exception as e:
            try:
                self.viewer.load_html(f"<pre>Erro ao carregar help: {e}</pre>")
            except Exception:
                pass
