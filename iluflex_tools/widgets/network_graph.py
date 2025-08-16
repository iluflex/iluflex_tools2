import customtkinter as ctk
import math

class MeshGraphView(ctk.CTkToplevel):
    def __init__(self, master, nodes, edges):
        super().__init__(master)
        self.title("Topologia Mesh")
        self.geometry("720x520")
        self.resizable(True, True)
        self.canvas = ctk.CTkCanvas(self, bg="#101010", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=10, pady=10)
        self.nodes = nodes  # list of labels
        self.edges = edges  # list of (labelA, labelB)
        self.after(50, self._draw)

    def _draw(self):
        self.canvas.delete("all")
        w = self.canvas.winfo_width() or 680
        h = self.canvas.winfo_height() or 480
        r = min(w, h)*0.35
        cx, cy = w/2, h/2
        pos = {}
        n = max(1, len(self.nodes))
        for i,label in enumerate(self.nodes):
            ang = (2*math.pi*i)/n
            x = cx + r*math.cos(ang)
            y = cy + r*math.sin(ang)
            pos[label] = (x,y)
            self.canvas.create_oval(x-18,y-18,x+18,y+18, fill="#2e86de", outline="")
            self.canvas.create_text(x, y, text=str(label), fill="white")
        for a,b in self.edges:
            if a in pos and b in pos:
                xa,ya = pos[a]; xb,yb = pos[b]
                self.canvas.create_line(xa,ya,xb,yb, fill="#7f8c8d", width=2)
