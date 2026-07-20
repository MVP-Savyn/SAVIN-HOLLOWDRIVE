import os
import sys
import time
import threading
import queue
import shutil  
import webbrowser
import subprocess
import re
import tarfile
import requests
import json
import logging
from datetime import datetime
from tkinter import messagebox
import tkinter as tk
from PIL import Image, ImageSequence, ImageTk
import customtkinter as ctk

# Importaciones de tu motor local
from engine.download_manager import descargar_y_extraer_ventoy, resolver_tamano_pack

try:
    from engine.download_manager import formatted_size as formatear_tamano
except ImportError:
    from engine.download_manager import formatear_tamano
from engine.disk_logic import obtener_unidades_usb, instalar_ventoy, crear_particion_adicional

import ctypes
from ctypes import wintypes

GITHUB_REPO = "MVP-Savyn/SAVIN-HOLLOWDRIVE"

def obtener_version_interna():
    """ Lee dinámicamente la versión del ejecutable desde sus propiedades de Windows """
    exe_actual = os.path.abspath(sys.argv[0])
    if not exe_actual.endswith(".exe"):
        return "12.5"  # Fallback automático para cuando ejecutas el script .py en desarrollo
    try:
        version_dll = ctypes.WinDLL('version', use_last_error=True)
        dw_handle = wintypes.DWORD()
        size = version_dll.GetFileVersionInfoSizeW(exe_actual, ctypes.byref(dw_handle))
        if size == 0: return "12.5"
        
        buffer = ctypes.create_string_buffer(size)
        if not version_dll.GetFileVersionInfoW(exe_actual, 0, size, buffer): return "12.5"
        
        lp_sub_block = "\\\\FixedFileInfo"
        lp_buffer = ctypes.c_void_p()
        pu_len = wintypes.UINT()
        
        if version_dll.VerQueryValueW(buffer, lp_sub_block, ctypes.byref(lp_buffer), ctypes.byref(pu_len)):
            class VS_FIXEDFILEINFO(ctypes.Structure):
                _fields_ = [
                    ("dwSignature", wintypes.DWORD), ("dwStrucVersion", wintypes.DWORD),
                    ("dwFileVersionMS", wintypes.DWORD), ("dwFileVersionLS", wintypes.DWORD)
                ]
            info = VS_FIXEDFILEINFO.from_address(lp_buffer.value)
            major = info.dwFileVersionMS >> 16
            minor = info.dwFileVersionMS & 0xFFFF
            return f"{major}.{minor}"
    except Exception:
        pass
    return "12.5"

VERSION_ACTUAL = obtener_version_interna()
# --- CONFIGURACIÓN DE LOGS ---
os.makedirs("logs", exist_ok=True)

def rotar_logs(carpeta="logs", max_archivos=5):
    """Mantiene únicamente los 5 registros de depuración más recientes en el disco."""
    try:
        # Listamos todos los archivos .log de la carpeta
        archivos = [os.path.join(carpeta, f) for f in os.listdir(carpeta) if f.endswith('.log')]
        # Los ordenamos por fecha de modificación (del más viejo al más nuevo)
        archivos.sort(key=os.path.getmtime)
        
        # Si hay 5 o más, eliminamos los necesarios para dejar sitio al nuevo log
        while len(archivos) >= max_archivos:
            os.remove(archivos.pop(0))
    except Exception:
        pass

# Ejecutamos la limpieza antes de instanciar el nuevo archivo de log
rotar_logs()

archivo_log = os.path.join("logs", f"savin_hollowdrive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(archivo_log, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logging.info("=== INICIANDO SAVIN SUPER_USB ===")


def resource_path(relative_path):
    # Compatibilidad con PyInstaller y Nuitka Onefile
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    # Desarrollo local o carpetas relativas del binario compilado
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)

# --- CONFIGURACIÓN ESTRUCTURAL ---
if hasattr(sys, 'frozen') or '__compiled__' in globals():
    # Si es un ejecutable (PyInstaller o Nuitka), apuntamos a la carpeta real donde reside el .exe
    BASE_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
else:
    # Si estamos en VS Code desarrollando el .py, usamos la ruta nativa del script
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CARPETA_MEDIA = resource_path("media")

# --- CARGA DE MIRRORS ---
def cargar_mirrors():
    try:
        # Forzamos a resolver la ruta dentro del paquete interno de Nuitka
        ruta_json = resource_path(os.path.join("engine", "mirrors.json"))
        with open(ruta_json, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error cargando mirrors.json o no se encontró el archivo: {e}")
        return {}

MIRRORS_DATA = cargar_mirrors()
GB_GRUB = 0.512  # Ajustado para compensar el margen de alineación y asegurar los 512MB reales

try:
    URL_BATOCERA = MIRRORS_DATA["batocera_base"]["mirrors"][0]["url"]
except KeyError:
    URL_BATOCERA = "https://pub-988eebcee5e94631a55af8a89d12129d.r2.dev/batocerumen.img" 

# --- CONFIGURACIÓN ESTÉTICA ---
AZUL_FONDO = "#05080a"  
AZUL_CARD = "#0d1117"   
AZUL_CIAN = "#00d4ff"       
AZUL_ELECTRICO = "#005eff"  
AZUL_SUAVE = "#70a1ff"
COLOR_HOLLOW, COLOR_CACHY = "#1e3799", "#2ecc71"  
COLOR_LIMINE, COLOR_LIBRE = "#4b6584", "#444444"
VERDE_EXITO = "#2ecc71"


# =====================================================================
# ⚡ MOTOR DE EXTRACCIÓN DUAL (CON FILTRADO ANTI-SATURACIÓN DE CPU)
# =====================================================================

class AsyncBufferStream(object):
    def __init__(self, response, progress_callback=None, total_size=None, abort_check=None):
        self.q = queue.Queue(maxsize=400) 
        self.total_size = total_size
        self.progress_callback = progress_callback
        self.abort_check = abort_check
        self.bytes_read = 0
        self.last_reported_bytes = 0 
        self.leftover = b""
        self.error = None
        
        self.t_downloader = threading.Thread(target=self._downloader, args=(response,), daemon=True)
        self.t_downloader.start()

    def _downloader(self, response):
        try:
            for chunk in response.iter_content(chunk_size=5 * 1024 * 1024): 
                if self.abort_check and self.abort_check(): break
                if chunk: self.q.put(chunk) 
        except Exception as e: self.error = e
        finally: self.q.put(None) 

    def read(self, size=-1):
        if self.abort_check and self.abort_check(): raise InterruptedError("Extracción cancelada.")

        if size == -1:
            data = self.leftover
            self.leftover = b""
            while True:
                chunk = self.q.get()
                if chunk is None:
                    if self.error: raise self.error
                    break
                data += chunk
                self.bytes_read += len(chunk)
            if self.progress_callback and (self.bytes_read - self.last_reported_bytes > 5 * 1024 * 1024):
                self.last_reported_bytes = self.bytes_read
                self.progress_callback(self.bytes_read, self.total_size, "Extrayendo al vuelo")
            return data

        while len(self.leftover) < size:
            if self.abort_check and self.abort_check(): raise InterruptedError("Extracción cancelada.")
            chunk = self.q.get()
            if chunk is None:
                if self.error: raise self.error
                break
            self.leftover += chunk

        data = self.leftover[:size]
        self.leftover = self.leftover[size:]
        self.bytes_read += len(data)
        
        if self.progress_callback and (self.bytes_read - self.last_reported_bytes > 5 * 1024 * 1024):
            self.last_reported_bytes = self.bytes_read
            self.progress_callback(self.bytes_read, self.total_size, "Extrayendo al vuelo")
            
        return data


def obtener_stream_gdrive(file_id):
    """ Gestiona Google Drive extrayendo el token de confirmación mediante un motor multi-estrategia """
    session = requests.Session()
    url = "https://docs.google.com/uc?export=download"
    
    res = session.get(url, params={'id': file_id}, stream=True)
    
    token = None
    for cookie in session.cookies:
        if cookie.name.startswith('download_warning'):
            token = cookie.value
            break
    
    if not token and 'text/html' in res.headers.get('Content-Type', ''):
        texto_html = res.text
        match_raw = re.search(r'confirm=([^"&\'\s>]+)', texto_html)
        if match_raw:
            token = match_raw.group(1)
        else:
            match_input = re.search(r'name="confirm"\s+value="([^"]+)"', texto_html) or \
                          re.search(r'value="([^"]+)"\s+name="confirm"', texto_html)
            if match_input:
                token = match_input.group(1)
            else:
                match_id = re.search(r'href="([^"]+)"[^>]*id="uc-download-link"', texto_html) or \
                           re.search(r'id="uc-download-link"[^>]*href="([^"]+)"', texto_html)
                if match_id:
                    url_href = match_id.group(1)
                    match_confirm = re.search(r'confirm=([^&"\'\s>]+)', url_href)
                    if match_confirm:
                        token = match_confirm.group(1)

    if token and len(token) > 2:  # Evita falsos positivos con caracteres sueltos
        logging.info(f"[GDRIVE] Pantalla de virus saltada con éxito. Token de confirmación: {token}")
        res = session.get(url, params={'id': file_id, 'confirm': token}, stream=True)

    # Validación definitiva contra páginas de error HTML post-token
    if 'text/html' in res.headers.get('Content-Type', ''):
        body_snip = res.text[:1000] if hasattr(res, 'text') else ""
        logging.error(f"[DIAGNÓSTICO] Google Drive denegó el flujo. HTML Recibido:\n{body_snip}")
        if "quotaExceeded" in body_snip or "cuota" in body_snip.lower() or "exceeded" in body_snip.lower():
            raise RuntimeError("Google Drive: Límite de cuota de descarga excedido para este archivo público. Inténtalo más tarde.")
        raise RuntimeError("Google Drive bloqueó el acceso directo o el archivo ya no está disponible.")
        
    return res


def stream_extract_tar(url_or_id, target_dir, is_gdrive=False, progress_callback=None, abort_check=None, method="ram"):
    if is_gdrive:
        match = re.search(r'/d/([a-zA-Z0-9_-]+)', url_or_id)
        file_id = match.group(1) if match else url_or_id
        response = obtener_stream_gdrive(file_id)
    else:
        response = requests.get(url_or_id, stream=True)
        
    if response.status_code != 200:
        raise RuntimeError(f"Fallo de conexión: HTTP {response.status_code}")
        
    total_size = None
    if 'Content-Length' in response.headers:
        total_size = int(response.headers['Content-Length'])
        
    os.makedirs(target_dir, exist_ok=True)
    
    if method == "disco":
        temp_dir = os.path.join(BASE_DIR, "engine", "temp_downloads")
        os.makedirs(temp_dir, exist_ok=True)
        temp_tar = os.path.join(temp_dir, "temp_pack.tar")
        
        bytes_read = 0
        with open(temp_tar, "wb") as f:
            for chunk in response.iter_content(chunk_size=4 * 1024 * 1024):
                if abort_check and abort_check(): raise InterruptedError()
                if chunk:
                    f.write(chunk)
                    bytes_read += len(chunk)
                    if progress_callback: progress_callback(bytes_read, total_size, "Descargando a SSD")
                    
        extracted_bytes = 0
        last_reported_bytes = 0
        t_start_extract = time.time() 
        
        with open(temp_tar, "rb") as f:
            with tarfile.open(fileobj=f, mode="r|*") as tar:
                for member in tar:
                    if abort_check and abort_check(): raise InterruptedError()
                    
                    if member.isreg(): 
                        f_in = tar.extractfile(member)
                        dest_file = os.path.normpath(os.path.join(target_dir, member.name))
                        os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                        
                        with open(dest_file, "wb") as f_out:
                            while True:
                                buf = f_in.read(2 * 1024 * 1024)
                                if not buf: break
                                if abort_check and abort_check(): raise InterruptedError()
                                f_out.write(buf)
                                extracted_bytes += len(buf)
                                
                                if progress_callback and (extracted_bytes - last_reported_bytes > 5 * 1024 * 1024):
                                    last_reported_bytes = extracted_bytes
                                    progress_callback(extracted_bytes, total_size or extracted_bytes, "Extrayendo a USB", t_start_extract)
                    else:
                        tar.extract(member, path=target_dir)
                        
        if progress_callback: progress_callback(extracted_bytes, total_size or extracted_bytes, "Extrayendo a USB", t_start_extract)
        
        try: os.remove(temp_tar)
        except Exception as e: logging.warning(f"No se pudo borrar el temporal de extracción: {e}")

    else:
        stream = AsyncBufferStream(response, progress_callback=progress_callback, total_size=total_size, abort_check=abort_check)
        with tarfile.open(fileobj=stream, mode="r|*") as tar:
            for member in tar:
                if abort_check and abort_check(): raise InterruptedError()
                tar.extract(member, path=target_dir)
        if progress_callback: progress_callback(stream.bytes_read, total_size, "Extrayendo al vuelo")


def stream_download_file_direct(url_or_id, dest_path, is_gdrive=False, progress_callback=None, abort_check=None):
    if is_gdrive:
        match = re.search(r'/d/([a-zA-Z0-9_-]+)', url_or_id)
        file_id = match.group(1) if match else url_or_id
        response = obtener_stream_gdrive(file_id)
    else:
        response = requests.get(url_or_id, stream=True)

    if response.status_code != 200:
        raise RuntimeError(f"Fallo de conexión al descargar archivo: HTTP {response.status_code}")

    total_size = None
    if 'Content-Length' in response.headers:
        total_size = int(response.headers['Content-Length'])

    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    bytes_read = 0
    with open(dest_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=4 * 1024 * 1024):
            if abort_check and abort_check(): raise InterruptedError()
            if chunk:
                f.write(chunk)
                bytes_read += len(chunk)
                if progress_callback: progress_callback(bytes_read, total_size, "Descarga Directa")

def stream_flash_image_direct(url, letra_unidad, progress_callback=None, abort_check=None):
    """ Descarga una imagen cruda (.img) en streaming y la vuelca usando la API nativa de Windows (Win32) """
    import requests
    import ctypes
    from ctypes import wintypes
    import time
    
    letra_limpia = letra_unidad.strip().replace("\\", "").replace("/", "")
    ruta_raw = f"\\\\.\\{letra_limpia}"
    
    # --- Configuración de la API de Windows nativa (Win32) ---
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    
    GENERIC_READ = 0x80000000
    GENERIC_WRITE = 0x40000000
    FILE_SHARE_READ = 0x00000001
    FILE_SHARE_WRITE = 0x00000002
    OPEN_EXISTING = 3
    FSCTL_LOCK_VOLUME = 0x00090018
    FSCTL_DISMOUNT_VOLUME = 0x00090020
    INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
    
    # 1. Pequeño respiro para que el sistema asiente desmontajes previos
    time.sleep(1)
    
    # 2. Abrir el manejador físico del disco con permisos de compartición explícitos
    handle = kernel32.CreateFileW(
        ruta_raw,
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        0,
        None
    )
    
    if handle == INVALID_HANDLE_VALUE or handle == 0:
        error_code = kernel32.GetLastError()
        raise PermissionError(f"Windows bloqueó el acceso físico a {ruta_raw}.\nCódigo de error Win32: {error_code}.\nCierra cualquier ventana del Explorador de archivos.")
        
    try:
        bytes_returned = wintypes.DWORD(0)
        
        # 3. FORZAR EL LOCK EXCLUSIVO (Aquí es donde ganamos al sistema)
        if not kernel32.DeviceIoControl(handle, FSCTL_LOCK_VOLUME, None, 0, None, 0, ctypes.byref(bytes_returned), None):
            error_code = kernel32.GetLastError()
            raise PermissionError(f"No se pudo obtener el bloqueo exclusivo del volumen. Código Win32: {error_code}.")
            
        # 4. Forzar el desmontaje del sistema de archivos desde el propio manejador
        kernel32.DeviceIoControl(handle, FSCTL_DISMOUNT_VOLUME, None, 0, None, 0, ctypes.byref(bytes_returned), None)
        
        # 5. Iniciar la descarga por streaming desde Hugging Face
        response = requests.get(url, stream=True)
        if response.status_code != 200:
            raise RuntimeError(f"Fallo de conexión al repositorio: HTTP {response.status_code}")
            
        total_size = int(response.headers.get('Content-Length', 0)) or None
        bytes_escritos = 0
        
        # 6. Escritura masiva sector por sector usando WriteFile nativo
        for chunk in response.iter_content(chunk_size=4 * 1024 * 1024):
            if abort_check and abort_check():
                raise InterruptedError("Proceso de flasheo abortado por el usuario.")
            if chunk:
                chunk_len = len(chunk)
                buffer = ctypes.create_string_buffer(chunk, chunk_len)
                written = wintypes.DWORD(0)
                
                # Escritura directa en los sectores puros del USB
                if not kernel32.WriteFile(handle, buffer, chunk_len, ctypes.byref(written), None):
                    error_code = kernel32.GetLastError()
                    raise IOError(f"Error crítico de escritura en hardware. Código Win32: {error_code}")
                    
                bytes_escritos += written.value
                if progress_callback:
                    progress_callback(bytes_escritos, total_size, "Volcando sectores nativos")
                    
    finally:
        # 7. Pase lo que pase, cerramos el manejador para devolverle la unidad al sistema operativo
        kernel32.CloseHandle(handle)


def encontrar_letra_por_etiqueta_ps(label):
    try:
        cmd = f'Get-Volume | Where-Object {{$_.FileSystemLabel -eq "{label}"}} | Select-Object -ExpandProperty DriveLetter'
        startupinfo = None
        creationflags = 0
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            creationflags = subprocess.CREATE_NO_WINDOW
            
        output = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", cmd], 
            startupinfo=startupinfo, creationflags=creationflags, text=True, errors="ignore"
        )
        
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        clean_output = ansi_escape.sub('', output).strip()
        if clean_output and len(clean_output) == 1 and clean_output.isalpha():
            return f"{clean_output.upper()}:\\"
    except Exception as e: logging.error(f"Error detectando volumen '{label}': {e}")
    return None


