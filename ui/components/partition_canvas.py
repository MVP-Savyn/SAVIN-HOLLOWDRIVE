import tkinter as tk
import customtkinter as ctk
from ui.theme import (
    AZUL_FONDO, AZUL_CARD, AZUL_CIAN, AZUL_ELECTRICO,
    COLOR_HOLLOW, COLOR_CACHY, COLOR_LIMINE, COLOR_LIBRE,
    color_canvas_actual, calc_brillo
)

class PartitionCanvas(ctk.CTkFrame):
    """
    Componente visual interactivo para la distribución del espacio del disco USB.
    Dibuja particiones (HollowDrive, GRUB, CachyOS, Libre) con manetas de arrastre
    y ajuste milimétrico con rueda de ratón bloqueando la propagación (return 'break').
    """
    def __init__(self, master, state, on_change_callback=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.state = state
        self.on_change_callback = on_change_callback

        self._active_handle = None
        self._pos_h1 = 0
        self._pos_h2 = 0
        self.bloqueado = False

        bg_canvas = color_canvas_actual()
        self.canvas = tk.Canvas(
            self,
            height=85,
            bg=bg_canvas,
            highlightthickness=0,
            borderwidth=0
        )
        self.canvas.pack(fill="x", expand=True)

        self.canvas.bind("<Button-1>", self._on_bar_click)
        self.canvas.bind("<B1-Motion>", self._on_bar_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_bar_release)
        self.canvas.bind("<Motion>", self._on_bar_hover)
        self.canvas.bind("<MouseWheel>", self._on_bar_wheel)
        self.canvas.bind("<Left>", self._on_bar_key_left)
        self.canvas.bind("<Right>", self._on_bar_key_right)

        self.bind("<Configure>", lambda e: self.actualizar())

    def set_bloqueado(self, bloqueado):
        self.bloqueado = bloqueado
        self.actualizar()

    def _coords_bar(self):
        w = self.canvas.winfo_width()
        pad_x = 24
        y1, y2 = 18, 32
        return pad_x, max(pad_x + 30, w - pad_x), y1, y2

    def _dibujar_maneta(self, x, hy1, hy2, glow_color):
        self.canvas.create_line(x, hy1 + 3, x, hy2 - 3, width=8, capstyle="round", fill=glow_color)
        self.canvas.create_line(x, hy1 + 3, x, hy2 - 3, width=6, capstyle="round", fill="#05080a")
        self.canvas.create_line(x, hy1 + 3, x, hy2 - 3, width=4, capstyle="round", fill="#ffffff")
        self.canvas.create_line(x, hy1 + 7, x, hy2 - 7, width=1.5, capstyle="round", fill="#64748b")

    def _formato_gb(self, val):
        val_r = round(val, 1)
        if val_r == int(val_r):
            return f"{int(val_r)} GB"
        return f"{val_r:.1f} GB"

    def _ajustar_maneta_delta(self, handle_idx, delta_gb):
        if self.bloqueado:
            return
        total = self.state.gb_totales
        if total <= 0:
            return

        base_h = 10.0 if self.state.descargar_pack_hollow else 3.0
        gb_bato = (self.state.tamanos_reales.get("bato_64", 0.0) if self.state.bato_64_act else 0.0) if self.state.instalar_bato else 0.0
        min_h = base_h + gb_bato
        min_c = 20.0 if self.state.instalar_cachy else 0.0
        min_libre = 5.0 if self.state.preservar_espacio else 0.0

        if handle_idx == 1:
            if self.state.instalar_cachy:
                max_h = total - min_c - (self.state.val_libre_gb if self.state.preservar_espacio else 0.0)
                self.state.val_hollow_gb = max(min_h, min(max_h, round(self.state.val_hollow_gb + delta_gb, 1)))
                if self.state.preservar_espacio:
                    self.state.val_cachy_gb = round(total - self.state.val_hollow_gb - self.state.val_libre_gb, 1)
                else:
                    self.state.val_cachy_gb = round(total - self.state.val_hollow_gb, 1)
            else:
                max_h = total - min_libre
                self.state.val_hollow_gb = max(min_h, min(max_h, round(self.state.val_hollow_gb + delta_gb, 1)))
                self.state.val_libre_gb = round(total - self.state.val_hollow_gb, 1) if self.state.preservar_espacio else 0.0

        elif handle_idx == 2 and self.state.instalar_cachy and self.state.preservar_espacio:
            max_pos = total - min_libre
            pos_act = self.state.val_hollow_gb + self.state.val_cachy_gb
            nueva_pos = max(self.state.val_hollow_gb + min_c, min(max_pos, round(pos_act + delta_gb, 1)))
            self.state.val_cachy_gb = round(nueva_pos - self.state.val_hollow_gb, 1)
            self.state.val_libre_gb = round(total - nueva_pos, 1)

        self.actualizar()
        if self.on_change_callback:
            self.on_change_callback()

    def _on_bar_wheel(self, event):
        if self.bloqueado:
            return "break"
        tiene_h1 = (self.state.instalar_cachy and self.state.val_cachy_gb > 0) or (self.state.preservar_espacio and self.state.val_libre_gb >= 0.1)
        tiene_h2 = self.state.instalar_cachy and self.state.preservar_espacio and (self.state.val_libre_gb >= 0.1)
        if not tiene_h1 and not tiene_h2:
            return "break"

        d1 = abs(event.x - getattr(self, '_pos_h1', -999)) if tiene_h1 else 999
        d2 = abs(event.x - getattr(self, '_pos_h2', -999)) if tiene_h2 else 999

        handle = 1 if d1 <= d2 else 2
        paso = 0.1 if (event.state & 0x0001) else 1.0
        delta = paso if event.delta > 0 else -paso
        self._ajustar_maneta_delta(handle, delta)
        return "break"  # Bloquea la propagación para evitar mover la ventana

    def _on_bar_key_left(self, event):
        if self.bloqueado:
            return
        paso = 0.1 if (event.state & 0x0001) else 1.0
        handle = getattr(self, '_active_handle', 1) or 1
        self._ajustar_maneta_delta(handle, -paso)

    def _on_bar_key_right(self, event):
        if self.bloqueado:
            return
        paso = 0.1 if (event.state & 0x0001) else 1.0
        handle = getattr(self, '_active_handle', 1) or 1
        self._ajustar_maneta_delta(handle, paso)

    def _on_bar_hover(self, event):
        if self.bloqueado:
            self.canvas.configure(cursor="")
            return

        pos1 = getattr(self, '_pos_h1', -999)
        pos2 = getattr(self, '_pos_h2', -999)

        d1 = abs(event.x - pos1) if pos1 > 0 else 999
        d2 = abs(event.x - pos2) if pos2 > 0 else 999

        if d1 <= 10 or d2 <= 10:
            self.canvas.configure(cursor="sb_h_double_arrow")
        else:
            self.canvas.configure(cursor="")

    def _on_bar_click(self, event):
        if self.bloqueado:
            self._active_handle = None
            return

        self.canvas.focus_set()
        pos1 = getattr(self, '_pos_h1', -999)
        pos2 = getattr(self, '_pos_h2', -999)

        d1 = abs(event.x - pos1) if pos1 > 0 else 999
        d2 = abs(event.x - pos2) if pos2 > 0 else 999

        if pos1 > 0 and d1 <= 12 and d1 <= d2:
            self._active_handle = 1
        elif pos2 > 0 and d2 <= 12:
            self._active_handle = 2
        else:
            self._active_handle = None

    def _on_bar_drag(self, event):
        if self.bloqueado or not getattr(self, '_active_handle', None):
            return
        total = self.state.gb_totales
        if total <= 0:
            return

        x_start, x_end, _, _ = self._coords_bar()
        ancho_util = x_end - x_start
        mouse_x = max(x_start, min(x_end, event.x))
        gb_raw = ((mouse_x - x_start) / ancho_util) * total
        gb_cursor = round(gb_raw, 1) if (event.state & 0x0001) else round(gb_raw)

        base_h = 10.0 if self.state.descargar_pack_hollow else 3.0
        gb_bato = (self.state.tamanos_reales.get("bato_64", 0.0) if self.state.bato_64_act else 0.0) if self.state.instalar_bato else 0.0
        min_h = base_h + gb_bato
        min_c = 20.0 if self.state.instalar_cachy else 0.0
        min_libre = 5.0 if self.state.preservar_espacio else 0.0

        if self._active_handle == 1:
            if self.state.instalar_cachy:
                max_h = total - min_c - (self.state.val_libre_gb if self.state.preservar_espacio else 0.0)
                nueva_h = max(min_h, min(max_h, gb_cursor))
                self.state.val_hollow_gb = round(nueva_h, 1)

                if self.state.preservar_espacio:
                    self.state.val_cachy_gb = round(total - self.state.val_hollow_gb - self.state.val_libre_gb, 1)
                else:
                    self.state.val_cachy_gb = round(total - self.state.val_hollow_gb, 1)
                    self.state.val_libre_gb = 0.0
            else:
                max_h = total - min_libre
                nueva_h = max(min_h, min(max_h, gb_cursor))
                self.state.val_hollow_gb = round(nueva_h, 1)
                self.state.val_libre_gb = round(total - self.state.val_hollow_gb, 1) if self.state.preservar_espacio else 0.0
                self.state.val_cachy_gb = 0.0

        elif self._active_handle == 2:
            min_pos_gb = self.state.val_hollow_gb + min_c
            max_pos_gb = total - min_libre
            nuevo_pos = max(min_pos_gb, min(max_pos_gb, gb_cursor))

            self.state.val_cachy_gb = round(nuevo_pos - self.state.val_hollow_gb, 1)
            self.state.val_libre_gb = round(total - nuevo_pos, 1)

        self.actualizar()
        if self.on_change_callback:
            self.on_change_callback()

    def _on_bar_release(self, event):
        self._active_handle = None

    def actualizar(self):
        if not self.winfo_exists() or not self.canvas.winfo_exists():
            return
        w = self.canvas.winfo_width()
        if w <= 20:
            self.after(50, self.actualizar)
            return

        self.canvas.delete("all")
        total = self.state.gb_totales
        if total <= 0:
            self.canvas.create_text(w // 2, 42, text="Conecta o selecciona una unidad USB para ver particiones", fill="#64748b", font=("Segoe UI", 11, "italic"))
            return

        x_start, x_end, y1, y2 = self._coords_bar()
        ancho_util = x_end - x_start
        r_bar = 7
        y_mid = (y1 + y2) // 2

        self.canvas.create_line(x_start + r_bar, y_mid, x_end - r_bar, y_mid, width=16, capstyle="round", fill="#1e293b")
        self.canvas.create_line(x_start + r_bar, y_mid, x_end - r_bar, y_mid, width=14, capstyle="round", fill="#0f172a")

        pix_h = max(2, int((self.state.val_hollow_gb / total) * ancho_util))
        pix_c = int((self.state.val_cachy_gb / total) * ancho_util) if self.state.instalar_cachy else 0

        x_h_end = min(x_end, x_start + pix_h)
        x_c_end = min(x_end, x_h_end + pix_c)

        tiene_cachy = self.state.instalar_cachy and pix_c > 0
        tiene_libre = self.state.preservar_espacio and (x_c_end < x_end)

        # 1. Segmento HollowDrive
        rx1 = x_start
        rx2 = x_h_end
        if rx2 > rx1:
            c_fill = COLOR_HOLLOW
            self.canvas.create_rectangle(rx1, y1, rx2, y2, fill=c_fill, outline="")
            self.canvas.create_rectangle(rx1, y1, rx2, y1 + 3, fill=calc_brillo(c_fill, 1.4), outline="")

        # 2. Segmento CachyOS
        if tiene_cachy:
            cx1 = x_h_end
            cx2 = x_c_end
            if cx2 > cx1:
                c_fill = COLOR_CACHY
                self.canvas.create_rectangle(cx1, y1, cx2, y2, fill=c_fill, outline="")
                self.canvas.create_rectangle(cx1, y1, cx2, y1 + 3, fill=calc_brillo(c_fill, 1.4), outline="")

        # 3. Segmento Libre
        if tiene_libre:
            lx1 = x_c_end
            lx2 = x_end
            if lx2 > lx1:
                self.canvas.create_rectangle(lx1, y1, lx2, y2, fill=COLOR_LIBRE, outline="")

        # Textos e indicadores sobre los segmentos
        y_text = y2 + 20
        # Texto Hollow
        if pix_h > 45:
            self.canvas.create_text((x_start + x_h_end) // 2, y_text, text=f"HollowDrive: {self._formato_gb(self.state.val_hollow_gb)}", fill="#38bdf8", font=("Segoe UI", 10, "bold"))
        # Texto Cachy
        if tiene_cachy and pix_c > 45:
            self.canvas.create_text((x_h_end + x_c_end) // 2, y_text, text=f"CachyOS: {self._formato_gb(self.state.val_cachy_gb)}", fill="#34d399", font=("Segoe UI", 10, "bold"))
        # Texto Libre
        if tiene_libre and (x_end - x_c_end) > 40:
            self.canvas.create_text((x_c_end + x_end) // 2, y_text, text=f"Libre: {self._formato_gb(self.state.val_libre_gb)}", fill="#94a3b8", font=("Segoe UI", 10, "bold"))

        # Dibujar Manetas interactivas
        hy1, hy2 = y1 - 4, y2 + 4
        if tiene_cachy or tiene_libre:
            self._pos_h1 = x_h_end
            self._dibujar_maneta(x_h_end, hy1, hy2, AZUL_CIAN[1])
        else:
            self._pos_h1 = -999

        if tiene_cachy and tiene_libre:
            self._pos_h2 = x_c_end
            self._dibujar_maneta(x_c_end, hy1, hy2, COLOR_CACHY)
        else:
            self._pos_h2 = -999
