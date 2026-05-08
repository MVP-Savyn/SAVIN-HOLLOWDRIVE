from engine.download_manager import descargar_y_extraer_ventoy
from engine.disk_logic import obtener_unidades_usb
from tkinter import messagebox
from PIL import Image # Necesario para las fotos
import customtkinter as ctk
import tkinter as tk
import threading
import webbrowser
import threading
import time
import os
import sys

def resource_path(relative_path):
    """ Obtiene la ruta absoluta de los recursos, compatible con PyInstaller """
    try:
        # PyInstaller crea una carpeta temporal y guarda la ruta en _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# Y ahora actualizas tus constantes:
BASE_DIR = os.path.abspath(".")
CARPETA_MEDIA = resource_path("media")

# --- CONFIGURACIÓN ESTRUCTURAL ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CARPETA_MEDIA = os.path.join(BASE_DIR, "media")

# --- CONFIGURACIÓN ESTÉTICA ORIGINAL ---
AZUL_FONDO = "#05080a"  
AZUL_CARD = "#0d1117"   
AZUL_CIAN = "#00d4ff"       
AZUL_ELECTRICO = "#005eff"  
AZUL_SUAVE = "#70a1ff"
COLOR_HOLLOW, COLOR_BATO, COLOR_CACHY = "#1e3799", "#4a69bd", "#0fbcf9"
COLOR_LIMINE, COLOR_LIBRE = "#4b6584", "#444444"
VERDE_EXITO = "#2ecc71"

