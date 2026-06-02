from engine.download_manager import descargar_y_extraer_ventoy
from engine.disk_logic import obtener_unidades_usb
from tkinter import messagebox
from PIL import Image, ImageSequence, ImageTk
import customtkinter as ctk
import tkinter as tk
import threading
import webbrowser
import time
import os
import sys

def resource_path(relative_path):
    """ Obtiene la ruta absoluta de los recursos, compatible con PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- CONFIGURACIÓN ESTRUCTURAL ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CARPETA_MEDIA = resource_path("media")

# --- CONFIGURACIÓN ESTÉTICA ---
AZUL_FONDO = "#05080a"  
AZUL_CARD = "#0d1117"   
AZUL_CIAN = "#00d4ff"       
AZUL_ELECTRICO = "#005eff"  
AZUL_SUAVE = "#70a1ff"
COLOR_HOLLOW, COLOR_CACHY = "#1e3799", "#2ecc71"  
COLOR_LIMINE, COLOR_LIBRE = "#4b6584", "#444444"
VERDE_EXITO = "#2ecc71"
GB_GRUB = 0.5

class SavinOceanicCommand(ctk.CTk):

    def verificar_herramientas(self):
        """Verifica si Ventoy ya existe en la carpeta tools."""
        tools_path = os.path.join("engine", "tools")
        if os.path.exists(tools_path):
            if any("ventoy" in f.lower() for f in os.listdir(tools_path)):
                return True
        return False
    
    def animar_pulso(self):
        if not hasattr(self, 'lbl_btn_descarga') or not self.lbl_btn_descarga.winfo_exists():
            return

        step = 2           
        min_s = 500        
        max_s = 560        

        if self.creciendo:
            self.tamaño_actual += step
            if self.tamaño_actual >= max_s: 
                self.creciendo = False
        else:
            self.tamaño_actual -= step
            if self.tamaño_actual <= min_s: 
                self.creciendo = True

        if self.img_descarga_data:
            nuevo_tam = int(self.tamaño_actual)
            self.img_descarga_data.configure(size=(nuevo_tam, nuevo_tam))
        
        self.animacion_id = self.after(120, self.animar_pulso)

    def clic_en_descarga(self):
        """Gestión del click: Detiene el pulso y cambia el botón por la barra."""
        if self.animacion_id:
            try:
                self.after_cancel(self.animacion_id)
            except:
                pass
            self.animacion_id = None

        if hasattr(self, 'lbl_btn_descarga'):
            self.lbl_btn_descarga.destroy()
        if hasattr(self, 'lbl_info'):
            self.lbl_info.destroy()
        if hasattr(self, 'btn_info_ventoy'):
            self.btn_info_ventoy.destroy()

        if hasattr(self, 'prog_descarga'):
            self.prog_descarga.place(relx=0.5, rely=0.5, anchor="center")
            threading.Thread(target=self.ejecutar_descarga, daemon=True).start()
        else:
            print("Error: La barra de progreso no fue inicializada.")

    def ejecutar_descarga(self):
        """Ejecuta la descarga de Ventoy y cierra la capa al terminar."""
        def update_bar(val):
            self.after(0, lambda: self.prog_descarga.set(val))

        exito = descargar_y_extraer_ventoy(progress_callback=update_bar)
        
        if exito:
            time.sleep(1) 
            self.after(0, self.overlay.destroy)
            print("Descarga completa: Capa de bloqueo eliminada.")
        else:
            self.after(0, lambda: self.prog_descarga.configure(progress_color="red"))
            print("Error crítico en la descarga de complementos.")

    def abrir_info_ventoy(self):
        """Ventana informativa sobre la descarga base de Ventoy"""
        v = self.creventana_info_base("INFORMACIÓN DE COMPLEMENTOS", 620, 340)
        frame_interno = ctk.CTkFrame(v, fg_color="transparent")
        frame_interno.pack(expand=True, fill="both", padx=25, pady=20)
        
        ctk.CTkLabel(frame_interno, text="🔧 COMPLEMENTO CORE: VENTOY", font=("Impact", 26), text_color=AZUL_CIAN).pack(pady=(0, 15))
        info = ("Ventoy es una herramienta open-source esencial que gestiona el entorno multi-boot de tu HollowDrive.\n\n"
                "Permite arrancar múltiples sistemas operativos directamente desde archivos ISO sin formatear la unidad. "
                "Haz click abajo si deseas conocer más detalles en su ecosistema oficial.")
        ctk.CTkLabel(frame_interno, text=info, font=("Segoe UI", 14), justify="center", wraplength=540).pack(pady=5)
        
        f_botones = ctk.CTkFrame(frame_interno, fg_color="transparent")
        f_botones.pack(pady=(20, 0))
        
        ctk.CTkButton(f_botones, text="VISITAR VENTOY", font=("Segoe UI", 12, "bold"), 
                      fg_color=AZUL_CARD, border_width=1, border_color=AZUL_CIAN, height=40, width=180,
                      command=lambda: self.abrir_url("https://www.ventoy.net")).pack(side="left", padx=10)
                      
        ctk.CTkButton(f_botones, text="ENTENDIDO", font=("Segoe UI", 12, "bold"), 
                      fg_color=AZUL_ELECTRICO, height=40, width=140, command=v.destroy).pack(side="left", padx=10)
        v.update(); v.grab_set()

    def mostrar_capa_descarga(self):
        if self.verificar_herramientas():
            return

        overlay_color = ("#D9D9D9", "#1A1A1A")
        self.overlay = ctk.CTkFrame(self, fg_color=overlay_color)
        self.overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.prog_descarga = ctk.CTkProgressBar(
            self.overlay, width=400, progress_color=VERDE_EXITO
        )
        self.prog_descarga.set(0)

        # Botón de información de Ventoy usando I.png ampliado (45x45)
        self.btn_info_ventoy = ctk.CTkButton(
            self.overlay, 
            image=self.img_info_descarga if hasattr(self, 'img_info_descarga') else None,
            text="" if hasattr(self, 'img_info_descarga') else "I",
            width=120, 
            height=120, 
            fg_color="transparent",
            hover_color="#122d3d",
            command=self.abrir_info_ventoy
        )
        self.btn_info_ventoy.place(relx=0.5, rely=0.92, anchor="center")

        if self.img_descarga_data:
            self.tamaño_actual = 500
            self.img_descarga_data.configure(size=(500, 500))
            
            self.lbl_btn_descarga = ctk.CTkButton(
                self.overlay,
                image=self.img_descarga_data,
                text="",
                fg_color="transparent",
                hover_color=overlay_color,
                width=600, height=600,
                cursor="hand2",
                command=self.clic_en_descarga
            )
            self.lbl_btn_descarga.place(relx=0.5, rely=0.45, anchor="center")
            
            self.animar_pulso()
            
            self.lbl_info = ctk.CTkLabel(
                self.overlay, 
                text="PULSA EL ICONO PARA DESCARGAR COMPLEMENTOS",
                font=("Arial", 16, "bold"), 
                text_color=AZUL_CIAN
            )
            self.lbl_info.place(relx=0.5, rely=0.85, anchor="center")

    def refrescar_discos(self):
        print(f"Refrescando... (Internos: {self.mostrar_internos.get()})")
        self.lista_discos_reales = obtener_unidades_usb(incluir_internos=self.mostrar_internos.get())
        
        if not self.lista_discos_reales:
            self.combo_disk.configure(values=["⚠️ NO SE DETECTAN UNIDADES"])
            self.combo_disk.set("⚠️ NO SE DETECTAN UNIDADES")
        else:
            nombres = [d["display"] for d in self.lista_discos_reales]
            self.combo_disk.configure(values=nombres)
            self.combo_disk.set("--- Selecciona una unidad ---")

    def abrir_url(self, url):
        webbrowser.open_new_tab(url)

    def crear_boton_info(self, master, comando):
        """ Genera un botón informativo usando la imagen triangulo.png a tamaño 30x30 """
        return ctk.CTkButton(
            master, 
            image=self.img_triangulo if hasattr(self, 'img_triangulo') else None,
            text="" if hasattr(self, 'img_triangulo') else "▲",
            width=30, 
            height=30, 
            fg_color="transparent",
            hover_color="#122d3d",
            command=comando
        )
    
    def alternar_modo_instalacion(self, en_progreso=True):
        """ Intercambia visualmente el botón de instalar por el panel de progreso y cancelación """
        if en_progreso:
            self.btn_start.pack_forget()
            self.f_progress.pack(side="left", fill="x", expand=True, padx=(0, 10))
            self.btn_cancel.pack(side="right", padx=10)
        else:
            self.f_progress.pack_forget()
            self.btn_cancel.pack_forget()
            self.btn_start.pack(pady=5)

    def confirmar_inicio(self):
        if messagebox.askyesno("CONFIRMACIÓN", "¿Proceder con la instalación?"): 
            self.abortar_proceso = False
            self.alternar_modo_instalacion(True) 
            threading.Thread(target=self.proceso_real, daemon=True).start()

    def cancelar_proceso(self):
        if messagebox.askyesno("CANCELAR", "¿Seguro que deseas cancelar el proceso?"):
            self.abortar_proceso = True
            self.lbl_status.configure(text="CANCELANDO...", text_color="#ff4d4d")

    def mostrar_info(self, titulo, mensaje):
        messagebox.showinfo(titulo, mensaje)

    def __init__(self):
        super().__init__()
        self.title("SAVIN SUPER_USB // V12.5")
        self.geometry("1000x850")
        self.resizable(False, False)
        
        self.animacion_id = None
        self.gif_after_id = None
        self.creciendo = True
        self.tamaño_actual = 180
        self.img_descarga_data = None
        self.progreso_valor = ctk.DoubleVar(master=self, value=0.0)
        
        self.en_proceso = False
        self.abortar_proceso = False
        self.widgets_interactivos = []
        self.mostrar_internos = ctk.BooleanVar(master=self, value=False)
        self.gb_totales = 0.0 
        self.min_cachy = 20.0 
        
        # Historial de posiciones de los sliders para anular el parpadeo
        self.ultimo_h = 3.0
        self.ultimo_c = 20.0
        
        self.instalar_bato = ctk.BooleanVar(master=self, value=False)
        self.instalar_cachy = ctk.BooleanVar(master=self, value=False) 
        
        self.bato_64_act = ctk.BooleanVar(master=self, value=True)
        self.bato_32_act = ctk.BooleanVar(master=self, value=False)
        self.bato_atom_act = ctk.BooleanVar(master=self, value=False)
        self.preservar_espacio = ctk.BooleanVar(master=self, value=False)
        
        # --- CONFIGURACIÓN DE PACKS ADICIONALES ---
        self.descargar_pack_bato = ctk.BooleanVar(master=self, value=False)
        self.pack_bato_size_var = ctk.StringVar(master=self, value="16GB") # Inicializado en 16GB
        
        self.descargar_pack_hollow = ctk.BooleanVar(master=self, value=False)
        self.pack_hollow_size_var = ctk.StringVar(master=self, value="6GB")

        self.configure(fg_color=AZUL_FONDO) 
        self.attributes("-alpha", 0.94)
        
        self.cargar_recursos() 
        self.setup_ui()
        
        # Sincronizamos las barras de opciones al iniciar el programa
        self.actualizar_estados_bato()
        self.actualizar_estados_cachy()
        
        self.refrescar_discos()

        self.after(100, self.mostrar_capa_descarga)
        self.protocol("WM_DELETE_WINDOW", self.cerrar_aplicacion)

    def cerrar_aplicacion(self):
        if self.animacion_id:
            self.after_cancel(self.animacion_id)
        if self.gif_after_id:
            self.after_cancel(self.gif_after_id)
        self.destroy()

    def toggle_discos_internos(self):
        if self.mostrar_internos.get():
            confirmar = messagebox.askyesno(
                "⚠️ MODO PELIGRO", 
                "Vas a habilitar la visualización de DISCOS INTERNOS.\n\n"
                "Instalar HollowDrive en un disco interno BORRARÁ TODO su contenido.\n"
                "¿Estás seguro de que quieres continuar?",
                icon='warning'
            )
            if not confirmar:
                self.mostrar_internos.set(False)
                return
        self.refrescar_discos()

    def cargar_gif_pil(self, ruta_gif, size=(70, 70), espejo=False):
        """ Carga y redimensiona fotogramas de un GIF usando PIL """
        if not os.path.exists(ruta_gif):
            print(f"Advertencia: No se localiza el recurso GIF en {ruta_gif}")
            return []
        try:
            pil_img = Image.open(ruta_gif)
            frames = []
            for frame in ImageSequence.Iterator(pil_img):
                frame_resized = frame.copy().resize(size, Image.Resampling.LANCZOS)
                # 🔄 Si pasamos espejo=True, invertimos el fotograma horizontalmente
                if espejo:
                    frame_resized = frame_resized.transpose(Image.FLIP_LEFT_RIGHT)
                frames.append(ImageTk.PhotoImage(frame_resized))
            return frames
        except Exception as e:
            print(f"Error parseando estructura del GIF: {e}")
            return []

    def cargar_recursos(self):
        path_media = os.path.join(os.path.dirname(__file__), "media")
        try:
            img_bato = Image.open(os.path.join(path_media, "batocera.png"))
            self.logo_batocera = ctk.CTkImage(light_image=img_bato, dark_image=img_bato, size=(120, 120))
            img_cachy = Image.open(os.path.join(path_media, "cachy.png"))
            self.logo_cachy = ctk.CTkImage(light_image=img_cachy, dark_image=img_cachy, size=(280, 78))
            img_savin = Image.open(os.path.join(path_media, "Savin-2.png"))
            self.logo_savin = ctk.CTkImage(light_image=img_savin, dark_image=img_savin, size=(240, 135))
            img_maker = Image.open(os.path.join(path_media, "HollowDrive-2.png"))
            self.logo_maker = ctk.CTkImage(light_image=img_maker, dark_image=img_maker, size=(520, 310))
        except:
            self.logo_savin = self.logo_maker = self.logo_batocera = self.logo_cachy = None

        img_instalar_path = os.path.join(path_media, "instalar.png")
        if os.path.exists(img_instalar_path):
            try:
                pil_instalar = Image.open(img_instalar_path)
                self.img_instalar = ctk.CTkImage(light_image=pil_instalar, dark_image=pil_instalar, size=(512, 120))
            except Exception as e:
                print(f"Error cargando instalar.png: {e}")
                self.img_instalar = None
        else:
            self.img_instalar = None

        img_path = os.path.join(CARPETA_MEDIA, "descarga-morada.png")
        if os.path.exists(img_path):
            try:
                pil_image = Image.open(img_path)
                self.img_descarga_data = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=(350, 350))
            except Exception as e:
                print(f"Error abriendo imagen de descarga: {e}")

        # Recurso reload.png para el botón de actualización de discos
        img_reload_path = os.path.join(path_media, "reload.png")
        if os.path.exists(img_reload_path):
            try:
                pil_reload = Image.open(img_reload_path)
                self.img_reload = ctk.CTkImage(light_image=pil_reload, dark_image=pil_reload, size=(25, 25))
            except Exception as e:
                print(f"Error cargando reload.png: {e}")
                self.img_reload = None
        else:
            self.img_reload = None

        self.frames_linterna = self.cargar_gif_pil(os.path.join(CARPETA_MEDIA, "hollow-linterna.gif"), espejo=True)
        self.frames_breakdance = self.cargar_gif_pil(os.path.join(CARPETA_MEDIA, "breakdance.gif"))
    def setup_ui(self):
        ruta_i = os.path.join(CARPETA_MEDIA, "I.png")
        if os.path.exists(ruta_i):
            img_i_pil = Image.open(ruta_i)
            self.img_info = ctk.CTkImage(light_image=img_i_pil, dark_image=img_i_pil, size=(100, 100))
            self.img_info_descarga = ctk.CTkImage(light_image=img_i_pil, dark_image=img_i_pil, size=(120, 120))
        
        ruta_triangulo = os.path.join(CARPETA_MEDIA, "triangulo.png")
        if os.path.exists(ruta_triangulo):
            img_t_pil = Image.open(ruta_triangulo)
            self.img_triangulo = ctk.CTkImage(light_image=img_t_pil, dark_image=img_t_pil, size=(30, 30))

        # --- CABECERA ---
        self.header = ctk.CTkFrame(self, fg_color="transparent", height=120)
        self.header.pack(fill="x", padx=20, pady=0)
        if self.logo_savin:
            ctk.CTkLabel(self.header, image=self.logo_savin, text="").place(x=0, y=-10)
        if self.logo_maker:
            ctk.CTkLabel(self.header, image=self.logo_maker, text="").place(relx=0.5, y=-85, anchor="n")
            
        self.btn_info_main = ctk.CTkButton(self, image=self.img_info if hasattr(self, 'img_info') else None,
                                          text="" if hasattr(self, 'img_info') else "I", 
                                          width=100, height=100, fg_color="transparent", 
                                          hover_color=AZUL_CARD, command=self.abrir_ventana_info)
        self.btn_info_main.place(x=880, y=10)

        # --- SELECTOR DE DISCOS ---
        self.f_selection = ctk.CTkFrame(self, fg_color=AZUL_CARD, border_width=1, border_color=AZUL_ELECTRICO)
        self.f_selection.pack(fill="x", padx=20, pady=(0, 10)) 
        
        ctk.CTkLabel(self.f_selection, text="Selecciona un dispositivo para instalar HOLLOWDRIVE.", 
                     font=("Segoe UI", 15, "italic"), text_color=AZUL_SUAVE).pack(pady=(10,0))
        
        f_combo = ctk.CTkFrame(self.f_selection, fg_color="transparent")
        f_combo.pack(pady=15)

        self.combo_disk = ctk.CTkComboBox(f_combo, values=["Buscando unidades..."], 
                                         width=450, command=self.activar_interfaz_completa)
        self.combo_disk.set("Buscando unidades...")
        self.combo_disk.pack(side="left", padx=10)
        self.widgets_interactivos.append(self.combo_disk)

        # Botón de refresco usando reload.png
        self.btn_refresh = ctk.CTkButton(
            f_combo, 
            image=self.img_reload if hasattr(self, 'img_reload') and self.img_reload else None,
            text="" if hasattr(self, 'img_reload') and self.img_reload else "🔄", 
            width=40, height=40, fg_color="#222", 
            command=self.refrescar_discos
        )
        self.btn_refresh.pack(side="left", padx=5)

        self.sw_internos = ctk.CTkCheckBox(f_combo, text="Mostrar discos internos", 
                                          variable=self.mostrar_internos,
                                          command=self.toggle_discos_internos,
                                          text_color="#aa3333", font=("Segoe UI", 11, "bold"))
        self.sw_internos.pack(side="left", padx=10)

        # --- CONTENEDOR MAESTRO ---
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        
        # PANEL IZQUIERDO (CONFIGURACIONES)
        self.p_left = ctk.CTkFrame(self.main_container, fg_color=AZUL_CARD, corner_radius=15, border_width=1, border_color="#222")
        self.p_left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        # SECCIÓN BATOCERA
        f_bato_master = ctk.CTkFrame(self.p_left, fg_color="transparent")
        f_bato_master.pack(fill="x", padx=15, pady=15)
        f_bato_txt = ctk.CTkFrame(f_bato_master, fg_color="transparent")
        f_bato_txt.pack(side="left", fill="both", expand=True)
        f_bato_h = ctk.CTkFrame(f_bato_txt, fg_color="transparent")
        f_bato_h.pack(fill="x")
        
        sw_bato = ctk.CTkSwitch(f_bato_h, text="¿Instalar Batocera?", font=("Segoe UI", 12, "bold"), 
                                variable=self.instalar_bato, command=self.actualizar_estados_bato, progress_color=AZUL_CIAN)
        sw_bato.pack(side="left")
        self.widgets_interactivos.append(sw_bato)
        
        self.crecar_boton_info = self.crear_boton_info(f_bato_h, self.abrir_info_batocera)
        self.crecar_boton_info.pack(side="left", padx=5)

        self.f_bato_opts = ctk.CTkFrame(f_bato_txt, fg_color="#0d141c", corner_radius=8)
        self.f_bato_opts.pack(fill="x", pady=5)
        self.ch_b64 = ctk.CTkCheckBox(self.f_bato_opts, text="Batocera 64bits (10GB)", variable=self.bato_64_act, command=self.rebalancear)
        self.ch_b64.pack(pady=2, padx=10, anchor="w")
        self.ch_b32 = ctk.CTkCheckBox(self.f_bato_opts, text="Batocera 32bits (1GB)", variable=self.bato_32_act, command=self.rebalancear)
        self.ch_b32.pack(pady=2, padx=10, anchor="w")
        self.ch_bat = ctk.CTkCheckBox(self.f_bato_opts, text="Batocera ATOM (1GB)", variable=self.bato_atom_act, command=self.rebalancear)
        self.ch_bat.pack(pady=2, padx=10, anchor="w")
        self.widgets_interactivos.extend([self.ch_b64, self.ch_b32, self.ch_bat])

        if self.logo_batocera:
            lbl_img_bato = ctk.CTkLabel(f_bato_master, image=self.logo_batocera, text="", cursor="hand2")
            lbl_img_bato.pack(side="right", padx=10)
            lbl_img_bato.bind("<Button-1>", lambda e: self.abrir_url("https://batocera.org"))

        # --- SECCIÓN DE PACKS ADICIONALES ---
        f_packs_container = ctk.CTkFrame(self.p_left, fg_color="#0d141c", corner_radius=8)
        f_packs_container.pack(fill="x", padx=15, pady=5)

        # 1. FILA: PACK BATOCERA
        f_pack_bato = ctk.CTkFrame(f_packs_container, fg_color="transparent")
        f_pack_bato.pack(fill="x", padx=10, pady=6)
        
        self.ch_pack_bato = ctk.CTkCheckBox(f_pack_bato, text="PACK BATOCERA", 
                                            variable=self.descargar_pack_bato, command=lambda: self.rebalancear("h"))
        self.ch_pack_bato.pack(side="left", anchor="w")
        self.widgets_interactivos.append(self.ch_pack_bato)
        
        self.crear_boton_info(f_pack_bato, self.abrir_info_roms).pack(side="left", padx=5)
        
        self.menu_pack_bato = ctk.CTkOptionMenu(f_pack_bato, values=["16GB", "32GB", "64GB"], 
                                                variable=self.pack_bato_size_var, command=lambda _: self.rebalancear("h"), 
                                                height=25, width=110)
        self.menu_pack_bato.pack(side="right", padx=5)
        self.widgets_interactivos.append(self.menu_pack_bato)

        # 2. FILA: PACK HOLLOWDRIVE
        f_pack_hollow = ctk.CTkFrame(f_packs_container, fg_color="transparent")
        f_pack_hollow.pack(fill="x", padx=10, pady=6)
        
        self.ch_pack_hollow = ctk.CTkCheckBox(f_pack_hollow, text="PACK HOLLOWDRIVE", 
                                              variable=self.descargar_pack_hollow, command=lambda: self.rebalancear("h"))
        self.ch_pack_hollow.pack(side="left", anchor="w")
        self.widgets_interactivos.append(self.ch_pack_hollow)
        
        self.crear_boton_info(f_pack_hollow, self.abrir_info_pack_hollow).pack(side="left", padx=5)
        
        self.menu_pack_hollow = ctk.CTkOptionMenu(f_pack_hollow, values=["6GB", "10GB", "20GB"], 
                                                 variable=self.pack_hollow_size_var, command=lambda _: self.rebalancear("h"), 
                                                 height=25, width=110)
        self.menu_pack_hollow.pack(side="right", padx=5)
        self.widgets_interactivos.append(self.menu_pack_hollow)

        # SECCIÓN CACHYOS
        f_cachy_master = ctk.CTkFrame(self.p_left, fg_color="transparent")
        f_cachy_master.pack(fill="x", padx=15, pady=15)
        if self.logo_cachy:
            lbl_img_cachy = ctk.CTkLabel(f_cachy_master, image=self.logo_cachy, text="", cursor="hand2")
            lbl_img_cachy.pack(pady=(0,10))
            lbl_img_cachy.bind("<Button-1>", lambda e: self.abrir_url("https://cachyos.org"))

        f_cachy_h = ctk.CTkFrame(f_cachy_master, fg_color="transparent")
        f_cachy_h.pack(fill="x")
        sw_cachy = ctk.CTkSwitch(f_cachy_h, text="¿Instalar CachyOS?", font=("Segoe UI", 12, "bold"), variable=self.instalar_cachy, command=self.actualizar_estados_cachy, progress_color=AZUL_CIAN)
        sw_cachy.pack(side="left")
        self.widgets_interactivos.append(sw_cachy)
        
        self.crear_boton_info(f_cachy_h, self.abrir_info_cachyos).pack(side="left", padx=5)

        # PANEL DERECHO (CONTROL DE ESPACIO Y GRÁFICA)
        self.p_right = ctk.CTkFrame(self.main_container, fg_color=AZUL_CARD, corner_radius=15, border_width=1, border_color="#222")
        self.p_right.pack(side="right", fill="both", expand=True)
        
        self.sw_preservar = ctk.CTkSwitch(self.p_right, text="BLOQUEAR LIBRE", variable=self.preservar_espacio, command=self.toggle_preservar_espacio, progress_color=AZUL_ELECTRICO)
        self.sw_preservar.pack(pady=10)
        self.widgets_interactivos.append(self.sw_preservar)

        # Sliders de control
        self.f_row_h = self.crear_ocean_slider(self.p_right, "HOLLOWDRIVE STORAGE", COLOR_HOLLOW, "h", min_val=3)
        self.f_row_c = self.crear_ocean_slider(self.p_right, "CACHYOS PARTITION", COLOR_CACHY, "c", min_val=20)

        self.canvas = tk.Canvas(self.p_right, height=40, bg=AZUL_CARD, highlightthickness=0, borderwidth=0)
        self.canvas.pack(fill="x", pady=(15, 5), padx=20)
        self.lbl_libre_info = ctk.CTkLabel(self.p_right, text="LIBRE: 0.00 GB", font=("Consolas", 18, "bold"), text_color=AZUL_CIAN)
        self.lbl_libre_info.pack()

        # --- LEYENDA DINÁMICA ---
        self.f_leyenda = ctk.CTkFrame(self.p_right, fg_color="transparent")
        self.f_leyenda.pack(pady=10, fill="x", padx=15)
        self.dic_leyenda = {}
        
        info_textos = {
            "Hollow": ("Partición HOLLOWDRIVE", "Espacio principal multi-boot (Ventoy). Incluye Batocera y packs de herramientas."),
            "GRUB": ("Arranque GRUB", "Partición esencial de arranque para el sistema (512 MB)."),
            "Cachy": ("Sistema CACHYOS", "Distribución Linux portable optimizada para alto rendimiento.")
        }

        for nombre, color in [("Hollow", COLOR_HOLLOW), ("GRUB", COLOR_LIMINE), ("Cachy", COLOR_CACHY)]:
            tit, msg = info_textos[nombre]
            btn = ctk.CTkButton(
                self.f_leyenda, text=f"{nombre} (0GB)", fg_color=color,
                width=140, height=28, corner_radius=15, text_color="white",
                font=("Segoe UI Bold", 11),
                command=lambda t=tit, m=msg: self.mostrar_info(t, m)
            )
            btn.pack(side="left", padx=10, expand=True)
            self.dic_leyenda[nombre.lower()] = btn

        # --- FOOTER ---
        self.footer = ctk.CTkFrame(self, fg_color="transparent")
        self.f_progress = ctk.CTkFrame(self.footer, fg_color="transparent")
        
        # Subcontenedor izquierdo para alinear barras
        self.f_bars_layout = ctk.CTkFrame(self.f_progress, fg_color="transparent")
        self.f_bars_layout.pack(side="left", fill="x", expand=True)
        
        self.lbl_status = ctk.CTkLabel(self.f_bars_layout, text="ESPERANDO INICIO...", font=("Consolas", 11), text_color=AZUL_SUAVE)
        self.lbl_status.pack(anchor="w")
        
        self.p_task = ctk.CTkProgressBar(self.f_bars_layout, height=4, progress_color=AZUL_CIAN)
        self.p_task.set(0)
        self.p_task.pack(fill="x", pady=2)
        
        self.p_total = ctk.CTkProgressBar(self.f_bars_layout, height=10, progress_color=AZUL_ELECTRICO)
        self.p_total.set(0)
        self.p_total.pack(fill="x", pady=2)
        
        # Etiqueta para los GIFs animados
        self.lbl_gif = ctk.CTkLabel(self.f_progress, text="", width=70, height=70)
        self.lbl_gif.pack(side="right", padx=(15, 0))
        
        self.btn_start = ctk.CTkButton(
            self.footer, 
            image=self.img_instalar if hasattr(self, 'img_instalar') else None,
            text="" if hasattr(self, 'img_instalar') else "🩵Instalar HollowDrive🩵",
            fg_color="transparent", 
            hover_color=AZUL_CARD,
            width=512,
            height=120,
            command=self.confirmar_inicio
        )
        self.btn_start.pack(pady=5)
        
        self.btn_cancel = ctk.CTkButton(
            self.footer, 
            text="CANCELAR", 
            fg_color="#aa3333", 
            width=120, 
            height=50, 
            command=self.cancelar_proceso
        )

    def toggle_preservar_espacio(self):
        """ Salva la posición justo al congelar el espacio """
        self.ultimo_h = self.slider_h.get()
        self.ultimo_c = self.slider_c.get()
        self.rebalancear()

    def bloquear_ui(self, bloquear=True):
        st = "disabled" if bloquear else "normal"
        for w in self.widgets_interactivos: w.configure(state=st)

    def creventana_info_base(self, titulo, ancho, alto):
        v = ctk.CTkToplevel(self)
        v.title(titulo)
        v.geometry(f"{ancho}x{alto}")
        v.configure(fg_color=AZUL_FONDO)
        v.attributes("-alpha", 0.96)
        v.resizable(False, False)
        v.transient(self) 
        v.lift()  
        v.focus_force()
        return v

    def abrir_info_batocera(self):
        v = self.creventana_info_base("¿QUÉ ES BATOCERA?", 620, 320)
        frame_interno = ctk.CTkFrame(v, fg_color="transparent")
        frame_interno.pack(expand=True, fill="both", padx=25, pady=20)
        ctk.CTkLabel(frame_interno, text="🎮 SOBRE BATOCERA", font=("Impact", 28), text_color=AZUL_CIAN).pack(pady=(0, 15))
        info = ("Batocera es un sistema de emulación que puede convertir\ncualquier ordenador en una consola de videojuegos.\n\n🛡️ SEGURIDAD DE DATOS:\nAunque inicies Batocera, NUNCA perderás los datos del ordenador.")
        ctk.CTkLabel(frame_interno, text=info, font=("Segoe UI", 14), justify="center", wraplength=550).pack(pady=5)
        ctk.CTkButton(frame_interno, text="ENTENDIDO", font=("Segoe UI", 14, "bold"), fg_color=AZUL_ELECTRICO, height=40, width=180, command=v.destroy).pack(pady=(15, 0))
        v.update(); v.grab_set()

    def abrir_info_cachyos(self):
        v = self.creventana_info_base("¿QUÉ ES CACHYOS?", 680, 440)
        frame_interno = ctk.CTkFrame(v, fg_color="transparent")
        frame_interno.pack(expand=True, fill="both", padx=25, pady=20)
        ctk.CTkLabel(frame_interno, text="🚀 CACHYOS: ARCH LINUX OPTIMIZADO", font=("Impact", 28), text_color=COLOR_CACHY).pack(pady=(0, 15))
        info = ("He preparado una version personalizada de CachyOS (Arch Linux)\ndiseñada específicamente para ser rápida y fácil de usar.\n\n⚡ CARACTERÍSTICAS PRINCIPALES:\n• Universal: Funciona en casi cualquier PC moderno.\n• Rendimiento: Optimizado para sacar el máximo provecho al hardware.\n• Portable: Llevas tu sistema operativo, archivos y apps siempre contigo.")
        ctk.CTkLabel(frame_interno, text=info, font=("Segoe UI", 14), justify="center", wraplength=600).pack(pady=5)
        ctk.CTkButton(frame_interno, text="¡EXCELENTE!", font=("Segoe UI", 14, "bold"), fg_color=AZUL_ELECTRICO, height=40, width=180, command=v.destroy).pack(pady=(15, 0))
        v.update(); v.grab_set()

    def abrir_info_roms(self):
        v = self.creventana_info_base("AVISO LEGAL", 620, 380)
        v.configure(fg_color="#1a0a0a") 
        frame_interno = ctk.CTkFrame(v, fg_color="transparent")
        frame_interno.pack(expand=True, fill="both", padx=25, pady=20)
        ctk.CTkLabel(frame_interno, text="⚠️ AVISO LEGAL", font=("Impact", 32), text_color="#ff4d4d").pack(pady=(0, 15))
        legal_text = ("Savin Super USB NO INCLUYE ROMS ni archivos de juegos\nprotegidos por derechos de autor.")
        ctk.CTkLabel(frame_interno, text=legal_text, font=("Segoe UI", 14), justify="center", wraplength=550).pack(pady=10)
        ctk.CTkButton(frame_interno, text="ACEPTO LOS RIESGOS", font=("Segoe UI", 14, "bold"), fg_color="#444", height=40, width=220, command=v.destroy).pack(pady=(15, 0))
        v.update(); v.grab_set()

    def abrir_info_pack_hollow(self):
        v = self.creventana_info_base("PACK HOLLOWDRIVE INFO", 620, 360)
        frame_interno = ctk.CTkFrame(v, fg_color="transparent")
        frame_interno.pack(expand=True, fill="both", padx=25, pady=20)
        
        ctk.CTkLabel(frame_interno, text="🛠️ PACK DE HERRAMIENTAS HOLLOWDRIVE", 
                     font=("Impact", 24), text_color=AZUL_CIAN).pack(pady=(0, 15))
        
        info = ("Este paquete inyecta una seleccion de entornos y utilidades de rescate "
                "booteables listas para usar desde el menú principal:\n\n"
                "• Herramientas avanzadas de particionado y gestión de discos.\n"
                "• Utilidades de clonación, backup y recuperación de datos.\n"
                "• Entornos Windows Live (WinPE) para reparar sistemas caídos.")
                
        ctk.CTkLabel(frame_interno, text=info, font=("Segoe UI", 14), justify="left", wraplength=550).pack(pady=5)
        ctk.CTkButton(frame_interno, text="ENTENDIDO", font=("Segoe UI", 14, "bold"), 
                      fg_color=AZUL_ELECTRICO, height=40, width=180, command=v.destroy).pack(pady=(15, 0))
        v.update(); v.grab_set()

    def abrir_ventana_info(self):
        v = self.creventana_info_base("SAVIN CORE INFO", 750, 720)
        frame_interno = ctk.CTkFrame(v, fg_color="transparent")
        frame_interno.pack(expand=True, fill="both", padx=25, pady=20)
        ctk.CTkLabel(frame_interno, text="≋ SAVIN CORE ENGINE ≋", font=("Impact", 38), text_color=AZUL_CIAN).pack(pady=(0, 15))
        ctk.CTkLabel(frame_interno, text="◈ MIS PLATAFORMAS ◈", font=("Consolas", 18, "bold"), text_color=AZUL_SUAVE).pack(pady=5)
        f_social = ctk.CTkFrame(frame_interno, fg_color="transparent")
        f_social.pack(pady=10)
        socials = [("💬 DISCORD", "https://discord.gg/HJvgmCRpGm"), ("📂 GITHUB", "https://github.com/MVP-Savyn"), ("📺 YOUTUBE", "https://youtube.com/@T0xicAre4")]
        for texto, url in socials:
            ctk.CTkButton(f_social, text=texto, font=("Consolas", 12, "bold"), fg_color=AZUL_CARD, border_width=1, border_color=AZUL_ELECTRICO, width=140, height=35, command=lambda u=url: webbrowser.open_new_tab(u)).pack(side="left", padx=8)
        credits = [("BATOCERA LINUX", "https://batocera.org"), ("CACHY OS", "https://cachyos.org"), ("LIMINE BOOTLOADER", "https://limine-bootloader.org")]
        for name, link in credits:
            row = ctk.CTkFrame(frame_interno, fg_color="transparent"); row.pack(fill="x", padx=100, pady=2)
            ctk.CTkLabel(row, text=f"• {name}", font=("Consolas", 13)).pack(side="left")
            ctk.CTkButton(row, text="Visitar", width=80, height=20, command=lambda l=link: webbrowser.open_new_tab(l)).pack(side="right")
        ctk.CTkButton(frame_interno, text="CERRAR", width=200, command=v.destroy).pack(pady=20)
        v.update(); v.grab_set()

    def activar_interfaz_completa(self, seleccion):
        if "---" in seleccion or "Buscando" in seleccion or "NO SE DETECTAN" in seleccion: 
            return
        
        disco_elegido = next((d for d in self.lista_discos_reales if d["display"] == seleccion), None)
        if disco_elegido:
            self.gb_totales = disco_elegido["size"]
        self.main_container.pack(fill="both", expand=True, padx=20, pady=5)
        self.footer.pack(fill="x", side="bottom", padx=20, pady=10)
        
        # Inicializamos los valores base
        self.ultimo_h = 10.0
        self.ultimo_c = 20.0
        self.slider_h.set(10.0)
        
        # Forzamos una pasada de rebalancear para bloquearlos desde el inicio
        self.rebalancear()

    def crear_ocean_slider(self, parent, label, color, key, min_val=10):
        f = ctk.CTkFrame(parent, fg_color="transparent"); f.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(f, text=f"❯ {label}", font=("Consolas", 11, "bold")).pack(anchor="w")
        row = ctk.CTkFrame(f, fg_color="transparent"); row.pack(fill="x")
        s = ctk.CTkSlider(row, from_=min_val, to=1000, progress_color=color, command=lambda v, k=key: self.rebalancear(k))
        s.pack(side="left", fill="x", expand=True)
        setattr(self, f"slider_{key}", s)
        self.widgets_interactivos.append(s)
        l_val = ctk.CTkLabel(row, text="0 GB", width=70, font=("Consolas", 14, "bold")); l_val.pack(side="right")
        setattr(self, f"lbl_{key}_gb", l_val)
        return f

    def rebalancear(self, source=None):
        if self.gb_totales <= 0: return
        
        # 🔴 LÓGICA INVERTIDA: Si NO está activado "Bloquear Libre", bloqueamos el movimiento
        if not self.preservar_espacio.get():
            if source == "h":
                self.slider_h.set(self.ultimo_h)
                return
            elif source == "c":
                self.slider_c.set(self.ultimo_c)
                return
        # 1. Base del sistema y estado de CachyOS
        espacio_grub = GB_GRUB if self.instalar_cachy.get() else 0.0
        gb_bato_interno = (3.8 if self.bato_64_act.get() else 0) + (1.0 if self.bato_32_act.get() else 0) + (1.0 if self.bato_atom_act.get() else 0) if self.instalar_bato.get() else 0
        
        # Mínimo condicional de HollowDrive
        base_hollow = 10.0 if self.descargar_pack_hollow.get() else 3.0
        base_obligatoria = base_hollow
        if self.instalar_cachy.get():
            base_obligatoria += self.min_cachy  
            
        espacio_libre_para_packs = self.gb_totales - base_obligatoria - gb_bato_interno - espacio_grub
        
        # 2. PANEL INDEPENDIENTE: PACK BATOCERA
        if self.instalar_bato.get():
            self.ch_pack_bato.configure(state="normal")
            opciones_bato = ["16GB", "32GB", "64GB"]
            
            opciones_validas_bato = [opt for opt in opciones_bato if int(opt.replace("GB","")) <= espacio_libre_para_packs]
            if not opciones_validas_bato: opciones_validas_bato = ["16GB"]
            
            self.menu_pack_bato.configure(values=opciones_validas_bato)
            if self.pack_bato_size_var.get() not in opciones_validas_bato:
                self.pack_bato_size_var.set(opciones_validas_bato[0])
                self.menu_pack_bato.set(opciones_validas_bato[0])
                
            if self.descargar_pack_bato.get():
                self.menu_pack_bato.configure(state="normal")
                val_pack_bato = int(self.pack_bato_size_var.get().replace("GB", ""))
            else:
                self.menu_pack_bato.configure(state="disabled")
                val_pack_bato = 0
        else:
            self.ch_pack_bato.configure(state="disabled")
            self.descargar_pack_bato.set(False)
            self.menu_pack_bato.configure(values=["OFF"], state="disabled")
            self.menu_pack_bato.set("OFF")
            val_pack_bato = 0

        # 3. PANEL INDEPENDIENTE: PACK HOLLOWDRIVE
        self.ch_pack_hollow.configure(state="normal")
        opciones_hollow = ["6GB", "10GB", "20GB"]
        espacio_para_hollow = self.gb_totales - base_obligatoria - gb_bato_interno - val_pack_bato - espacio_grub
        
        opciones_validas_hollow = [opt for opt in opciones_hollow if int(opt.replace("GB","")) <= espacio_para_hollow]
        if not opciones_validas_hollow: opciones_validas_hollow = ["6GB"]
        
        self.menu_pack_hollow.configure(values=opciones_validas_hollow)
        if self.pack_hollow_size_var.get() not in opciones_validas_hollow:
            self.pack_hollow_size_var.set(opciones_validas_hollow[0])
            self.menu_pack_hollow.set(opciones_validas_hollow[0])
            
        if self.descargar_pack_hollow.get():
            self.menu_pack_hollow.configure(state="normal")
            val_pack_hollow = int(self.pack_hollow_size_var.get().replace("GB", ""))
        else:
            self.menu_pack_hollow.configure(state="disabled")
            val_pack_hollow = 0

        # 4. Cálculo matemático definitivo para los Sliders
        min_h = base_hollow + gb_bato_interno + val_pack_bato + val_pack_hollow
        min_c = self.min_cachy if self.instalar_cachy.get() else 0
        disp = self.gb_totales - espacio_grub

        # Clampeo de seguridad
        if min_h > disp - min_c:
            min_h = max(base_hollow, disp - min_c)

        h = self.slider_h.get()
        c = self.slider_c.get() if self.instalar_cachy.get() else 0

        # BALANCEO AUTOMÁTICO
        if self.instalar_cachy.get():
            if source == "h":
                # Si el usuario mueve HOLLOW, ajustamos CACHY
                if h + c > disp:
                    c = max(min_c, disp - h)
                # Si al bajar h, c quedó muy grande, el slider c se ajusta solo
            elif source == "c":
                # Si el usuario mueve CACHY, ajustamos HOLLOW
                if h + c > disp:
                    h = max(min_h, disp - c)
            else:
                # Ajuste general si ninguna es source (ej: al iniciar)
                if h + c > disp:
                    h = max(min_h, disp - c)
                    c = max(min_c, disp - h)
        else:
            # Si solo existe Hollow
            h = min(h, disp)

        # Aplicamos valores calculados
        self.slider_h.set(h)
        self.slider_h.configure(from_=min_h, to=max(min_h + 1, disp - min_c))
        self.lbl_h_gb.configure(text=f"{int(h)} GB")
        
        if self.instalar_cachy.get():
            self.slider_c.set(c)
            self.slider_c.configure(from_=min_c, to=max(min_c + 1, disp - min_h))
            self.lbl_c_gb.configure(text=f"{int(c)} GB")

    def actualizar_estados_bato(self):
        if self.instalar_bato.get():
            self.f_bato_opts.pack(fill="x", pady=5)
        else:
            self.f_bato_opts.pack_forget()
        self.rebalancear()

    def actualizar_estados_cachy(self):
        if self.instalar_cachy.get():
            self.f_row_c.pack(fill="x", padx=20, pady=5, before=self.canvas)
        else:
            self.f_row_c.pack_forget()
        self.rebalancear()

    def reproducir_gif(self, label_widget, frames, delay=80, index=0):
        if not frames or not label_widget.winfo_exists():
            return
        img = frames[index % len(frames)]
        label_widget.configure(image=img)
        label_widget.image = img
        self.gif_after_id = self.after(delay, self.reproducir_gif, label_widget, frames, delay, index + 1)

    def cambiar_gif(self, frames):
        if hasattr(self, 'gif_after_id') and self.gif_after_id:
            try:
                self.after_cancel(self.gif_after_id)
            except:
                pass
            self.gif_after_id = None
        if frames:
            self.reproducir_gif(self.lbl_gif, frames, delay=80)
        else:
            self.lbl_gif.configure(image="")

    def actualizar_barra_visual(self, h, grub, cachy):
        w = self.canvas.winfo_width()
        if w <= 1: 
            self.after(100, lambda: self.actualizar_barra_visual(h, grub, cachy))
            return
            
        self.canvas.delete("all")
        total = self.gb_totales
        if total <= 0: return
        
        w_h = (h / total) * w
        w_g = (grub / total) * w
        w_c = (cachy / total) * w
        
        self.canvas.create_rectangle(0, 0, w_h, 40, fill=COLOR_HOLLOW, outline="")
        
        if self.instalar_cachy.get():
            self.canvas.create_rectangle(w_h, 0, w_h + w_g, 40, fill=COLOR_LIMINE, outline="")
            self.canvas.create_rectangle(w_h + w_g, 0, w_h + w_g + w_c, 40, fill=COLOR_CACHY, outline="")
            self.canvas.create_rectangle(w_h + w_g + w_c, 0, w, 40, fill=COLOR_LIBRE, outline="")
        else:
            self.canvas.create_rectangle(w_h, 0, w, 40, fill=COLOR_LIBRE, outline="")

    def proceso_real(self):
        self.en_proceso = True
        self.bloquear_ui(True)
        
        pasos_instalacion = [
            "Limpiando dispositivo...",
            "Creando particiones...",
            "descargando complementos...",
            "volcando imágen de GRUB...",
            "volcando imagen de Cachyos..."
        ]
        
        total_pasos = len(pasos_instalacion)
        for index, paso in enumerate(pasos_instalacion):
            if self.abortar_proceso:
                break
                
            if paso == "descargando complementos...":
                self.after(0, lambda: self.cambiar_gif(self.frames_breakdance))
            else:
                self.after(0, lambda: self.cambiar_gif(self.frames_linterna))
                
            self.after(0, lambda p=paso: self.lbl_status.configure(text=p, text_color=AZUL_SUAVE))
            self.after(0, lambda v=(index / total_pasos): self.p_total.set(v))
            
            for mini in range(1, 11):
                if self.abortar_proceso:
                    break
                time.sleep(0.18)
                self.after(0, lambda v=(mini / 10.0): self.p_task.set(v))
                
        self.bloquear_ui(False)
        self.en_proceso = False
        self.cambiar_gif(None)
        
        if self.abortar_proceso:
            self.after(0, lambda: messagebox.showinfo("PROCESO INTERRUMPIDO", "La instalación ha sido cancelada limpiamente."))
        else:
            self.after(0, lambda: self.p_total.set(1.0))
            self.after(0, lambda: self.p_task.set(1.0))
            self.after(0, lambda: messagebox.showinfo("HOLLOWDRIVE READY", "¡Instalación completada con éxito en tu unidad!"))
            
        self.after(0, lambda: self.alternar_modo_instalacion(False))

if __name__ == "__main__":
    app = SavinOceanicCommand()
    app.mainloop()