# =====================================================================
# 🖥️ INTERFAZ DE USUARIO Y CONTROLADOR DEL PIPELINE
# =====================================================================

class SavinOceanicCommand(ctk.CTk):

    def verificar_herramientas(self):
        """ Detecta de forma absoluta y recursiva si Ventoy2Disk.exe ya existe en la carpeta engine. """
        engine_path = os.path.join(BASE_DIR, "engine")
        if os.path.exists(engine_path):
            # Recorremos engine para ver si el ejecutable ya está ahí de una sesión previa
            for root, dirs, files in os.walk(engine_path):
                if "Ventoy2Disk.exe" in files:
                    logging.info(f"[FIRMWARE] Ventoy detectado correctamente en: {root}")
                    return True
        return False
    
    def animar_pulso(self):
        if not hasattr(self, 'lbl_btn_descarga') or not self.lbl_btn_descarga.winfo_exists(): return
        if not self.img_descarga_data: return

        step, min_s, max_s = 2, 500, 560        

        if self.creciendo:
            self.tamaño_actual += step
            if self.tamaño_actual >= max_s: self.creciendo = False
        else:
            self.tamaño_actual -= step
            if self.tamaño_actual <= min_s: self.creciendo = True

        self.img_descarga_data.configure(size=(int(self.tamaño_actual), int(self.tamaño_actual)))
        self.animacion_id = self.after(120, self.animar_pulso)

    def clic_en_descarga(self):
        if self.animacion_id:
            try: self.after_cancel(self.animacion_id)
            except: pass
            self.animacion_id = None

        if hasattr(self, 'lbl_btn_descarga'): self.lbl_btn_descarga.destroy()
        if hasattr(self, 'lbl_info'): self.lbl_info.destroy()
        if hasattr(self, 'btn_info_ventoy'): self.btn_info_ventoy.destroy()

        if hasattr(self, 'prog_descarga'):
            self.prog_descarga.place(relx=0.5, rely=0.5, anchor="center")
            threading.Thread(target=self.ejecutar_descarga, daemon=True).start()

    def ejecutar_descarga(self):
    # Usamos *args para tragar de forma segura cualquier parámetro extra que envíe el motor
        def update_bar(val, *args): self.after(0, lambda: self.prog_descarga.set(val))
        exito = descargar_y_extraer_ventoy(progress_callback=update_bar)
        
        if exito:
            time.sleep(1) 
            self.after(0, self.overlay.destroy)
            self.after(0, lambda: self.bloquear_ui(False))
        else: self.after(0, lambda: self.prog_descarga.configure(progress_color="red"))

    def abrir_info_ventoy(self):
        v = self.creventana_info_base("INFORMACIÓN DE COMPLEMENTOS", 620, 340)
        frame_interno = ctk.CTkFrame(v, fg_color="transparent")
        frame_interno.pack(expand=True, fill="both", padx=25, pady=20)
        
        ctk.CTkLabel(frame_interno, text="🔧 COMPLEMENTO CORE: VENTOY", font=("Impact", 26), text_color=AZUL_CIAN).pack(pady=(0, 15))
        info = ("Ventoy es una herramienta open-source esencial que gestiona el entorno multi-boot de tu HollowDrive.\n\n"
                "Permite arrancar múltiples sistemas operativos directamente desde archivos ISO sin formatear la unidad.")
        ctk.CTkLabel(frame_interno, text=info, font=("Segoe UI", 14), justify="center", wraplength=540).pack(pady=5)
        
        f_botones = ctk.CTkFrame(frame_interno, fg_color="transparent")
        f_botones.pack(pady=(20, 0))
        
        ctk.CTkButton(f_botones, text="VISITAR VENTOY", font=("Segoe UI", 12, "bold"), fg_color=AZUL_CARD, border_width=1, border_color=AZUL_CIAN, height=40, width=180, command=lambda: self.abrir_url("https://www.ventoy.net")).pack(side="left", padx=10)
        ctk.CTkButton(f_botones, text="ENTENDIDO", font=("Segoe UI", 12, "bold"), fg_color=AZUL_ELECTRICO, height=40, width=140, command=v.destroy).pack(side="left", padx=10)
        v.update(); v.grab_set()

    def mostrar_capa_descarga(self):
        if self.verificar_herramientas():
            self.bloquear_ui(False) 
            return

        self.bloquear_ui(True) 
        overlay_color = ("#D9D9D9", "#1A1A1A")
        self.overlay = ctk.CTkFrame(self, fg_color=overlay_color)
        self.overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.prog_descarga = ctk.CTkProgressBar(self.overlay, width=400, progress_color=VERDE_EXITO)
        self.prog_descarga.set(0)

        self.btn_info_ventoy = ctk.CTkButton(
            self.overlay, image=getattr(self, 'img_info_descarga', None), text="" if getattr(self, 'img_info_descarga', None) else "I",
            width=120, height=120, fg_color="transparent", hover_color="#122d3d", command=self.abrir_info_ventoy
        )
        self.btn_info_ventoy.place(relx=0.5, rely=0.92, anchor="center")

        self.lbl_btn_descarga = ctk.CTkButton(
            self.overlay, image=self.img_descarga_data, text="" if self.img_descarga_data else "DESCARGAR COMPLEMENTOS",
            font=("Arial", 14, "bold") if not self.img_descarga_data else None, fg_color="transparent" if self.img_descarga_data else AZUL_ELECTRICO,
            hover_color=overlay_color if self.img_descarga_data else "#122d3d", width=600 if self.img_descarga_data else 300, 
            height=600 if self.img_descarga_data else 60, cursor="hand2", command=self.clic_en_descarga
        )
        self.lbl_btn_descarga.place(relx=0.5, rely=0.45, anchor="center")
        
        if self.img_descarga_data:
            self.tamaño_actual = 500
            self.img_descarga_data.configure(size=(500, 500))
            self.animar_pulso()
        
        self.lbl_info = ctk.CTkLabel(
            self.overlay, text="PULSA EL ICONO PARA DESCARGAR COMPLEMENTOS" if self.img_descarga_data else "HAZ CLIC PARA DESCARGAR COMPLEMENTOS",
            font=("Arial", 16, "bold"), text_color=AZUL_CIAN
        )
        self.lbl_info.place(relx=0.5, rely=0.85, anchor="center")

    def refrescar_discos(self):
        self.btn_refresh.configure(state="disabled")
        self.combo_disk.configure(values=["Buscando unidades..."])
        self.combo_disk.set("Buscando unidades...")
        incluir_internos = self.mostrar_internos.get()
        
        def run():
            try:
                discos = obtener_unidades_usb(incluir_internos=incluir_internos)
                self.after(0, lambda: self._finalizar_refresco_discos(discos))
            except Exception as e:
                self.after(0, lambda: self._finalizar_refresco_discos([]))
                
        threading.Thread(target=run, daemon=True).start()

    def _finalizar_refresco_discos(self, discos):
        self.lista_discos_reales = discos
        self.btn_refresh.configure(state="normal")
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
        return ctk.CTkButton(
            master, image=getattr(self, 'img_triangulo', None), text="" if getattr(self, 'img_triangulo', None) else "▲",
            width=30, height=30, fg_color="transparent", hover_color="#122d3d", command=comando
        )
    
    def alternar_modo_instalacion(self, en_progreso=True):
        if en_progreso:
            self.btn_start.pack_forget()
            self.f_progress.pack(side="left", fill="x", expand=True, padx=(0, 10))
            self.btn_cancel.pack(side="right", padx=10)
        else:
            self.f_progress.pack_forget()
            self.btn_cancel.pack_forget()
            self.btn_start.pack(pady=5)

    def confirmar_inicio(self):
        if messagebox.askyesno("CONFIRMACIÓN", "¿Proceder con la instalación real? Se borrarán todos los datos del disco seleccionado."): 
            self.abortar_proceso = False
            self.alternar_modo_instalacion(True) 
            self.comenzar_instalacion()

    def cancelar_proceso(self):
        if messagebox.askyesno("CANCELAR", "¿Seguro que deseas cancelar el proceso?"):
            self.abortar_proceso = True
            self.lbl_status.configure(text="CANCELANDO Y LIMPIANDO... ESPERA POR FAVOR", text_color="#ff4d4d")

    def mostrar_info(self, titulo, mensaje):
        messagebox.showinfo(titulo, mensaje)

    def __init__(self):
        super().__init__()
        self.title(f"SAVIN SUPER_USB // V{VERSION_ACTUAL}")
        
        self.update_idletasks()
        self.geometry(f"1000x850+{(self.winfo_screenwidth() // 2) - 500}+{(self.winfo_screenheight() // 2) - 425}")
        self.resizable(False, False)  
        
        self.animacion_id = None
        self.gif_after_id = None
        self.gif_break_id = None
        self.creciendo = True
        self.tamaño_actual = 180
        self.img_descarga_data = None
        
        self.en_proceso = False
        self.abortar_proceso = False
        self.widgets_interactivos = []
        self.mostrar_internos = ctk.BooleanVar(value=False)
        self.gb_totales = 0.0 
        self.min_cachy = 20.0 
        
        self.instalar_bato = ctk.BooleanVar(value=False)
        self.instalar_cachy = ctk.BooleanVar(value=False) 
        self.bato_64_act = ctk.BooleanVar(value=True)
        self.bato_32_act = ctk.BooleanVar(value=False)
        self.preservar_espacio = ctk.BooleanVar(value=False)
        self.descargar_pack_bato = ctk.BooleanVar(value=False)
        self.descargar_pack_hollow = ctk.BooleanVar(value=True)
        self.metodo_descarga = ctk.StringVar(value="ram")
        self._bloqueo_rebalanceo = False

        self.tamanos_reales = {"bato_64": 4.60, "bato_32": 1.0, "pack_bato": 37.8, "pack_hollow": 8.66}
        self.tamanos_formateados = {"bato_64": "4.60GB", "bato_32": "1GB", "pack_bato": "37.8GB", "pack_hollow": "8.66GB"}

        self.configure(fg_color=AZUL_FONDO) 
        self.attributes("-alpha", 0.94)
        
        self.cargar_recursos() 
        self.setup_ui()
        
        self.actualizar_estados_bato()
        self.actualizar_estados_cachy()
        self.refrescar_discos()

        self.iniciar_carga_tamanos_reales()
        self.after(100, self.mostrar_capa_descarga)
        self.protocol("WM_DELETE_WINDOW", self.cerrar_aplicacion)
        self.after(1000, lambda: threading.Thread(target=self.comprobar_actualizaciones, daemon=True).start())
        self.after(1500, self.preguntar_telemetria_errores)

    def cerrar_aplicacion(self):
        if self.en_proceso:
            if not messagebox.askyesno("⚠️ PROCESO EN CURSO", "¿Estás seguro de que quieres salir?\nLa instalación se interrumpirá."): return  
            self.abortar_proceso = True
        try: self.after_cancel(self.animacion_id)
        except: pass
        try: self.after_cancel(self.gif_after_id)
        except: pass
        try: self.after_cancel(self.gif_break_id)
        except: pass
        self.destroy()

    def preguntar_telemetria_errores(self):
        """Lee la configuración guardada o pregunta al usuario la primera vez."""
        ruta_config = os.path.join(BASE_DIR, "config.json")
        
        # Si ya existe la configuración previa, cargamos el estado sin preguntar
        if os.path.exists(ruta_config):
            try:
                with open(ruta_config, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    self.compartir_errores = config.get("compartir_errores", False)
                    logging.info(f"Telemetría cargada desde configuración: {self.compartir_errores}")
                    return
            except Exception:
                pass

        # Primera ejecución: Lanzamos el cuadro de diálogo
        pregunta = (
            "¿Quieres compartir los errores conmigo?\n\n"
            "Si pones que sí, cuando el programa falle me enviará la información "
            "para que pueda trabajar en una solución, el programa no recopila ningún dato personal ;>"
        )
        self.compartir_errores = messagebox.askyesno("SOPORTE TÉCNICO", pregunta)
        
        # Guardamos la decisión de forma persistente en el disco duro
        try:
            with open(ruta_config, "w", encoding="utf-8") as f:
                json.dump({"compartir_errores": self.compartir_errores}, f, indent=4)
        except Exception as e:
            logging.error(f"No se pudo salvar config.json: {e}")

    def enviar_reporte_error(self, tipo_falla, mensaje_error):
        """ Envía de forma asíncrona el último log y el mensaje exacto del popup a Discord """
        # Coloca aquí tu URL de Webhook copiada de los ajustes del canal de Discord
        url_webhook = "https://discord.com/api/webhooks/1528752157006893127/TU_TOKEN_AQUI"
        
        # Validación de seguridad por si no se ha configurado el Webhook
        if "TU_TOKEN_AQUI" in url_webhook:
            logging.warning("[TELEMETRÍA] Webhook no configurado. Saltando envío.")
            return

        def hilo_envio():
            try:
                payload = {
                    "content": (
                        f"🚨 **¡PROCESO INTERRUMPIDO / CRASH DETECTADO!**\n"
                        f"💻 **Versión:** HollowDrive V{VERSION_ACTUAL}\n"
                        f"⚠️ **Tipo:** `{tipo_falla}`\n"
                        f"❌ **Error en Ventana:** `{mensaje_error}`"
                    )
                }
                
                # Buscamos el archivo de log actual de esta sesión
                if 'archivo_log' in globals() and os.path.exists(archivo_log):
                    with open(archivo_log, "rb") as f:
                        files = {"file": (os.path.basename(archivo_log), f, "text/plain")}
                        requests.post(url_webhook, data=payload, files=files, timeout=15)
                else:
                    requests.post(url_webhook, json=payload, timeout=15)
                    
                logging.info("[TELEMETRÍA] Reporte técnico enviado con éxito a Discord.")
            except Exception as e:
                print(f"Error crítico enviando el reporte a Discord: {e}")

        # Lo ejecutamos en segundo plano para que la interfaz gráfica no se congele ni un milisegundo
        threading.Thread(target=hilo_envio, daemon=True).start()

    def toggle_discos_internos(self):
        if self.mostrar_internos.get():
            if not messagebox.askyesno("⚠️ MODO PELIGRO", "Vas a habilitar la visualización de DISCOS INTERNOS.\nInstalar HollowDrive en un disco interno BORRARÁ TODO su contenido.\n¿Continuar?", icon='warning'):
                self.mostrar_internos.set(False)
                return
        self.refrescar_discos()

    def cargar_gif_pil(self, ruta_gif, size=None, espejo=False):
        if not os.path.exists(ruta_gif): return []
        try:
            pil_img = Image.open(ruta_gif)
            frames = []
            for frame in ImageSequence.Iterator(pil_img):
                frame_c = frame.copy().convert("RGBA")
                if size: frame_c = frame_c.resize(size, Image.Resampling.LANCZOS)
                if espejo: frame_c = frame_c.transpose(Image.FLIP_LEFT_RIGHT)
                
                final_size = size if size else frame_c.size
                frames.append(ctk.CTkImage(light_image=frame_c, dark_image=frame_c, size=final_size))
            return frames
        except Exception: return []

    def cargar_recursos(self):
        path_media = CARPETA_MEDIA
        try: 
            img_bato = Image.open(os.path.join(path_media, "batocera.png"))
            self.logo_batocera = ctk.CTkImage(light_image=img_bato, dark_image=img_bato, size=(125, 88))
            self.bato_size = (125, 88) # Nueva variable de rastreo
        except: self.logo_batocera = None
        
        try: 
            img_cachy = Image.open(os.path.join(path_media, "cachy.png"))
            self.logo_cachy = ctk.CTkImage(light_image=img_cachy, dark_image=img_cachy, size=(280, 78))
            self.cachy_size = (280, 78) # Nueva variable de rastreo
        except: self.logo_cachy = None
        try: img_savin = Image.open(os.path.join(path_media, "Savin-2.png")); self.logo_savin = ctk.CTkImage(light_image=img_savin, dark_image=img_savin, size=(240, 135))
        except: self.logo_savin = None
        try: img_maker = Image.open(os.path.join(path_media, "HollowDrive-2.png")); self.logo_maker = ctk.CTkImage(light_image=img_maker, dark_image=img_maker, size=(520, 310))
        except: self.logo_maker = None
        try: pil_instalar = Image.open(os.path.join(path_media, "instalar.png")); self.img_instalar = ctk.CTkImage(light_image=pil_instalar, dark_image=pil_instalar, size=(512, 120))
        except: self.img_instalar = None
        try: pil_image = Image.open(os.path.join(path_media, "descarga-morada.png")); self.img_descarga_data = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=(350, 350))
        except: self.img_descarga_data = None
        try: pil_reload = Image.open(os.path.join(path_media, "reload.png")); self.img_reload = ctk.CTkImage(light_image=pil_reload, dark_image=pil_reload, size=(25, 25))
        except: self.img_reload = None

        self.frames_linterna = self.cargar_gif_pil(os.path.join(CARPETA_MEDIA, "hollow-linterna.gif"), size=(70, 70), espejo=True)
        self.frames_breakdance = self.cargar_gif_pil(os.path.join(CARPETA_MEDIA, "breakdance.gif"), size=None)

    def al_clicar_pack_batocera(self):
        if self.descargar_pack_bato.get(): self.abrir_info_roms()
        self.rebalancear()

    def abrir_info_motor(self):
        v = self.creventana_info_base("MOTORES DE EXTRACCIÓN", 720, 520)
        frame_interno = ctk.CTkFrame(v, fg_color="transparent")
        frame_interno.pack(expand=True, fill="both", padx=25, pady=20)
        ctk.CTkLabel(frame_interno, text="⚙️ MOTORES DE INSTALACIÓN", font=("Impact", 28), text_color=AZUL_CIAN).pack(pady=(0, 10))
        
        info = ("HollowDrive te permite elegir cómo el sistema gestiona la red y los archivos pesados:\n\n"
                "⚡ ASÍNCRONO (RAM - Recomendado): Descarga a máxima velocidad volcando los datos a un colchón temporal en tu memoria RAM (usa ~2GB). Extrae directamente al USB. Es el método más rápido y no requiere espacio libre en el disco.\n\n"
                "🛡️ CLÁSICO (Disco Local): Si tu PC es lento o tiene poca RAM, este método descargará el archivo primero a una carpeta oculta en tu disco duro (temp_downloads), y después lo extracurricular al USB. Requiere espacio libre en el disco suficiente para almacenar el archivo descargado, pero es 100% infalible contra cortes de red.")
        ctk.CTkLabel(frame_interno, text=info, font=("Segoe UI", 13), justify="left", wraplength=640).pack(pady=5)
        
        consejo = ("CONSEJO:\n"
                   "• Usa \"Asíncrono\" si no tienes espacio libre en tu disco local.\n"
                   "• Usa \"Clásico\" si quieres máxima seguridad ante cortes de descarga o tienes poca RAM.\n\n"
                   "OJO: Si usas el método clásico, coloca el .exe de este programa en el disco que tengas espacio disponible (necesitarás 5 GB para batocera, 8,06 GB para el pack de Hollowdrive, 13GB para cachyos o 37GB si descargas el pack de batocera)")
        ctk.CTkLabel(frame_interno, text=consejo, font=("Segoe UI", 13, "bold"), text_color=AZUL_CIAN, justify="left", wraplength=640).pack(pady=10)

        ctk.CTkButton(frame_interno, text="ENTENDIDO", font=("Segoe UI", 14, "bold"), fg_color=AZUL_ELECTRICO, height=40, width=180, command=v.destroy).pack(pady=(15, 0))
        v.update(); v.grab_set()

    def iniciar_carga_tamanos_reales(self): threading.Thread(target=self.cargar_tamanos_reales_hilo, daemon=True).start()

    def consultar_tamano(self, clave, default_bytes):
        for var in [clave, clave.replace("bato", "batocera")]:
            try:
                tam_bytes = resolver_tamano_pack(var)
                if tam_bytes and tam_bytes > 0: return tam_bytes
            except: continue
        return default_bytes

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
        ctk.CTkLabel(frame_interno, text="🛠️ PACK DE HERRAMIENTAS HOLLOWDRIVE", font=("Impact", 24), text_color=AZUL_CIAN).pack(pady=(0, 15))
        info = ("Este paquete inyecta una seleccion de entornos y utilidades de rescate "
                "booteables listas para usar desde el menú principal:\n\n"
                "• Herramientas avanzadas de particionado y gestión de discos.\n"
                "• Utilidades de clonación, backup y recuperación de datos.\n"
                "• Entornos Windows Live (WinPE) para reparar sistemas caídos.")
        ctk.CTkLabel(frame_interno, text=info, font=("Segoe UI", 14), justify="left", wraplength=550).pack(pady=5)
        ctk.CTkButton(frame_interno, text="ENTENDIDO", font=("Segoe UI", 14, "bold"), fg_color=AZUL_ELECTRICO, height=40, width=180, command=v.destroy).pack(pady=(15, 0))
        v.update(); v.grab_set()

    def cargar_tamanos_reales_hilo(self):
        fallbacks = {"bato_64": 4.60*(1024**3), "bato_32": 1.0*(1024**3), "pack_bato": 37.8*(1024**3), "pack_hollow": 8.66*(1024**3)}
        for clave, fb_val in fallbacks.items():
            tam_bytes = self.consultar_tamano(clave, fb_val)
            self.tamanos_reales[clave] = tam_bytes / (1024**3) 
            try: self.tamanos_formateados[clave] = formatear_tamano(tam_bytes)
            except: self.tamanos_formateados[clave] = f"{self.tamanos_reales[clave]:.2f}GB"
        self.after(0, self.actualizar_labels_ui_con_tamanos_reales)

    def actualizar_labels_ui_con_tamanos_reales(self):
        self.ch_b64.configure(text=f"Batocera 64bits ({self.tamanos_formateados['bato_64']})")
        self.ch_b32.configure(text=f"Batocera 32bits ({self.tamanos_formateados['bato_32']})")
        self.ch_pack_bato.configure(text=f"PACK BATOCERA ({self.tamanos_formateados['pack_bato']})")
        self.ch_pack_hollow.configure(text=f"PACK HOLLOWDRIVE ({self.tamanos_formateados['pack_hollow']})")
        self.rebalancear()

    def setup_ui(self):
        ruta_i = os.path.join(CARPETA_MEDIA, "I.png")
        if os.path.exists(ruta_i):
            img_i_pil = Image.open(ruta_i)
            self.img_info = ctk.CTkImage(light_image=img_i_pil, dark_image=img_i_pil, size=(100, 100))
            self.img_info_descarga = ctk.CTkImage(light_image=img_i_pil, dark_image=img_i_pil, size=(120, 120))
        
        try: img_t_pil = Image.open(os.path.join(CARPETA_MEDIA, "triangulo.png")); self.img_triangulo = ctk.CTkImage(light_image=img_t_pil, dark_image=img_t_pil, size=(30, 30))
        except: self.img_triangulo = None

        # --- CABECERA ---
        self.header = ctk.CTkFrame(self, fg_color="transparent", height=120)
        self.header.pack(fill="x", padx=20, pady=0)
        if getattr(self, 'logo_savin', None): ctk.CTkLabel(self.header, image=self.logo_savin, text="").place(x=0, y=-10)
        if getattr(self, 'logo_maker', None): ctk.CTkLabel(self.header, image=self.logo_maker, text="").place(relx=0.5, y=-85, anchor="n")
        self.btn_info_main = ctk.CTkButton(self, image=getattr(self, 'img_info', None), text="" if getattr(self, 'img_info', None) else "I", width=100, height=100, fg_color="transparent", hover_color=AZUL_CARD, command=self.abrir_ventana_info)
        self.btn_info_main.place(x=880, y=10)

        # --- SELECTOR DE DISCOS ---
        self.f_selection = ctk.CTkFrame(self, fg_color=AZUL_CARD, border_width=1, border_color=AZUL_ELECTRICO)
        self.f_selection.pack(fill="x", padx=20, pady=(0, 10)) 
        ctk.CTkLabel(self.f_selection, text="Selecciona un dispositivo para instalar HOLLOWDRIVE.", font=("Segoe UI", 15, "italic"), text_color=AZUL_SUAVE).pack(pady=(10,0))
        
        f_combo = ctk.CTkFrame(self.f_selection, fg_color="transparent")
        f_combo.pack(pady=15)
        self.combo_disk = ctk.CTkComboBox(f_combo, values=["Buscando unidades..."], width=450, command=self.activar_interfaz_completa)
        self.combo_disk.set("Buscando unidades...")
        self.combo_disk.pack(side="left", padx=10)
        self.widgets_interactivos.append(self.combo_disk)

        self.btn_refresh = ctk.CTkButton(f_combo, image=getattr(self, 'img_reload', None), text="" if getattr(self, 'img_reload', None) else "🔄", width=40, height=40, fg_color="#222", command=self.refrescar_discos)
        self.btn_refresh.pack(side="left", padx=5)

        self.sw_internos = ctk.CTkCheckBox(f_combo, text="Mostrar discos internos", variable=self.mostrar_internos, command=self.toggle_discos_internos, text_color="#aa3333", font=("Segoe UI", 11, "bold"))
        self.sw_internos.pack(side="left", padx=10)

        # --- CONTENEDOR MAESTRO ---
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        
        # PANEL IZQUIERDO
        self.p_left = ctk.CTkFrame(self.main_container, fg_color=AZUL_CARD, corner_radius=15, border_width=1, border_color="#222")
        self.p_left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        # SECCIÓN BATOCERA
        f_bato_master = ctk.CTkFrame(self.p_left, fg_color="transparent")
        f_bato_master.pack(fill="x", padx=15, pady=15)
        f_bato_txt = ctk.CTkFrame(f_bato_master, fg_color="transparent")
        f_bato_txt.pack(side="left", fill="both", expand=True)
        f_bato_h = ctk.CTkFrame(f_bato_txt, fg_color="transparent")
        f_bato_h.pack(fill="x")
        
        sw_bato = ctk.CTkSwitch(f_bato_h, text="¿Instalar Batocera?", font=("Segoe UI", 12, "bold"), variable=self.instalar_bato, command=self.actualizar_estados_bato, progress_color=AZUL_CIAN)
        sw_bato.pack(side="left")
        self.widgets_interactivos.append(sw_bato)
        self.crear_boton_info(f_bato_h, self.abrir_info_batocera).pack(side="left", padx=5)

        self.f_bato_opts = ctk.CTkFrame(f_bato_txt, fg_color="#0d141c", corner_radius=8)
        self.f_bato_opts.pack(fill="x", pady=5)
        self.ch_b64 = ctk.CTkCheckBox(self.f_bato_opts, text="Batocera 64bits (4.60GB)", variable=self.bato_64_act, command=self.rebalancear)
        self.ch_b64.pack(pady=2, padx=10, anchor="w")
        self.ch_b32 = ctk.CTkCheckBox(self.f_bato_opts, text="Batocera 32bits (Próximamente)", variable=self.bato_32_act, command=self.rebalancear, state="disabled")
        self.ch_b32.pack(pady=2, padx=10, anchor="w")
        self.widgets_interactivos.extend([self.ch_b64, self.ch_b32])
        if getattr(self, 'logo_batocera', None):
            # 1. Contenedor fijo invisible con el tamaño máximo del zoom (135x95)
            f_bato_logo_container = ctk.CTkFrame(f_bato_master, width=135, height=95, fg_color="transparent")
            f_bato_logo_container.pack(side="right", padx=10)
            f_bato_logo_container.pack_propagate(False) # Congela el tamaño del frame
            
            # 2. El logo se centra dentro del contenedor
            lbl_img_bato = ctk.CTkLabel(f_bato_logo_container, image=self.logo_batocera, text="", cursor="hand2")
            lbl_img_bato.place(relx=0.5, rely=0.5, anchor="center")
            
            # 3. Eventos
            lbl_img_bato.bind("<Button-1>", lambda e: self.abrir_url("https://batocera.org"))
            lbl_img_bato.bind("<Enter>", lambda e: self.animar_zoom('logo_batocera', 'bato_size', (125, 88), (135, 95), True))
            lbl_img_bato.bind("<Leave>", lambda e: self.animar_zoom('logo_batocera', 'bato_size', (125, 88), (135, 95), False))

        # --- SECCIÓN DE PACKS ADICIONALES ---
        f_packs_container = ctk.CTkFrame(self.p_left, fg_color="#0d141c", corner_radius=8)
        f_packs_container.pack(fill="x", padx=15, pady=5)

        f_pack_bato = ctk.CTkFrame(f_packs_container, fg_color="transparent")
        f_pack_bato.pack(fill="x", padx=10, pady=6)
        self.ch_pack_bato = ctk.CTkCheckBox(f_pack_bato, text="PACK BATOCERA (37.8GB)", variable=self.descargar_pack_bato, command=self.al_clicar_pack_batocera)
        self.ch_pack_bato.pack(side="left", anchor="w")
        self.widgets_interactivos.append(self.ch_pack_bato)
        self.crear_boton_info(f_pack_bato, self.abrir_info_roms).pack(side="left", padx=5)

        f_pack_hollow = ctk.CTkFrame(f_packs_container, fg_color="transparent")
        f_pack_hollow.pack(fill="x", padx=10, pady=6)
        self.ch_pack_hollow = ctk.CTkCheckBox(f_pack_hollow, text="PACK HOLLOWDRIVE (8.06GB)", variable=self.descargar_pack_hollow, command=self.rebalancear)
        self.ch_pack_hollow.pack(side="left", anchor="w")
        self.widgets_interactivos.append(self.ch_pack_hollow)
        self.crear_boton_info(f_pack_hollow, self.abrir_info_pack_hollow).pack(side="left", padx=5)

        # SECCIÓN CACHYOS
        f_cachy_master = ctk.CTkFrame(self.p_left, fg_color="transparent")
        f_cachy_master.pack(fill="x", padx=15, pady=15)
        if getattr(self, 'logo_cachy', None):
            # 1. Contenedor fijo invisible con el tamaño máximo del zoom (305x85)
            f_cachy_logo_container = ctk.CTkFrame(f_cachy_master, width=305, height=85, fg_color="transparent")
            f_cachy_logo_container.pack(pady=(0, 10))
            f_cachy_logo_container.pack_propagate(False) # Congela el tamaño del frame
            
            # 2. El logo se centra dentro del contenedor
            lbl_img_cachy = ctk.CTkLabel(f_cachy_logo_container, image=self.logo_cachy, text="", cursor="hand2")
            lbl_img_cachy.place(relx=0.5, rely=0.5, anchor="center")
            
            # 3. Eventos
            lbl_img_cachy.bind("<Button-1>", lambda e: self.abrir_url("https://cachyos.org"))
            lbl_img_cachy.bind("<Enter>", lambda e: self.animar_zoom('logo_cachy', 'cachy_size', (280, 78), (305, 85), True))
            lbl_img_cachy.bind("<Leave>", lambda e: self.animar_zoom('logo_cachy', 'cachy_size', (280, 78), (305, 85), False))

        f_cachy_h = ctk.CTkFrame(f_cachy_master, fg_color="transparent")
        f_cachy_h.pack(fill="x")
        sw_cachy = ctk.CTkSwitch(f_cachy_h, text="¿Instalar CachyOS?", font=("Segoe UI", 12, "bold"), variable=self.instalar_cachy, command=self.actualizar_estados_cachy, progress_color=AZUL_CIAN)
        sw_cachy.pack(side="left")
        self.widgets_interactivos.append(sw_cachy)
        self.crear_boton_info(f_cachy_h, self.abrir_info_cachyos).pack(side="left", padx=5)

        # PANEL DERECHO (CONTROL DE ESPACIO Y CONFIGURACIÓN)
        self.p_right = ctk.CTkFrame(self.main_container, fg_color=AZUL_CARD, corner_radius=15, border_width=1, border_color="#222")
        self.p_right.pack(side="right", fill="both", expand=True)

        # --- SELECCIÓN DE MOTOR DE DESCARGA ---
        self.f_motor = ctk.CTkFrame(self.p_right, fg_color="#0d141c", corner_radius=8, border_width=1, border_color="#222")
        self.f_motor.pack(fill="x", padx=20, pady=(15, 5))
        f_motor_h = ctk.CTkFrame(self.f_motor, fg_color="transparent")
        f_motor_h.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(f_motor_h, text="⚙️ MOTOR DE EXTRACCIÓN:", font=("Consolas", 12, "bold"), text_color=AZUL_CIAN).pack(side="left")
        self.crear_boton_info(f_motor_h, self.abrir_info_motor).pack(side="right")
        
        f_radios = ctk.CTkFrame(self.f_motor, fg_color="transparent")
        f_radios.pack(fill="x", padx=10, pady=(0, 10))
        r1 = ctk.CTkRadioButton(f_radios, text="Asíncrono (RAM) - Rápido", variable=self.metodo_descarga, value="ram", font=("Segoe UI", 11))
        r1.pack(side="left", padx=(0, 10))
        r2 = ctk.CTkRadioButton(f_radios, text="Clásico (Disco) - Seguro", variable=self.metodo_descarga, value="disco", font=("Segoe UI", 11))
        r2.pack(side="left")
        self.widgets_interactivos.extend([r1, r2])

        self.sw_preservar = ctk.CTkSwitch(self.p_right, text="PRESERVAR ESPACIO LIBRE USB", variable=self.preservar_espacio, command=self.toggle_preservar_espacio, progress_color=AZUL_ELECTRICO)
        self.sw_preservar.pack(pady=10)
        self.widgets_interactivos.append(self.sw_preservar)

        self.f_row_h = self.crear_ocean_slider(self.p_right, "HOLLOWDRIVE STORAGE", COLOR_HOLLOW, "h", min_val=10)
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
                width=140, height=28, corner_radius=15, text_color="white", font=("Segoe UI Bold", 11),
                command=lambda t=tit, m=msg: self.mostrar_info(t, m)
            )
            btn.pack(side="left", padx=10, expand=True)
            self.dic_leyenda[nombre.lower()] = btn

        # --- FOOTER ---
        self.footer = ctk.CTkFrame(self, fg_color="transparent")
        self.f_progress = ctk.CTkFrame(self.footer, fg_color="transparent")
        
        self.f_bars_layout = ctk.CTkFrame(self.f_progress, fg_color="transparent")
        self.f_bars_layout.pack(side="left", fill="x", expand=True)
        
        self.f_status_header = ctk.CTkFrame(self.f_bars_layout, fg_color="transparent", height=35)
        self.f_status_header.pack(fill="x", pady=(0, 2))
        self.f_status_header.pack_propagate(False)
        
        self.lbl_status = ctk.CTkLabel(self.f_status_header, text="ESPERANDO INICIO...", font=("Consolas", 11), text_color=AZUL_SUAVE)
        self.lbl_status.pack(side="left", anchor="sw")
        
        self.p_task = ctk.CTkProgressBar(self.f_bars_layout, height=4, progress_color=AZUL_CIAN)
        self.p_task.set(0)
        self.p_task.pack(fill="x", pady=2)
        
        self.p_total = ctk.CTkProgressBar(self.f_bars_layout, height=10, progress_color=AZUL_ELECTRICO)
        self.p_total.set(0)
        self.p_total.pack(fill="x", pady=2)
        
        self.f_gifs = ctk.CTkFrame(self.f_progress, fg_color="transparent")
        self.f_gifs.pack(side="right", padx=(15, 0))
        
        self.lbl_gif_breakdance = ctk.CTkLabel(self.f_gifs, text="", fg_color="transparent")
        self.lbl_gif = ctk.CTkLabel(self.f_gifs, text="", width=70, height=70)
        self.lbl_gif.pack(side="right")
        
        self.btn_start = ctk.CTkButton(self.footer, image=getattr(self, 'img_instalar', None), text="" if getattr(self, 'img_instalar', None) else "Instalar HollowDrive🩵", fg_color="transparent", hover_color=AZUL_CARD, width=512, height=120, command=self.confirmar_inicio)
        self.btn_start.pack(pady=5)
        
        self.btn_cancel = ctk.CTkButton(self.footer, text="CANCELAR", fg_color="#aa3333", width=120, height=50, command=self.cancelar_proceso)

    def toggle_preservar_espacio(self): self.rebalancear()

    def bloquear_ui(self, bloquear=True):
        st = "disabled" if bloquear else "normal"
        for w in self.widgets_interactivos: 
            if hasattr(w, "winfo_exists") and w.winfo_exists(): w.configure(state=st)

    def creventana_info_base(self, titulo, ancho, alto):
        v = ctk.CTkToplevel(self)
        v.title(titulo)
        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (ancho // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (alto // 2)
        v.geometry(f"{ancho}x{alto}+{x}+{y}")
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

    def abrir_ventana_info(self):
        from PIL import Image
        import os

        # Ampliamos la altura a 780 para dar espacio al reproductor y los nuevos créditos sin apretar los elementos
        v = self.creventana_info_base("SAVIN CORE INFO", 750, 780)

        frame_interno = ctk.CTkFrame(v, fg_color="transparent")
        frame_interno.pack(expand=True, fill="both", padx=25, pady=20)

        # --- TÍTULO PRINCIPAL ---
        ctk.CTkLabel(frame_interno, text="👑 SAVIN HOLLOWDRIVE 👑", font=("Impact", 38), text_color=AZUL_CIAN).pack(pady=(0, 10))

        # --- SECCIÓN REDES SOCIALES (CONSERVADAS) ---
        ctk.CTkLabel(frame_interno, text="◈ MIS PLATAFORMAS ◈", font=("Consolas", 16, "bold"), text_color=AZUL_SUAVE).pack(pady=5)
        f_social = ctk.CTkFrame(frame_interno, fg_color="transparent")
        f_social.pack(pady=5)

        socials = [
            ("💬 DISCORD", "https://discord.gg/HJvgmCRpGm"), 
            ("📂 GITHUB", "https://github.com/MVP-Savyn"), 
            ("📺 YOUTUBE", "https://youtube.com/@T0xicArea")
        ]
        for texto, url in socials:
            ctk.CTkButton(f_social, text=texto, font=("Consolas", 12, "bold"), 
                          fg_color=AZUL_CARD, border_width=1, border_color=AZUL_ELECTRICO, 
                          width=140, height=35, command=lambda u=url: webbrowser.open_new_tab(u)).pack(side="left", padx=8)

        # --- SECCIÓN VISTA PREVIA DE VÍDEO CON IMAGEN LOCAL ---
        ctk.CTkLabel(frame_interno, text="◈ ¡MIRA ESTE VÍDEO PARA SABER CÓMO FUNCIONA! ◈", font=("Consolas", 16, "bold"), text_color=AZUL_SUAVE).pack(pady=(15, 5))

        url_video_youtube = "https://youtu.be/oHg5SJYRHA0?si=7nL_H5sIWuiLM4dp"

        # Frame contenedor con dimensiones 16:9 y bordes redondeados
        f_video = ctk.CTkFrame(frame_interno, fg_color=AZUL_CARD, border_width=2, border_color=AZUL_ELECTRICO, width=480, height=270, corner_radius=15)
        f_video.pack_propagate(False) # Evita que se encoja al meter la imagen
        f_video.pack(pady=10)

        # 1. Cargamos la imagen local de fondo
        ruta_miniatura = resource_path("miniatura.png") #  Seguro  
        try:
            img_raw = Image.open(ruta_miniatura)
            img_ctk = ctk.CTkImage(light_image=img_raw, dark_image=img_raw, size=(480, 270))
            lbl_fondo = ctk.CTkLabel(f_video, text="", image=img_ctk, corner_radius=15)
            lbl_fondo.place(relx=0.5, rely=0.5, anchor="center")
        except Exception:
            pass

        # 2. Cargamos el icono de play (¡Ahora el doble de grande!)
        ruta_play = os.path.join(CARPETA_MEDIA, "play.png")
        try:
            img_play_raw = Image.open(ruta_play)
            # Tamaño masivo de entrada: 75x75
            self.img_play_ctk = ctk.CTkImage(light_image=img_play_raw, dark_image=img_play_raw, size=(75, 75))
            self.play_size = (75, 75) # Rastreador de tamaño base
        except Exception as e:
            print(f"[AVISO] No se pudo cargar play.png: {e}")
            self.img_play_ctk = None

        # 3. Creamos el LBL interactivo gigante
        lbl_play = ctk.CTkLabel(
            f_video, 
            text="" if getattr(self, 'img_play_ctk', None) else "▶", 
            image=getattr(self, 'img_play_ctk', None),
            font=("Consolas", 65, "bold"), # Escalado por si la imagen no carga
            text_color="#ffffff",
            fg_color="transparent", 
            cursor="hand2"          
        )
        lbl_play.place(relx=0.5, rely=0.5, anchor="center")

        lbl_play.bind("<Button-1>", lambda e: webbrowser.open_new_tab(url_video_youtube))

        # 4. Transición fluida adaptada al tamaño gigante (de 75x75 a 95x95)
        def animacion_entrar(e):
            if getattr(self, 'img_play_ctk', None):
                self.animar_zoom('img_play_ctk', 'play_size', (75, 75), (95, 95), True)
            else:
                lbl_play.configure(font=("Consolas", 80, "bold"))
            
        def animacion_salir(e):
            if getattr(self, 'img_play_ctk', None):
                self.animar_zoom('img_play_ctk', 'play_size', (75, 75), (95, 95), False)
            else:
                lbl_play.configure(font=("Consolas", 65, "bold"))

        lbl_play.bind("<Enter>", animacion_entrar)
        lbl_play.bind("<Leave>", animacion_salir)

        # --- SECCIÓN RECURSOS Y CRÉDITOS ---
        ctk.CTkLabel(frame_interno, text="◈ CONTENIDO UTILIZADO Y RECURSOS ◈", font=("Consolas", 16, "bold"), text_color=AZUL_SUAVE).pack(pady=(15, 5))

        credits = [
            ("CACHY OS", "https://cachyos.org"),
            ("BATOCERA LINUX", "https://batocera.org"),
            ("VENTOY CORE", "https://www.ventoy.net")
        ]

        f_credits = ctk.CTkFrame(frame_interno, fg_color="transparent")
        f_credits.pack(fill="x", padx=100, pady=2)

        for name, link in credits:
            row = ctk.CTkFrame(f_credits, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=f"• {name}", font=("Consolas", 13)).pack(side="left")
            ctk.CTkButton(row, text="Visitar", width=80, height=20, fg_color=AZUL_CARD, border_width=1, border_color=AZUL_ELECTRICO, command=lambda l=link: webbrowser.open_new_tab(l)).pack(side="right")

        # --- TARJETA DE AGRADECIMIENTO ESPECIAL A MEDICAT ---
        f_medicat = ctk.CTkFrame(frame_interno, fg_color="#181824", border_width=1, border_color=AZUL_ELECTRICO, corner_radius=6)
        f_medicat.pack(fill="x", padx=100, pady=(15, 10))

        lbl_thanks = ctk.CTkLabel(f_medicat, text="💖 Gracias a MediCat USB, que me inspiró a crear un USB cercano a la perfección✨.", 
                                  font=("Consolas", 11, "italic"), text_color="#dddddd", wraplength=480)
        lbl_thanks.pack(pady=8, padx=15)

        # --- BOTÓN DE CIERRE DEFINTIVO ---
        ctk.CTkButton(frame_interno, text="CERRAR", width=200, height=35, command=v.destroy).pack(pady=(15, 0))

        v.update()
        v.grab_set()

    def activar_interfaz_completa(self, seleccion):
        if "---" in seleccion or "Buscando" in seleccion or "NO SE DETECTAN" in seleccion: return
        disco_elegido = next((d for d in self.lista_discos_reales if d["display"] == seleccion), None)
        if disco_elegido: self.gb_totales = disco_elegido["size"]
        self.footer.pack(fill="x", side="bottom", padx=20, pady=10)
        self.main_container.pack(fill="both", expand=True, padx=20, pady=5)
        self.slider_h.set(self.gb_totales)
        if hasattr(self, 'slider_c'): self.slider_c.set(0.0)
        self.rebalancear()

    def crear_ocean_slider(self, parent, label, color, key, min_val=10):
        f = ctk.CTkFrame(parent, fg_color="transparent"); f.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(f, text=f"❯ {label}", font=("Consolas", 11, "bold")).pack(anchor="w")
        row = ctk.CTkFrame(f, fg_color="transparent"); row.pack(fill="x")
        s = ctk.CTkSlider(row, from_=min_val, to=1000, progress_color=color, command=lambda v, k=key: self.rebalancear(f"slider_{k}"))
        s.pack(side="left", fill="x", expand=True)
        setattr(self, f"slider_{key}", s)
        self.widgets_interactivos.append(s)
        l_val = ctk.CTkLabel(row, text="0 GB", width=70, font=("Consolas", 14, "bold")); l_val.pack(side="right")
        setattr(self, f"lbl_{key}_gb", l_val)
        return f

    def rebalancear(self, source=None):
        if self.gb_totales <= 0: return
        if getattr(self, '_bloqueo_rebalanceo', False): return
        self._bloqueo_rebalanceo = True

        try:
            espacio_grub = GB_GRUB if self.instalar_cachy.get() else 0.0
            
            gb_bato_interno = (self.tamanos_reales["bato_64"] if self.bato_64_act.get() else 0.0) + \
                              (self.tamanos_reales["bato_32"] if self.bato_32_act.get() else 0.0) \
                              if self.instalar_bato.get() else 0.0
                    
            base_hollow = 10.0 if self.descargar_pack_hollow.get() else 3.0
            base_obligatoria = base_hollow
            if self.instalar_cachy.get(): base_obligatoria += self.min_cachy  
                
            espacio_libre_para_packs = self.gb_totales - base_obligatoria - gb_bato_interno - espacio_grub
            bato_disponible = self.instalar_bato.get() and (self.bato_64_act.get() or self.bato_32_act.get())
            val_pack_bato = 0.0
            
            if bato_disponible:
                self.ch_pack_bato.configure(state="normal")
                if self.descargar_pack_bato.get():
                    if espacio_libre_para_packs >= self.tamanos_reales["pack_bato"]:
                        val_pack_bato = self.tamanos_reales["pack_bato"]
                    else:
                        messagebox.showwarning("Espacio Insuficiente", "El pack de batocera no cabe en tu configuración.")
                        self.descargar_pack_bato.set(False)
                        self.ch_pack_bato.deselect()
            else:
                self.ch_pack_bato.configure(state="disabled")
                self.descargar_pack_bato.set(False)
                self.ch_pack_bato.deselect()

            min_h = base_hollow + gb_bato_interno + val_pack_bato
            min_c = self.min_cachy if self.instalar_cachy.get() else 0.0
            disp = self.gb_totales - espacio_grub

            if min_h + min_c > disp:
                min_h = min(min_h, disp)
                min_c = max(0.0, disp - min_h)

            self.slider_h.configure(state="normal")
            self.slider_c.configure(state="normal" if self.instalar_cachy.get() else "disabled")

            h = self.slider_h.get()
            c = self.slider_c.get() if self.instalar_cachy.get() else 0.0

            if h < min_h: h = min_h
            if self.instalar_cachy.get() and c < min_c: c = min_c

            if self.preservar_espacio.get():
                if source == "slider_h":
                    if h + c > disp:
                        c = max(min_c, disp - h)
                        if h + c > disp: h = disp - c
                elif source == "slider_c":
                    if h + c > disp:
                        h = max(min_h, disp - c)
                        if h + c > disp: c = disp - h
                else:
                    if h + c > disp:
                        h = max(min_h, disp - c)
                        if h + c > disp:
                            c = max(min_c, disp - h)
                            h = disp - c
            else:
                if self.instalar_cachy.get():
                    if source == "slider_h":
                        c = disp - h
                        if c < min_c:
                            c = min_c
                            h = disp - min_c
                    elif source == "slider_c":
                        h = disp - c
                        if h < min_h:
                            h = min_h
                            c = disp - min_h
                    else:
                        c = disp - h
                        if c < min_c:
                            c = min_c
                            h = disp - min_c
                        if h < min_h:
                            h = min_h
                            c = disp - min_h
                else:
                    c = 0.0
                    h = disp
                    self.slider_h.configure(state="disabled")

            max_h_slider = (disp - min_c) if self.instalar_cachy.get() else disp
            
            if source != "slider_h":
                self.slider_h.configure(from_=base_hollow, to=max(base_hollow + 0.1, max_h_slider))
                self.slider_h.set(h)  
            elif abs(self.slider_h.get() - h) > 0.05:
                self.slider_h.set(h)
                
            self.lbl_h_gb.configure(text=f"{h:.1f} GB")
            
            if self.instalar_cachy.get():
                from_c = min_c
                to_c = max(from_c + 1.0, disp - min_h)
                if source != "slider_c":
                    self.slider_c.configure(from_=from_c, to=to_c)
                    self.slider_c.set(c)  
                elif abs(self.slider_c.get() - c) > 0.05:
                    self.slider_c.set(c)
                self.lbl_c_gb.configure(text=f"{c:.1f} GB")

            libre_calculado = max(0.0, disp - (h + c))
            self.lbl_libre_info.configure(text=f"LIBRE: {libre_calculado:.2f} GB")

            self.dic_leyenda["hollow"].configure(text=f"Hollow ({h:.1f}GB)")
            if self.instalar_cachy.get():
                self.dic_leyenda["grub"].configure(text=f"GRUB ({espacio_grub:.1f}GB)")
                self.dic_leyenda["cachy"].configure(text=f"Cachy ({c:.1f}GB)")
            else:
                self.dic_leyenda["grub"].configure(text="GRUB (0GB)")
                self.dic_leyenda["cachy"].configure(text="Cachy (0GB)")

            self.actualizar_barra_visual(h, espacio_grub, c)
            
        finally:
            self._bloqueo_rebalanceo = False
    
    def comprobar_actualizaciones(self):
        """ Filtra la última release buscando estrictamente el binario oficial """
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                tag_remoto = data["tag_name"].strip().lower().replace("v", "")
                version_local = VERSION_ACTUAL.strip().lower().replace("v", "")
                
                if tag_remoto != version_local:
                    url_exe_descarga = None
                    # Buscamos el ejecutable con el nombre exacto que has definido
                    for asset in data.get("assets", []):
                        if asset["name"] == "HollowDrive.exe":
                            url_exe_descarga = asset["browser_download_url"]
                            break
                    
                    if url_exe_descarga:
                        self.after(0, lambda: self.notificar_actualizacion(data["tag_name"], url_exe_descarga))
        except Exception as e:
            logging.warning(f"No se pudo comprobar las actualizaciones: {e}")

    def notificar_actualizacion(self, nueva_version, url_descarga):
        """ Muestra un aviso estético al usuario preguntando si desea actualizar """
        msg = f"¡Hay una nueva versión disponible de HollowDrive ({nueva_version})!\n\n¿Deseas descargarla e instalarla ahora automáticamente?"
        if messagebox.askyesno("ACTUALIZACIÓN DETECTADA", msg):
            # Bloqueamos la interfaz y lanzamos la descarga en un hilo para no congelar la UI
            self.bloquear_ui(True)
            self.lbl_status.configure(text="DESCARGANDO NUEVA VERSIÓN... POR FAVOR ESPERA", text_color=AZUL_CIAN)
            threading.Thread(target=self.ejecutar_auto_update, args=(url_descarga,), daemon=True).start()

    def ejecutar_auto_update(self, url_descarga):
        """ Descarga el binario y delega el reemplazo a un script Batch externo """
        try:
            # Ruta de donde se está ejecutando el programa actual
            exe_actual = os.path.abspath(sys.argv[0])
            
            # Control de entorno de desarrollo: Si ejecutas el script .py, no queremos sobreescribirlo con un .exe
            if not exe_actual.endswith(".exe"):
                self.after(0, lambda: messagebox.showinfo("MODO DESARROLLO", f"Actualización ({GITHUB_REPO}) disponible.\nSaltando reemplazo físico porque estás ejecutando el script nativo de Python."))
                self.after(0, lambda: self.bloquear_ui(False))
                self.after(0, lambda: self.lbl_status.configure(text="ESPERANDO INICIO...", text_color=AZUL_SUAVE))
                return

            ruta_temporal_exe = exe_actual + ".tmp"
            
            # Descarga directa del flujo de datos del asset
            response = requests.get(url_descarga, stream=True)
            if response.status_code != 200:
                raise RuntimeError(f"HTTP {response.status_code}")
                
            with open(ruta_temporal_exe, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            # Escribimos el script Batch autolimpiable que ejecutará el cambiazo físico en Windows
            ruta_bat = os.path.join(os.path.dirname(exe_actual), "hollow_updater.bat")
            with open(ruta_bat, "w", encoding="ansi") as f:
                f.write('@echo off\n')
                f.write('timeout /t 1 /nobreak > nul\n')  # Espera 1 segundo a que el proceso principal de Python muera por completo
                f.write(f'del "{exe_actual}"\n')          # Elimina el binario antiguo desactualizado
                f.write(f'move "{ruta_temporal_exe}" "{exe_actual}"\n') # Renombra el temporal al nombre del ejecutable oficial
                f.write(f'start "" "{exe_actual}"\n')     # Lanza la nueva versión optimizada
                f.write('del "%~f0"\n')                   # El propio archivo .bat se autodestruye de forma limpia sin dejar rastro

            # Lanzamos el script .bat de forma totalmente invisible para el usuario
            subprocess.Popen(["cmd.exe", "/c", ruta_bat], creationflags=subprocess.CREATE_NO_WINDOW)
            
            # Forzamos el cierre inmediato de la aplicación actual para liberar el descriptor del .exe viejo
            self.after(0, self.destroy)

        except Exception as e:
            logging.error(f"Fallo crítico en el proceso de auto-actualización: {e}")
            self.after(0, lambda: messagebox.showerror("ERROR DE ACTUALIZACIÓN", f"No se pudo completar la instalación de la nueva versión:\n{e}"))
            self.after(0, lambda: self.bloquear_ui(False))
            self.after(0, lambda: self.lbl_status.configure(text="FALLO AL ACTUALIZAR", text_color="#aa3333"))

    def comenzar_instalacion(self):
        if self.en_proceso: return
        self.en_proceso = True
        self.abortar_proceso = False
        
        self.bloquear_ui(True)
        self.alternar_modo_instalacion(True)
        
        seleccion = self.combo_disk.get()
        disco_elegido = next((d for d in self.lista_discos_reales if d["display"] == seleccion), None)
        
        if not disco_elegido:
            messagebox.showerror("Error", "No se pudo identificar la unidad seleccionada.")
            self.en_proceso = False
            self.bloquear_ui(False)
            self.alternar_modo_instalacion(False)
            return

        config = {
            "disk_index": disco_elegido["device"],
            "cachy_gb": self.slider_c.get() if self.instalar_cachy.get() else 0.0,
            "hollow_gb": self.slider_h.get(),                  
            "gb_totales": self.gb_totales,                     
            "preservar_espacio": self.preservar_espacio.get(), 
            "instalar_cachy": self.instalar_cachy.get(),
            "descargar_pack_hollow": self.descargar_pack_hollow.get(),
            "descargar_pack_bato": self.descargar_pack_bato.get(), # <--- CORREGIDO: Añadimos el pack de Batocera
            "instalar_bato": self.instalar_bato.get(),
            "metodo_descarga": self.metodo_descarga.get()
        }
        
        self.hilo_instalacion = threading.Thread(target=self.proceso_instalacion_background, args=(config,), daemon=True)
        self.hilo_instalacion.start()

    def animar_breakdance(self, index=0):
        if not hasattr(self, 'gif_break_id'): return
        if not self.lbl_gif_breakdance.winfo_ismapped() or not self.frames_breakdance: return
        img = self.frames_breakdance[index % len(self.frames_breakdance)]
        self.lbl_gif_breakdance.configure(image=img)
        self.lbl_gif_breakdance.image = img
        self.gif_break_id = self.after(80, self.animar_breakdance, index + 1)
        
    def alternar_gif_descarga(self, activo=True):
        if activo:
            # Sincroniza el motor de animación sobre el widget estable de la linterna
            self.after(0, lambda: self.cambiar_gif(self.frames_breakdance))
        else:
            # Devuelve el estado original al terminar la descarga
            self.after(0, lambda: self.cambiar_gif(self.frames_linterna))

    def mostrar_popup_exito(self, t_total, tiempos):
        v = self.creventana_info_base("¡INSTALACIÓN COMPLETADA!", 500, 480)
        f_in = ctk.CTkFrame(v, fg_color="transparent")
        f_in.pack(expand=True, fill="both", padx=20, pady=20)
        
        mins_t, secs_t = divmod(int(t_total), 60)
        horas_t, mins_t = divmod(mins_t, 60)
        
        tiempo_str = f"{horas_t:02d}:{mins_t:02d}:{secs_t:02d}" if horas_t > 0 else f"{mins_t:02d}:{secs_t:02d}"
        
        ctk.CTkLabel(f_in, text="🎉 ¡LISTO!", font=("Impact", 38), text_color=VERDE_EXITO).pack(pady=(0, 5))
        ctk.CTkLabel(f_in, text=f"El proceso total ha durado: {tiempo_str}", font=("Segoe UI", 18, "bold"), text_color=AZUL_CIAN).pack(pady=(0, 15))
        
        f_grid = ctk.CTkScrollableFrame(f_in, fg_color="#0d141c", height=200, corner_radius=10, border_width=1, border_color="#222")
        f_grid.pack(fill="x", pady=5)
        
        for nombre, dur in tiempos.items():
            m, s = divmod(int(dur), 60)
            row = ctk.CTkFrame(f_grid, fg_color="transparent")
            row.pack(fill="x", pady=4, padx=10)
            ctk.CTkLabel(row, text=nombre, font=("Segoe UI", 13)).pack(side="left")
            ctk.CTkLabel(row, text=f"{m:02d}m {s:02d}s", font=("Consolas", 13, "bold"), text_color="#aaaaaa").pack(side="right")
            
        ctk.CTkButton(f_in, text="FINALIZAR", font=("Segoe UI", 14, "bold"), fg_color=AZUL_ELECTRICO, height=40, width=200, command=v.destroy).pack(pady=(20, 0))
        v.update()
        v.grab_set()

    # =====================================================================
    # 💥 PIPELINE EXCLUSIVO DE INSTALACIÓN
    # =====================================================================

    def proceso_instalacion_background(self, config):
        self.after(0, lambda: self.cambiar_gif(self.frames_linterna))
        
        t_inicio_global = time.time()
        registro_tiempos = {}
        step_starts = {}
        letra_grub = None
        letra_cachy = None

        def iniciar_cronometro(nombre):
            step_starts[nombre] = time.time()

        def detener_cronometro(nombre):
            if nombre in step_starts:
                d = time.time() - step_starts[nombre]
                registro_tiempos[nombre] = d
                mins, secs = divmod(int(d), 60)
                logging.info(f"[CRONÓMETRO] {nombre} completado en {mins:02d}m {secs:02d}s")

        def limpiar_temporales():
            temp_dir = os.path.join(BASE_DIR, "engine", "temp_downloads")
            if os.path.exists(temp_dir):
                logging.info("Purgando carpeta de descargas temporales...")
                shutil.rmtree(temp_dir, ignore_errors=True)

        try:
            disk_index = config["disk_index"]
            cachy_gb = config["cachy_gb"]
            hollow_gb = config["hollow_gb"]               
            gb_totales = config["gb_totales"]             
            preservar_espacio = config["preservar_espacio"] 
            instalar_cachy = config["instalar_cachy"]
            descargar_pack_hollow = config["descargar_pack_hollow"]
            descargar_pack_bato = config["descargar_pack_bato"] # <--- CORREGIDO: Extraemos la variable
            instalar_bato = config["instalar_bato"]
            metodo_ext = config["metodo_descarga"]
            
            if mantener_espacio := preservar_espacio: espacio_reservado_gb = gb_totales - hollow_gb
            else:
                espacio_reservado_gb = 0.0
                if instalar_cachy: espacio_reservado_gb = cachy_gb + GB_GRUB
            
            # --- CORRECCIÓN DE RUTA: ESCANEO GENERAL DE ENGINE ---
            tools_base = os.path.join(BASE_DIR, "engine")
            ventoy_dir = None
            
            if os.path.exists(tools_base):
                for root, dirs, files in os.walk(tools_base):
                    if "Ventoy2Disk.exe" in files:
                        ventoy_dir = root
                        break
            
            if not ventoy_dir: 
                raise RuntimeError(f"No se encontró Ventoy2Disk.exe en ninguna subcarpeta de: {tools_base}")

            def esperar_unidad_por_etiqueta(etiqueta, intentos=6, retardo=2):
                for i in range(intentos):
                    if self.abortar_proceso: raise InterruptedError("Proceso abortado por el usuario.")
                    self.after(0, lambda: self.lbl_status.configure(text=f"Esperando montaje de '{etiqueta}' (Intento {i+1}/{intentos})...", text_color=AZUL_SUAVE))
                    letra = encontrar_letra_por_etiqueta_ps(etiqueta)
                    if letra: return letra
                    time.sleep(retardo)
                return None

            pasos_activos = ["ventoy"]
            if descargar_pack_bato: pasos_activos.append("pack_bato")     
            if descargar_pack_hollow: 
                pasos_activos.append("pack_hollow") 
            else:
                pasos_activos.append("ventoy_base") # <--- NUEVO: Si no descarga el pack, extrae la base local
                
            if instalar_bato: pasos_activos.append("batocera_img")
            if instalar_cachy:
                pasos_activos.extend(["grub_part", "grub_extract", "cachy_part", "cachy_extract"])
                
            total_pasos = len(pasos_activos)
            paso_actual = 1

            def actualizar_progreso_paso(prog_interno, texto_paso):
                now = time.time()
                if not hasattr(actualizar_progreso_paso, "last_update"):
                    actualizar_progreso_paso.last_update = 0.0
                if now - actualizar_progreso_paso.last_update < 0.1 and prog_interno < 1.0 and prog_interno > 0.0:
                    return
                actualizar_progreso_paso.last_update = now

                prog_global = (paso_actual - 1 + prog_interno) / total_pasos
                self.after(0, lambda: self.p_task.set(prog_interno))
                self.after(0, lambda: self.p_total.set(prog_global))
                self.after(0, lambda: self.lbl_status.configure(text=f"Paso {paso_actual}/{total_pasos}: {texto_paso}"))

            def generar_mensaje_progreso(nombre_tarea, bytes_read, total_bytes, start_time, fase_str, override_start_time=None):
                t_ref = override_start_time if override_start_time else start_time
                elapsed = time.time() - t_ref
                if elapsed > 0 and bytes_read > 0:
                    speed_bps = bytes_read / elapsed
                    speed_mbs = speed_bps / (1024 * 1024)
                    if total_bytes:
                        eta_secs = max(0, (total_bytes - bytes_read) / speed_bps) if speed_bps > 0 else 0
                        mins, secs = divmod(int(eta_secs), 60)
                        pct = bytes_read / total_bytes
                        return pct, f"{nombre_tarea} [{fase_str}] | {pct*100:.1f}% | {speed_mbs:.1f} MB/s | Faltan: {mins:02d}:{secs:02d}"
                    else:
                        return 0.5, f"{nombre_tarea} [{fase_str}] | {speed_mbs:.1f} MB/s"
                return 0.0 if total_bytes else 0.5, f"{nombre_tarea} | Calculando..."


           # -----------------------------------------------------------------
            # [PASO] VENTOY CORE
            # -----------------------------------------------------------------
            iniciar_cronometro("Estructura Core (Ventoy)")
            actualizar_progreso_paso(0.0, "Ejecutando particionamiento base con Ventoy...")
            def progreso_ventoy(porcentaje, mensaje):
                if self.abortar_proceso: raise InterruptedError()
                actualizar_progreso_paso(porcentaje / 100.0, f"Ventoy: {mensaje}")

            instalar_ventoy(disk_index=disk_index, reserved_space_gb=espacio_reservado_gb, ventoy_dir=ventoy_dir, progress_callback=progreso_ventoy)
            detener_cronometro("Estructura Core (Ventoy)")
            paso_actual += 1

            # =====================================================================
            # 🛡️ ESTABILIZACIÓN FÍSICA DE UNIDADES (Movido aquí para liberar el USB)
            # =====================================================================
            self.after(0, lambda: self.lbl_status.configure(text="Asentando almacenamiento y liberando descriptores...", text_color=AZUL_CIAN))
            time.sleep(6)  # Permite al kernel asentar la nueva tabla de particiones
            
            try:
                ruta_rescan = os.path.join(BASE_DIR, "engine", "rescan.txt")
                with open(ruta_rescan, "w") as f:
                    f.write("rescan\n")
                
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = subprocess.SW_HIDE
                subprocess.run(["diskpart", "/s", ruta_rescan], startupinfo=si, creationflags=subprocess.CREATE_NO_WINDOW)
                
                if os.path.exists(ruta_rescan):
                    os.remove(ruta_rescan)
            except Exception as e:
                logging.warning(f"No se pudo forzar el rescan de topología: {e}")

            time.sleep(2) # Respiro final para asegurar el montaje limpio de las letras

            # -----------------------------------------------------------------
            # 🏷️ BÚSQUEDA DE LETRA DEFINITIVA Y RE-ETIQUETADO
            # -----------------------------------------------------------------
            letra_hollow = None
            intentos_totales = 12
            retardo = 2

            for i in range(intentos_totales):
                if self.abortar_proceso: raise InterruptedError("Proceso abortado por el usuario.")
                
                # Escaneamos bajo cualquier firma válida tras el rescan
                letra = encontrar_letra_por_etiqueta_ps("Ventoy") or encontrar_letra_por_etiqueta_ps("HOLLOWDRIVE")
                if letra:
                    # Si todavía conserva el nombre de Ventoy, el acceso exclusivo ya está libre para cambiarlo
                    es_ventoy = encontrar_letra_por_etiqueta_ps("Ventoy") is not None
                    if es_ventoy:
                        logging.info(f"[INFO] Detectada firma core en {letra[:2]}. Forzando cambio de etiqueta a HOLLOWDRIVE...")
                        subprocess.run(f"label {letra[:2]} HOLLOWDRIVE", shell=True)
                        time.sleep(1.5) # Tiempo de refresco del explorador de Windows
                        letra_hollow = encontrar_letra_por_etiqueta_ps("HOLLOWDRIVE") or letra
                    else:
                        letra_hollow = letra
                    break
                    
                time.sleep(retardo)
            
            # Contingencia extrema por desasentamiento del subsistema de volúmenes
            if not letra_hollow:
                for letra_alt in [f"{chr(x)}:\\" for x in range(69, 91)]:
                    if os.path.exists(letra_alt):
                        letra_hollow = letra_alt
                        break

            if not letra_hollow: 
                raise RuntimeError("No se detectó la letra de unidad física para HOLLOWDRIVE.")
                
            logging.info(f"[ENTORNO] Unidad vinculada firmemente en: {letra_hollow}")

            # -----------------------------------------------------------------
            # [PASO] PACK ROMS BATOCERA
            # -----------------------------------------------------------------
            if "pack_bato" in pasos_activos:
                iniciar_cronometro("Pack Roms Batocera")
                if self.abortar_proceso: raise InterruptedError()
                self.after(0, lambda: self.alternar_gif_descarga(True))
                actualizar_progreso_paso(0.0, "Iniciando descarga de Pack Batocera...")
                
                # CORREGIDO: Ahora apunta a su propia clave "batocera_games"
                try: url_pack_bato = MIRRORS_DATA["batocera_games"]["mirrors"][0]["url"]
                except KeyError: url_pack_bato = "https://huggingface.co/datasets/HollowDrive/HollowDrive/resolve/main/batocera-hollowpack.tar"
                
                t_start_bato_pack = time.time()
                def progreso_batocera_pack(bytes_read, total_bytes, fase, override_start=None):
                    pct, msg = generar_mensaje_progreso("Pack Batocera", bytes_read, total_bytes, t_start_bato_pack, fase, override_start)
                    actualizar_progreso_paso(pct, msg)

                stream_extract_tar(url_pack_bato, letra_hollow, is_gdrive=False, progress_callback=progocera_pack if 'progocera_pack' in globals() else progreso_batocera_pack, abort_check=lambda: self.abortar_proceso, method=metodo_ext)
                
                self.after(0, lambda: self.alternar_gif_descarga(False))
                detener_cronometro("Pack Roms Batocera")
                paso_actual += 1

           # -----------------------------------------------------------------
            # [PASO] PACK UTILS HOLLOWDRIVE
            # -----------------------------------------------------------------
            if "pack_hollow" in pasos_activos:
                iniciar_cronometro("Pack Utils HollowDrive")
                if self.abortar_proceso: raise InterruptedError()
                self.after(0, lambda: self.alternar_gif_descarga(True))
                actualizar_progreso_paso(0.0, "Iniciando descarga de Pack HollowDrive...")
                
                # CORREGIDO: Apunta a su clave independiente que ahora solo tiene su archivo
                try: url_pack_hollow = MIRRORS_DATA["hollowdrive_pack"]["mirrors"][0]["url"]
                except KeyError: url_pack_hollow = "https://pub-b872cd561e404a9599c943c6705afe9e.r2.dev/HollowdrivePackV1.tar"
                
                t_start_hollow = time.time()
                def progreso_hollow_pack(bytes_read, total_bytes, fase, override_start=None):
                    pct, msg = generar_mensaje_progreso("Pack HollowDrive", bytes_read, total_bytes, t_start_hollow, fase, override_start)
                    actualizar_progreso_paso(pct, msg)

                stream_extract_tar(url_pack_hollow, letra_hollow, is_gdrive=False, progress_callback=progreso_hollow_pack, abort_check=lambda: self.abortar_proceso, method=metodo_ext)
                
                self.after(0, lambda: self.alternar_gif_descarga(False))
                detener_cronometro("Pack Utils HollowDrive")
                paso_actual += 1

            # -----------------------------------------------------------------
            # [PASO NUEVO] EXTRACTOR DE CONFIGURACIÓN BASE LOCAL VENTOY
            # -----------------------------------------------------------------
            if "ventoy_base" in pasos_activos:
                iniciar_cronometro("Configuración Base Ventoy")
                if self.abortar_proceso: raise InterruptedError()
                
                # Forzamos a Nuitka a buscar el .tar en la ruta interna de recursos integrados
                ruta_tar_local = resource_path(os.path.join("engine", "resources", "ventoy.tar"))
                actualizar_progreso_paso(0.0, "Buscando configuración base de Ventoy local...")
                
                if not os.path.exists(ruta_tar_local):
                    logging.warning(f"[ALERTA] No se encontró el archivo base en {ruta_tar_local}. Saltando paso...")
                else:
                    t_start_local = time.time()
                    actualizar_progreso_paso(0.1, "Descomprimiendo estructura base local en USB...")
                    
                    try:
                        with tarfile.open(ruta_tar_local, "r") as tar:
                            miembros = tar.getmembers()
                            total_miembros = len(miembros)
                            
                            for idx, member in enumerate(miembros):
                                if self.abortar_proceso: raise InterruptedError()
                                
                                # Extrae elemento por elemento manteniendo la topología
                                tar.extract(member, path=letra_hollow)
                                
                                # Refrescamos el string por cada elemento para que la UI no parezca congelada
                                pct = (idx + 1) / total_miembros
                                actualizar_progreso_paso(pct, f"Inyectando base local: {member.name[:30]} ({idx+1}/{total_miembros})")
                                
                        logging.info("Estructura base de Ventoy inyectada de forma limpia desde recursos locales.")
                    except Exception as e:
                        logging.error(f"Error crítico descomprimiendo ventoy.tar: {e}")
                        raise RuntimeError(f"Fallo al desempaquetar la configuración interna de Ventoy:\n{e}")
                
                detener_cronometro("Configuración Base Ventoy")
                paso_actual += 1

            # -----------------------------------------------------------------
            # [PASO] BATOCERA
            # -----------------------------------------------------------------
            if "batocera_img" in pasos_activos:
                iniciar_cronometro("Sistema Batocera OS")
                if self.abortar_proceso: raise InterruptedError()
                self.after(0, lambda: self.alternar_gif_descarga(True))
                
                ruta_batocerumen = os.path.join(letra_hollow, "HOLLOWDRIVE", "BATOCERUMEN")
                os.makedirs(ruta_batocerumen, exist_ok=True)
                archivo_dest_bato = os.path.join(ruta_batocerumen, "batocera.img")
                is_gdrive_bato = "drive.google.com" in URL_BATOCERA or len(URL_BATOCERA) < 40
                
                t_start_bato = time.time()
                def progreso_batocera(bytes_read, total_bytes, fase, override_start=None):
                    pct, msg = generar_mensaje_progreso("Batocera.img", bytes_read, total_bytes, t_start_bato, fase, override_start)
                    actualizar_progreso_paso(pct, msg)

                stream_download_file_direct(URL_BATOCERA, archivo_dest_bato, is_gdrive=is_gdrive_bato, progress_callback=progreso_batocera, abort_check=lambda: self.abortar_proceso)
                
                self.after(0, lambda: self.alternar_gif_descarga(False))
                detener_cronometro("Sistema Batocera OS")
                paso_actual += 1


            # -----------------------------------------------------------------
            # [PASO] CACHYOS - GRUB PARTITION
            # -----------------------------------------------------------------
            if "grub_part" in pasos_activos:
                iniciar_cronometro("Creación Bootloader GRUB")
                if self.abortar_proceso: raise InterruptedError()
                actualizar_progreso_paso(0.0, "Creando partición GRUB a la derecha de HollowDrive...")
                crear_particion_adicional(disk_index=disk_index, size_gb=GB_GRUB, label="GRUB", fs="fat32")
                letra_grub = esperar_unidad_por_etiqueta("GRUB", intentos=12, retardo=2)
                if not letra_grub: raise RuntimeError("Windows tardó demasiado en asignar una letra a la partición 'GRUB'.")
                detener_cronometro("Creación Bootloader GRUB")
                paso_actual += 1

            if "grub_extract" in pasos_activos:
                iniciar_cronometro("Inyección Bootloader GRUB")
                if self.abortar_proceso: raise InterruptedError()
                self.after(0, lambda: self.alternar_gif_descarga(True))
                actualizar_progreso_paso(0.0, "Iniciando descarga y flasheo de GRUB...")
                
                # Obtiene el link de HF directamente del JSON (índice 0)
                try: 
                    url_grub_hf = MIRRORS_DATA["cachyos_images"]["efi_grub"]["mirrors"][0]["url"]
                except KeyError: 
                    url_grub_hf = "https://huggingface.co/datasets/HollowDrive/HollowDrive/resolve/main/hollowdrive_cachy_efi.img"
                
                t_start_grub = time.time()
                def progreso_grub(bytes_read, total_bytes, fase, override_start=None):
                    pct, msg = generar_mensaje_progreso("Arranque GRUB", bytes_read, total_bytes, t_start_grub, fase, override_start)
                    actualizar_progreso_paso(pct, msg)

                if not letra_grub:
                    letra_grub = encontrar_letra_por_etiqueta_ps("GRUB") or esperar_unidad_por_etiqueta("GRUB", intentos=6)
                if not letra_grub: raise RuntimeError("No se localizó la unidad GRUB para la inyección de bootloader.")

                # Volcado directo sectorial a la partición
                stream_flash_image_direct(url_grub_hf, letra_grub, progress_callback=progreso_grub, abort_check=lambda: self.abortar_proceso)
                
                self.after(0, lambda: self.alternar_gif_descarga(False))
                detener_cronometro("Inyección Bootloader GRUB")
                paso_actual += 1

            # -----------------------------------------------------------------
            # [PASO] CACHYOS - SYSTEM PARTITION
            # -----------------------------------------------------------------
            if "cachy_part" in pasos_activos:
                iniciar_cronometro("Creación Partición CachyOS")
                if self.abortar_proceso: raise InterruptedError()
                actualizar_progreso_paso(0.0, "Generando partición CachyOS (Ntfs to Btrfs)...")
                
                # FIX: Margen de seguridad para discos masivos (1TB+)
                margen_seguridad = 0.15 if not preservar_espacio else 0.0
                tamano_seguro_cachy = max(1.0, cachy_gb - margen_seguridad)
                
                crear_particion_adicional(disk_index=disk_index, size_gb=tamano_seguro_cachy, label="CachyOS", fs="ntfs")
                letra_cachy = esperar_unidad_por_etiqueta("CachyOS", intentos=12, retardo=2)
                if not letra_cachy: raise RuntimeError("Windows tardó demasiado en asignar una letra a la partición 'CachyOS'.")
                detener_cronometro("Creación Partición CachyOS")
                paso_actual += 1

            if "cachy_extract" in pasos_activos:
                iniciar_cronometro("Volcado Sistema CachyOS")
                if self.abortar_proceso: raise InterruptedError()
                self.after(0, lambda: self.alternar_gif_descarga(True))
                actualizar_progreso_paso(0.0, "Iniciando volcado sectorial de CachyOS...")
                
                # Obtiene el link de HF directamente del JSON (índice 0)
                try: 
                    url_cachy_hf = MIRRORS_DATA["cachyos_images"]["sistema"]["mirrors"][0]["url"]
                except KeyError: 
                    url_cachy_hf = "https://huggingface.co/datasets/HollowDrive/HollowDrive/resolve/main/hollowdrive_cachy_sistema.img"
                
                t_start_cachy = time.time()
                def progreso_cachy(bytes_read, total_bytes, fase, override_start=None):
                    pct, msg = generar_mensaje_progreso("CachyOS (Btrfs)", bytes_read, total_bytes, t_start_cachy, fase, override_start)
                    actualizar_progreso_paso(pct, msg)

                if not letra_cachy:
                    letra_cachy = encontrar_letra_por_etiqueta_ps("CachyOS") or esperar_unidad_por_etiqueta("CachyOS", intentos=6)
                if not letra_cachy: raise RuntimeError("No se localizó la unidad CachyOS para volcar la imagen base.")

                # Volcado directo sectorial a la partición
                stream_flash_image_direct(url_cachy_hf, letra_cachy, progress_callback=progreso_cachy, abort_check=lambda: self.abortar_proceso)
                
                self.after(0, lambda: self.alternar_gif_descarga(False))
                detener_cronometro("Volcado Sistema CachyOS")

            self.after(0, lambda: self.p_total.set(1.0))
            self.after(0, lambda: self.p_task.set(1.0))
            
            tiempo_total = time.time() - t_inicio_global
            logging.info(f"Instalación finalizada con éxito. Tiempo total: {tiempo_total} segundos.")
            
            limpiar_temporales()
            self.after(0, lambda: self.mostrar_popup_exito(tiempo_total, registro_tiempos))

        except InterruptedError:
            limpiar_temporales()
            self.after(0, lambda: messagebox.showinfo("PROCESO CANCELADO", "La instalación ha sido abortada y los archivos temporales han sido purgados del disco."))
            self.after(0, lambda: self.lbl_status.configure(text="CANCELADO", text_color="#aa3333"))
        except RuntimeError as e:
            limpiar_temporales()
            msg = str(e)
            self.after(0, lambda: messagebox.showerror("ERROR DE CONEXIÓN", msg))
            self.after(0, lambda: self.p_total.set(0.0))
            self.after(0, lambda: self.p_task.set(0.0))
            
            # 🔥 ENVIAR SOLO SI EL USUARIO DIO SU CONSENTIMIENTO
            if getattr(self, "compartir_errores", False):
                self.enviar_reporte_error("RuntimeError (Problema de Proceso/Red)", msg)

        except Exception as e:
            limpiar_temporales()
            msg = str(e)
            self.after(0, lambda: messagebox.showerror("ERROR FATAL", f"Ocurrió un fallo de sistema:\n{msg}"))
            self.after(0, lambda: self.p_total.set(0.0))
            self.after(0, lambda: self.p_task.set(0.0))
            
            # 🔥 ENVIAR SOLO SI EL USUARIO DIO SU CONSENTIMIENTO
            if getattr(self, "compartir_errores", False):
                self.enviar_reporte_error("Fatal Crash (Excepción Crítica)", msg)
        finally:
            self.en_proceso = False
            self.after(0, lambda: self.alternar_gif_descarga(False)) 
            self.after(0, lambda: self.bloquear_ui(False))
            self.after(0, lambda: self.alternar_modo_instalacion(False))
            self.after(0, lambda: self.cambiar_gif(None))

    def actualizar_barra_visual(self, h, grub, cachy):
        if not self.canvas.winfo_exists(): return
        w = self.canvas.winfo_width()
        if w <= 1: 
            self.after(100, lambda: self.actualizar_barra_visual(h, grub, cachy))
            return
            
        self.canvas.delete("all")
        total = self.gb_totales
        if total <= 0: return
        
        pix_h = int((h / total) * w)
        pix_g = int((grub / total) * w)
        pix_c = int((cachy / total) * w)
        
        x_start = 0
        x_end = pix_h
        
        if not self.instalar_cachy.get() and not self.preservar_espacio.get(): x_end = w
            
        self.canvas.create_rectangle(x_start, 0, x_end, 40, fill=COLOR_HOLLOW, outline="")
        
        if self.instalar_cachy.get():
            x_start = x_end
            x_end = x_start + pix_g
            self.canvas.create_rectangle(x_start, 0, x_end, 40, fill=COLOR_LIMINE, outline="")
            
            x_start = x_end
            if not self.preservar_espacio.get(): x_end = w  
            else: x_end = x_start + pix_c
            self.canvas.create_rectangle(x_start, 0, x_end, 40, fill=COLOR_CACHY, outline="")
            
        if x_end < w: self.canvas.create_rectangle(x_end, 0, w, 40, fill=COLOR_LIBRE, outline="")

    def actualizar_estados_bato(self):
        if self.instalar_bato.get(): self.f_bato_opts.pack(fill="x", pady=5)
        else: self.f_bato_opts.pack_forget()
        self.rebalancear()

    def actualizar_estados_cachy(self):
        if self.instalar_cachy.get(): self.f_row_c.pack(fill="x", padx=20, pady=5, before=self.canvas)
        else: self.f_row_c.pack_forget()
        self.rebalancear()

    def reproducir_gif(self, label_widget, frames, delay=80, index=0):
        if not frames or not label_widget.winfo_exists(): return
        img = frames[index % len(frames)]
        label_widget.configure(image=img)
        label_widget.image = img
        self.gif_after_id = self.after(delay, self.reproducir_gif, label_widget, frames, delay, index + 1)

    def cambiar_gif(self, frames):
        if hasattr(self, 'gif_after_id') and self.gif_after_id:
            try: self.after_cancel(self.gif_after_id)
            except: pass
            self.gif_after_id = None
        if frames: self.reproducir_gif(self.lbl_gif, frames, delay=80)
        else: self.lbl_gif.configure(image=None)

    def animar_zoom(self, attr_img, attr_size, base_size, zoom_size, entrar):
        """ Escala suavemente una imagen de CTkImage creando un efecto de físicas en hover """
        anim_key = f"{attr_img}_anim"
        prev_anim = getattr(self, anim_key, None)
        if prev_anim: self.after_cancel(prev_anim)
        
        tw, th = zoom_size if entrar else base_size
        
        def step():
            cw, ch = getattr(self, attr_size)
            if cw == tw and ch == th: return
            
            # Velocidad adaptativa de la transición
            step_w = max(1, abs(tw - cw) // 4) * (1 if tw > cw else -1)
            step_h = max(1, abs(th - ch) // 4) * (1 if th > ch else -1)
            
            nw, nh = cw + step_w, ch + step_h
            
            # Forzar encaje final exacto
            if (step_w > 0 and nw >= tw) or (step_w < 0 and nw <= tw): nw = tw
            if (step_h > 0 and nh >= th) or (step_h < 0 and nh <= th): nh = th
            
            setattr(self, attr_size, (nw, nh))
            getattr(self, attr_img).configure(size=(nw, nh))
            
            anim_id = self.after(15, step)
            setattr(self, anim_key, anim_id)
            
        step()

    def enviar_reporte_error(self, tipo_falla, mensaje_error):
        """ Envía de forma asíncrona el último log y el mensaje exacto del popup a Discord """
        url_webhook = "https://discord.com/api/webhooks/1528755076339073034/M33425jD90QwjII-hH8r7TXh3DdV0hY9qTiEsj47QPvowKxgOuuSc8pFceIqgu0zay6T"

        def hilo_envio():
            try:
                payload = {
                    "content": (
                        f"🚨 **¡PROCESO INTERRUMPIDO / CRASH DETECTADO!**\n"
                        f"💻 **Versión:** HollowDrive V{VERSION_ACTUAL}\n"
                        f"⚠️ **Tipo:** `{tipo_falla}`\n"
                        f"❌ **Error en Ventana:** `{mensaje_error}`"
                    )
                }
                
                # Buscamos el archivo de log dinámico de esta sesión
                if 'archivo_log' in globals() and os.path.exists(archivo_log):
                    with open(archivo_log, "rb") as f:
                        files = {"file": (os.path.basename(archivo_log), f, "text/plain")}
                        requests.post(url_webhook, data=payload, files=files, timeout=15)
                else:
                    requests.post(url_webhook, json=payload, timeout=15)
                    
                logging.info("[TELEMETRÍA] Reporte técnico enviado con éxito a Discord.")
            except Exception as e:
                print(f"Error crítico enviando el reporte a Discord: {e}")

        # Lo ejecutamos en segundo plano para no congelar la UI principal
        threading.Thread(target=hilo_envio, daemon=True).start()

if __name__ == "__main__":
    app = SavinOceanicCommand()
    app.mainloop()