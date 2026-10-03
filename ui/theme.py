import os
import sys
import time
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageSequence

# =====================================================================
# 🎨 PALETA DE COLORES CIBERPUNK Y OCEANIC
# =====================================================================

AZUL_FONDO = ("#e2e8f0", "#05080a")
AZUL_CARD = ("#ffffff", "#0d1117")
AZUL_CARD_INNER = ("#f1f5f9", "#090d12")
AZUL_CIAN = ("#0284c7", "#00d4ff")
AZUL_ELECTRICO = ("#2563eb", "#005eff")
AZUL_SUAVE = ("#1d4ed8", "#70a1ff")
COLOR_BORDE = ("#cbd5e1", "#1e293b")

COLOR_HOLLOW = "#2563eb"
COLOR_CACHY = "#10b981"
COLOR_LIMINE = "#64748b"
COLOR_LIBRE = "#1e293b"
VERDE_EXITO = "#2ecc71"
COLOR_ROJO_PELIGRO = "#ef4444"
COLOR_AMARILLO_CYBER = "#f59e0b"
COLOR_MORADO_CYBER = "#a855f7"

def calc_brillo(hex_color, factor=1.35):
    try:
        h = hex_color.lstrip('#')
        rgb = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
        return "#{:02x}{:02x}{:02x}".format(*[min(255, max(0, int(c * factor))) for c in rgb])
    except Exception:
        return hex_color

def calc_sombra(hex_color, factor=0.65):
    try:
        h = hex_color.lstrip('#')
        rgb = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
        return "#{:02x}{:02x}{:02x}".format(*[min(255, max(0, int(c * factor))) for c in rgb])
    except Exception:
        return hex_color

def color_canvas_actual():
    return AZUL_CARD[0] if ctk.get_appearance_mode() == "Light" else AZUL_CARD[1]


# =====================================================================
# 💡 TOOLTIPS FLOTANTES
# =====================================================================

class CTkToolTip:
    """
    Tooltip flotante con retardo configurable.
    """
    def __init__(self, widget, text="Info", delay_ms=450):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.tooltip_window = None
        self.after_id = None

        self.widget.bind("<Enter>", self.on_enter, add="+")
        self.widget.bind("<Leave>", self.on_leave, add="+")
        self.widget.bind("<Button-1>", self.on_leave, add="+")

    def on_enter(self, event=None):
        self.schedule()

    def on_leave(self, event=None):
        self.unschedule()
        self.hide_tooltip()

    def schedule(self):
        self.unschedule()
        if hasattr(self.widget, "after"):
            self.after_id = self.widget.after(self.delay_ms, self.show_tooltip)

    def unschedule(self):
        if self.after_id:
            try:
                self.widget.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None

    def show_tooltip(self):
        if self.tooltip_window or not self.widget.winfo_exists():
            return
        try:
            x = self.widget.winfo_rootx() + (self.widget.winfo_width() // 2) - 30
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6

            tw = tk.Toplevel(self.widget)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{x}+{y}")
            tw.attributes("-topmost", True)
            tw.config(bg="#1e293b")

            label = tk.Label(
                tw,
                text=self.text,
                justify="left",
                background="#0f172a",
                foreground="#38bdf8",
                relief="solid",
                borderwidth=1,
                font=("Segoe UI", 9, "bold"),
                padx=8,
                pady=4
            )
            label.pack()
            self.tooltip_window = tw
        except Exception:
            pass

    def hide_tooltip(self):
        if self.tooltip_window:
            try:
                self.tooltip_window.destroy()
            except Exception:
                pass
            self.tooltip_window = None


# =====================================================================
# 🖱️ FIX PARA COMBOBOX COMPLETAMENTE CLICABLE
# =====================================================================

def hacer_combobox_clicable_total(combobox):
    combobox._last_menu_close = 0.0

    orig_menu_open = combobox._dropdown_menu.open
    def safe_menu_open(x, y):
        try:
            orig_menu_open(x, y)
        finally:
            combobox._last_menu_close = time.time()
            combobox._close_on_next_click = False

    combobox._dropdown_menu.open = safe_menu_open

    def toggle_dropdown(e=None):
        if str(combobox.cget("state")) == "disabled":
            return "break"

        now = time.time()
        if (now - getattr(combobox, "_last_menu_close", 0.0)) < 0.35:
            return "break"

        if len(combobox._values) > 0:
            combobox._open_dropdown_menu()
        return "break"

    combobox._clicked = toggle_dropdown

    if hasattr(combobox, "_entry"):
        combobox._entry.bind("<Button-1>", toggle_dropdown)
        combobox._entry.configure(cursor="hand2")

    if hasattr(combobox, "_canvas"):
        combobox._canvas.bind("<Button-1>", toggle_dropdown)
        combobox._canvas.tag_bind("right_parts", "<Button-1>", toggle_dropdown)
        combobox._canvas.tag_bind("dropdown_arrow", "<Button-1>", toggle_dropdown)

    combobox.configure(cursor="hand2")


# =====================================================================
# 🖼️ CARGADOR CENTRALIZADO DE RECURSOS DE MEDIOS
# =====================================================================

def cargar_gif_frames(ruta_gif, size=None, espejo=False):
    if not os.path.exists(ruta_gif):
        return []
    try:
        pil_img = Image.open(ruta_gif)
        frames = []
        for frame in ImageSequence.Iterator(pil_img):
            frame_c = frame.copy().convert("RGBA")
            if size:
                frame_c = frame_c.resize(size, Image.Resampling.LANCZOS)
            if espejo:
                frame_c = frame_c.transpose(Image.FLIP_LEFT_RIGHT)
            final_size = size if size else frame_c.size
            frames.append(ctk.CTkImage(light_image=frame_c, dark_image=frame_c, size=final_size))
        return frames
    except Exception:
        return []


def crear_ventana_modal_base(parent, titulo, ancho, alto):
    v = ctk.CTkToplevel(parent)
    v.title(titulo)
    parent.update_idletasks()
    x = parent.winfo_x() + (parent.winfo_width() // 2) - (ancho // 2)
    y = parent.winfo_y() + (parent.winfo_height() // 2) - (alto // 2)
    v.geometry(f"{ancho}x{alto}+{x}+{y}")
    v.configure(fg_color=AZUL_FONDO)
    v.attributes("-alpha", 0.97)
    v.resizable(False, False)
    v.transient(parent)
    v.lift()
    v.focus_force()
    return v
