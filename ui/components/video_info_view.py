import os
import threading
import time
import tkinter as tk
from PIL import Image, ImageTk
import customtkinter as ctk
import imageio.v3 as iio
from ui.theme import AZUL_CARD, AZUL_CIAN, AZUL_ELECTRICO, COLOR_BORDE

class VideoInfoView(ctk.CTkFrame):
    """
    Vista de información con reproducción en bucle del vídeo demostrativo (.mp4).
    Incluye barra superior con botón para volver a las opciones y descripción informativa.
    """
    def __init__(self, master, video_filename, titulo, descripcion, on_volver, **kwargs):
        super().__init__(master, fg_color="#0a0f18", corner_radius=0, **kwargs)
        self.video_filename = video_filename
        self.titulo = titulo
        self.descripcion = descripcion
        self.on_volver = on_volver

        self._corriendo = False
        self._hilo = None
        self._video_path = self._localizar_video(video_filename)

        # 1. Barra Superior con Título y Botón Volver
        f_top = ctk.CTkFrame(self, fg_color="transparent", height=45)
        f_top.pack(fill="x", padx=25, pady=(12, 6))

        self.btn_volver = ctk.CTkButton(
            f_top,
            text="⬅ Volver a Opciones",
            font=("Segoe UI", 12, "bold"),
            fg_color="#1e293b",
            hover_color="#334155",
            width=150,
            height=34,
            corner_radius=8,
            cursor="hand2",
            command=self._al_volver_click
        )
        self.btn_volver.pack(side="left")

        lbl_tit = ctk.CTkLabel(
            f_top,
            text=self.titulo.upper(),
            font=("Segoe UI", 16, "bold"),
            text_color=AZUL_CIAN[1]
        )
        lbl_tit.pack(side="right")

        # 2. Marco del Reproductor de Vídeo (520x292 para aspect ratio 16:9)
        self.f_video_frame = ctk.CTkFrame(
            self,
            fg_color="#000000",
            corner_radius=12,
            border_width=2,
            border_color=AZUL_ELECTRICO,
            width=500,
            height=280
        )
        self.f_video_frame.pack(pady=(4, 8))
        self.f_video_frame.pack_propagate(False)

        self.lbl_video = tk.Label(self.f_video_frame, bg="#000000")
        self.lbl_video.place(relx=0.5, rely=0.5, anchor="center")

        # 3. Texto descriptivo inferior
        if self.descripcion:
            self.lbl_desc = ctk.CTkLabel(
                self,
                text=self.descripcion,
                font=("Segoe UI", 11),
                text_color="#94a3b8",
                wraplength=640,
                justify="center"
            )
            self.lbl_desc.pack(padx=20, pady=(2, 6))

    def _localizar_video(self, nombre):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        rutas_posibles = [
            os.path.join(base_dir, "media", nombre),
            os.path.join(base_dir, "docs", "media", "videos", nombre),
            os.path.join(base_dir, "media", "videos", nombre)
        ]
        for r in rutas_posibles:
            if os.path.exists(r):
                return r
        return None

    def iniciar(self):
        """ Inicia la reproducción en bucle en segundo plano """
        if not self._video_path or not os.path.exists(self._video_path):
            self.lbl_video.configure(text=f"Vídeo '{self.video_filename}' no disponible", fg="#ef4444", font=("Segoe UI", 12))
            return

        self._corriendo = True
        self._hilo = threading.Thread(target=self._bucle_video, daemon=True)
        self._hilo.start()

    def detener(self):
        """ Detiene la reproducción y libera recursos """
        self._corriendo = False

    def _al_volver_click(self):
        self.detener()
        if self.on_volver:
            self.on_volver()

    def _bucle_video(self):
        fps = 25.0
        frame_time = 1.0 / fps

        while self._corriendo:
            try:
                for frame in iio.imiter(self._video_path):
                    if not self._corriendo:
                        break

                    t_inicio = time.time()

                    # Convertir a PIL y PhotoImage en resolución reducida para fluidez total
                    img = Image.fromarray(frame).resize((490, 275), Image.Resampling.BILINEAR)
                    pimg = ImageTk.PhotoImage(img)

                    def actualizar(pi=pimg):
                        if self._corriendo and self.lbl_video.winfo_exists():
                            self.lbl_video.configure(image=pi)
                            self.lbl_video.image = pi

                    self.lbl_video.after(0, actualizar)

                    t_espera = max(0.005, frame_time - (time.time() - t_inicio))
                    time.sleep(t_espera)

            except Exception:
                time.sleep(0.5)