class SavinOceanicCommand(ctk.CTk):

    def verificar_herramientas(self):
        """Verifica si Ventoy ya existe en la carpeta tools."""
        tools_path = os.path.join("engine", "tools")
        # Buscamos cualquier carpeta que empiece por 'ventoy'
        if os.path.exists(tools_path):
            if any("ventoy" in f.lower() for f in os.listdir(tools_path)):
                return True
        return False
    
    def animar_pulso(self):
        # Si el botón ya no existe, paramos la animación
        if not hasattr(self, 'lbl_btn_descarga') or not self.lbl_btn_descarga.winfo_exists():
            return

        # Configuración para imagen gigante
        step = 2           # Salto de 2 en 2 para mantener paridad
        min_s = 500        
        max_s = 560        # Crece 60 píxeles en total

        if self.creciendo:
            self.tamaño_actual += step
            if self.tamaño_actual >= max_s: 
                self.creciendo = False
        else:
            self.tamaño_actual -= step
            if self.tamaño_actual <= min_s: 
                self.creciendo = True

        if self.img_descarga_data:
            # Forzamos entero para el renderizado
            nuevo_tam = int(self.tamaño_actual)
            self.img_descarga_data.configure(size=(nuevo_tam, nuevo_tam))
        
        # 120ms para un efecto de "respiración" muy profunda y lenta
        self.animacion_id = self.after(120, self.animar_pulso)

    def clic_en_descarga(self):
        """Gestión del click: Detiene el pulso y cambia el botón por la barra."""
        # 1. Detener la animación
        if self.animacion_id:
            try:
                self.after_cancel(self.animacion_id)
            except:
                pass
            self.animacion_id = None

        # 2. Borrar elementos visuales
        if hasattr(self, 'lbl_btn_descarga'):
            self.lbl_btn_descarga.destroy()
        if hasattr(self, 'lbl_info'):
            self.lbl_info.destroy()

        # 3. Mostrar la barra de progreso (Verificamos que exista)
        if hasattr(self, 'prog_descarga'):
            self.prog_descarga.place(relx=0.5, rely=0.5, anchor="center")
            # 4. Lanzar la descarga
            threading.Thread(target=self.ejecutar_descarga, daemon=True).start()
        else:
            print("Error: La barra de progreso no fue inicializada.")

    def ejecutar_descarga(self):
        """Ejecuta la descarga de Ventoy y cierra la capa al terminar."""
        def update_bar(val):
            # Usamos after para que la GUI se actualice desde el hilo principal
            self.after(0, lambda: self.prog_descarga.set(val))

        # Llamamos al manager que creamos en engine/download_manager.py
        exito = descargar_y_extraer_ventoy(progress_callback=update_bar)
        
        if exito:
            # Si todo sale bien, esperamos un segundo y quitamos la capa negra
            time.sleep(1) 
            self.after(0, self.overlay.destroy)
            print("Descarga completa: Capa de bloqueo eliminada.")
        else:
            # Si falla, avisamos en la barra (se pone roja si tienes el tema configurado)
            self.after(0, lambda: self.prog_descarga.configure(progress_color="red"))
            print("Error crítico en la descarga de complementos.")

    def mostrar_capa_descarga(self):
        if self.verificar_herramientas():
            return

        overlay_color = ("#D9D9D9", "#1A1A1A")
        self.overlay = ctk.CTkFrame(self, fg_color=overlay_color)
        self.overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

        # 1. Crear la barra (así evitamos el AttributeError)
        self.prog_descarga = ctk.CTkProgressBar(
            self.overlay, width=400, progress_color=VERDE_EXITO
        )
        self.prog_descarga.set(0)

        # 2. El botón con la imagen gigante
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

    def iniciar_descarga_hilo(self):
        self.btn_descarga.configure(state="disabled", text="Descargando...")
        self.prog_descarga.place(relx=0.5, rely=0.80, anchor="center")
        
        # Ejecutamos en hilo para no congelar la GUI
        threading.Thread(target=self.ejecutar_descarga, daemon=True).start()

    def ejecutar_descarga(self):
        def update_bar(val):
            self.prog_descarga.set(val)

        success = descargar_y_extraer_ventoy(progress_callback=update_bar)
        
        if success:
            self.overlay.destroy() # Quitamos el bloqueo
        else:
            self.btn_descarga.configure(state="normal", text="Error. Reintentar?")

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

    def mostrar_info(self, titulo, mensaje):
        messagebox.showinfo(titulo, mensaje)

    def __init__(self):
        super().__init__()
        self.title("SAVIN SUPER_USB // V12.5")
        self.geometry("1000x850")
        self.resizable(False, False)
        
        # 1. ESTADO DE ANIMACIÓN Y DESCARGA (Definir antes de cargar recursos)
        self.animacion_id = None
        self.creciendo = True
        self.tamaño_actual = 180
        self.img_descarga_data = None
        self.progreso_valor = ctk.DoubleVar(value=0.0)
        
        # 2. VARIABLES DE LA INTERFAZ
        self.en_proceso = False
        self.abortar_proceso = False
        self.widgets_interactivos = []
        self.mostrar_internos = ctk.BooleanVar(value=False)
        self.gb_totales = 0.0 
        self.min_cachy = 20.0 
        
        self.instalar_bato = ctk.BooleanVar(value=True)
        self.instalar_cachy = ctk.BooleanVar(value=True) 
        self.bato_64_act = ctk.BooleanVar(value=True)
        self.bato_32_act = ctk.BooleanVar(value=False)
        self.bato_atom_act = ctk.BooleanVar(value=False)
        self.preservar_espacio = ctk.BooleanVar(value=False)
        self.descargar_pack = ctk.BooleanVar(value=False)
        self.pack_size_var = ctk.StringVar(value="32GB")

        # 3. CARGA DE RECURSOS Y UI
        self.configure(fg_color=AZUL_FONDO) 
        self.attributes("-alpha", 0.94)
        self.cargar_recursos() # Ahora sí guardará la imagen correctamente
        self.setup_ui()
        self.refrescar_discos()
        self.rebalancear()

        # 4. VERIFICACIÓN DE HERRAMIENTAS
        self.after(100, self.mostrar_capa_descarga)

        # Al cerrar la ventana, llamamos a una función de limpieza
        self.protocol("WM_DELETE_WINDOW", self.cerrar_aplicacion)

    def cerrar_aplicacion(self):
        """Detiene animaciones y cierra de forma segura."""
        if self.animacion_id:
            self.after_cancel(self.animacion_id)
        self.destroy()

    def toggle_discos_internos(self):
        """Muestra un aviso antes de activar la visualización de discos internos."""
        if self.mostrar_internos.get():
            # askyesno devuelve True o False. icon='warning' pone el triángulo amarillo.
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
        # Icono de descarga con pulso
        img_path = os.path.join(CARPETA_MEDIA, "descarga-morada.png")
        print(f"Buscando icono en: {img_path}") # Esto te ayudará a ver si la ruta es real
        
        if os.path.exists(img_path):
            try:
                pil_image = Image.open(img_path)
                self.img_descarga_data = ctk.CTkImage(
                  light_image=pil_image, 
                  dark_image=pil_image, 
                  size=(350, 350) # Tamaño inicial
             )
                print("Icono de descarga cargado con éxito.")
            except Exception as e:
                print(f"Error abriendo imagen de descarga: {e}")
        else:
            print(f"ALERTA: No existe el archivo {img_path}")

    def setup_ui(self):
        # --- CABECERA ---
        self.header = ctk.CTkFrame(self, fg_color="transparent", height=120)
        self.header.pack(fill="x", padx=20, pady=0)
        if self.logo_savin:
            ctk.CTkLabel(self.header, image=self.logo_savin, text="").place(x=0, y=-10)
        if self.logo_maker:
            ctk.CTkLabel(self.header, image=self.logo_maker, text="").place(relx=0.5, y=-85, anchor="n")
            
        self.btn_info_main = ctk.CTkButton(self, text="i", width=30, height=30, corner_radius=15, 
                                          fg_color=AZUL_ELECTRICO, font=("Serif", 14, "bold"), 
                                          command=self.abrir_ventana_info)
        self.btn_info_main.place(x=950, y=20)

        # --- SELECTOR DE DISCOS (MODIFICADO) ---
        self.f_selection = ctk.CTkFrame(self, fg_color=AZUL_CARD, border_width=1, border_color=AZUL_ELECTRICO)
        self.f_selection.pack(fill="x", padx=20, pady=(0, 10)) 
        
        ctk.CTkLabel(self.f_selection, text="Selecciona un dispositivo para instalar HOLLOWDRIVE.", 
                     font=("Segoe UI", 15, "italic"), text_color=AZUL_SUAVE).pack(pady=(10,0))
        
        f_combo = ctk.CTkFrame(self.f_selection, fg_color="transparent")
        f_combo.pack(pady=15)

        # Iniciamos el combo vacío
        self.combo_disk = ctk.CTkComboBox(f_combo, values=["Buscando unidades..."], 
                                         width=450, command=self.activar_interfaz_completa)
        self.combo_disk.set("Buscando unidades...")
        self.combo_disk.pack(side="left", padx=10)
        self.widgets_interactivos.append(self.combo_disk)

        # Añadimos un botón para refrescar la lista
        self.btn_refresh = ctk.CTkButton(f_combo, text="🔄", width=40, fg_color="#222", 
                                        command=self.refrescar_discos)
        self.btn_refresh.pack(side="left", padx=5)

        self.sw_internos = ctk.CTkCheckBox(f_combo, text="Mostrar discos internos", 
                                          variable=self.mostrar_internos,
                                          command=self.toggle_discos_internos, # <--- Cambiado aquí
                                          text_color="#aa3333", font=("Segoe UI", 11, "bold"))
        self.sw_internos.pack(side="left", padx=10)

        # --- CONTENEDOR MAESTRO ---
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        
        # PANEL IZQUIERDO
        self.p_left = ctk.CTkFrame(self.main_container, fg_color=AZUL_CARD, corner_radius=15, border_width=1, border_color="#222")
        self.p_left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        # SECCIÓN BATOCERA
        f_bato_master = ctk.CTkFrame(self.p_left, fg_color="transparent")
        f_bato_master.pack(fill="x", padx=15, pady=15)
        f_bato_txt = ctk.CTkFrame(f_bato_master, fg_color="transparent"); f_bato_txt.pack(side="left", fill="both", expand=True)
        f_bato_h = ctk.CTkFrame(f_bato_txt, fg_color="transparent"); f_bato_h.pack(fill="x")
        sw_bato = ctk.CTkSwitch(f_bato_h, text="¿Instalar Batocera?", font=("Segoe UI", 12, "bold"), variable=self.instalar_bato, command=self.actualizar_estados_bato, progress_color=AZUL_CIAN)
        sw_bato.pack(side="left")
        self.widgets_interactivos.append(sw_bato)
        ctk.CTkButton(f_bato_h, text="i", width=20, height=20, corner_radius=10, fg_color="#333", command=self.abrir_info_batocera).pack(side="left", padx=5)

        self.f_bato_opts = ctk.CTkFrame(f_bato_txt, fg_color="#0d141c", corner_radius=8); self.f_bato_opts.pack(fill="x", pady=5)
        self.ch_b64 = ctk.CTkCheckBox(self.f_bato_opts, text="Batocera 64bits (3.8GB)", variable=self.bato_64_act, command=self.rebalancear); self.ch_b64.pack(pady=2, padx=10, anchor="w")
        self.ch_b32 = ctk.CTkCheckBox(self.f_bato_opts, text="Batocera 32bits (1GB)", variable=self.bato_32_act, command=self.rebalancear); self.ch_b32.pack(pady=2, padx=10, anchor="w")
        self.ch_bat = ctk.CTkCheckBox(self.f_bato_opts, text="Batocera ATOM (1GB)", variable=self.bato_atom_act, command=self.rebalancear); self.ch_bat.pack(pady=2, padx=10, anchor="w")
        self.widgets_interactivos.extend([self.ch_b64, self.ch_b32, self.ch_bat])

        if self.logo_batocera:
            lbl_img_bato = ctk.CTkLabel(f_bato_master, image=self.logo_batocera, text="", cursor="hand2")
            lbl_img_bato.pack(side="right", padx=10)
            lbl_img_bato.bind("<Button-1>", lambda e: self.abrir_url("https://batocera.org"))

        # PACK DE JUEGOS
        f_pack_h = ctk.CTkFrame(self.p_left, fg_color="transparent"); f_pack_h.pack(fill="x", padx=15, pady=5)
        self.ch_pack = ctk.CTkCheckBox(f_pack_h, text="PACK DE JUEGOS", variable=self.descargar_pack, command=self.toggle_pack_menu); self.ch_pack.pack(side="left")
        self.widgets_interactivos.append(self.ch_pack)
        self.menu_pack = ctk.CTkOptionMenu(self.p_left, values=["16GB", "32GB", "64GB", "128GB"], variable=self.pack_size_var, command=lambda _: self.rebalancear("h"), height=25)
        self.menu_pack.pack(fill="x", padx=35, pady=5)
        self.widgets_interactivos.append(self.menu_pack)

        # SECCIÓN CACHYOS
        f_cachy_master = ctk.CTkFrame(self.p_left, fg_color="transparent"); f_cachy_master.pack(fill="x", padx=15, pady=15)
        if self.logo_cachy:
            lbl_img_cachy = ctk.CTkLabel(f_cachy_master, image=self.logo_cachy, text="", cursor="hand2"); lbl_img_cachy.pack(pady=(0,10))
            lbl_img_cachy.bind("<Button-1>", lambda e: self.abrir_url("https://cachyos.org"))

        f_cachy_h = ctk.CTkFrame(f_cachy_master, fg_color="transparent"); f_cachy_h.pack(fill="x")
        sw_cachy = ctk.CTkSwitch(f_cachy_h, text="¿Instalar CachyOS?", font=("Segoe UI", 12, "bold"), variable=self.instalar_cachy, command=self.actualizar_estados_cachy, progress_color=AZUL_CIAN)
        sw_cachy.pack(side="left")
        self.widgets_interactivos.append(sw_cachy)
        ctk.CTkButton(f_cachy_h, text="i", width=20, height=20, corner_radius=10, fg_color="#333", command=self.abrir_info_cachy).pack(side="left", padx=5)

        # PANEL DERECHO
        self.p_right = ctk.CTkFrame(self.main_container, fg_color=AZUL_CARD, corner_radius=15, border_width=1, border_color="#222")
        self.p_right.pack(side="right", fill="both", expand=True)
        
        self.sw_preservar = ctk.CTkSwitch(self.p_right, text="BLOQUEAR LIBRE", variable=self.preservar_espacio, command=lambda: self.rebalancear("h"), progress_color=AZUL_ELECTRICO)
        self.sw_preservar.pack(pady=10)
        self.widgets_interactivos.append(self.sw_preservar)

        self.f_row_h = self.crear_ocean_slider(self.p_right, "HOLLOWDRIVE STORAGE", COLOR_HOLLOW, "h")
        self.f_row_c = self.crear_ocean_slider(self.p_right, "CACHYOS PARTITION", COLOR_CACHY, "c", min_val=20)

        self.canvas = tk.Canvas(
            self.p_right, 
            height=40,            # Altura exacta de los rectángulos
            bg=AZUL_CARD,         # Fondo igual al de la tarjeta para evitar contraste al borrar
            highlightthickness=0, # Elimina el borde/línea negra
            borderwidth=0         # Asegura que no haya relieve
        )
        self.canvas.pack(fill="x", pady=(15, 5), padx=20)
        self.lbl_libre_info = ctk.CTkLabel(self.p_right, text="LIBRE: 0.00 GB", font=("Consolas", 18, "bold"), text_color=AZUL_CIAN)
        self.lbl_libre_info.pack()

        # --- LEYENDA DINÁMICA ---
        self.f_leyenda = ctk.CTkFrame(self.p_right, fg_color="transparent")
        self.f_leyenda.pack(pady=10, fill="x", padx=15)
        self.dic_leyenda = {}
        
        info_textos = {
            "Hollow": ("Partición HOLLOWDRIVE", "Aquí podrás almacenar todos los datos que quieras. Todas las imágenes que pongas aquí serán booteables (usamos Ventoy). Incluye un kit de herramientas diseñado por mí :)"),
            "Bato": ("Partición BATOCERA", "Partición donde se guardarán las imágenes de Batocera. Se podrán utilizar todas las ROMs guardadas en HOLLOWDRIVE."),
            "Limine": ("Partición LIMINE", "Partición de arranque de CachyOS. Es obligatoria para que el sistema funcione."),
            "Cachy": ("Sistema CACHYOS", "Sistema Linux portable optimizado para rendimiento.")
        }

        for nombre, color in [("Hollow", COLOR_HOLLOW), ("Bato", COLOR_BATO), ("Limine", COLOR_LIMINE), ("Cachy", COLOR_CACHY)]:
            tit, msg = info_textos[nombre]
            btn = ctk.CTkButton(
                self.f_leyenda, text=f"{nombre} (0GB)", fg_color=color,
                width=120, height=28, corner_radius=15, text_color="white",
                font=("Segoe UI Bold", 11),
                command=lambda t=tit, m=msg: self.mostrar_info(t, m)
            )
            btn.pack(side="left", padx=10)
            self.dic_leyenda[nombre.lower()] = btn

        # FOOTER
        self.footer = ctk.CTkFrame(self, fg_color="transparent")
        self.lbl_status = ctk.CTkLabel(self.footer, text="ESPERANDO INICIO...", font=("Consolas", 11), text_color=AZUL_SUAVE); self.lbl_status.pack(anchor="w")
        self.p_task = ctk.CTkProgressBar(self.footer, height=4, progress_color=AZUL_CIAN); self.p_task.set(0); self.p_task.pack(fill="x", pady=2)
        self.p_total = ctk.CTkProgressBar(self.footer, height=10, progress_color=AZUL_ELECTRICO); self.p_total.set(0); self.p_total.pack(fill="x", pady=5)
        self.f_btns = ctk.CTkFrame(self.footer, fg_color="transparent"); self.f_btns.pack(fill="x", pady=5)
        self.btn_start = ctk.CTkButton(self.f_btns, text="🩵Instalar HollowDrive🩵", font=("Impact", 24), fg_color=AZUL_ELECTRICO, height=50, command=self.confirmar_inicio)
        self.btn_start.pack(side="left", fill="x", expand=True)
        self.btn_cancel = ctk.CTkButton(self.f_btns, text="CANCELAR", fg_color="#aa3333", width=120, height=50, command=self.cancelar_proceso)
        self.btn_cancel.pack(side="left", padx=(10, 0))

    def bloquear_ui(self, bloquear=True):
        st = "disabled" if bloquear else "normal"
        for w in self.widgets_interactivos: w.configure(state=st)
        self.btn_start.configure(state=st)

    def cancelar_proceso(self):
        if messagebox.askyesno("CANCELAR", "¿Seguro?"):
            self.abortar_proceso = True
            self.lbl_status.configure(text="CANCELANDO...", text_color="#ff4d4d")

        # --- MÉTODOS ORIGINALES DE VENTANAS ---
    def crear_ventana_info_base(self, titulo, ancho, alto):
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
        v = self.crear_ventana_info_base("¿QUÉ ES BATOCERA?", 620, 320)
        frame_interno = ctk.CTkFrame(v, fg_color="transparent")
        frame_interno.pack(expand=True, fill="both", padx=25, pady=20)
        ctk.CTkLabel(frame_interno, text="🎮 SOBRE BATOCERA", font=("Impact", 28), text_color=AZUL_CIAN).pack(pady=(0, 15))
        info = ("Batocera es un sistema de emulación que puede convertir\ncualquier ordenador en una consola de videojuegos.\n\n🛡️ SEGURIDAD DE DATOS:\nAunque inicies Batocera, NUNCA perderás los datos del ordenador.\nTodo funciona de forma aislada dentro de tu USB.")
        ctk.CTkLabel(frame_interno, text=info, font=("Segoe UI", 14), justify="center", wraplength=550).pack(pady=5)
        ctk.CTkButton(frame_interno, text="ENTENDIDO", font=("Segoe UI", 14, "bold"), fg_color=AZUL_ELECTRICO, height=40, width=180, command=v.destroy).pack(pady=(15, 0))
        v.update(); v.grab_set()

    def abrir_info_cachy(self):
        v = self.crear_ventana_info_base("¿QUÉ ES CACHYOS?", 680, 440)
        frame_interno = ctk.CTkFrame(v, fg_color="transparent")
        frame_interno.pack(expand=True, fill="both", padx=25, pady=20)
        ctk.CTkLabel(frame_interno, text="🚀 CACHYOS: ARCH LINUX OPTIMIZADO", font=("Impact", 28), text_color=COLOR_CACHY).pack(pady=(0, 15))
        info = ("He preparado una versión personalizada de CachyOS (Arch Linux)\ndiseñada específicamente para ser rápida y fácil de usar.\n\n⚡ CARACTERÍSTICAS PRINCIPALES:\n• Universal: Funciona en casi cualquier PC moderno.\n• Rendimiento: Optimizado para sacar el máximo provecho al hardware.\n• Portable: Llevas tu sistema operativo, archivos y apps siempre contigo.\n\nEs una estación de trabajo completa que arranca directamente\ndesde tu USB sin tocar el disco duro de tu ordenador.")
        ctk.CTkLabel(frame_interno, text=info, font=("Segoe UI", 14), justify="center", wraplength=600).pack(pady=5)
        ctk.CTkButton(frame_interno, text="¡EXCELENTE!", font=("Segoe UI", 14, "bold"), fg_color=AZUL_ELECTRICO, height=40, width=180, command=v.destroy).pack(pady=(15, 0))
        v.update(); v.grab_set()

    def abrir_info_roms(self):
        v = self.crear_ventana_info_base("AVISO LEGAL", 620, 380)
        v.configure(fg_color="#1a0a0a") 
        frame_interno = ctk.CTkFrame(v, fg_color="transparent")
        frame_interno.pack(expand=True, fill="both", padx=25, pady=20)
        ctk.CTkLabel(frame_interno, text="⚠️ AVISO LEGAL", font=("Impact", 32), text_color="#ff4d4d").pack(pady=(0, 15))
        legal_text = ("Savin Super USB NO INCLUYE ROMS ni archivos de juegos\nprotegidos por derechos de autor.\n\nEl usuario es el único responsable de obtener sus propias\ncopias de seguridad legales.\n\nSavin Core Engine es una herramienta de automatización y no\naloja ni distribuye contenido con copyright.")
        ctk.CTkLabel(frame_interno, text=legal_text, font=("Segoe UI", 14), justify="center", wraplength=550).pack(pady=10)
        ctk.CTkButton(frame_interno, text="ACEPTO LOS RIESGOS", font=("Segoe UI", 14, "bold"), fg_color="#444", height=40, width=220, command=v.destroy).pack(pady=(15, 0))
        v.update(); v.grab_set()

    def abrir_ventana_info(self):
        v = self.crear_ventana_info_base("SAVIN CORE INFO", 750, 720)
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
        # Evitamos que se active con el texto por defecto
        if "---" in seleccion or "Buscando" in seleccion or "NO SE DETECTAN" in seleccion: 
            return
        
        # Buscamos los datos del disco en la lista que guardamos al refrescar
        disco_elegido = next((d for d in self.lista_discos_reales if d["display"] == seleccion), None)
        
        if disco_elegido:
            # Ahora self.gb_totales será el tamaño FÍSICO del disco (ej: 931GB para un tera)
            self.gb_totales = disco_elegido["size"]
            
            # Mostramos la interfaz
            self.main_container.pack(fill="both", expand=True, padx=20, pady=10)
            self.footer.pack(fill="x", side="bottom", padx=20, pady=10)
            
            # Forzamos un rebalanceo para que los sliders se ajusten al nuevo máximo
            self.slider_h.set(10) # Reseteamos a un mínimo seguro para evitar errores de rango
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
        
        # 1. TAMAÑOS FIJOS (Bato + Limine)
        val_pack = int(self.pack_size_var.get().replace("GB", "")) if (self.instalar_bato.get() and self.descargar_pack.get()) else 0
        min_h = 10.0 + val_pack
        min_c = self.min_cachy if self.instalar_cachy.get() else 0
        
        gb_bato = (3.8 if self.bato_64_act.get() else 0) + (1.0 if self.bato_32_act.get() else 0) + (1.0 if self.bato_atom_act.get() else 0) if self.instalar_bato.get() else 0
        gb_limine = 4.09 if (self.instalar_cachy.get() or self.instalar_bato.get()) else 0
        
        # Espacio que queda para repartir entre Hollow y Cachy
        disp = self.gb_totales - gb_bato - gb_limine

        # 2. CAPTURAR VALORES ACTUALES
        h = self.slider_h.get()
        c = self.slider_c.get() if self.instalar_cachy.get() else 0

        # 3. LÓGICA DE REPARTO SEGÚN LA FUENTE (Source)
        if not self.instalar_cachy.get():
            # Si no hay Cachy, Hollow manda.
            if not self.preservar_espacio.get():
                h = disp
            else:
                h = max(min_h, min(h, disp))
            c = 0
        else:
            # Si Cachy está activo, tenemos que ser estrictos
            if not self.preservar_espacio.get():
                # CASO: ABSORCIÓN TOTAL (H + C = DISP)
                if source == "h":
                    # El usuario mueve Hollow: limitamos H y el resto va a C
                    h = max(min_h, min(h, disp - min_c))
                    c = disp - h
                else:
                    # El usuario mueve Cachy: limitamos C y el resto va a H
                    c = max(min_c, min(c, disp - min_h))
                    h = disp - c
            else:
                # CASO: LIBRE (H + C <= DISP)
                # Primero limitamos Hollow al mínimo
                h = max(min_h, h)
                # Si la suma se pasa del total, encogemos el que NO se está moviendo
                if h + c > disp:
                    if source == "h":
                        h = min(h, disp - c) # No puede quitarle a C si C es fijo
                        if h < min_h: h = min_h; c = disp - h
                    else:
                        c = min(c, disp - h)

        # 4. ACTUALIZAR SLIDERS (Para que el puntito no se escape)
        self.slider_h.configure(to=disp - min_c)
        self.slider_h.set(h)
        self.lbl_h_gb.configure(text=f"{int(h)} GB")
        
        if self.instalar_cachy.get():
            self.slider_c.configure(to=disp - min_h)
            self.slider_c.set(c)
            self.lbl_c_gb.configure(text=f"{int(c)} GB")

        # 5. RESULTADO FINAL
        libre = max(0, disp - h - c)
        self.lbl_libre_info.configure(text=f"LIBRE: {round(libre, 2)} GB")
        self.actualizar_barra_visual(h, gb_bato, gb_limine, c)

        # Actualizar Leyenda
        if hasattr(self, 'dic_leyenda'):
            self.dic_leyenda["hollow"].configure(text=f"Hollow ({int(h)}GB)")
            self.dic_leyenda["bato"].configure(text=f"Bato ({round(gb_bato,1)}GB)")
            self.dic_leyenda["limine"].configure(text=f"Limine ({round(gb_limine,1)}GB)")
            st = "normal" if self.instalar_cachy.get() else "disabled"
            txt_c = f"Cachy ({int(c)}GB)" if self.instalar_cachy.get() else "Cachy (OFF)"
            self.dic_leyenda["cachy"].configure(text=txt_c, state=st)
            
    def actualizar_barra_visual(self, h, bato, limine, cachy):
        # 1. Obtener ancho actual
        w = self.canvas.winfo_width()
        if w <= 1: 
            self.update_idletasks()
            w = self.canvas.winfo_width()
            if w <= 1: w = 450 # Valor por defecto si aún no se renderiza

        # 2. Borrar y dibujar inmediatamente
        self.canvas.delete("all")
        
        def px(gb): return (gb / self.gb_totales) * w
        x = 0
        
        segmentos = [
            (COLOR_HOLLOW, h), 
            (COLOR_BATO, bato), 
            (COLOR_LIMINE, limine), 
            (COLOR_CACHY, cachy)
        ]
        
        for color, val in segmentos:
            if val > 0:
                width = px(val)
                # Dibujamos el rectángulo con altura 40 para que llene el canvas
                self.canvas.create_rectangle(x, 0, x + width, 40, fill=color, outline="")
                x += width
        
        # Rellenar el espacio libre si existe
        if x < w: 
            self.canvas.create_rectangle(x, 0, w, 40, fill=COLOR_LIBRE, outline="")

    def actualizar_estados_bato(self):
        # Estado general según el switch de Batocera
        st = "normal" if self.instalar_bato.get() else "disabled"
        
        # Bloqueamos/Desbloqueamos los checks de versiones
        for w in [self.ch_b64, self.ch_b32, self.ch_bat, self.ch_pack]:
            w.configure(state=st)
            
        # El menú del pack tiene una doble condición: 
        # Debe estar Batocera activo Y el check del pack marcado
        if self.instalar_bato.get() and self.descargar_pack.get():
            self.menu_pack.configure(state="normal", button_color=AZUL_ELECTRICO)
        else:
            self.menu_pack.configure(state="disabled", button_color="#444")
            
        self.rebalancear()

    def actualizar_estados_cachy(self):
        if self.instalar_cachy.get(): self.f_row_c.pack(fill="x", padx=20, pady=5)
        else: self.f_row_c.pack_forget()
        self.rebalancear()

    def toggle_pack_menu(self):
        # Si se activa, mostramos el aviso legal
        if self.descargar_pack.get():
            self.abrir_info_roms()
            self.menu_pack.configure(state="normal", button_color=AZUL_ELECTRICO, button_hover_color=AZUL_CIAN)
        else:
            # Si se desactiva, lo ponemos en gris y bloqueamos
            self.menu_pack.configure(state="disabled", button_color="#444", button_hover_color="#444")
        
        self.rebalancear("h")

    def confirmar_inicio(self):
        if messagebox.askyesno("CONFIRMACIÓN", "¿Proceder?"): 
            self.abortar_proceso = False; threading.Thread(target=self.proceso_real, daemon=True).start()

    def proceso_real(self):
        self.en_proceso = True; self.bloquear_ui(True)
        for i in range(1, 6):
            if self.abortar_proceso: break
            self.lbl_status.configure(text=f"PASO {i}/5..."); self.p_total.set(i/5)
            for j in range(1, 11): 
                if self.abortar_proceso: break
                self.p_task.set(j/10); time.sleep(0.05)
        self.lbl_status.configure(text="¡COMPLETADO!" if not self.abortar_proceso else "CANCELADO")
        self.bloquear_ui(False); self.en_proceso = False

if __name__ == "__main__": 
    app = SavinOceanicCommand(); app.mainloop()