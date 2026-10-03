import customtkinter as ctk
from ui.theme import AZUL_CARD, AZUL_CIAN, AZUL_ELECTRICO, AZUL_SUAVE

class DynamicTaskItem:
    """ Tarjeta de tarea con barra de progreso individual para tareas concurrentes """
    def __init__(self, contenedor, id_tarea, titulo, color_barra=AZUL_CIAN):
        self.id_tarea = id_tarea
        self.frame = ctk.CTkFrame(contenedor, fg_color="#090d12", corner_radius=8, border_width=1, border_color="#1e293b")
        self.frame.pack(fill="x", pady=3, padx=5, expand=True)

        self.lbl_status = ctk.CTkLabel(self.frame, text=titulo, font=("Consolas", 11, "bold"), text_color=AZUL_SUAVE)
        self.lbl_status.pack(anchor="w", padx=10, pady=(4, 2))

        self.p_bar = ctk.CTkProgressBar(self.frame, height=8, progress_color=color_barra)
        self.p_bar.set(0)
        self.p_bar.pack(fill="x", padx=10, pady=(0, 6))

    def actualizar(self, progreso, texto):
        self.p_bar.set(progreso)
        self.lbl_status.configure(text=texto)

    def destruir(self):
        self.frame.destroy()


class ProgressPanel(ctk.CTkFrame):
    """
    Panel de progreso en tiempo real multi-tarea:
    - Indicador de estado general
    - Barra de progreso de paso/tarea actual
    - Barra de progreso total
    - Soporte para tareas secundarias dinámicas
    - Botón de cancelación
    - Soporte para animación GIF
    """
    def __init__(self, master, on_cancel=None, **kwargs):
        super().__init__(master, fg_color=AZUL_CARD, corner_radius=12, border_width=1, border_color="#1e293b", **kwargs)
        self.on_cancel = on_cancel
        self.tareas_dinamicas = {}

        # Contenedor Horizontal
        self.f_main_row = ctk.CTkFrame(self, fg_color="transparent")
        self.f_main_row.pack(fill="both", expand=True, padx=12, pady=10)

        # Label de GIF (Izquierda)
        self.lbl_gif = ctk.CTkLabel(self.f_main_row, text="")
        self.lbl_gif.pack(side="left", padx=(5, 12))

        # Barras de Progreso (Centro)
        self.f_bars = ctk.CTkFrame(self.f_main_row, fg_color="transparent")
        self.f_bars.pack(side="left", fill="both", expand=True)

        self.lbl_status = ctk.CTkLabel(
            self.f_bars,
            text="ESPERANDO INICIO...",
            font=("Consolas", 12, "bold"),
            text_color=AZUL_SUAVE
        )
        self.lbl_status.pack(anchor="w", padx=2, pady=(0, 3))

        # Barra Paso Actual
        self.p_task = ctk.CTkProgressBar(self.f_bars, height=8, progress_color=AZUL_CIAN)
        self.p_task.set(0)
        self.p_task.pack(fill="x", padx=2, pady=2)

        # Barra Total
        self.p_total = ctk.CTkProgressBar(self.f_bars, height=8, progress_color=AZUL_ELECTRICO)
        self.p_total.set(0)
        self.p_total.pack(fill="x", padx=2, pady=2)

        # Contenedor dinámico para sub-tareas
        self.f_subtasks = ctk.CTkScrollableFrame(self.f_bars, height=75, fg_color="transparent")

        # Botón Cancelar (Derecha)
        self.btn_cancel = ctk.CTkButton(
            self.f_main_row,
            text="❌ CANCELAR",
            font=("Segoe UI", 12, "bold"),
            fg_color="#aa3333",
            hover_color="#882222",
            width=110,
            height=38,
            corner_radius=8,
            command=self.on_cancel
        )
        self.btn_cancel.pack(side="right", padx=(10, 5))

    def set_status(self, text, color="suave"):
        colors = {
            "suave": AZUL_SUAVE,
            "cian": AZUL_CIAN,
            "rojo": "#ef4444",
            "verde": "#10b981",
            "normal": "#f8fafc"
        }
        self.lbl_status.configure(text=text, text_color=colors.get(color, "#f8fafc"))

    def set_task_progress(self, val):
        self.p_task.set(max(0.0, min(1.0, val)))

    def set_total_progress(self, val):
        self.p_total.set(max(0.0, min(1.0, val)))

    def reset(self):
        self.p_task.set(0)
        self.p_total.set(0)
        self.set_status("ESPERANDO INICIO...", "suave")
        self.f_subtasks.pack_forget()
        for t in list(self.tareas_dinamicas.values()):
            t.destruir()
        self.tareas_dinamicas.clear()

    def crear_tarea_dinamica(self, id_tarea, titulo, color=AZUL_CIAN):
        if not self.f_subtasks.winfo_ismapped():
            self.f_subtasks.pack(fill="x", expand=True, pady=(4, 0))

        if id_tarea in self.tareas_dinamicas:
            self.tareas_dinamicas[id_tarea].destruir()

        item = DynamicTaskItem(self.f_subtasks, id_tarea, titulo, color)
        self.tareas_dinamicas[id_tarea] = item
        return item

    def actualizar_tarea_dinamica(self, id_tarea, progreso, texto):
        if id_tarea in self.tareas_dinamicas:
            self.tareas_dinamicas[id_tarea].actualizar(progreso, texto)

    def eliminar_tarea_dinamica(self, id_tarea):
        if id_tarea in self.tareas_dinamicas:
            self.tareas_dinamicas[id_tarea].destruir()
            del self.tareas_dinamicas[id_tarea]

        if not self.tareas_dinamicas:
            self.f_subtasks.pack_forget()
