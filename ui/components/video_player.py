import os
import threading
import time
import tkinter as tk
from PIL import Image, ImageTk
import customtkinter as ctk
import imageio.v3 as iio

class EmbeddedVideoLoop(ctk.CTkFrame):
    """
    Componente de reproductor de vídeo integrado en bucle (.mp4).
    Ocupa el ancho central de la pantalla, utiliza vídeos optimizados de 24fps
    y decodifica en un hilo de fondo sin bloquear la interfaz.
    """
    def __init__(self, master, video_basename, width=640, height=340, **kwargs):
        super().__init__(master, fg_color="#000000", corner_radius=12, border_width=1, border_color="#1e293b", width=width, height=height, **kwargs)
        self.pack_propagate(False)
        self.video_width = width
        self.video_height = height
        self.video_basename = video_basename
        self._video_path = self._localizar_video(video_basename)
        self._corriendo = False
        self._hilo = None

        self.lbl_video = tk.Label(self, bg="#000000")
        self.lbl_video.place(relx=0.5, rely=0.5, anchor="center")

    def _localizar_video(self, base):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        nombres = [f"{base}_opt.mp4", f"{base}.mp4"]
        carpetas = [
            os.path.join(base_dir, "media"),
            os.path.join(base_dir, "docs", "media", "videos"),
            os.path.join(base_dir, "media", "videos")
        ]
        for n in nombres:
            for c in carpetas:
                ruta = os.path.join(c, n)
                if os.path.exists(ruta):
                    return ruta
        return None

    def cambiar_video(self, nuevo_basename):
        self.detener()
        self.video_basename = nuevo_basename
        self._video_path = self._localizar_video(nuevo_basename)
        self.iniciar()

    def iniciar(self):
        if not self._video_path or not os.path.exists(self._video_path):
            self.lbl_video.configure(text=f"Vídeo '{self.video_basename}' no encontrado", fg="#ef4444", font=("Segoe UI", 11))
            return
        if self._corriendo:
            return
        self._corriendo = True
        self._hilo = threading.Thread(target=self._bucle, daemon=True)
        self._hilo.start()

    def detener(self):
        self._corriendo = False

    def _bucle(self):
        fps = 24.0
        frame_time = 1.0 / fps

        while self._corriendo:
            try:
                for frame in iio.imiter(self._video_path):
                    if not self._corriendo:
                        break

                    t_inicio = time.time()
                    img = Image.fromarray(frame).resize((self.video_width, self.video_height), Image.Resampling.BILINEAR)
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
