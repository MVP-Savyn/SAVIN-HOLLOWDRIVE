import os
import sys
import time
import io
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
import ctypes
from urllib.parse import urlparse

# Token de Acceso Hugging Face (Requerido para evitar límites anónimos en la CDN)
HF_TOKEN = "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"
from ctypes import wintypes
from datetime import datetime
from tkinter import messagebox, filedialog
import tkinter as tk
from PIL import Image, ImageSequence, ImageTk
import customtkinter as ctk

# Importación para Drag & Drop nativo de Windows
try:
    import windnd
    HAS_WINDND = True
except ImportError:
    HAS_WINDND = False

def enganchar_drag_drop_recursivo(widget, callback):
    """ Engancha el evento drag & drop en el widget y en todos sus elementos hijos """
    if not HAS_WINDND: return
    try:
        windnd.hook_dropfiles(widget, func=callback)
        if hasattr(widget, "winfo_children"):
            for child in widget.winfo_children():
                enganchar_drag_drop_recursivo(child, callback)
    except Exception:
        pass

# Importaciones del motor local
from engine.download_manager import descargar_y_extraer_ventoy, resolver_tamano_pack

try:
    from engine.download_manager import formatted_size as formatear_tamano
except ImportError:
    from engine.download_manager import formatear_tamano
from engine.disk_logic import obtener_unidades_usb, instalar_ventoy, crear_particion_adicional, obtener_estructura_disco_ps

GITHUB_REPO = "MVP-Savyn/SAVIN-HOLLOWDRIVE"
URL_MIRRORS_GITHUB = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/engine/mirrors.json"

def es_administrador():
    """ Comprueba si la aplicación tiene privilegios de Administrador en Windows """
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False
    
def enganchar_drag_drop_global_win32(hwnd_tkinter, callback):
    """ Desbloquea UIPI y engancha windnd a la ventana raíz y a todos sus handles hijos en Win32 """
    if os.name != 'nt' or not HAS_WINDND: return
    try:
        user32 = ctypes.windll.user32
        shell32 = ctypes.windll.shell32
        GA_ROOT = 2
        
        hwnd_root = user32.GetAncestor(hwnd_tkinter, GA_ROOT) or hwnd_tkinter
        
        WM_DROPFILES = 0x0233
        WM_COPYDATA = 0x004A
        WM_COPYGLOBALDATA = 0x0049
        
        # Recopilar todos los handles de subventanas/canvases internos de Tkinter
        hwnds = [hwnd_root]
        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        
        def enum_child_proc(hwnd, lparam):
            hwnds.append(hwnd)
            return True
            
        user32.EnumChildWindows(hwnd_root, WNDENUMPROC(enum_child_proc), 0)
        
        for h in hwnds:
            user32.ChangeWindowMessageFilterEx(h, WM_DROPFILES, 1, None)
            user32.ChangeWindowMessageFilterEx(h, WM_COPYDATA, 1, None)
            user32.ChangeWindowMessageFilterEx(h, WM_COPYGLOBALDATA, 1, None)
            shell32.DragAcceptFiles(h, True)
            try:
                windnd.hook_dropfiles(h, func=callback)
            except Exception:
                pass
    except Exception as e:
        logging.warning(f"Error al configurar enganche Win32 Drag&Drop: {e}")

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)

if hasattr(sys, 'frozen') or '__compiled__' in globals():
    BASE_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- RUTA DE ARCHIVOS MULTIMEDIA ---
CARPETA_MEDIA = resource_path("media")

# 2. OBTENER VERSIÓN DEL EJECUTABLE
def obtener_version_interna():
    """ Lee dinámicamente la versión del ejecutable desde sus propiedades de Windows """
    exe_actual = os.path.abspath(sys.argv[0])
    if not exe_actual.endswith(".exe"):
        return "12.5"
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
            minor = info.dwFileVersionLS & 0xFFFF
            return f"{major}.{minor}"
    except Exception:
        pass
    return "12.5"

VERSION_ACTUAL = obtener_version_interna()

# 3. CLASES Y FUNCIONES DE SOPORTE PARA LOGS
class TeeStream:
    """ Redirige sys.stdout y sys.stderr hacia logging manteniendo la salida en pantalla """
    def __init__(self, log_level_func, original_stream):
        self.log_level_func = log_level_func
        self.original_stream = original_stream
        self._buffer = ""

    def write(self, message):
        self.original_stream.write(message)
        self.original_stream.flush()
        self._buffer += message
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line_clean = line.rstrip("\r")
            if line_clean.strip():
                self.log_level_func(line_clean)

    def flush(self):
        if self._buffer.strip():
            self.log_level_func(self._buffer.strip())
            self._buffer = ""
        self.original_stream.flush()

def rotar_logs(carpeta_logs, max_archivos=5):
    """ Borra los archivos de log más antiguos si sobrepasan el límite """
    try:
        # Obtener todos los archivos .log de la carpeta
        archivos = [
            os.path.join(carpeta_logs, f) for f in os.listdir(carpeta_logs)
            if f.endswith(".log")
        ]
        # Ordenar por fecha de modificación (de más viejo a más nuevo)
        archivos.sort(key=os.path.getmtime)
        
        # Dejar espacio para el log nuevo que se creará en esta sesión (máximo max_archivos - 1)
        limite = max_archivos - 1
        
        while len(archivos) > limite:
            f_a_borrar = archivos.pop(0)
            try:
                os.remove(f_a_borrar)
            except Exception as ex:
                # Si un archivo está bloqueado por otro proceso, se omite y continúa borrando los demás
                print(f"No se pudo borrar {os.path.basename(f_a_borrar)} (posiblemente bloqueado): {ex}")
    except Exception as e:
        print(f"Aviso: Error general al rotar logs: {e}")

# 4. CONFIGURACIÓN DEL SISTEMA DE REGISTRO
LOGS_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

# Limpiar logs viejos
rotar_logs(LOGS_DIR, max_archivos=5)

# Crear archivo de log único para esta sesión
timestamp_inicio = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
archivo_log = os.path.join(LOGS_DIR, f"hollowdrive_{timestamp_inicio}.log")

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(archivo_log, mode='w', encoding='utf-8')
    ]
)

# Redirección única de la consola
sys.stdout = TeeStream(logging.info, sys.__stdout__)
sys.stderr = TeeStream(logging.error, sys.__stderr__)

# 5. MENSAJE DE ARRANQUE
logging.info(f"=== INICIANDO HOLLOWDRIVE V{VERSION_ACTUAL} ===")
logging.info(f"Ruta base del programa: {BASE_DIR}")
logging.info(f"Archivo de registro de la sesión: {archivo_log}")

def cargar_mirrors():
    try:
        response = requests.get(URL_MIRRORS_GITHUB, timeout=4)
        if response.status_code == 200:
            datos_remotos = response.json()
            logging.info("[MIRRORS] mirrors.json actualizado dinámicamente desde GitHub.")
            return datos_remotos
    except Exception as e:
        logging.warning(f"[MIRRORS] No se pudo obtener mirrors.json de GitHub ({e}). Recurriendo a copia local.")

    try:
        ruta_json = resource_path(os.path.join("engine", "mirrors.json"))
        with open(ruta_json, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"[MIRRORS] Fallo al leer mirrors.json local: {e}")
        return {}

MIRRORS_DATA = cargar_mirrors()
GB_GRUB = 0.512

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
COLOR_LIMINE, COLOR_LIBRE = "#6c757d", "#444444"
VERDE_EXITO = "#2ecc71"

# =====================================================================
# ⚡ MOTOR DE EXTRACCIÓN, DESCARGA Y COPIA ULTRARRÁPIDA
# =====================================================================

def formatear_eta(segundos):
    """ Convierte segundos a formato hh:mm:ss o mm:ss """
    if segundos <= 0 or segundos > 86400: return "--:--"
    mins, secs = divmod(int(segundos), 60)
    hrs, mins = divmod(mins, 60)
    return f"{hrs:02d}:{mins:02d}:{secs:02d}" if hrs > 0 else f"{mins:02d}:{secs:02d}"

class ETACalculator:
    def __init__(self, total_bytes, window_size=5.0):
        """
        window_size: Segundos de historial para calcular la velocidad media.
        5.0 segundos da un ETA muy estable y profesional.
        """
        self.total_bytes = total_bytes
        self.history = [(time.time(), 0)]  # Guarda tuplas de (tiempo, bytes_descargados)
        self.window_size = window_size
        self.last_speed = 0.0

    def update(self, bytes_actuales):
        now = time.time()
        self.history.append((now, bytes_actuales))
        
        # 1. Limpiar el historial para mantener solo los últimos 'window_size' segundos
        while len(self.history) > 1 and (now - self.history[0][0]) > self.window_size:
            self.history.pop(0)

        # 2. Calcular la velocidad media exacta en esa ventana de tiempo
        dt = now - self.history[0][0]
        db = bytes_actuales - self.history[0][1]
        
        if dt > 0:
            self.last_speed = (db / (1024 * 1024)) / dt  # Resultado en MB/s
        
        # 3. Calcular el tiempo restante (ETA)
        if self.total_bytes and self.last_speed > 0:
            bytes_restantes = max(0, self.total_bytes - bytes_actuales)
            eta_sec = (bytes_restantes / (1024 * 1024)) / self.last_speed
        else:
            eta_sec = 0

        return self.last_speed, eta_sec

class AsyncBufferStream(object):
    def __init__(self, response, progress_callback=None, total_size=None, abort_check=None):
        # Búfer acotado a 32 bloques de 4MB (128 MB máximo de RAM)
        self.q = queue.Queue(maxsize=32) 
        self.total_size = total_size
        self.progress_callback = progress_callback
        self.abort_check = abort_check
        self.bytes_read = 0
        self.last_reported_bytes = 0 
        self.leftover = b""
        self.error = None
        self.finished = False
        
        self.t_downloader = threading.Thread(target=self._downloader, args=(response,), daemon=True)
        self.t_downloader.start()

    def _downloader(self, response):
        try:
            for chunk in response.iter_content(chunk_size=4 * 1024 * 1024): 
                if self.abort_check and self.abort_check(): break
                if chunk: self.q.put(chunk) 
        except Exception as e: self.error = e
        finally: self.q.put(None) 

    def read(self, size=-1):
        if self.abort_check and self.abort_check(): raise InterruptedError("Extracción cancelada.")

        if size == -1:
            data = self.leftover
            self.leftover = b""
            while not self.finished:
                chunk = self.q.get()
                if chunk is None:
                    self.finished = True
                    if self.error: raise self.error
                    break
                data += chunk
                self.bytes_read += len(chunk)
            return data

        while len(self.leftover) < size and not self.finished:
            if self.abort_check and self.abort_check(): raise InterruptedError("Extracción cancelada.")
            chunk = self.q.get()
            if chunk is None:
                self.finished = True
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
        if match_raw: token = match_raw.group(1)

    if token and len(token) > 2:
        res = session.get(url, params={'id': file_id, 'confirm': token}, stream=True)

    if 'text/html' in res.headers.get('Content-Type', ''):
        body_snip = res.text[:1000] if hasattr(res, 'text') else ""
        if "quotaExceeded" in body_snip or "cuota" in body_snip.lower():
            raise RuntimeError("Google Drive: Límite de cuota de descarga excedido para este archivo público.")
        raise RuntimeError("Google Drive bloqueó el acceso directo o el archivo no está disponible.")
        
    return res


# =====================================================================
# CONFIGURACIÓN DE DEBUG
# =====================================================================
MODO_DEBUG = True

def generar_stream_resiliente_v2(url, chunk_size=512*1024, abort_check=None):
    """
    Motor de Red de Flujo Continuo:
    Mantiene una sola conexión a máxima velocidad sin cierres artificiales.
    Solo reconecta si la red cae a 0 KB/s durante más de 6 segundos.
    """
    if not url or not isinstance(url, str) or not url.startswith("http"):
        raise ValueError(f"URL no válida: '{url}'")

    domain = urlparse(url).netloc
    is_hf = "huggingface.co" in domain

    headers_base = {"User-Agent": "HollowDrive-Installer/1.1", "Connection": "keep-alive"}
    if is_hf and HF_TOKEN:
        headers_base["Authorization"] = f"Bearer {HF_TOKEN}"

    # 1. Obtener tamaño total de la imagen
    try:
        head_res = requests.head(url, headers=headers_base, allow_redirects=True, timeout=8.0)
        total_size = int(head_res.headers.get('Content-Length', 0)) or None
    except Exception:
        total_size = None

    def stream_generator():
        bytes_read = 0
        retries = 0
        max_retries = 10

        while True:
            if abort_check and abort_check():
                raise InterruptedError()

            headers = headers_base.copy()
            if bytes_read > 0:
                headers["Range"] = f"bytes={bytes_read}-"
                logging.info(f"🔄 [RED] Reanudando descarga desde byte {bytes_read} ({bytes_read / (1024**2):.1f} MB)...")

            try:
                # Timeout: 6s para conectar, 8s para recibir chunks de datos sin congelarse
                with requests.get(url, headers=headers, stream=True, timeout=(6.0, 8.0)) as response:
                    if bytes_read > 0 and response.status_code != 206:
                        raise RuntimeError(f"El servidor no aceptó HTTP 206 Range (Status: {response.status_code})")
                    response.raise_for_status()
                    
                    retries = 0  # Reset de reintentos tras conexión exitosa

                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if abort_check and abort_check():
                            raise InterruptedError()

                        if chunk:
                            len_chunk = len(chunk)
                            bytes_read += len_chunk
                            yield chunk

            except (requests.RequestException, RuntimeError, TimeoutError) as e:
                retries += 1
                if retries > max_retries:
                    raise RuntimeError(f"Conexión de red fallida tras {max_retries} intentos: {e}")
                
                logging.warning(f"⚠️ [RED] Pausa de red detectada ({e}). Reintentando {retries}/{max_retries} en 2s...")
                time.sleep(2)

            # Si se alcanzó el tamaño total esperado, finalizar limpiamente
            if total_size and bytes_read >= total_size:
                return

    return stream_generator(), total_size

def stream_extract_tar(url_or_id, target_dir, is_gdrive=False, progress_callback=None, abort_check=None, method="ram"):
    total_size = None
    response_gd = None

    if is_gdrive:
        match = re.search(r'/d/([a-zA-Z0-9_-]+)', url_or_id)
        file_id = match.group(1) if match else url_or_id
        response_gd = obtener_stream_gdrive(file_id)
        if response_gd.status_code != 200:
            raise RuntimeError(f"Fallo de conexión: HTTP {response_gd.status_code}")
        total_size = int(response_gd.headers.get('Content-Length', 0)) or None
        
    os.makedirs(target_dir, exist_ok=True)
    
    if method == "disco":
        # === MODO DISCO CLÁSICO ===
        temp_dir = os.path.join(BASE_DIR, "engine", "temp_downloads")
        os.makedirs(temp_dir, exist_ok=True)
        temp_tar = os.path.join(temp_dir, "temp_pack.tar")
        
        bytes_read = 0
        
        # 1. Asignar el stream correcto según el origen
        if is_gdrive:
            stream = response_gd.iter_content(chunk_size=4 * 1024 * 1024)
        else:
            # USA EL NUEVO SISTEMA RESILIENTE
            stream, total_size = generar_stream_resiliente_v2(url_or_id, chunk_size=4 * 1024 * 1024, abort_check=abort_check)
            
        eta_calc_net = ETACalculator(total_size) if total_size else None
        
        with open(temp_tar, "wb") as f:
            for chunk in stream:
                if abort_check and abort_check(): raise InterruptedError()
                if chunk:
                    f.write(chunk)
                    bytes_read += len(chunk)
                    if progress_callback and eta_calc_net:
                        mb_s, eta_sec = eta_calc_net.update(bytes_read)
                        if mb_s is not None:
                            progress_callback(bytes_read, total_size, f"Descargando a SSD ({mb_s:.1f} MB/s | Faltan: {formatear_eta(eta_sec)})")
                    
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
        try: os.remove(temp_tar)
        except Exception: pass

    else:
        # === MODO AL VUELO CON MONITOR DE CONEXIÓN Y LOGGING FÍSICO ===
        letra_usb = os.path.splitdrive(target_dir)[0] + "\\"
        
        try:
            subprocess.run(
                ["powershell", "-Command", f"Add-MpPreference -ExclusionPath '{letra_usb}'"],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        except Exception:
            pass

        cmd_tar = ["tar.exe", "-xf", "-", "-C", target_dir]
        proc_tar = subprocess.Popen(
            cmd_tar, 
            stdin=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            bufsize=10 * 1024 * 1024, # Buffer de tubería ampliado a 10MB
            creationflags=subprocess.CREATE_NO_WINDOW
        )

        bytes_read = 0
        chunk_index = 0
        t_inicio = time.perf_counter()
        t_last_pkt = time.perf_counter()
        last_ui_update = 0.0
        UI_UPDATE_INTERVAL = 1.0

        try:
            CHUNK_SIZE = 2 * 1024 * 1024 
            
            # 2. Asignar el stream correcto según el origen
            if is_gdrive:
                stream = response_gd.iter_content(chunk_size=CHUNK_SIZE)
            else:
                # USA EL NUEVO SISTEMA RESILIENTE
                stream, total_size = generar_stream_resiliente(url_or_id, chunk_size=CHUNK_SIZE, abort_check=abort_check)
                
            eta_calc = ETACalculator(total_size) if total_size else None
            
            if MODO_DEBUG:
                logging.debug("="*60)
                logging.debug(f"[DEBUG STREAM] Iniciando extracción nativa hacia: {target_dir}")
                logging.debug(f"[DEBUG STREAM] Tamaño total esperado: {total_size / (1024**3):.2f} GB" if total_size else "[DEBUG STREAM] Tamaño total desconocido")
                logging.debug("="*60)
                
            for chunk in stream:
                if abort_check and abort_check():
                    proc_tar.kill()
                    raise InterruptedError("Extracción cancelada por el usuario.")
                
                if chunk:
                    now = time.perf_counter()
                    net_delay = now - t_last_pkt  # Tiempo que tardó la red en entregar este paquete
                    t_last_pkt = now
                    
                    chunk_len = len(chunk)
                    t_write_start = time.perf_counter()
                    
                    # Inyección a tar.exe
                    proc_tar.stdin.write(chunk)
                    proc_tar.stdin.flush()
                    t_write_duration = time.perf_counter() - t_write_start
                    
                    bytes_read += chunk_len
                    chunk_index += 1

                    # TELEMETRÍA EN REGISTRO DE LOGS
                    if MODO_DEBUG:
                        elapsed = now - t_inicio
                        instant_speed = (chunk_len / (1024 * 1024)) / t_write_duration if t_write_duration > 0 else 0
                        avg_speed = (bytes_read / (1024 * 1024)) / elapsed if elapsed > 0 else 0
                        pct = (bytes_read / total_size * 100) if total_size else 0.0
                        
                        logging.debug(
                            f"[PKT #{chunk_index:04d}] "
                            f"Bloque: {chunk_len / (1024*1024):.2f}MB | "
                            f"Espera Red: {net_delay:5.2f}s | "
                            f"I/O Pipe: {t_write_duration*1000:5.1f}ms ({instant_speed:5.1f} MB/s) | "
                            f"Media: {avg_speed:5.1f} MB/s | "
                            f"Total: {bytes_read / (1024**3):5.2f} GB ({pct:5.1f}%)"
                        )

                    # ACTUALIZACIÓN DE INTERFAZ
                    if progress_callback and (now - last_ui_update >= UI_UPDATE_INTERVAL):
                        last_ui_update = now
                        mb_s, eta_sec = eta_calc.update(bytes_read) if eta_calc else (None, None)
                        if mb_s is not None:
                            progress_callback(
                                bytes_read, 
                                total_size or bytes_read, 
                                f"Extrayendo al vuelo: {mb_s:.1f} MB/s | Faltan: {formatear_eta(eta_sec)}"
                            )

            if progress_callback and eta_calc:
                mb_s, eta_sec = eta_calc.update(bytes_read)
                progress_callback(bytes_read, total_size or bytes_read, "Vaciando búferes a la unidad USB...")

            proc_tar.stdin.close()
            proc_tar.wait()

            if proc_tar.returncode != 0:
                err = proc_tar.stderr.read().decode('utf-8', errors='ignore')
                raise RuntimeError(f"Error nativo en descompresión: {err}")

            if MODO_DEBUG:
                t_total = time.perf_counter() - t_inicio
                vel_final = (bytes_read / (1024 * 1024)) / t_total if t_total > 0 else 0
                logging.debug("="*60)
                logging.debug(f"[DEBUG STREAM] Proceso finalizado con éxito en {t_total:.2f}s (Media global: {vel_final:.2f} MB/s)")
                logging.debug("="*60)

        except Exception as e:
            proc_tar.kill()
            raise e
            
        finally:
            try:
                subprocess.run(
                    ["powershell", "-Command", f"Remove-MpPreference -ExclusionPath '{letra_usb}'"],
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            except Exception:
                pass


def stream_download_file_direct(url_or_id, dest_path, is_gdrive=False, progress_callback=None, abort_check=None):
    if is_gdrive:
        match = re.search(r'/d/([a-zA-Z0-9_-]+)', url_or_id)
        file_id = match.group(1) if match else url_or_id
        response = obtener_stream_gdrive(file_id)
        if response.status_code != 200: raise RuntimeError(f"Fallo HTTP {response.status_code}")
        total_size = int(response.headers.get('Content-Length', 0)) or None
        stream, eta_calc = response.iter_content(chunk_size=2*1024*1024), ETACalculator(total_size) if total_size else None
    else:
        # USA EL NUEVO SISTEMA RESILIENTE
        stream, total_size = generar_stream_resiliente_v2(url_or_id, chunk_size=2*1024*1024, abort_check=abort_check)
        eta_calc = ETACalculator(total_size) if total_size else None

    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    bytes_read = 0

    last_ui_update = 0.0
    with open(dest_path, "wb") as f:
        for chunk in stream:
            if abort_check and abort_check(): raise InterruptedError()
            f.write(chunk)
            f.flush() # Vacía RAM a disco inmediatamente
            bytes_read += len(chunk)
            
            now = time.time()
            # Validamos que haya pasado 1 segundo desde la última actualización
            if progress_callback and eta_calc and (now - last_ui_update >= 1.0):
                last_ui_update = now
                mb_s, eta_sec = eta_calc.update(bytes_read)
                if mb_s is not None:
                    progress_callback(bytes_read, total_size, f"Descargando: {mb_s:.1f} MB/s | Faltan: {formatear_eta(eta_sec)}")
                    
        # Forzamos una última actualización al 100% cuando termina el bucle
        if progress_callback:
            progress_callback(bytes_read, total_size, "Descarga completada, vaciando búferes...")


def stream_flash_image_direct(url, letra_unidad, progress_callback=None, abort_check=None, method="ram"):
    """
    Volcado RAW con precarga en RAM y diagnóstico calibrado.
    """
    letra_limpia = letra_unidad.strip().replace("\\", "").replace("/", "")
    ruta_raw = f"\\\\.\\{letra_limpia}"

    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    GENERIC_READ, GENERIC_WRITE = 0x80000000, 0x40000000
    FILE_SHARE_READ, FILE_SHARE_WRITE = 0x00000001, 0x00000002
    OPEN_EXISTING = 3
    FILE_FLAG_NO_BUFFERING = 0x20000000
    FSCTL_LOCK_VOLUME, FSCTL_DISMOUNT_VOLUME = 0x00090018, 0x00090020
    INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value

    time.sleep(0.3)

    if method == "ram":
        logging.info(f"=======================================================")
        logging.info(f"[DIAGNÓSTICO RAM] Iniciando Stream Directo a USB: {ruta_raw}")
        logging.info(f"=======================================================")

        if progress_callback: progress_callback(0, 100, "Conectando al servidor...")
        
        # 1. Obtener stream y tamaño con el proxy resiliente
        stream_gen, total_size = generar_stream_resiliente_v2(url, chunk_size=512*1024, abort_check=abort_check)
        
        handle = kernel32.CreateFileW(
            ruta_raw, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE,
            None, OPEN_EXISTING, FILE_FLAG_NO_BUFFERING, None
        )
        if handle == INVALID_HANDLE_VALUE or handle == 0:
            handle = kernel32.CreateFileW(ruta_raw, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None)
            if handle == INVALID_HANDLE_VALUE or handle == 0:
                raise PermissionError(f"Windows denegó el acceso físico al USB {ruta_raw}.")

        MAX_COLA = 256
        cola_bloques = queue.Queue(maxsize=MAX_COLA)
        error_red = []

        def hilo_descarga_red():
            """ Productor: Descarga por red en bloques de 512KB para mayor fluidez """
            try:
                bytes_net = 0
                t_net_start = time.time()
                
                for chunk in stream_gen:
                    bytes_net += len(chunk)
                    cola_bloques.put(chunk)
                    
                    if (bytes_net // (1024 * 1024)) % 50 == 0:
                        mb_desc = bytes_net / (1024 * 1024)
                        dt_net = time.time() - t_net_start
                        vel_net = mb_desc / dt_net if dt_net > 0 else 0
                        logging.info(f"[RED -> RAM] Descargados: {mb_desc:.0f} MB | Vel. Red: {vel_net:.1f} MB/s | Cola: {cola_bloques.qsize()}/{MAX_COLA}")
            except Exception as ex:
                error_red.append(ex)
            finally:
                cola_bloques.put(None)

        t_red = threading.Thread(target=hilo_descarga_red, daemon=True)
        t_red.start()

        # PRECARGA EN RAM: Esperar a tener al menos 32 bloques (16 MB) en memoria antes de escribir
        logging.info("[RAM -> USB] Llenando colchón inicial de precarga en RAM...")
        if progress_callback: progress_callback(0, total_size or 100, "Llenando búfer de RAM...")
        while cola_bloques.qsize() < 64 and t_red.is_alive():
            if abort_check and abort_check(): raise InterruptedError("Flasheo abortado durante precarga.")
            if error_red: raise error_red[0]
            time.sleep(0.05)

        try:
            bytes_returned = wintypes.DWORD(0)
            kernel32.DeviceIoControl(handle, FSCTL_LOCK_VOLUME, None, 0, None, 0, ctypes.byref(bytes_returned), None)
            kernel32.DeviceIoControl(handle, FSCTL_DISMOUNT_VOLUME, None, 0, None, 0, ctypes.byref(bytes_returned), None)

            bytes_escritos = 0
            eta_calc = ETACalculator(total_size) if total_size else None
            i_bloque = 0
            last_ui_update = 0.0

            while True:
                if abort_check and abort_check(): 
                    raise InterruptedError("Flasheo abortado por el usuario.")
                
                if error_red:
                    raise error_red[0]

                t_wait_queue_start = time.perf_counter()
                bloque = cola_bloques.get()
                t_wait_queue = time.perf_counter() - t_wait_queue_start

                if bloque is None: 
                    break

                if len(bloque) % 4096 != 0:
                    bloque += b'\x00' * (4096 - (len(bloque) % 4096))

                written = wintypes.DWORD(0)
                t_write_start = time.perf_counter()
                exito = kernel32.WriteFile(handle, bloque, len(bloque), ctypes.byref(written), None)
                dt_write = time.perf_counter() - t_write_start

                if not exito:
                    raise IOError(f"Error de escritura en sector físico: Win32 Code {kernel32.GetLastError()}")

                bytes_escritos += written.value
                i_bloque += 1

                pct = (bytes_escritos / total_size * 100) if total_size else 0.0
                
                # REGISTRO DE TELEMETRÍA (Aviso solo si la espera supera los 2.5 segundos reales)
                if dt_write > 0.8 or t_wait_queue > 2.5:
                    q_level = cola_bloques.qsize()
                    if dt_write > 0.8:
                        logging.warning(f"[{pct:5.1f}%] [RAM -> USB] {bytes_escritos/(1024*1024):.0f} MB | WriteFile lento: {dt_write*1000:5.0f} ms | Cola: {q_level:3d}/{MAX_COLA}")
                    elif t_wait_queue > 2.5:
                        logging.warning(f"[{pct:5.1f}%] [RAM -> USB] {bytes_escritos/(1024*1024):.0f} MB | Parón de Red: esperó {t_wait_queue:.2f}s | Cola: {q_level:3d}/{MAX_COLA}")
                elif i_bloque % 50 == 0:
                    logging.info(f"[{pct:5.1f}%] [RAM -> USB] {bytes_escritos/(1024*1024):.0f} MB | WriteFile: {dt_write*1000:5.0f} ms | Cola: {cola_bloques.qsize():3d}/{MAX_COLA}")

                # Actualización de UI a 1Hz
                now = time.time()
                if progress_callback and eta_calc and (now - last_ui_update >= 1.0):
                    last_ui_update = now
                    mb_s, eta_sec = eta_calc.update(bytes_escritos)
                    if mb_s is not None:
                        progress_callback(bytes_escritos, total_size, f"{mb_s:.1f} MB/s | Faltan: {formatear_eta(eta_sec)}")
        finally:
            kernel32.CloseHandle(handle)
            logging.info("=======================================================\n")

    else:
        # Modo Disco SSD
        logging.info(f"=======================================================")
        logging.info(f"[DIAGNÓSTICO SSD] Iniciando descarga previa a disco para: {ruta_raw}")
        logging.info(f"=======================================================")

        temp_dir = os.path.join(BASE_DIR, "engine", "temp_downloads")
        os.makedirs(temp_dir, exist_ok=True)
        temp_img = os.path.join(temp_dir, "temp_flash.img")

        stream_gen, total_size = generar_stream_resiliente_v2(url, chunk_size=2*1024*1024, abort_check=abort_check)

        # Paso 1: Descargar imagen a disco local (SSD)
        bytes_net = 0
        eta_calc_net = ETACalculator(total_size) if total_size else None
        last_ui_update = 0.0

        with open(temp_img, "wb") as f_out:
            for chunk in stream_gen:
                if abort_check and abort_check():
                    if os.path.exists(temp_img): os.remove(temp_img)
                    raise InterruptedError("Descarga a SSD abortada por el usuario.")
                if chunk:
                    f_out.write(chunk)
                    bytes_net += len(chunk)
                    
                    now = time.time()
                    if progress_callback and eta_calc_net and (now - last_ui_update >= 1.0):
                        last_ui_update = now
                        mb_s, eta_sec = eta_calc_net.update(bytes_net)
                        if mb_s is not None:
                            progress_callback(bytes_net, total_size, f"Descargando a SSD: {mb_s:.1f} MB/s | Faltan: {formatear_eta(eta_sec)}")

        # Paso 2: Volcado RAW desde SSD hacia el USB
        logging.info(f"[DIAGNÓSTICO SSD] Descarga completada. Iniciando volcado RAW a USB: {ruta_raw}")
        handle = kernel32.CreateFileW(
            ruta_raw, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE,
            None, OPEN_EXISTING, FILE_FLAG_NO_BUFFERING, None
        )
        if handle == INVALID_HANDLE_VALUE or handle == 0:
            handle = kernel32.CreateFileW(ruta_raw, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None)
            if handle == INVALID_HANDLE_VALUE or handle == 0:
                if os.path.exists(temp_img): os.remove(temp_img)
                raise PermissionError(f"Windows denegó el acceso físico al USB {ruta_raw}.")

        try:
            bytes_returned = wintypes.DWORD(0)
            kernel32.DeviceIoControl(handle, FSCTL_LOCK_VOLUME, None, 0, None, 0, ctypes.byref(bytes_returned), None)
            kernel32.DeviceIoControl(handle, FSCTL_DISMOUNT_VOLUME, None, 0, None, 0, ctypes.byref(bytes_returned), None)

            bytes_escritos = 0
            eta_calc_flash = ETACalculator(total_size) if total_size else None
            last_ui_update = 0.0

            with open(temp_img, "rb") as f_in:
                while True:
                    if abort_check and abort_check():
                        raise InterruptedError("Flasheo desde SSD abortado por el usuario.")

                    bloque = f_in.read(1 * 1024 * 1024)
                    if not bloque:
                        break

                    if len(bloque) % 4096 != 0:
                        bloque += b'\x00' * (4096 - (len(bloque) % 4096))

                    written = wintypes.DWORD(0)
                    exito = kernel32.WriteFile(handle, bloque, len(bloque), ctypes.byref(written), None)

                    if not exito:
                        raise IOError(f"Error de escritura en sector físico: Win32 Code {kernel32.GetLastError()}")

                    bytes_escritos += written.value

                    now = time.time()
                    if progress_callback and eta_calc_flash and (now - last_ui_update >= 1.0):
                        last_ui_update = now
                        mb_s, eta_sec = eta_calc_flash.update(bytes_escritos)
                        if mb_s is not None:
                            progress_callback(bytes_escritos, total_size, f"Flasheando desde SSD: {mb_s:.1f} MB/s | Faltan: {formatear_eta(eta_sec)}")
        finally:
            kernel32.CloseHandle(handle)
            if os.path.exists(temp_img):
                try: os.remove(temp_img)
                except Exception: pass
            logging.info("=======================================================\n")

def encontrar_letra_por_etiqueta_ps(label):
    try:
        cmd = f'Get-Volume | Where-Object {{$_.FileSystemLabel -eq "{label}"}} | Select-Object -ExpandProperty DriveLetter'
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        output = subprocess.check_output(["powershell", "-NoProfile", "-Command", cmd], startupinfo=si, creationflags=subprocess.CREATE_NO_WINDOW, text=True, errors="ignore")
        clean_output = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', output).strip()
        if clean_output and len(clean_output) == 1 and clean_output.isalpha():
            return f"{clean_output.upper()}:\\"
    except Exception as e: logging.error(f"Error detectando volumen '{label}': {e}")
    return None


def asignar_letra_particion_ps(disk_index, part_number):
    """ Asigna una letra de unidad libre a la partición especificada usando diskpart """
    try:
        cmd_used = "Get-Volume | Select-Object -ExpandProperty DriveLetter"
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        out = subprocess.check_output(["powershell", "-NoProfile", "-Command", cmd_used], startupinfo=si, creationflags=subprocess.CREATE_NO_WINDOW, text=True, errors="ignore")
        used = set(re.findall(r'[A-Z]', out.upper()))
        
        free_letter = None
        for char in "ZYXWVUTSRQPONMLKJIHGFED":
            if char not in used:
                free_letter = char
                break
        if not free_letter: return None
        
        script = f"select disk {disk_index}\nselect partition {part_number}\nassign letter={free_letter}\nrescan\n"
        script_path = os.path.join(BASE_DIR, "engine", "assign_temp.txt")
        with open(script_path, "w") as f: f.write(script)
        subprocess.run(["diskpart", "/s", script_path], startupinfo=si, creationflags=subprocess.CREATE_NO_WINDOW)
        if os.path.exists(script_path): os.remove(script_path)
        time.sleep(1.5)
        return f"{free_letter}:\\"
    except Exception as e:
        logging.error(f"Fallo asignando letra a disco {disk_index} part {part_number}: {e}")
        return None


def obtener_o_asignar_letras_cachyos_grub(disk_index):
    """ Garantiza que las particiones GRUB y CachyOS posean una letra de unidad válida """
    particiones = obtener_estructura_disco_ps(disk_index)
    letra_grub = None
    letra_cachy = None

    for p in particiones:
        lbl = (p.get("Label") or "").upper()
        num = p.get("Number")
        size = p.get("Size", 0.0)
        letra = p.get("Letter")

        if "GRUB" in lbl or (0.2 <= size <= 1.5 and num != 1):
            if letra: letra_grub = f"{letra}:\\"
            else:
                letra_grub = asignar_letra_particion_ps(disk_index, num)
        elif "CACHY" in lbl or (size >= 5.0 and num != 1):
            if letra: letra_cachy = f"{letra}:\\"
            else:
                letra_cachy = asignar_letra_particion_ps(disk_index, num)

    if not letra_grub:
        letra_grub = encontrar_letra_por_etiqueta_ps("GRUB") or asignar_letra_particion_ps(disk_index, 2)
    if not letra_cachy:
        letra_cachy = encontrar_letra_por_etiqueta_ps("CachyOS") or asignar_letra_particion_ps(disk_index, 3)

    return letra_grub, letra_cachy


def eliminar_particiones_cachy_diskpart(disk_index):
    try:
        script_path = os.path.join(BASE_DIR, "engine", "del_cachy.txt")
        lines = [
            f"select disk {disk_index}\n",
            "select partition 2\n",
            "delete partition override\n",
            "select partition 3\n",
            "delete partition override\n",
            "rescan\n"
        ]
        with open(script_path, "w") as f:
            f.writelines(lines)
            
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        subprocess.run(["diskpart", "/s", script_path], startupinfo=si, creationflags=subprocess.CREATE_NO_WINDOW)
        if os.path.exists(script_path): os.remove(script_path)
        return True
    except Exception as e:
        logging.error(f"Error al eliminar particiones de CachyOS: {e}")
        return False


def copiar_iso_ultrarrapido(origen, destino, callback_progreso=None, abort_check=None):
    """ Copia directa por bloques nativos de Python para un progreso 100% preciso """
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    total_size = os.path.getsize(origen)
    bytes_copiados = 0

    with open(origen, "rb") as f_src, open(destino, "wb") as f_dst:
        buffer_size = 2 * 1024 * 1024  # Buffer de 2MB
        while True:
            if abort_check and abort_check():
                f_dst.close()
                if os.path.exists(destino):
                    try: os.remove(destino)
                    except Exception: pass
                raise InterruptedError("Copia cancelada por el usuario.")
            
            chunk = f_src.read(buffer_size)
            if not chunk:
                break
            f_dst.write(chunk)
            bytes_copiados += len(chunk)
            if callback_progreso:
                callback_progreso(bytes_copiados, total_size)

# =====================================================================
# 🖥️ INTERFAZ PRINCIPAL Y CONTROLADOR
# =====================================================================
class ItemTareaProgreso:
    """ Representa una barra de progreso individual para una tarea en segundo plano """
    def __init__(self, contenedor, id_tarea, titulo, color_barra=AZUL_CIAN):
        self.id_tarea = id_tarea
        self.frame = ctk.CTkFrame(contenedor, fg_color="#090d12", corner_radius=8, border_width=1, border_color="#1e293b")
        self.frame.pack(fill="x", pady=3, padx=5, expand=True)

        self.lbl_status = ctk.CTkLabel(self.frame, text=titulo, font=("Consolas", 11, "bold"), text_color=AZUL_SUAVE)
        self.lbl_status.pack(anchor="w", padx=10, pady=(4, 2))

        self.p_bar = ctk.CTkProgressBar(self.frame, height=8, progress_color=color_barra)
        self.p_bar.set(0)
        self.p_bar.pack(fill="x", padx=10, pady=(0, 6))
        
        contenedor.update_idletasks()

    def actualizar(self, progreso, texto):
        self.p_bar.set(progreso)
        self.lbl_status.configure(text=texto)

    def destruir(self):
        self.frame.destroy()

class SavinOceanicCommand(ctk.CTk):

    def verificar_conexion_servidores(self):
        urls = ["https://huggingface.co", "https://pub-988eebcee5e94631a55af8a89d12129d.r2.dev"]
        for u in urls:
            try:
                r = requests.head(u, timeout=3)
                if r.status_code < 500: return True
            except Exception: continue
        return False

    def verificar_herramientas(self):
        engine_path = os.path.join(BASE_DIR, "engine")
        if os.path.exists(engine_path):
            for root, dirs, files in os.walk(engine_path):
                if "Ventoy2Disk.exe" in files:
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
        def update_bar(val, *args): self.after(0, lambda: self.prog_descarga.set(val))
        exito = descargar_y_extraer_ventoy(progress_callback=update_bar)
        if exito:
            time.sleep(1) 
            self.after(0, self.overlay.destroy)
            self.after(0, lambda: self.bloquear_ui(False))
        else: self.after(0, lambda: self.prog_descarga.configure(progress_color="red"))

    def abrir_info_ventoy(self):
        v = self.creventana_info_base("INFORMACIÓN DE COMPLEMENTOS", 640, 420)
        frame_interno = ctk.CTkFrame(v, fg_color="transparent")
        frame_interno.pack(expand=True, fill="both", padx=25, pady=20)
        ctk.CTkLabel(frame_interno, text="🔧 COMPLEMENTO CORE: VENTOY", font=("Impact", 28), text_color=AZUL_CIAN).pack(pady=(0, 15))
        info = ("Ventoy es una herramienta open-source esencial que gestiona el entorno multi-boot de tu HollowDrive.\n\n"
                "Permite arrancar múltiples sistemas operativos directamente desde archivos ISO sin formatear la unidad.")
        ctk.CTkLabel(frame_interno, text=info, font=("Segoe UI", 17), justify="center", wraplength=560).pack(pady=5)
        
        f_botones = ctk.CTkFrame(frame_interno, fg_color="transparent")
        f_botones.pack(pady=(20, 0))
        ctk.CTkButton(f_botones, text="VISITAR VENTOY", font=("Segoe UI", 13, "bold"), fg_color=AZUL_CARD, border_width=1, border_color=AZUL_CIAN, height=42, width=180, command=lambda: self.abrir_url("https://www.ventoy.net")).pack(side="left", padx=10)
        ctk.CTkButton(f_botones, text="ENTENDIDO", font=("Segoe UI", 13, "bold"), fg_color=AZUL_ELECTRICO, height=42, width=140, command=v.destroy).pack(side="left", padx=10)
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
            except Exception:
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

    def abrir_url(self, url): webbrowser.open_new_tab(url)

    def crear_boton_info(self, master, comando):
        return ctk.CTkButton(
            master, image=getattr(self, 'img_triangulo', None), text="" if getattr(self, 'img_triangulo', None) else "▲",
            width=30, height=30, fg_color="transparent", hover_color="#122d3d", command=comando
        )
    
    def alternar_modo_instalacion(self, en_progreso=True):
        self.en_proceso = en_progreso
        if en_progreso:
            if hasattr(self, 'btn_start') and self.btn_start.winfo_exists():
                self.btn_start.pack_forget()

            if not self.f_progress.winfo_ismapped():
                self.f_progress.pack(side="left", fill="both", expand=True, padx=(0, 10))

            # Asegurar que el instalador principal usa sus barras estáticas (NO el Scroll de HT)
            self.f_tasks_scroll.pack_forget()
            if not self.lbl_status.winfo_ismapped():
                self.lbl_status.pack(anchor="w", padx=5, pady=(2, 2))
            if not self.p_task.winfo_ismapped():
                self.p_task.pack(fill="x", padx=5, pady=2)
            if not self.p_total.winfo_ismapped():
                self.p_total.pack(fill="x", padx=5, pady=2)

            if not self.btn_cancel.winfo_ismapped():
                self.btn_cancel.pack(side="right", padx=10)
        else:
            self.f_progress.pack_forget()
            self.btn_cancel.pack_forget()
            self.f_tasks_scroll.pack_forget()

            self.lbl_status.configure(text="ESPERANDO INICIO...", text_color=AZUL_SUAVE)
            if not self.lbl_status.winfo_ismapped():
                self.lbl_status.pack(anchor="w", padx=5, pady=(2, 2))
            if not self.p_task.winfo_ismapped():
                self.p_task.pack(fill="x", padx=5, pady=2)
            if not self.p_total.winfo_ismapped():
                self.p_total.pack(fill="x", padx=5, pady=2)

            if getattr(self, 'pestana_actual', 'instalador') == 'instalador':
                if hasattr(self, 'btn_start') and self.btn_start.winfo_exists():
                    self.btn_start.pack(fill="x", padx=20, pady=(15, 10))

    def confirmar_inicio(self):
        seleccion = self.combo_disk.get()
        disco_elegido = next((d for d in self.lista_discos_reales if d["display"] == seleccion), None)
        if not disco_elegido:
            messagebox.showerror("Error", "No se identificó ninguna unidad válida.")
            return

        if "[INT]" in seleccion or self.mostrar_internos.get():
            dialog = ctk.CTkInputDialog(
                text=f"⚠️ ¡ATENCIÓN: DISCO INTERNO SELECCIONADO! ⚠️\n\n"
                     f"Estás a punto de formatear la unidad:\n'{disco_elegido['display']}'.\n\n"
                     f"Escribe 'BORRAR' en mayúsculas para continuar:",
                title="Doble Candado de Seguridad"
            )
            res = dialog.get_input()
            if res != "BORRAR":
                messagebox.showerror("ABORTADO", "Confirmación incorrecta. Cancelado por seguridad.")
                return

        if not self.verificar_conexion_servidores():
            afectados = []
            if self.instalar_bato.get(): afectados.append("Batocera OS (.img)")
            if self.descargar_pack_bato.get(): afectados.append("Pack Batocera ROMs (37.8GB)")
            if self.descargar_pack_hollow.get(): afectados.append("Pack HollowDrive (8.06GB)")
            if self.instalar_cachy.get(): afectados.append("Imágenes de CachyOS / GRUB")

            if afectados:
                msg = "⚠️ SIN CONEXIÓN A LOS SERVIDORES\n\nNo se pueden alcanzar los repositorios para los paquetes seleccionados:\n"
                msg += "\n".join([f"• {p}" for p in afectados])
                msg += "\n\n¿Deseas abortar la instalación?"
                if messagebox.askyesno("Error de Red", msg): return

        if messagebox.askyesno("CONFIRMACIÓN", "¿Proceder con la instalación real? Se borrarán todos los datos del disco seleccionado."): 
            self.abortar_proceso = False
            self.comenzar_instalacion()

    def cancelar_proceso(self):
        if messagebox.askyesno("CANCELAR", "¿Seguro que deseas cancelar el proceso?"):
            self.abortar_proceso = True
            self.cambiar_gif(None)

            if hasattr(self, 'tareas_activas') and self.tareas_activas:
                for task in list(self.tareas_activas.values()):
                    task.actualizar(task.p_bar.get(), "CANCELANDO... ESPERA POR FAVOR")
            else:
                if not self.lbl_status.winfo_ismapped():
                    self.lbl_status.pack(anchor="w", padx=5, pady=(2, 2))
                self.lbl_status.configure(text="CANCELANDO Y LIMPIANDO... ESPERA POR FAVOR", text_color="#ff4d4d")

    def mostrar_info(self, titulo, mensaje): messagebox.showinfo(titulo, mensaje)

    def __init__(self):
        super().__init__()
        self.title(f"SAVIN SUPER_USB // V{VERSION_ACTUAL}")
        
        self.update_idletasks()
        self.geometry(f"1000x870+{(self.winfo_screenwidth() // 2) - 500}+{(self.winfo_screenheight() // 2) - 435}")
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
        self.pestana_actual = "instalador"

        self.tool_bato_img = ctk.BooleanVar(value=False)
        self.tool_pack_bato = ctk.BooleanVar(value=False)
        self.tool_pack_hollow = ctk.BooleanVar(value=False)
        self.lista_discos_hollow = []

        self.tamanos_reales = {"bato_64": 4.60, "bato_32": 1.0, "pack_bato": 37.8, "pack_hollow": 8.66}
        self.tamanos_formateados = {"bato_64": "4.60GB", "bato_32": "1GB", "pack_bato": "37.8GB", "pack_hollow": "8.66GB"}

        self.configure(fg_color=AZUL_FONDO) 
        self.attributes("-alpha", 0.94)
        
        self.cargar_recursos() 
        self.setup_ui()
        
        if HAS_WINDND:
            self.after(500, lambda: enganchar_drag_drop_global_win32(self.winfo_id(), self.al_arrastrar_archivos_iso))

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
        ruta_config = os.path.join(BASE_DIR, "config.json")
        if os.path.exists(ruta_config):
            try:
                with open(ruta_config, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    self.compartir_errores = config.get("compartir_errores", False)
                    return
            except Exception: pass

        pregunta = (
            "¿Quieres compartir los errores conmigo?\n\n"
            "Si pones que sí, cuando el programa falle me enviará la información "
            "para que pueda trabajar en una solución, el programa no recopila ningún dato personal ;>"
        )
        self.compartir_errores = messagebox.askyesno("SOPORTE TÉCNICO", pregunta)
        try:
            with open(ruta_config, "w", encoding="utf-8") as f:
                json.dump({"compartir_errores": self.compartir_errores}, f, indent=4)
        except Exception: pass

    def enviar_reporte_error(self, tipo_falla, mensaje_error):
        url_webhook = "https://discord.com/api/webhooks/1528755076339073034/M33425jD90QwjII-hH8r7TXh3DdV0hY9qTiEsj47QPvowKxgOuuSc8pFceIqgu0zay6T"

        def hilo_envio():
            try:
                payload = {
                    "content": (
                        f"🚨 **¡ERROR FATAL DETECTADO EN CLIENTE!**\n"
                        f"💻 **Versión:** HollowDrive V{VERSION_ACTUAL}\n"
                        f"⚠️ **Tipo:** `{tipo_falla}`\n"
                        f"❌ **Detalle:** `{mensaje_error}`"
                    )
                }
                # Buscar el archivo de log más reciente en la carpeta /logs
                log_file_path = archivo_log if ('archivo_log' in globals() and os.path.exists(archivo_log)) else "savin_debug.log"
                
                if os.path.exists(log_file_path):
                    with open(log_file_path, "rb") as f:
                        files = {"file": (os.path.basename(log_file_path), f, "text/plain")}
                        requests.post(url_webhook, data=payload, files=files, timeout=15)
                else:
                    requests.post(url_webhook, json=payload, timeout=15)
            except Exception as e:
                logging.error(f"No se pudo enviar el reporte a Discord: {e}")

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
            self.bato_size = (125, 88)
        except: self.logo_batocera = None
        
        try: 
            img_cachy = Image.open(os.path.join(path_media, "cachy.png"))
            self.logo_cachy = ctk.CTkImage(light_image=img_cachy, dark_image=img_cachy, size=(280, 78))
            self.cachy_size = (280, 78)
        except: self.logo_cachy = None
        try: img_savin = Image.open(os.path.join(path_media, "Savin-2.png")); self.logo_savin = ctk.CTkImage(light_image=img_savin, dark_image=img_savin, size=(240, 135))
        except: self.logo_savin = None
        try: img_maker = Image.open(os.path.join(path_media, "HollowDrive-2.png")); self.logo_maker = ctk.CTkImage(light_image=img_maker, dark_image=img_maker, size=(520, 310))
        except: self.logo_maker = None
        try: 
            pil_instalar = Image.open(os.path.join(path_media, "instalar.png"))
            self.img_instalar = ctk.CTkImage(light_image=pil_instalar, dark_image=pil_instalar, size=(380, 75))
        except: self.img_instalar = None
        try: pil_image = Image.open(os.path.join(path_media, "descarga-morada.png")); self.img_descarga_data = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=(350, 350))
        except: self.img_descarga_data = None
        try: pil_reload = Image.open(os.path.join(path_media, "reload.png")); self.img_reload = ctk.CTkImage(light_image=pil_reload, dark_image=pil_reload, size=(25, 25))
        except: self.img_reload = None
        try: 
            img_isos_pil = Image.open(os.path.join(path_media, "ISOs.png"))
            self.img_isos = ctk.CTkImage(light_image=img_isos_pil, dark_image=img_isos_pil, size=(150, 150))
            self.isos_size = (150, 150)
        except Exception:
            self.img_isos = None

        self.frames_linterna = self.cargar_gif_pil(os.path.join(CARPETA_MEDIA, "hollow-linterna.gif"), size=(70, 70), espejo=True)
        self.frames_breakdance = self.cargar_gif_pil(os.path.join(CARPETA_MEDIA, "breakdance.gif"), size=None)
        
        # [NUEVO] FIX: Imagen fantasma transparente para borrar el GIF al cancelar
        self.dummy_img = ctk.CTkImage(Image.new("RGBA", (1, 1), (0, 0, 0, 0)), size=(1, 1))
        

    def al_clicar_pack_batocera(self):
        if self.descargar_pack_bato.get(): self.abrir_info_roms()
        self.rebalancear()

    def abrir_info_motor(self):
        v = self.creventana_info_base("MOTORES DE EXTRACCIÓN", 740, 600)
        frame_interno = ctk.CTkFrame(v, fg_color="transparent")
        frame_interno.pack(expand=True, fill="both", padx=25, pady=20)
        ctk.CTkLabel(frame_interno, text="⚙️ MOTORES DE INSTALACIÓN", font=("Impact", 30), text_color=AZUL_CIAN).pack(pady=(0, 10))
        
        info = ("HollowDrive te permite elegir cómo el sistema gestiona la red y los archivos pesados:\n\n"
                "⚡ ASÍNCRONO (RAM - Recomendado): Descarga a máxima velocidad volcando los datos a un colchón temporal en tu memoria RAM. Extrae directamente al USB sin saturar el disco duro.\n\n"
                "🛡️ CLÁSICO (Disco Local): Si el primer modo falla por algo, este método descargará el archivo a una carpeta oculta en tu disco SSD/HDD (temp_downloads), y después lo extraerá al USB.")
        ctk.CTkLabel(frame_interno, text=info, font=("Segoe UI", 16), justify="left", wraplength=660).pack(pady=5)
        
        consejo = ("CONSEJO:\n"
                   "• Usa \"Asíncrono\" si no te da fallos, simplemente es más rápido.\n"
                   "• Usa \"Clásico\" si buscas máxima estabilidad ante cortes de red (requiere espacio libre en SSD).")
        ctk.CTkLabel(frame_interno, text=consejo, font=("Segoe UI", 16, "bold"), text_color=AZUL_CIAN, justify="left", wraplength=660).pack(pady=10)

        ctk.CTkButton(frame_interno, text="ENTENDIDO", font=("Segoe UI", 14, "bold"), fg_color=AZUL_ELECTRICO, height=42, width=180, command=v.destroy).pack(pady=(15, 0))
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
        v = self.creventana_info_base("AVISO LEGAL", 620, 420)
        v.configure(fg_color="#1a0a0a") 
        frame_interno = ctk.CTkFrame(v, fg_color="transparent")
        frame_interno.pack(expand=True, fill="both", padx=25, pady=20)
        ctk.CTkLabel(frame_interno, text="⚠️ AVISO LEGAL", font=("Impact", 32), text_color="#ff4d4d").pack(pady=(0, 15))
        legal_text = ("Savin Super USB NO INCLUYE ROMS ni archivos de juegos\nprotegidos por derechos de autor.")
        ctk.CTkLabel(frame_interno, text=legal_text, font=("Segoe UI", 16), justify="center", wraplength=550).pack(pady=10)
        ctk.CTkButton(frame_interno, text="ACEPTO LOS RIESGOS", font=("Segoe UI", 14, "bold"), fg_color="#444", height=40, width=220, command=v.destroy).pack(pady=(15, 0))
        v.update(); v.grab_set()

    def abrir_info_pack_hollow(self):
        v = self.creventana_info_base("PACK HOLLOWDRIVE INFO", 620, 400)
        frame_interno = ctk.CTkFrame(v, fg_color="transparent")
        frame_interno.pack(expand=True, fill="both", padx=25, pady=20)
        ctk.CTkLabel(frame_interno, text="🛠️ PACK DE HERRAMIENTAS HOLLOWDRIVE", font=("Impact", 24), text_color=AZUL_CIAN).pack(pady=(0, 15))
        info = ("Este paquete inyecta una selección de entornos y utilidades de rescate "
                "booteables listas para usar desde el menú principal:\n\n"
                "• Herramientas avanzadas de particionado y gestión de discos.\n"
                "• Utilidades de clonación, backup y recuperación de datos.\n"
                "• Entornos Windows Live (WinPE) para reparar sistemas caídos.\n\n"
                "Y mucho más...")
        ctk.CTkLabel(frame_interno, text=info, font=("Segoe UI", 16), justify="left", wraplength=550).pack(pady=5)
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
        # ELIMINA O COMENTA ESTA LÍNEA PARA QUE NO SOBRESCRIBA EL TEXTO:
        # self.ch_b32.configure(text=f"Batocera 32bits ({self.tamanos_formateados['bato_32']})")
        self.ch_pack_bato.configure(text=f"PACK BATOCERA ({self.tamanos_formateados['pack_bato']})")
        self.ch_pack_hollow.configure(text=f"PACK HOLLOWDRIVE ({self.tamanos_formateados['pack_hollow']})")
        self.rebalancear()

# =====================================================================
    # 🎛️ CONSTRUCCIÓN Y NAVEGACIÓN DE LA INTERFAZ
    # =====================================================================

    def setup_ui(self):
        ruta_i = os.path.join(CARPETA_MEDIA, "I.png")
        if os.path.exists(ruta_i):
            img_i_pil = Image.open(ruta_i)
            self.img_info = ctk.CTkImage(light_image=img_i_pil, dark_image=img_i_pil, size=(100, 100))
            self.img_info_descarga = ctk.CTkImage(light_image=img_i_pil, dark_image=img_i_pil, size=(120, 120))
        
        try: img_t_pil = Image.open(os.path.join(CARPETA_MEDIA, "triangulo.png")); self.img_triangulo = ctk.CTkImage(light_image=img_t_pil, dark_image=img_t_pil, size=(30, 30))
        except: self.img_triangulo = None

        # --- CABECERA ---
        self.header = ctk.CTkFrame(self, fg_color="transparent", height=110)
        self.header.pack(fill="x", padx=20, pady=0)
        if getattr(self, 'logo_savin', None): ctk.CTkLabel(self.header, image=self.logo_savin, text="").place(x=0, y=-10)
        if getattr(self, 'logo_maker', None): ctk.CTkLabel(self.header, image=self.logo_maker, text="").place(relx=0.5, y=-85, anchor="n")
        self.btn_info_main = ctk.CTkButton(self, image=getattr(self, 'img_info', None), text="" if getattr(self, 'img_info', None) else "I", width=90, height=90, fg_color="transparent", hover_color=AZUL_CARD, command=self.abrir_ventana_info)
        self.btn_info_main.place(x=890, y=10)

        # --- BARRA DE NAVEGACIÓN POR PESTAÑAS ---
        self.nav_bar = ctk.CTkFrame(self, fg_color=AZUL_CARD, height=45, corner_radius=10, border_width=1, border_color="#222")
        self.nav_bar.pack(fill="x", padx=20, pady=(0, 5))
        
        self.btn_modo_installer = ctk.CTkButton(self.nav_bar, text="🚀 INSTALADOR PRINCIPAL", font=("Segoe UI", 12, "bold"), fg_color=AZUL_ELECTRICO, width=220, command=lambda: self.cambiar_pestana("instalador"))
        self.btn_modo_installer.pack(side="left", padx=10, pady=5)
        
        self.btn_modo_tools = ctk.CTkButton(self.nav_bar, text="🛠️ HOLLOWTOOLS (MANTENIMIENTO)", font=("Segoe UI", 12, "bold"), fg_color="transparent", border_width=1, border_color=AZUL_CIAN, text_color=AZUL_CIAN, width=260, command=lambda: self.cambiar_pestana("tools"))
        self.btn_modo_tools.pack(side="left", padx=5, pady=5)

        # --- SELECTOR DE DISCOS (PERTENECE EXCLUSIVAMENTE AL INSTALADOR) ---
        self.f_selection = ctk.CTkFrame(self, fg_color=AZUL_CARD, border_width=1, border_color=AZUL_ELECTRICO)
        self.f_selection.pack(fill="x", padx=20, pady=(0, 5)) 
        ctk.CTkLabel(self.f_selection, text="Selecciona un dispositivo para instalar HOLLOWDRIVE.", font=("Segoe UI", 14, "italic"), text_color=AZUL_SUAVE).pack(pady=(6,0))
        
        f_combo = ctk.CTkFrame(self.f_selection, fg_color="transparent")
        f_combo.pack(pady=10)
        self.combo_disk = ctk.CTkComboBox(f_combo, values=["Buscando unidades..."], width=450, command=self.activar_interfaz_completa)
        self.combo_disk.set("Buscando unidades...")
        self.combo_disk.pack(side="left", padx=10)
        self.widgets_interactivos.append(self.combo_disk)

        self.btn_refresh = ctk.CTkButton(f_combo, image=getattr(self, 'img_reload', None), text="" if getattr(self, 'img_reload', None) else "🔄", width=40, height=40, fg_color="#222", command=self.refrescar_discos)
        self.btn_refresh.pack(side="left", padx=5)

        self.sw_internos = ctk.CTkCheckBox(f_combo, text="Mostrar discos internos", variable=self.mostrar_internos, command=self.toggle_discos_internos, text_color="#aa3333", font=("Segoe UI", 11, "bold"))
        self.sw_internos.pack(side="left", padx=10)

        # --- CONTENEDOR INSTALADOR MAESTRO ---
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        
        # PANEL IZQUIERDO
        self.p_left = ctk.CTkFrame(self.main_container, fg_color=AZUL_CARD, corner_radius=15, border_width=1, border_color="#222")
        self.p_left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        # SECCIÓN BATOCERA
        f_bato_master = ctk.CTkFrame(self.p_left, fg_color="transparent")
        f_bato_master.pack(fill="x", padx=15, pady=10)
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
        # --- CÓDIGO CORREGIDO ---
        self.ch_b64 = ctk.CTkCheckBox(self.f_bato_opts, text="Batocera 64bits (4.60GB)", variable=self.bato_64_act, command=self.rebalancear)
        self.ch_b64.pack(pady=2, padx=10, anchor="w")
        self.ch_b32 = ctk.CTkCheckBox(self.f_bato_opts, text="Batocera 32bits (Próximamente)", variable=self.bato_32_act, command=self.rebalancear, state="disabled")
        self.ch_b32.pack(pady=2, padx=10, anchor="w")
        self.widgets_interactivos.append(self.ch_b64)  # Solo añadimos el de 64bits
        if getattr(self, 'logo_batocera', None):
            f_bato_logo_container = ctk.CTkFrame(f_bato_master, width=135, height=95, fg_color="transparent")
            f_bato_logo_container.pack(side="right", padx=10)
            f_bato_logo_container.pack_propagate(False)
            
            lbl_img_bato = ctk.CTkLabel(f_bato_logo_container, image=self.logo_batocera, text="", cursor="hand2")
            lbl_img_bato.place(relx=0.5, rely=0.5, anchor="center")
            lbl_img_bato.bind("<Button-1>", lambda e: self.abrir_url("https://batocera.org"))
            lbl_img_bato.bind("<Enter>", lambda e: self.animar_zoom('logo_batocera', 'bato_size', (125, 88), (135, 95), True))
            lbl_img_bato.bind("<Leave>", lambda e: self.animar_zoom('logo_batocera', 'bato_size', (125, 88), (135, 95), False))

        # SECCIÓN PACKS ADICIONALES
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
        f_cachy_master.pack(fill="x", padx=15, pady=10)
        if getattr(self, 'logo_cachy', None):
            f_cachy_logo_container = ctk.CTkFrame(f_cachy_master, width=305, height=85, fg_color="transparent")
            f_cachy_logo_container.pack(pady=(0, 5))
            f_cachy_logo_container.pack_propagate(False)
            
            lbl_img_cachy = ctk.CTkLabel(f_cachy_logo_container, image=self.logo_cachy, text="", cursor="hand2")
            lbl_img_cachy.place(relx=0.5, rely=0.5, anchor="center")
            lbl_img_cachy.bind("<Button-1>", lambda e: self.abrir_url("https://cachyos.org"))
            lbl_img_cachy.bind("<Enter>", lambda e: self.animar_zoom('logo_cachy', 'cachy_size', (280, 78), (305, 85), True))
            lbl_img_cachy.bind("<Leave>", lambda e: self.animar_zoom('logo_cachy', 'cachy_size', (280, 78), (305, 85), False))

        f_cachy_h = ctk.CTkFrame(f_cachy_master, fg_color="transparent")
        f_cachy_h.pack(fill="x")
        sw_cachy = ctk.CTkSwitch(f_cachy_h, text="¿Instalar CachyOS?", font=("Segoe UI", 12, "bold"), variable=self.instalar_cachy, command=self.actualizar_estados_cachy, progress_color=AZUL_CIAN)
        sw_cachy.pack(side="left")
        self.widgets_interactivos.append(sw_cachy)
        self.crear_boton_info(f_cachy_h, self.abrir_info_cachyos).pack(side="left", padx=5)

        # Contenedor para elegir escritorio de CachyOS
        self.cachy_flavor = ctk.StringVar(value="kde")
        self.f_cachy_opts = ctk.CTkFrame(f_cachy_master, fg_color="#0d141c", corner_radius=8)
        
        # Opción KDE
        f_kde = ctk.CTkFrame(self.f_cachy_opts, fg_color="transparent")
        f_kde.pack(fill="x", padx=10, pady=2)
        r_kde = ctk.CTkRadioButton(f_kde, text="KDE Plasma", variable=self.cachy_flavor, value="kde", font=("Segoe UI", 12))
        r_kde.pack(side="left", pady=6)
        self.crear_boton_info(f_kde, self.abrir_info_kde).pack(side="right")

        # Opción Hyprland
        f_hypr = ctk.CTkFrame(self.f_cachy_opts, fg_color="transparent")
        f_hypr.pack(fill="x", padx=10, pady=2)
        r_hypr = ctk.CTkRadioButton(f_hypr, text="Hyprland", variable=self.cachy_flavor, value="hyprland", font=("Segoe UI", 12))
        r_hypr.pack(side="left", pady=6)
        self.crear_boton_info(f_hypr, self.abrir_info_hyprland).pack(side="right")

        self.widgets_interactivos.extend([r_kde, r_hypr])

        # PANEL DERECHO (CONTROL DE ESPACIO Y CONFIGURACIÓN)
        self.p_right = ctk.CTkFrame(self.main_container, fg_color=AZUL_CARD, corner_radius=15, border_width=1, border_color="#222")
        self.p_right.pack(side="right", fill="both", expand=True)

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

       # ---------------------------------------------------------------------
        # 🚀 BOTÓN PRINCIPAL DE INICIO (Ubicado en el panel derecho p_right)
        # ---------------------------------------------------------------------
        if getattr(self, 'img_instalar', None):
            self.btn_start = ctk.CTkButton(
                self.p_right, 
                image=self.img_instalar, 
                text="", 
                fg_color="transparent", 
                hover_color="#0d141c", 
                height=75, 
                cursor="hand2",
                command=self.confirmar_inicio
            )
        else:
            self.btn_start = ctk.CTkButton(
                self.p_right, 
                text="🚀 COMENZAR INSTALACIÓN", 
                font=("Segoe UI", 14, "bold"), 
                fg_color=AZUL_ELECTRICO, 
                hover_color="#0046c7", 
                height=45, 
                command=self.confirmar_inicio
            )
        self.btn_start.pack(fill="x", padx=20, pady=(15, 10))
        self.widgets_interactivos.append(self.btn_start)

        # =====================================================================
        # 🛠️ PANEL MÓDULO HOLLOWTOOLS
        # =====================================================================
        self.hollow_tools_container = ctk.CTkFrame(self, fg_color="transparent")

        # CABECERA Y SELECTOR
        f_ht_top = ctk.CTkFrame(self.hollow_tools_container, fg_color=AZUL_CARD, corner_radius=12, border_width=1, border_color="#222")
        f_ht_top.pack(fill="x", padx=5, pady=(0, 10))
        
        ctk.CTkLabel(f_ht_top, text="🛠️ MANTENIMIENTO Y GESTIÓN HOLLOWDRIVE", font=("Impact", 22), text_color=AZUL_CIAN).pack(pady=(10, 2))
        
        f_combo_ht = ctk.CTkFrame(f_ht_top, fg_color="transparent")
        f_combo_ht.pack(pady=(2, 10))
        self.combo_ht_disk = ctk.CTkComboBox(f_combo_ht, values=["Buscando HOLLOWDRIVES..."], width=460, font=("Segoe UI", 12), command=self.al_seleccionar_disco_hollowtools)
        self.combo_ht_disk.pack(side="left", padx=10)
        self.btn_ht_refresh = ctk.CTkButton(f_combo_ht, text="🔄 ESCANEAR", font=("Segoe UI", 12, "bold"), width=130, height=32, fg_color="#222", hover_color="#333", command=self.refrescar_discos_hollowtools)
        self.btn_ht_refresh.pack(side="left")

        # PANEL PRINCIPAL DE 3 MÓDULOS
        f_ht_grid = ctk.CTkFrame(self.hollow_tools_container, fg_color="transparent")
        f_ht_grid.pack(fill="both", expand=True, padx=0, pady=0)

        # ---------------------------------------------------------------------
        # TARJETA 1: AÑADIR ISOs
        # ---------------------------------------------------------------------
        self.card_iso = ctk.CTkFrame(f_ht_grid, fg_color=AZUL_CARD, corner_radius=15, border_width=1, border_color="#222")
        self.card_iso.pack(side="left", fill="both", expand=True, padx=4)

        f_head_iso = ctk.CTkFrame(self.card_iso, fg_color="transparent")
        f_head_iso.pack(fill="x", padx=12, pady=(12, 4))
        ctk.CTkLabel(f_head_iso, text="CD GESTOR DE ISOs", font=("Segoe UI", 16, "bold"), text_color=AZUL_CIAN).pack(side="left")
        self.crear_boton_info(f_head_iso, self.abrir_info_ht_isos).pack(side="right")

        self.f_drop_area = ctk.CTkFrame(self.card_iso, fg_color="#090d12", corner_radius=12, border_width=1, border_color="#1e293b")
        self.f_drop_area.pack(fill="both", expand=True, padx=12, pady=10)

        self.lbl_drag_msg = ctk.CTkLabel(self.f_drop_area, text="Arrastra tus .ISO a cualquier punto\nde este recuadro o haz clic abajo", font=("Segoe UI", 12), text_color=AZUL_SUAVE, justify="center")
        self.lbl_drag_msg.pack(pady=(10, 2))

        self.f_iso_logo_container = ctk.CTkFrame(self.f_drop_area, width=170, height=170, fg_color="transparent")
        self.f_iso_logo_container.pack(expand=True, pady=5)
        self.f_iso_logo_container.pack_propagate(False)

        if getattr(self, 'img_isos', None):
            self.btn_plus_iso = ctk.CTkLabel(self.f_iso_logo_container, image=self.img_isos, text="", cursor="hand2")
            self.btn_plus_iso.place(relx=0.5, rely=0.5, anchor="center")
            self.btn_plus_iso.bind("<Button-1>", lambda e: self.ht_agregar_isos())
            self.btn_plus_iso.bind("<Enter>", lambda e: self.animar_zoom('img_isos', 'isos_size', (150, 150), (165, 165), True))
            self.btn_plus_iso.bind("<Leave>", lambda e: self.animar_zoom('img_isos', 'isos_size', (150, 150), (165, 165), False))
        else:
            self.btn_plus_iso = ctk.CTkButton(
                self.f_iso_logo_container, text="+", font=("Segoe UI", 60, "bold"), 
                fg_color=AZUL_ELECTRICO, hover_color="#0046c7", corner_radius=25,
                width=110, height=110, command=self.ht_agregar_isos
            )
            self.btn_plus_iso.place(relx=0.5, rely=0.5, anchor="center")

        # ---------------------------------------------------------------------
        # TARJETA 2: INYECTAR REPOSITORIOS
        # ---------------------------------------------------------------------
        card_content = ctk.CTkFrame(f_ht_grid, fg_color=AZUL_CARD, corner_radius=15, border_width=1, border_color="#222")
        card_content.pack(side="left", fill="both", expand=True, padx=4)

        f_head_content = ctk.CTkFrame(card_content, fg_color="transparent")
        f_head_content.pack(fill="x", padx=12, pady=(12, 4))
        ctk.CTkLabel(f_head_content, text="📦 PAQUETES", font=("Segoe UI", 16, "bold"), text_color=AZUL_CIAN).pack(side="left")
        self.crear_boton_info(f_head_content, self.abrir_info_ht_packs).pack(side="right")

        f_ch_ht = ctk.CTkFrame(card_content, fg_color="#090d12", corner_radius=12, border_width=1, border_color="#1e293b")
        f_ch_ht.pack(fill="x", padx=12, pady=10)

        self.ch_tool_bato = ctk.CTkCheckBox(f_ch_ht, text="Batocera OS (.img)", font=("Segoe UI", 12), variable=self.tool_bato_img)
        self.ch_tool_bato.pack(anchor="w", pady=8, padx=12)

        self.ch_tool_pack_bato = ctk.CTkCheckBox(f_ch_ht, text="Pack ROMs (37.8GB)", font=("Segoe UI", 12), variable=self.tool_pack_bato)
        self.ch_tool_pack_bato.pack(anchor="w", pady=8, padx=12)

        self.ch_tool_pack_hollow = ctk.CTkCheckBox(f_ch_ht, text="Pack HollowDrive (8.06GB)", font=("Segoe UI", 12), variable=self.tool_pack_hollow)
        self.ch_tool_pack_hollow.pack(anchor="w", pady=8, padx=12)

        ctk.CTkButton(
            card_content, text="📥 Inyectar Seleccionados", font=("Segoe UI", 12, "bold"), 
            fg_color=AZUL_ELECTRICO, hover_color="#0046c7", height=42, command=self.ht_inyectar_contenido
        ).pack(side="bottom", pady=12, padx=12, fill="x")

        # ---------------------------------------------------------------------
        # TARJETA 3: GESTIÓN CACHYOS
        # ---------------------------------------------------------------------
        card_cachy = ctk.CTkFrame(f_ht_grid, fg_color=AZUL_CARD, corner_radius=15, border_width=1, border_color="#222")
        card_cachy.pack(side="left", fill="both", expand=True, padx=4)

        f_head_cachy = ctk.CTkFrame(card_cachy, fg_color="transparent")
        f_head_cachy.pack(fill="x", padx=12, pady=(12, 4))
        ctk.CTkLabel(f_head_cachy, text="🚀 CACHYOS OS", font=("Segoe UI", 16, "bold"), text_color=COLOR_CACHY).pack(side="left")
        self.crear_boton_info(f_head_cachy, self.abrir_info_ht_cachy).pack(side="right")

        f_body_cachy = ctk.CTkFrame(card_cachy, fg_color="transparent")
        f_body_cachy.pack(fill="both", expand=True, padx=12, pady=5)

        self.seg_ht_cachy = ctk.CTkSegmentedButton(
            f_body_cachy, 
            values=["🔄 Actualizar CachyOS", "➕ Instalar CachyOS"], 
            command=self.al_cambiar_modo_cachy,
            font=("Segoe UI", 11, "bold"),
            selected_color=AZUL_ELECTRICO,
            selected_hover_color="#0046c7"
        )
        self.seg_ht_cachy.set("🔄 Actualizar CachyOS")
        self.seg_ht_cachy.pack(fill="x", pady=(2, 8))

        # NUEVO: Selector de KDE/Hyprland para HollowTools
        self.ht_cachy_flavor = ctk.StringVar(value="kde")
        self.f_ht_flavor = ctk.CTkFrame(f_body_cachy, fg_color="#090d12", corner_radius=8, border_width=1, border_color="#1e293b")
        self.f_ht_flavor.pack(fill="x", pady=(0, 8))
        
        ctk.CTkLabel(self.f_ht_flavor, text="Entorno:", font=("Segoe UI", 11, "bold"), text_color=AZUL_SUAVE).pack(side="left", padx=10, pady=6)
        r_ht_kde = ctk.CTkRadioButton(self.f_ht_flavor, text="KDE", variable=self.ht_cachy_flavor, value="kde", font=("Segoe UI", 11))
        r_ht_kde.pack(side="left", padx=5)
        r_ht_hypr = ctk.CTkRadioButton(self.f_ht_flavor, text="Hyprland", variable=self.ht_cachy_flavor, value="hyprland", font=("Segoe UI", 11))
        r_ht_hypr.pack(side="left", padx=5)

        self.f_slider_sec = ctk.CTkFrame(f_body_cachy, fg_color="#090d12", corner_radius=10, border_width=1, border_color="#1e293b")

        ctk.CTkLabel(self.f_slider_sec, text="TAMAÑO CACHYOS (DERECHA):", font=("Segoe UI", 10, "bold"), text_color=AZUL_SUAVE).pack(pady=(6, 0))
        self.lbl_ht_right_space = ctk.CTkLabel(self.f_slider_sec, text="Disponible: 0.00 GB", font=("Consolas", 12, "bold"), text_color="white")
        self.lbl_ht_right_space.pack(pady=(0, 2))

        self.slider_ht_cachy = ctk.CTkSlider(self.f_slider_sec, from_=20, to=100, progress_color=COLOR_CACHY, command=lambda v: self.actualizar_preview_barras_ht())
        self.slider_ht_cachy.pack(pady=(2, 8), padx=10, fill="x")

        self.btn_ht_ejecutar_cachy = ctk.CTkButton(
            f_body_cachy, text="⚡ Aplicar en CachyOS", font=("Segoe UI", 12, "bold"), 
            fg_color=AZUL_ELECTRICO, hover_color="#0046c7", height=38, command=self.ht_ejecutar_accion_cachyos
        )
        self.btn_ht_ejecutar_cachy.pack(side="bottom", fill="x", pady=(8, 4))

        # ---------------------------------------------------------------------
        # BARRAS VISUALES COMPARATIVAS (ANTES / DESPUÉS)
        # ---------------------------------------------------------------------
        f_ht_preview = ctk.CTkFrame(self.hollow_tools_container, fg_color=AZUL_CARD, corner_radius=12, border_width=1, border_color="#222")
        f_ht_preview.pack(fill="x", padx=5, pady=(10, 0))

        # Estado Actual (ANTES)
        f_p1 = ctk.CTkFrame(f_ht_preview, fg_color="transparent")
        f_p1.pack(fill="x", padx=12, pady=(6, 2))
        ctk.CTkLabel(f_p1, text="ANTES", font=("Segoe UI", 13, "bold"), text_color=AZUL_SUAVE).pack(side="left")
        self.lbl_ht_bar_actual_info = ctk.CTkLabel(f_p1, text="", font=("Consolas", 13, "bold"), text_color="#ffffff")
        self.lbl_ht_bar_actual_info.pack(side="right")
        self.canvas_ht_actual = tk.Canvas(f_ht_preview, height=26, bg=AZUL_CARD, highlightthickness=0, borderwidth=0)
        self.canvas_ht_actual.pack(fill="x", padx=12, pady=(0, 2))

        self.lbl_ht_arrow = ctk.CTkLabel(f_ht_preview, text="⬇      ⬇      ⬇      ⬇      ⬇      ⬇      ⬇      ⬇", font=("Segoe UI", 12, "bold"), text_color=AZUL_CIAN)
        self.lbl_ht_arrow.pack(pady=1)

        # Estado Futuro (DESPUÉS)
        f_p2 = ctk.CTkFrame(f_ht_preview, fg_color="transparent")
        f_p2.pack(fill="x", padx=12, pady=(2, 2))
        ctk.CTkLabel(f_p2, text="DESPUÉS", font=("Segoe UI", 13, "bold"), text_color=COLOR_CACHY).pack(side="left")
        self.lbl_ht_bar_futuro_info = ctk.CTkLabel(f_p2, text="", font=("Consolas", 13, "bold"), text_color="#ffffff")
        self.lbl_ht_bar_futuro_info.pack(side="right")
        self.canvas_ht_futuro = tk.Canvas(f_ht_preview, height=26, bg=AZUL_CARD, highlightthickness=0, borderwidth=0)
        self.canvas_ht_futuro.pack(fill="x", padx=12, pady=(0, 8))

        # =====================================================================
        # FOOTER / PIE DE PÁGINA CON MULTI-BARRA DINÁMICA
        # =====================================================================
        self.footer = ctk.CTkFrame(self, fg_color="transparent")

        self.lbl_gif = ctk.CTkLabel(self.footer, text="")
        self.lbl_gif.pack(side="left", padx=10)

        # Contenedor para progreso
        self.f_progress = ctk.CTkFrame(self.footer, fg_color="transparent")

        # --- ETIQUETA DE ESTADO PRINCIPAL Y BARRAS GLOBALES ---
        self.lbl_status = ctk.CTkLabel(self.f_progress, text="ESPERANDO INICIO...", font=("Consolas", 12, "bold"), text_color=AZUL_SUAVE)
        self.lbl_status.pack(anchor="w", padx=5, pady=(2, 2))

        self.p_task = ctk.CTkProgressBar(self.f_progress, height=8, progress_color=AZUL_CIAN)
        self.p_task.set(0)
        self.p_task.pack(fill="x", padx=5, pady=2)

        self.p_total = ctk.CTkProgressBar(self.f_progress, height=8, progress_color=AZUL_ELECTRICO)
        self.p_total.set(0)
        self.p_total.pack(fill="x", padx=5, pady=2)
        
        # Contenedor desplazable para procesos dinámicos de HollowTools (Inicialmente SIN pack)
        self.f_tasks_scroll = ctk.CTkScrollableFrame(self.f_progress, height=70, fg_color="transparent", label_text="")

        self.btn_cancel = ctk.CTkButton(
            self.footer, text="❌ CANCELAR", font=("Segoe UI", 12, "bold"), 
            fg_color="#aa3333", hover_color="#882222", height=40, command=self.cancelar_proceso
        )

    def cambiar_pestana(self, destino):
        if self.en_proceso:
            messagebox.showwarning("PROCESO EN CURSO", "No puedes usar HollowTools mientras se ejecuta una instalación.")
            return

        self.pestana_actual = destino

        if destino == "instalador":
            self.hollow_tools_container.pack_forget()
            self.f_selection.pack(fill="x", padx=20, pady=(0, 5), after=self.nav_bar)
            
            seleccion = self.combo_disk.get()
            if seleccion and not any(k in seleccion for k in ["---", "Buscando", "NO SE DETECTAN"]):
                self.main_container.pack(fill="both", expand=True, padx=20, pady=5)
            self.footer.pack(fill="x", side="bottom", padx=20, pady=10)
            
            if not self.en_proceso:
                if hasattr(self, 'btn_start') and self.btn_start.winfo_exists():
                    self.btn_start.pack(fill="x", padx=20, pady=(15, 10))
                self.f_progress.pack_forget()
                self.btn_cancel.pack_forget()
                
            self.btn_modo_installer.configure(fg_color=AZUL_ELECTRICO, text_color="white")
            self.btn_modo_tools.configure(fg_color="transparent", text_color=AZUL_CIAN)
        else:
            self.f_selection.pack_forget()
            self.main_container.pack_forget()
            
            # Ocultar el botón de inicio de p_right al pasar a HollowTools
            if hasattr(self, 'btn_start') and self.btn_start.winfo_exists():
                self.btn_start.pack_forget()

            self.hollow_tools_container.pack(fill="both", expand=True, padx=20, pady=(5, 5), after=self.nav_bar)
            self.footer.pack(fill="x", side="bottom", padx=20, pady=10)
            
            if not self.en_proceso:
                self.f_progress.pack_forget()
                self.btn_cancel.pack_forget()
                
            self.btn_modo_tools.configure(fg_color=AZUL_ELECTRICO, text_color="white")
            self.btn_modo_installer.configure(fg_color="transparent", text_color=AZUL_CIAN)
            self.refrescar_discos_hollowtools()

    def refrescar_discos_hollowtools(self):
        self.btn_ht_refresh.configure(state="disabled")
        self.combo_ht_disk.configure(values=["Buscando HOLLOWDRIVES..."])
        self.combo_ht_disk.set("Buscando HOLLOWDRIVES...")
        
        def run():
            unidades = obtener_unidades_usb(incluir_internos=False)
            filtradas = []
            for u in unidades:
                particiones = obtener_estructura_disco_ps(u["device"])
                es_hollow = False
                for p in particiones:
                    lbl = (p.get("Label") or "").upper()
                    letra = p.get("Letter")
                    if "HOLLOW" in lbl or "VENTOY" in lbl or (letra and os.path.exists(f"{letra}:\\HOLLOWDRIVE")):
                        es_hollow = True
                        break
                if es_hollow:
                    filtradas.append(u)

            lista_final = filtradas if filtradas else unidades
            self.after(0, lambda: self._finalizar_refresco_ht(lista_final))
            
        threading.Thread(target=run, daemon=True).start()

    def _finalizar_refresco_ht(self, discos):
        self.lista_discos_hollow = discos
        self.btn_ht_refresh.configure(state="normal")
        if not discos:
            self.combo_ht_disk.configure(values=["⚠️ NO SE DETECTAN UNIDADES HOLLOWDRIVE"])
            self.combo_ht_disk.set("⚠️ NO SE DETECTAN UNIDADES HOLLOWDRIVE")
        else:
            nombres = [d["display"] for d in discos]
            self.combo_ht_disk.configure(values=nombres)
            self.combo_ht_disk.set(nombres[0])
            self.al_seleccionar_disco_hollowtools(nombres[0])

    def al_seleccionar_disco_hollowtools(self, seleccion):
        disco = next((d for d in self.lista_discos_hollow if d["display"] == seleccion), None)
        if not disco: return
        
        self.seg_ht_cachy.configure(state="disabled")
        self.btn_ht_ejecutar_cachy.configure(state="disabled")
        self.slider_ht_cachy.configure(state="disabled")
        self.lbl_ht_right_space.configure(text="Consultando particiones...")

        def consultar_disco_hilo():
            particiones = obtener_estructura_disco_ps(disco["device"])
            
            tiene_cachy = any((p.get("Label") or "").upper() == "CACHYOS" for p in particiones)
            puedes_actualizar = tiene_cachy or (len(particiones) >= 2)

            size_hollow = 0.0
            for p in particiones:
                lbl = (p.get("Label") or "").upper()
                if p.get("Number") == 1 or lbl in ["HOLLOWDRIVE", "VENTOY"]:
                    size_hollow = p.get("Size", 0.0)
                    break
            
            if size_hollow == 0.0 and particiones:
                size_hollow = particiones[0].get("Size", 0.0)

            total_disk_gb = disco["size"]
            espacio_derecha = max(0.0, total_disk_gb - size_hollow)

            def actualizar_gui():
                if not self.winfo_exists(): return
                self.ht_particiones_actuales = particiones
                self.ht_size_hollow = size_hollow
                self.ht_total_disk_gb = total_disk_gb
                self.ht_espacio_derecha = espacio_derecha

                self.btn_ht_ejecutar_cachy.configure(state="normal")
                self.seg_ht_cachy.configure(state="normal")

                if puedes_actualizar and espacio_derecha < 20.0:
                    self.seg_ht_cachy.set("🔄 Actualizar CachyOS")
                    self.al_cambiar_modo_cachy("🔄 Actualizar CachyOS")
                elif not puedes_actualizar and espacio_derecha >= 20.0:
                    self.seg_ht_cachy.set("➕ Instalar CachyOS")
                    self.al_cambiar_modo_cachy("➕ Instalar CachyOS")

                if espacio_derecha >= 20.0:
                    self.slider_ht_cachy.configure(state="normal", from_=20.0, to=espacio_derecha)
                    if self.slider_ht_cachy.get() < 20.0 or self.slider_ht_cachy.get() > espacio_derecha:
                        self.slider_ht_cachy.set(espacio_derecha)
                    self.lbl_ht_right_space.configure(text=f"Disponible a la derecha: {espacio_derecha:.2f} GB")
                else:
                    self.slider_ht_cachy.configure(state="disabled")
                    self.lbl_ht_right_space.configure(text=f"Insuficiente: {espacio_derecha:.2f} GB (mín. 20GB)")

                self.update_idletasks()
                self.actualizar_preview_barras_ht()

            self.after(0, actualizar_gui)

        threading.Thread(target=consultar_disco_hilo, daemon=True).start()

    def al_cambiar_modo_cachy(self, value):
        if "Actualizar" in value:
            self.f_slider_sec.pack_forget()
        else:
            self.f_slider_sec.pack(fill="x", pady=2, padx=0, after=self.seg_ht_cachy)
        self.actualizar_preview_barras_ht()

    def ht_ejecutar_accion_cachyos(self):
        modo = self.seg_ht_cachy.get()
        if "Actualizar" in modo:
            self.ht_actualizar_cachyos()
        else:
            self.ht_instalar_cachyos_libre()

    def actualizar_preview_barras_ht(self, *args):
        if not hasattr(self, 'ht_particiones_actuales'): return
        total_gb = getattr(self, 'ht_total_disk_gb', 0.0)
        if total_gb <= 0: return

        modo_actualizar = "Actualizar" in self.seg_ht_cachy.get()

        w_act = self.canvas_ht_actual.winfo_width()
        w_fut = self.canvas_ht_futuro.winfo_width()

        if w_act <= 1 or w_fut <= 1:
            self.after(100, self.actualizar_preview_barras_ht)
            return

        # BARRA ANTES
        self.canvas_ht_actual.delete("all")
        x = 0
        size_cachy_act = 0.0

        for p in self.ht_particiones_actuales:
            p_size = p.get("Size", 0.0)
            pix = int((p_size / total_gb) * w_act)
            lbl = (p.get("Label") or "").upper()
            num = p.get("Number")
            
            if "HOLLOW" in lbl or "VENTOY" in lbl or num == 1:
                color = COLOR_HOLLOW
            elif "GRUB" in lbl or (0.2 <= p_size <= 1.5 and num != 1):
                color = COLOR_LIMINE
            elif "CACHY" in lbl or (p_size >= 5.0 and num != 1):
                color = COLOR_CACHY
                size_cachy_act = p_size
            else:
                color = COLOR_HOLLOW
            
            self.canvas_ht_actual.create_rectangle(x, 0, x + pix, 26, fill=color, outline="#111")
            
            if ("HOLLOW" in lbl or "VENTOY" in lbl or num == 1) and pix > 45:
                self.canvas_ht_actual.create_text(x + (pix / 2), 13, text=f"Hollow: {p_size:.1f}GB", fill="#ffffff", font=("Segoe UI", 10, "bold"))
                
            x += pix
        
        libre_act = max(0.0, total_gb - sum(p.get("Size", 0.0) for p in self.ht_particiones_actuales))
        if x < w_act:
            self.canvas_ht_actual.create_rectangle(x, 0, w_act, 26, fill=COLOR_LIBRE, outline="")

        info_act_items = []
        if size_cachy_act > 0:
            info_act_items.append(f"CachyOS: {size_cachy_act:.1f}GB")
        info_act_items.append(f"Libre: {libre_act:.1f}GB")
        self.lbl_ht_bar_actual_info.configure(text=" | ".join(info_act_items))

        # BARRA DESPUÉS
        self.canvas_ht_futuro.delete("all")
        
        if modo_actualizar:
            x = 0
            for p in self.ht_particiones_actuales:
                p_size = p.get("Size", 0.0)
                pix = int((p_size / total_gb) * w_fut)
                lbl = (p.get("Label") or "").upper()
                num = p.get("Number")
                
                es_target = False
                if "HOLLOW" in lbl or "VENTOY" in lbl or num == 1:
                    color = COLOR_HOLLOW
                elif "GRUB" in lbl or (0.2 <= p_size <= 1.5 and num != 1):
                    color = COLOR_LIMINE
                    es_target = True
                elif "CACHY" in lbl or (p_size >= 5.0 and num != 1):
                    color = COLOR_CACHY
                    es_target = True
                else:
                    color = COLOR_HOLLOW

                self.canvas_ht_futuro.create_rectangle(x, 0, x + pix, 26, fill=color, outline="#111")
                
                if ("HOLLOW" in lbl or "VENTOY" in lbl or num == 1) and pix > 45:
                    self.canvas_ht_futuro.create_text(x + (pix / 2), 13, text=f"Hollow: {p_size:.1f}GB", fill="#ffffff", font=("Segoe UI", 10, "bold"))

                if es_target and pix > 12:
                    self.canvas_ht_futuro.create_text(x + (pix / 2), 13, text="✔", fill="#ffffff", font=("Segoe UI", 12, "bold"))
                
                x += pix
            
            if x < w_fut:
                self.canvas_ht_futuro.create_rectangle(x, 0, w_fut, 26, fill=COLOR_LIBRE, outline="")

            info_fut_items = []
            if size_cachy_act > 0:
                info_fut_items.append(f"CachyOS: {size_cachy_act:.1f}GB")
            info_fut_items.append(f"Libre: {libre_act:.1f}GB")
            self.lbl_ht_bar_futuro_info.configure(text=" | ".join(info_fut_items))

        else:
            size_h = self.ht_size_hollow
            size_g = GB_GRUB
            for p in self.ht_particiones_actuales:
                lbl = (p.get("Label") or "").upper()
                p_size = p.get("Size", 0.0)
                if "GRUB" in lbl or (0.2 <= p_size <= 1.5 and p.get("Number") != 1):
                    size_g = p_size
                    break

            size_c = self.slider_ht_cachy.get()

            pix_h = int((size_h / total_gb) * w_fut)
            pix_g = int((size_g / total_gb) * w_fut)
            pix_c = int((size_c / total_gb) * w_fut)

            self.canvas_ht_futuro.create_rectangle(0, 0, pix_h, 26, fill=COLOR_HOLLOW, outline="#111")
            if pix_h > 45:
                self.canvas_ht_futuro.create_text(pix_h / 2, 13, text=f"Hollow: {size_h:.1f}GB", fill="#ffffff", font=("Segoe UI", 10, "bold"))
            
            x = pix_h
            if size_c > 0:
                self.canvas_ht_futuro.create_rectangle(x, 0, x + pix_g, 26, fill=COLOR_LIMINE, outline="#111")
                x += pix_g
                self.canvas_ht_futuro.create_rectangle(x, 0, x + pix_c, 26, fill=COLOR_CACHY, outline="#111")
                x += pix_c
            
            if x < w_fut:
                self.canvas_ht_futuro.create_rectangle(x, 0, w_fut, 26, fill=COLOR_LIBRE, outline="")

            libre_futuro = max(0.0, total_gb - size_h - size_g - size_c)
            info_fut_items = [f"CachyOS: {size_c:.1f}GB", f"Libre: {libre_futuro:.1f}GB"]
            self.lbl_ht_bar_futuro_info.configure(text=" | ".join(info_fut_items))
            
    def ht_actualizar_cachyos(self):
        seleccion = self.combo_ht_disk.get()
        disco = next((d for d in self.lista_discos_hollow if d["display"] == seleccion), None)
        if not disco: return

        letra_grub, letra_cachy = obtener_o_asignar_letras_cachyos_grub(disco["device"])

        if not (letra_grub and letra_cachy):
            messagebox.showerror("Error de Letra", "No se pudieron asignar/encontrar las letras de unidad de GRUB y CachyOS.")
            return

        if messagebox.askyesno("CONFIRMAR ACTUALIZACIÓN", f"Se reescribirán los datos en:\n• GRUB ({letra_grub})\n• CachyOS ({letra_cachy})\n\n¿Continuar?"):
            self._ejecutar_flasheo_cachy(letra_grub, letra_cachy)

    def ht_instalar_cachyos_libre(self):
        seleccion = self.combo_ht_disk.get()
        disco = next((d for d in self.lista_discos_hollow if d["display"] == seleccion), None)
        if not disco: return

        tamano_gb = self.slider_ht_cachy.get()

        if not messagebox.askyesno("CONFIRMAR INSTALACIÓN", f"Se borrará cualquier partición a la derecha de HOLLOWDRIVE y se creará CachyOS con {tamano_gb:.1f} GB.\n\n¿Proceder con la operación?"):
            return

        self.bloquear_ui(True)
        self.en_proceso = True
        self.abortar_proceso = False

        id_part = "ht_cachy_part"
        id_grub = "ht_cachy_grub"
        id_sys = "ht_cachy_sys"

        self.crear_barra_tarea_dinamica(id_part, "Paso 1/3: Preparando y creando particiones...", color=AZUL_CIAN)
        self.crear_barra_tarea_dinamica(id_grub, "Paso 2/3: Volcado GRUB Bootloader (en espera)", color=COLOR_CACHY)
        self.crear_barra_tarea_dinamica(id_sys, "Paso 3/3: Volcado CachyOS Btrfs (en espera)", color=COLOR_CACHY)

        def hilo():
            try:
                # PASO 1: Particionado
                self.actualizar_barra_tarea_dinamica(id_part, 0.1, "Eliminando particiones posteriores...")
                if self.abortar_proceso: raise InterruptedError()
                eliminar_particiones_cachy_diskpart(disco["device"])

                self.actualizar_barra_tarea_dinamica(id_part, 0.4, "Creando partición GRUB (FAT32)...")
                if self.abortar_proceso: raise InterruptedError()
                crear_particion_adicional(disk_index=disco["device"], size_gb=GB_GRUB, label="GRUB", fs="fat32")

                tamano_cachy_real = max(1.0, tamano_gb - GB_GRUB - 0.15)

                self.actualizar_barra_tarea_dinamica(id_part, 0.7, f"Creando partición CachyOS ({tamano_cachy_real:.1f} GB)...")
                if self.abortar_proceso: raise InterruptedError()
                crear_particion_adicional(disk_index=disco["device"], size_gb=tamano_cachy_real, label="CachyOS", fs="ntfs")

                self.actualizar_barra_tarea_dinamica(id_part, 0.9, "Asignando y verificando letras de unidad...")
                if self.abortar_proceso: raise InterruptedError()

                letra_grub, letra_cachy = obtener_o_asignar_letras_cachyos_grub(disco["device"])
                if not (letra_grub and letra_cachy):
                    raise RuntimeError("No se pudieron asignar o encontrar las letras de unidad de GRUB y CachyOS.")

                self.actualizar_barra_tarea_dinamica(id_part, 1.0, "✔ Particiones creadas correctamente")

                metodo = self.metodo_descarga.get()
                url_grub = MIRRORS_DATA["cachyos_images"]["efi_grub"]["mirrors"][0]["url"]
                
                # SELECCIÓN DE ENTORNO EN HOLLOWTOOLS
                sabor_ht = getattr(self, 'ht_cachy_flavor', ctk.StringVar(value="kde")).get()
                if sabor_ht == "hyprland":
                    try: url_cachy = MIRRORS_DATA["cachyos_images"]["hyprland"]["mirrors"][0]["url"]
                    except KeyError: url_cachy = "AQUI_IRÁ_EL_FUTURO_LINK_DE_HYPRLAND"
                else:
                    url_cachy = MIRRORS_DATA["cachyos_images"]["sistema"]["mirrors"][0]["url"]

                # PASO 2: Flashear GRUB
                self.actualizar_barra_tarea_dinamica(id_grub, 0.0, "Flasheando GRUB Bootloader...")
                if self.abortar_proceso: raise InterruptedError()

                def prog_grub(written, total, fase="Flasheando", *args):
                    if total and total > 0:
                        pct = written / total
                        self.actualizar_barra_tarea_dinamica(id_grub, pct, f"Flasheando GRUB ({pct*100:.1f}%)")

                stream_flash_image_direct(
                    url_grub, letra_grub, 
                    progress_callback=prog_grub, 
                    abort_check=lambda: self.abortar_proceso, 
                    method=metodo
                )
                self.actualizar_barra_tarea_dinamica(id_grub, 1.0, "✔ GRUB Bootloader completado")

                # PASO 3: Flashear CachyOS
                self.actualizar_barra_tarea_dinamica(id_sys, 0.0, "Flasheando CachyOS Btrfs...")
                if self.abortar_proceso: raise InterruptedError()

                def prog_cachy(written, total, fase="Flasheando", *args):
                    if total and total > 0:
                        pct = written / total
                        self.actualizar_barra_tarea_dinamica(id_sys, pct, f"Flasheando CachyOS ({pct*100:.1f}%)")

                stream_flash_image_direct(
                    url_cachy, letra_cachy, 
                    progress_callback=prog_cachy, 
                    abort_check=lambda: self.abortar_proceso, 
                    method=metodo
                )
                self.actualizar_barra_tarea_dinamica(id_sys, 1.0, "✔ CachyOS Btrfs completado")

                self.after(0, lambda: messagebox.showinfo("ÉXITO", "¡CachyOS instalado y configurado correctamente!"))
                self.refrescar_discos_hollowtools()

            except InterruptedError:
                self.after(0, lambda: messagebox.showinfo("CANCELADO", "Operación abortada por el usuario."))
            except Exception as e:
                err_msg = str(e)
                self.after(0, lambda msg=err_msg: messagebox.showerror("ERROR", msg))
            finally:
                self.eliminar_barra_tarea_dinamica(id_part)
                self.eliminar_barra_tarea_dinamica(id_grub)
                self.eliminar_barra_tarea_dinamica(id_sys)

        threading.Thread(target=hilo, daemon=True).start()

    def obtener_letra_hollowdrive(self):
        letra = encontrar_letra_por_etiqueta_ps("HOLLOWDRIVE") or encontrar_letra_por_etiqueta_ps("Ventoy")
        if letra: return letra

        seleccion = self.combo_ht_disk.get()
        disco = next((d for d in self.lista_discos_hollow if d["display"] == seleccion), None)
        if disco and hasattr(self, 'ht_particiones_actuales'):
            for p in self.ht_particiones_actuales:
                lbl = (p.get("Label") or "").upper()
                if p.get("Number") == 1 or "HOLLOW" in lbl or "VENTOY" in lbl:
                    if p.get("Letter"):
                        return f"{p.get('Letter')}:\\"

        for char in range(68, 91):
            l = f"{chr(char)}:\\"
            if os.path.exists(os.path.join(l, "HOLLOWDRIVE")) or os.path.exists(os.path.join(l, "OSimages")) or os.path.exists(os.path.join(l, "ventoy")):
                return l
        return None

    def al_arrastrar_archivos_iso(self, archivos):
        letra_hollow = self.obtener_letra_hollowdrive()
        if not letra_hollow:
            messagebox.showerror("Error", "No se detectó un USB 'HOLLOWDRIVE' montado.")
            return

        isos_validas = []
        lista = archivos if isinstance(archivos, (list, tuple)) else [archivos]

        for item in lista:
            if isinstance(item, bytes):
                try: ruta = item.decode('utf-8')
                except UnicodeDecodeError: ruta = item.decode('mbcs', errors='ignore')
            else: ruta = str(item)

            ruta = ruta.strip('{}').strip()
            if ruta.lower().endswith(".iso") and os.path.isfile(ruta):
                isos_validas.append(os.path.normpath(ruta))

        if not isos_validas:
            messagebox.showwarning("Formato No Soportado", "Por favor arrastra únicamente archivos con extensión .iso")
            return

        self.procesar_e_inyectar_isos(isos_validas, letra_hollow)

    def ht_agregar_isos(self):
        letra_hollow = self.obtener_letra_hollowdrive()
        if not letra_hollow:
            messagebox.showerror("Error", "No se encontró la unidad 'HOLLOWDRIVE' montada.")
            return

        archivos = filedialog.askopenfilenames(
            title="Selecciona archivos ISO para HOLLOWDRIVE", 
            filetypes=[("Archivos ISO", "*.iso")]
        )
        if not archivos: return
        self.procesar_e_inyectar_isos(archivos, letra_hollow)

    def ht_inyectar_contenido(self):
        seleccion = self.combo_ht_disk.get()
        disco = next((d for d in self.lista_discos_hollow if d["display"] == seleccion), None)
        if not disco:
            messagebox.showerror("Error", "No se identificó ningún disco HOLLOWDRIVE válido.")
            return

        bato_img = self.tool_bato_img.get()
        pack_bato = self.tool_pack_bato.get()
        pack_hollow = self.tool_pack_hollow.get()

        if not (bato_img or pack_bato or pack_hollow):
            messagebox.showwarning("Selección Vacía", "Por favor, marca al menos un paquete para inyectar.")
            return

        letra_hollow = self.obtener_letra_hollowdrive()
        if not letra_hollow:
            messagebox.showerror("Error", "No se encontró la partición 'HOLLOWDRIVE' montada.")
            return

        self.bloquear_ui(True)
        self.abortar_proceso = False
        id_tarea = "ht_inyectar_packs"
        self.crear_barra_tarea_dinamica(id_tarea, "Iniciando inyección de paquetes...", color=AZUL_CIAN)

        def hilo_inyeccion():
            try:
                if bato_img and not self.abortar_proceso:
                    ruta_batocerumen = os.path.join(letra_hollow, "HOLLOWDRIVE", "BATOCERUMEN")
                    os.makedirs(ruta_batocerumen, exist_ok=True)
                    dest = os.path.join(ruta_batocerumen, "batocera.img")
                    is_gdrive = "drive.google.com" in URL_BATOCERA or len(URL_BATOCERA) < 40

                    def prog_bato(bytes_read, total_bytes, fase):
                        if total_bytes:
                            pct = bytes_read / total_bytes
                            self.actualizar_barra_tarea_dinamica(id_tarea, pct, f"Batocera OS: {pct*100:.1f}%")

                    stream_download_file_direct(
                        URL_BATOCERA, dest, is_gdrive=is_gdrive,
                        progress_callback=prog_bato,
                        abort_check=lambda: self.abortar_proceso
                    )

                if pack_bato and not self.abortar_proceso:
                    url = MIRRORS_DATA.get("batocera_games", {}).get("mirrors", [{}])[0].get(
                        "url", "https://huggingface.co/datasets/HollowDrive/HollowDrive/resolve/main/batocera-hollowpack.tar"
                    )

                    def prog_pack_b(bytes_read, total_bytes, fase, *args):
                        if total_bytes:
                            pct = bytes_read / total_bytes
                            self.actualizar_barra_tarea_dinamica(id_tarea, pct, f"Pack ROMs: {pct*100:.1f}%")

                    stream_extract_tar(
                        url, letra_hollow, is_gdrive=False,
                        progress_callback=prog_pack_b,
                        abort_check=lambda: self.abortar_proceso,
                        method=self.metodo_descarga.get()
                    )

                if pack_hollow and not self.abortar_proceso:
                    url = MIRRORS_DATA.get("hollowdrive_pack", {}).get("mirrors", [{}])[0].get(
                        "url", "https://pub-b872cd561e404a9599c943c6705afe9e.r2.dev/HollowdrivePackV1.tar"
                    )

                    def prog_pack_h(bytes_read, total_bytes, fase, *args):
                        if total_bytes:
                            pct = bytes_read / total_bytes
                            self.actualizar_barra_tarea_dinamica(id_tarea, pct, f"Pack HollowDrive: {pct*100:.1f}%")

                    stream_extract_tar(
                        url, letra_hollow, is_gdrive=False,
                        progress_callback=prog_pack_h,
                        abort_check=lambda: self.abortar_proceso,
                        method=self.metodo_descarga.get()
                    )

                self.actualizar_barra_tarea_dinamica(id_tarea, 1.0, "✔ Paquetes inyectados correctamente")
                self.after(0, lambda: messagebox.showinfo("ÉXITO", "¡Los paquetes seleccionados se han inyectado correctamente!"))

            except InterruptedError:
                self.after(0, lambda: messagebox.showinfo("CANCELADO", "Operación de inyección abortada por el usuario."))
            except Exception as e:
                err_msg = str(e)
                self.after(0, lambda msg=err_msg: messagebox.showerror("ERROR DE INYECCIÓN", f"Ocurrió un error al inyectar paquetes:\n{msg}"))
            finally:
                self.eliminar_barra_tarea_dinamica(id_tarea)

        threading.Thread(target=hilo_inyeccion, daemon=True).start()

    def procesar_e_inyectar_isos(self, lista_isos, letra_hollow):
        """ Copia ultrarrápida en segundo plano con barra dinámica dedicada """
        letra_clean = letra_hollow.rstrip("\\").rstrip("/")
        destino_osimages = os.path.join(letra_clean, "HOLLOWDRIVE", "OSimages")
        os.makedirs(destino_osimages, exist_ok=True)

        self.en_proceso = True
        self.abortar_proceso = False
        id_tarea = "copia_isos"
        self.crear_barra_tarea_dinamica(id_tarea, "Preparando copia de ISOs...", color=AZUL_CIAN)

        def hilo_copiado_nativo():
            total_archivos = len(lista_isos)
            exitosos = 0

            try:
                for idx, iso in enumerate(lista_isos, 1):
                    if self.abortar_proceso: raise InterruptedError()
                    nombre_iso = os.path.basename(iso)
                    ruta_destino = os.path.join(destino_osimages, nombre_iso)
                    t_start = time.time()

                    def callback_prog(bytes_trans, total_bytes, i_local=idx, n_local=nombre_iso):
                        elapsed = time.time() - t_start
                        mb_s = (bytes_trans / (1024 * 1024)) / elapsed if elapsed > 0 else 0
                        if total_bytes > 0:
                            pct_archivo = bytes_trans / total_bytes
                            pct_global = (i_local - 1 + pct_archivo) / total_archivos
                            
                            txt = f"ISO ({i_local}/{total_archivos}): {n_local} | {pct_archivo*100:.1f}% | {mb_s:.1f} MB/s"
                            self.actualizar_barra_tarea_dinamica(id_tarea, pct_global, txt)

                    copiar_iso_ultrarrapido(
                        iso, ruta_destino, 
                        callback_progreso=callback_prog, 
                        abort_check=lambda: self.abortar_proceso
                    )
                    exitosos += 1

                self.after(0, lambda e_cnt=exitosos, t_cnt=total_archivos, d_path=destino_osimages: messagebox.showinfo(
                    "ÉXITO", f"¡{e_cnt} de {t_cnt} archivo(s) ISO volcado(s) correctamente en:\n{d_path}!"
                ))

            except InterruptedError:
                self.after(0, lambda: messagebox.showinfo("CANCELADO", "Operación de copia abortada por el usuario."))
            except Exception as e:
                err_msg = str(e)
                self.after(0, lambda msg=err_msg: messagebox.showerror("ERROR DE COPIA", f"Ocurrió un error durante la copia:\n{msg}"))
            finally:
                self.eliminar_barra_tarea_dinamica(id_tarea)

        threading.Thread(target=hilo_copiado_nativo, daemon=True).start()

    def ht_reinstalar_cachyos(self):
        seleccion = self.combo_ht_disk.get()
        disco = next((d for d in self.lista_discos_hollow if d["display"] == seleccion), None)
        if not disco:
            messagebox.showerror("Error", "No se identificó ningún disco HOLLOWDRIVE.")
            return

        letra_grub, letra_cachy = obtener_o_asignar_letras_cachyos_grub(disco["device"])

        if letra_grub and letra_cachy:
            v = self.creventana_info_base("GESTIÓN CACHYOS DETECTADO", 540, 360)
            f_in = ctk.CTkFrame(v, fg_color="transparent")
            f_in.pack(expand=True, fill="both", padx=20, pady=20)

            ctk.CTkLabel(f_in, text="🚀 CACHYOS DETECTADO", font=("Impact", 28), text_color=COLOR_CACHY).pack(pady=(0, 10))
            msg = "Se han detectado particiones de CachyOS existentes en esta unidad.\n¿Qué acción deseas realizar?"
            ctk.CTkLabel(f_in, text=msg, font=("Segoe UI", 15), justify="center", wraplength=480).pack(pady=10)

            def opt_actualizar():
                v.destroy()
                self._ejecutar_flasheo_cachy(letra_grub, letra_cachy)

            def opt_borrar():
                v.destroy()
                if messagebox.askyesno("CONFIRMAR BORRADO", "¿Seguro que quieres eliminar las particiones de CachyOS y liberar su espacio?"):
                    if eliminar_particiones_cachy_diskpart(disco["device"]):
                        messagebox.showinfo("ÉXITO", "Particiones eliminadas. Ahora puedes redimensionar el espacio unallocated.")
                        self.refrescar_discos_hollowtools()
                    else:
                        messagebox.showerror("ERROR", "No se pudieron eliminar las particiones.")

            ctk.CTkButton(f_in, text="🔄 ACTUALIZAR / REINSTALAR", font=("Segoe UI", 12, "bold"), fg_color=AZUL_ELECTRICO, height=40, command=opt_actualizar).pack(fill="x", pady=5)
            ctk.CTkButton(f_in, text="🗑️ BORRAR PARTICIONES Y LIBERAR ESPACIO", font=("Segoe UI", 12, "bold"), fg_color="#aa3333", height=40, command=opt_borrar).pack(fill="x", pady=5)
            ctk.CTkButton(f_in, text="CANCELAR", font=("Segoe UI", 11), fg_color="#333", height=30, command=v.destroy).pack(pady=5)
            v.update(); v.grab_set()

        else:
            messagebox.showinfo("INFO", "No se detectaron particiones previas de CachyOS en la unidad.")

    def _ejecutar_flasheo_cachy(self, letra_grub, letra_cachy):
        self.en_proceso = True
        self.abortar_proceso = False
        id_grub = "cachy_grub"
        id_sys = "cachy_sistema"

        self.crear_barra_tarea_dinamica(id_grub, "Paso 1/2: Conectando para flashear GRUB...", color=COLOR_CACHY)
        self.crear_barra_tarea_dinamica(id_sys, "Paso 2/2: En espera...", color=COLOR_CACHY)

        def hilo():
            try:
                url_grub = MIRRORS_DATA["cachyos_images"]["efi_grub"]["mirrors"][0]["url"]
                metodo = self.metodo_descarga.get()

                # SELECCIÓN DE ENTORNO EN HOLLOWTOOLS
                sabor_ht = getattr(self, 'ht_cachy_flavor', ctk.StringVar(value="kde")).get()
                if sabor_ht == "hyprland":
                    try: url_cachy = MIRRORS_DATA["cachyos_images"]["hyprland"]["mirrors"][0]["url"]
                    except KeyError: url_cachy = "AQUI_IRÁ_EL_FUTURO_LINK_DE_HYPRLAND"
                else:
                    try: url_cachy = MIRRORS_DATA["cachyos_images"]["sistema"]["mirrors"][0]["url"]
                    except KeyError: url_cachy = "https://huggingface.co/datasets/HollowDrive/HollowDrive/resolve/main/hollowdrive_cachy_sistema.img"

                # PASO 1: Volcar GRUB Bootloader
                def prog_grub(written, total, info_estado="Flasheando", *args):
                    if total and total > 0:
                        pct = written / total
                        self.actualizar_barra_tarea_dinamica(id_grub, pct, f"GRUB ({pct*100:.1f}%): {info_estado}")

                stream_flash_image_direct(
                    url_grub, letra_grub, 
                    progress_callback=prog_grub, 
                    abort_check=lambda: self.abortar_proceso, 
                    method=metodo
                )
                self.actualizar_barra_tarea_dinamica(id_grub, 1.0, "✔ GRUB Bootloader completado")

                # PASO 2: Volcar Sistema CachyOS
                self.actualizar_barra_tarea_dinamica(id_sys, 0.0, "Paso 2/2: Preparando CachyOS Btrfs...")

                def prog_cachy(written, total, info_estado="Flasheando", *args):
                    if total and total > 0:
                        pct = written / total
                        self.actualizar_barra_tarea_dinamica(id_sys, pct, f"CachyOS ({pct*100:.1f}%): {info_estado}")

                stream_flash_image_direct(
                    url_cachy, letra_cachy, 
                    progress_callback=prog_cachy, 
                    abort_check=lambda: self.abortar_proceso, 
                    method=metodo
                )
                self.actualizar_barra_tarea_dinamica(id_sys, 1.0, "✔ CachyOS completado")

                self.after(0, lambda: messagebox.showinfo("ÉXITO", "¡CachyOS ha sido actualizado / reinstalado correctamente!"))

            except InterruptedError:
                self.after(0, lambda: messagebox.showinfo("CANCELADO", "Operación de actualización abortada por el usuario."))
            except Exception as e:
                err_msg = str(e)
                self.after(0, lambda msg=err_msg: messagebox.showerror("ERROR", msg))
            finally:
                self.eliminar_barra_tarea_dinamica(id_grub)
                self.eliminar_barra_tarea_dinamica(id_sys)

        threading.Thread(target=hilo, daemon=True).start()

    def toggle_preservar_espacio(self): self.rebalancear()

    def bloquear_ui(self, bloquear=True):
        st = "disabled" if bloquear else "normal"
        for w in self.widgets_interactivos: 
            if hasattr(w, "winfo_exists") and w.winfo_exists(): w.configure(state=st)
        self.btn_modo_tools.configure(state=st)

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
        v = self.creventana_info_base("¿QUÉ ES BATOCERA?", 640, 360)
        frame_interno = ctk.CTkFrame(v, fg_color="transparent")
        frame_interno.pack(expand=True, fill="both", padx=25, pady=20)
        ctk.CTkLabel(frame_interno, text="🎮 SOBRE BATOCERA", font=("Impact", 30), text_color=AZUL_CIAN).pack(pady=(0, 15))
        info = ("Batocera es un sistema de emulación que puede convertir cualquier ordenador en una consola de videojuegos.\n\n🛡️ SEGURIDAD DE DATOS:\nAunque inicies Batocera, NUNCA perderás los datos del ordenador.")
        ctk.CTkLabel(frame_interno, text=info, font=("Segoe UI", 16), justify="center", wraplength=560).pack(pady=5)
        ctk.CTkButton(frame_interno, text="ENTENDIDO", font=("Segoe UI", 14, "bold"), fg_color=AZUL_ELECTRICO, height=42, width=180, command=v.destroy).pack(pady=(15, 0))
        v.update(); v.grab_set()

    def abrir_info_cachyos(self):
        v = self.creventana_info_base("¿QUÉ ES CACHYOS?", 700, 480)
        frame_interno = ctk.CTkFrame(v, fg_color="transparent")
        frame_interno.pack(expand=True, fill="both", padx=25, pady=20)
        ctk.CTkLabel(frame_interno, text="🚀 CACHYOS: ARCH LINUX OPTIMIZADO", font=("Impact", 30), text_color=COLOR_CACHY).pack(pady=(0, 15))
        info = ("He preparado una versión personalizada de CachyOS (Arch Linux) diseñada específicamente para ser rápida y fácil de usar.\n\n⚡ CARACTERÍSTICAS PRINCIPALES:\n• Universal: Funciona en casi cualquier PC moderno.\n• Rendimiento: Optimizado para sacar el máximo provecho al hardware.\n• Portable: Llevas tu sistema operativo, archivos y apps siempre contigo.")
        ctk.CTkLabel(frame_interno, text=info, font=("Segoe UI", 16), justify="center", wraplength=620).pack(pady=5)
        ctk.CTkButton(frame_interno, text="¡EXCELENTE!", font=("Segoe UI", 14, "bold"), fg_color=AZUL_ELECTRICO, height=42, width=180, command=v.destroy).pack(pady=(15, 0))
        v.update(); v.grab_set()
        
    def abrir_info_kde(self):
        v = self.creventana_info_base("INFO: KDE PLASMA", 540, 300)
        f = ctk.CTkFrame(v, fg_color="transparent")
        f.pack(expand=True, fill="both", padx=25, pady=20)
        ctk.CTkLabel(f, text="❄️ KDE PLASMA", font=("Impact", 26), text_color=AZUL_CIAN).pack(pady=(0, 10))
        info = "Es perfecto para los que quieren algo familiar como Windows. Es el entorno más fácil de usar de primeras, aunque ocupa algo más que Hyprland."
        ctk.CTkLabel(f, text=info, font=("Segoe UI", 16), justify="center", wraplength=480).pack(pady=5)
        ctk.CTkButton(f, text="ENTENDIDO", font=("Segoe UI", 13, "bold"), fg_color=AZUL_ELECTRICO, height=40, command=v.destroy).pack(pady=(15,0))
        v.update(); v.grab_set()

    def abrir_info_hyprland(self):
        v = self.creventana_info_base("INFO: HYPRLAND", 620, 340)
        f = ctk.CTkFrame(v, fg_color="transparent")
        f.pack(expand=True, fill="both", padx=25, pady=20)
        ctk.CTkLabel(f, text="🌀 HYPRLAND", font=("Impact", 26), text_color=COLOR_CACHY).pack(pady=(0, 10))
        info = "Uno de los escritorios más bonitos y fluidos para Linux. Es ideal para máxima productividad, consume poquísimos recursos y ofrece un control total del sistema."
        ctk.CTkLabel(f, text=info, font=("Segoe UI", 16), justify="center", wraplength=550).pack(pady=5)
        ctk.CTkButton(f, text="ENTENDIDO", font=("Segoe UI", 13, "bold"), fg_color=AZUL_ELECTRICO, height=40, command=v.destroy).pack(pady=(15,0))
        v.update(); v.grab_set()

    def abrir_ventana_info(self):
        v = self.creventana_info_base("SAVIN CORE INFO", 750, 780)
        frame_interno = ctk.CTkFrame(v, fg_color="transparent")
        frame_interno.pack(expand=True, fill="both", padx=25, pady=20)

        ctk.CTkLabel(frame_interno, text="👑 SAVIN HOLLOWDRIVE 👑", font=("Impact", 38), text_color=AZUL_CIAN).pack(pady=(0, 10))

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

        ctk.CTkLabel(frame_interno, text="◈ ¡MIRA ESTE VÍDEO PARA SABER CÓMO FUNCIONA! ◈", font=("Consolas", 16, "bold"), text_color=AZUL_SUAVE).pack(pady=(15, 5))
        url_video_youtube = "https://youtu.be/oHg5SJYRHA0?si=7nL_H5sIWuiLM4dp"

        f_video = ctk.CTkFrame(frame_interno, fg_color=AZUL_CARD, border_width=2, border_color=AZUL_ELECTRICO, width=480, height=270, corner_radius=15)
        f_video.pack_propagate(False)
        f_video.pack(pady=10)

        ruta_miniatura = resource_path("miniatura.png")
        try:
            img_raw = Image.open(ruta_miniatura)
            img_ctk = ctk.CTkImage(light_image=img_raw, dark_image=img_raw, size=(480, 270))
            lbl_fondo = ctk.CTkLabel(f_video, text="", image=img_ctk, corner_radius=15)
            lbl_fondo.place(relx=0.5, rely=0.5, anchor="center")
        except Exception: pass

        ruta_play = os.path.join(CARPETA_MEDIA, "play.png")
        try:
            img_play_raw = Image.open(ruta_play)
            self.img_play_ctk = ctk.CTkImage(light_image=img_play_raw, dark_image=img_play_raw, size=(75, 75))
            self.play_size = (75, 75)
        except Exception: self.img_play_ctk = None

        lbl_play = ctk.CTkLabel(
            f_video, 
            text="" if getattr(self, 'img_play_ctk', None) else "▶", 
            image=getattr(self, 'img_play_ctk', None),
            font=("Consolas", 65, "bold"),
            text_color="#ffffff",
            fg_color="transparent", 
            cursor="hand2"          
        )
        lbl_play.place(relx=0.5, rely=0.5, anchor="center")
        lbl_play.bind("<Button-1>", lambda e: webbrowser.open_new_tab(url_video_youtube))

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

        f_medicat = ctk.CTkFrame(frame_interno, fg_color="#181824", border_width=1, border_color=AZUL_ELECTRICO, corner_radius=6)
        f_medicat.pack(fill="x", padx=100, pady=(15, 10))

        lbl_thanks = ctk.CTkLabel(f_medicat, text="💖 Gracias a MediCat USB, que me inspiró a crear un USB cercano a la perfección✨.", 
                                  font=("Consolas", 11, "italic"), text_color="#dddddd", wraplength=480)
        lbl_thanks.pack(pady=8, padx=15)

        ctk.CTkButton(frame_interno, text="CERRAR", width=200, height=35, command=v.destroy).pack(pady=(15, 0))
        v.update(); v.grab_set()

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
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                tag_remoto = data["tag_name"].strip().lower().replace("v", "")
                version_local = VERSION_ACTUAL.strip().lower().replace("v", "")
                if tag_remoto != version_local:
                    url_exe_descarga = None
                    for asset in data.get("assets", []):
                        if asset["name"] == "HollowDrive.exe":
                            url_exe_descarga = asset["browser_download_url"]
                            break
                    if url_exe_descarga:
                        self.after(0, lambda: self.notificar_actualizacion(data["tag_name"], url_exe_descarga))
        except Exception: pass

    def notificar_actualizacion(self, nueva_version, url_descarga):
        msg = f"¡Hay una nueva versión disponible de HollowDrive ({nueva_version})!\n\n¿Deseas descargarla e instalarla ahora automáticamente?"
        if messagebox.askyesno("ACTUALIZACIÓN DETECTADA", msg):
            self.bloquear_ui(True)
            self.lbl_status.configure(text="DESCARGANDO NUEVA VERSIÓN... POR FAVOR ESPERA", text_color=AZUL_CIAN)
            threading.Thread(target=self.ejecutar_auto_update, args=(url_descarga,), daemon=True).start()

    def ejecutar_auto_update(self, url_descarga):
        try:
            exe_actual = os.path.abspath(sys.argv[0])
            if not exe_actual.endswith(".exe"):
                self.after(0, lambda: messagebox.showinfo("MODO DESARROLLO", f"Actualización ({GITHUB_REPO}) disponible.\nSaltando reemplazo físico porque estás ejecutando el script nativo de Python."))
                self.after(0, lambda: self.bloquear_ui(False))
                self.after(0, lambda: self.lbl_status.configure(text="ESPERANDO INICIO...", text_color=AZUL_SUAVE))
                return

            ruta_temporal_exe = exe_actual + ".tmp"
            response = requests.get(url_descarga, stream=True)
            if response.status_code != 200: raise RuntimeError(f"HTTP {response.status_code}")
                
            with open(ruta_temporal_exe, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk: f.write(chunk)

            ruta_bat = os.path.join(os.path.dirname(exe_actual), "hollow_updater.bat")
            with open(ruta_bat, "w", encoding="ansi") as f:
                f.write('@echo off\n')
                f.write('timeout /t 1 /nobreak > nul\n')
                f.write(f'del "{exe_actual}"\n')
                f.write(f'move "{ruta_temporal_exe}" "{exe_actual}"\n')
                f.write(f'start "" "{exe_actual}"\n')
                f.write('del "%~f0"\n')

            subprocess.Popen(["cmd.exe", "/c", ruta_bat], creationflags=subprocess.CREATE_NO_WINDOW)
            self.after(0, self.destroy)

        except Exception as e:
            logging.error(f"Fallo crítico en el proceso de auto-actualización: {e}")
            err_msg = str(e)
            self.after(0, lambda msg=err_msg: messagebox.showerror("ERROR DE ACTUALIZACIÓN", f"No se pudo completar la instalación de la nueva versión:\n{msg}"))
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
            "descargar_pack_bato": self.descargar_pack_bato.get(),
            "instalar_bato": self.instalar_bato.get(),
            "metodo_descarga": self.metodo_descarga.get(),
            "cachy_flavor": getattr(self, 'cachy_flavor', ctk.StringVar(value="kde")).get() # NUEVO
        }
        
        self.hilo_instalacion = threading.Thread(target=self.proceso_instalacion_background, args=(config,), daemon=True)
        self.hilo_instalacion.start()

    def alternar_gif_descarga(self, activo=True):
        if getattr(self, 'abortar_proceso', False):
            self.after(0, lambda: self.cambiar_gif(None))
            return
        if activo: 
            self.after(0, lambda: self.cambiar_gif(self.frames_breakdance))
        else: 
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
        v.update(); v.grab_set()

    # =====================================================================
    # 💥 PIPELINE COMPLETO DE INSTALACIÓN
    # =====================================================================

    def proceso_instalacion_background(self, config):
        self.after(0, lambda: self.cambiar_gif(self.frames_linterna))
        
        t_inicio_global = time.time()
        registro_tiempos = {}
        step_starts = {}
        letra_grub = None
        letra_cachy = None

        def iniciar_cronometro(nombre): step_starts[nombre] = time.time()
        def detener_cronometro(nombre):
            if nombre in step_starts:
                d = time.time() - step_starts[nombre]
                registro_tiempos[nombre] = d

        def limpiar_temporales():
            temp_dir = os.path.join(BASE_DIR, "engine", "temp_downloads")
            if os.path.exists(temp_dir): shutil.rmtree(temp_dir, ignore_errors=True)

        try:
            disk_index = config["disk_index"]
            cachy_gb = config["cachy_gb"]
            hollow_gb = config["hollow_gb"]               
            gb_totales = config["gb_totales"]             
            preservar_espacio = config["preservar_espacio"] 
            instalar_cachy = config["instalar_cachy"]
            descargar_pack_hollow = config["descargar_pack_hollow"]
            descargar_pack_bato = config["descargar_pack_bato"]
            instalar_bato = config["instalar_bato"]
            metodo_ext = config["metodo_descarga"]
            
            espacio_reservado_gb = (gb_totales - hollow_gb) if preservar_espacio else (cachy_gb + GB_GRUB if instalar_cachy else 0.0)
            
            tools_base = os.path.join(BASE_DIR, "engine")
            ventoy_dir = None
            if os.path.exists(tools_base):
                for root, dirs, files in os.walk(tools_base):
                    if "Ventoy2Disk.exe" in files:
                        ventoy_dir = root
                        break
            
            if not ventoy_dir: raise RuntimeError(f"No se encontró Ventoy2Disk.exe en: {tools_base}")

            def esperar_unidad_por_etiqueta(etiqueta, intentos=6, retardo=2):
                for i in range(intentos):
                    if self.abortar_proceso: raise InterruptedError("Proceso abortado.")
                    self.after(0, lambda idx_i=i: self.lbl_status.configure(text=f"Esperando montaje de '{etiqueta}' ({idx_i+1}/{intentos})...", text_color=AZUL_SUAVE))
                    letra = encontrar_letra_por_etiqueta_ps(etiqueta)
                    if letra: return letra
                    time.sleep(retardo)
                return None

            pasos_activos = ["ventoy"]
            if descargar_pack_bato: pasos_activos.append("pack_bato")     
            if descargar_pack_hollow: pasos_activos.append("pack_hollow") 
            else: pasos_activos.append("ventoy_base")
                
            if instalar_bato: pasos_activos.append("batocera_img")
            if instalar_cachy: pasos_activos.extend(["grub_part", "grub_extract", "cachy_part", "cachy_extract"])
                
            total_pasos = len(pasos_activos)
            paso_actual = 1

            def actualizar_progreso_paso(prog_interno, texto_paso):
                now = time.time()
                if not hasattr(actualizar_progreso_paso, "last_update"): actualizar_progreso_paso.last_update = 0.0
                if now - actualizar_progreso_paso.last_update < 0.1 and prog_interno < 1.0 and prog_interno > 0.0: return
                actualizar_progreso_paso.last_update = now

                prog_global = (paso_actual - 1 + prog_interno) / total_pasos
                self.after(0, lambda: self.p_task.set(prog_interno))
                self.after(0, lambda: self.p_total.set(prog_global))
                self.after(0, lambda txt=texto_paso, p_idx=paso_actual: self.lbl_status.configure(text=f"Paso {p_idx}/{total_pasos}: {txt}"))

            def generar_mensaje_progreso(nombre_tarea, bytes_read, total_bytes, start_time, fase_str, override_start_time=None):
                pct = (bytes_read / total_bytes) if (total_bytes and total_bytes > 0) else 0.0

                # Si la fase ya viene formateada con velocidad en tiempo real y ETA desde ETACalculator
                if "MB/s" in fase_str:
                    return pct, f"{nombre_tarea} | {pct*100:.1f}% | {fase_str}"

                # Cálculo por defecto para tareas tradicionales que solo pasan palabras clave ("Descargando", "Extrayendo")
                t_ref = override_start_time if override_start_time else start_time
                elapsed = time.time() - t_ref
                if elapsed > 0 and bytes_read > 0:
                    speed_bps = bytes_read / elapsed
                    speed_mbs = speed_bps / (1024 * 1024)
                    if total_bytes:
                        eta_secs = max(0, (total_bytes - bytes_read) / speed_bps) if speed_bps > 0 else 0
                        mins, secs = divmod(int(eta_secs), 60)
                        hrs, mins = divmod(mins, 60)
                        eta_str = f"{hrs:02d}:{mins:02d}:{secs:02d}" if hrs > 0 else f"{mins:02d}:{secs:02d}"
                        return pct, f"{nombre_tarea} [{fase_str}] | {pct*100:.1f}% | {speed_mbs:.1f} MB/s | Faltan: {eta_str}"
                    else:
                        return 0.5, f"{nombre_tarea} [{fase_str}] | {speed_mbs:.1f} MB/s"

                return 0.0 if total_bytes else 0.5, f"{nombre_tarea} | Calculando..."

            # PASO VENTOY CORE
            iniciar_cronometro("Estructura Core (Ventoy)")
            actualizar_progreso_paso(0.0, "Ejecutando particionamiento base...")
            def progreso_ventoy(porcentaje, mensaje):
                if self.abortar_proceso: raise InterruptedError()
                actualizar_progreso_paso(porcentaje / 100.0, f"Ventoy: {mensaje}")

            instalar_ventoy(disk_index=disk_index, reserved_space_gb=espacio_reservado_gb, ventoy_dir=ventoy_dir, progress_callback=progreso_ventoy)
            detener_cronometro("Estructura Core (Ventoy)")
            paso_actual += 1

            self.after(0, lambda: self.lbl_status.configure(text="Asentando almacenamiento...", text_color=AZUL_CIAN))
            time.sleep(6)
            
            try:
                ruta_rescan = os.path.join(BASE_DIR, "engine", "rescan.txt")
                with open(ruta_rescan, "w") as f: f.write("rescan\n")
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = subprocess.SW_HIDE
                subprocess.run(["diskpart", "/s", ruta_rescan], startupinfo=si, creationflags=subprocess.CREATE_NO_WINDOW)
                if os.path.exists(ruta_rescan): os.remove(ruta_rescan)
            except Exception: pass

            time.sleep(2)

            letra_hollow = None
            for i in range(12):
                if self.abortar_proceso: raise InterruptedError()
                letra = encontrar_letra_por_etiqueta_ps("Ventoy") or encontrar_letra_por_etiqueta_ps("HOLLOWDRIVE")
                if letra:
                    if encontrar_letra_por_etiqueta_ps("Ventoy") is not None:
                        subprocess.run(f"label {letra[:2]} HOLLOWDRIVE", shell=True)
                        time.sleep(1.5)
                        letra_hollow = encontrar_letra_por_etiqueta_ps("HOLLOWDRIVE") or letra
                    else: letra_hollow = letra
                    break
                time.sleep(2)
            
            if not letra_hollow:
                for letra_alt in [f"{chr(x)}:\\" for x in range(69, 91)]:
                    if os.path.exists(letra_alt):
                        letra_hollow = letra_alt
                        break

            if not letra_hollow: raise RuntimeError("No se detectó la letra de unidad física para HOLLOWDRIVE.")

            # PASO PACK ROMS BATOCERA
            if "pack_bato" in pasos_activos:
                iniciar_cronometro("Pack Roms Batocera")
                if self.abortar_proceso: raise InterruptedError()
                self.after(0, lambda: self.alternar_gif_descarga(True))
                actualizar_progreso_paso(0.0, "Descargando Pack Batocera...")
                
                try: url_pack_bato = MIRRORS_DATA["batocera_games"]["mirrors"][0]["url"]
                except KeyError: url_pack_bato = "https://huggingface.co/datasets/HollowDrive/HollowDrive/resolve/main/batocera-hollowpack.tar"
                
                t_start_bato_pack = time.time()
                def progreso_batocera_pack(bytes_read, total_bytes, fase, override_start=None):
                    pct, msg = generar_mensaje_progreso("Pack Batocera", bytes_read, total_bytes, t_start_bato_pack, fase, override_start)
                    actualizar_progreso_paso(pct, msg)

                stream_extract_tar(url_pack_bato, letra_hollow, is_gdrive=False, progress_callback=progreso_batocera_pack, abort_check=lambda: self.abortar_proceso, method=metodo_ext)
                self.after(0, lambda: self.alternar_gif_descarga(False))
                detener_cronometro("Pack Roms Batocera")
                paso_actual += 1

            # PASO PACK UTILS HOLLOWDRIVE
            if "pack_hollow" in pasos_activos:
                iniciar_cronometro("Pack Utils HollowDrive")
                if self.abortar_proceso: raise InterruptedError()
                self.after(0, lambda: self.alternar_gif_descarga(True))
                actualizar_progreso_paso(0.0, "Descargando Pack HollowDrive...")
                
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

            # PASO ESTRUCTURA BASE LOCAL VENTOY
            if "ventoy_base" in pasos_activos:
                iniciar_cronometro("Configuración Base Ventoy")
                if self.abortar_proceso: raise InterruptedError()
                ruta_tar_local = resource_path(os.path.join("engine", "resources", "ventoy.tar"))
                if os.path.exists(ruta_tar_local):
                    try:
                        with tarfile.open(ruta_tar_local, "r") as tar:
                            miembros = tar.getmembers()
                            total_m = len(miembros)
                            for idx, member in enumerate(miembros):
                                if self.abortar_proceso: raise InterruptedError()
                                tar.extract(member, path=letra_hollow)
                                pct = (idx + 1) / total_m
                                actualizar_progreso_paso(pct, f"Inyectando base local: {member.name[:30]} ({idx+1}/{total_m})")
                    except Exception as e: raise RuntimeError(f"Fallo al desempaquetar la configuración interna:\n{e}")
                detener_cronometro("Configuración Base Ventoy")
                paso_actual += 1

            # PASO BATOCERA OS
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

                stream_download_file_direct(
                    URL_BATOCERA, archivo_dest_bato, is_gdrive=is_gdrive_bato, 
                    progress_callback=progreso_batocera, abort_check=lambda: self.abortar_proceso
                )
                self.after(0, lambda: self.alternar_gif_descarga(False))
                detener_cronometro("Sistema Batocera OS")
                paso_actual += 1

            # PASO CACHYOS GRUB
            if "grub_part" in pasos_activos:
                iniciar_cronometro("Creación Bootloader GRUB")
                if self.abortar_proceso: raise InterruptedError()
                actualizar_progreso_paso(0.0, "Creando partición GRUB...")
                crear_particion_adicional(disk_index=disk_index, size_gb=GB_GRUB, label="GRUB", fs="fat32")
                letra_grub = esperar_unidad_por_etiqueta("GRUB", intentos=12, retardo=2)
                if not letra_grub: raise RuntimeError("Windows tardó demasiado en asignar letra a la partición 'GRUB'.")
                detener_cronometro("Creación Bootloader GRUB")
                paso_actual += 1

            # PASO FLASHEO DE GRUB
            if "grub_extract" in pasos_activos:
                iniciar_cronometro("Inyección Bootloader GRUB")
                if self.abortar_proceso: raise InterruptedError()
                self.after(0, lambda: self.alternar_gif_descarga(True))
                actualizar_progreso_paso(0.0, "Flasheando GRUB...")
                
                try: url_grub_hf = MIRRORS_DATA["cachyos_images"]["efi_grub"]["mirrors"][0]["url"]
                except KeyError: url_grub_hf = "https://huggingface.co/datasets/HollowDrive/HollowDrive/resolve/main/hollowdrive_cachy_efi.img"
                
                t_start_grub = time.time()
                def progreso_grub(bytes_read, total_bytes, fase, override_start=None):
                    pct, msg = generar_mensaje_progreso("Arranque GRUB", bytes_read, total_bytes, t_start_grub, fase, override_start)
                    actualizar_progreso_paso(pct, msg)

                if not letra_grub: letra_grub = encontrar_letra_por_etiqueta_ps("GRUB") or esperar_unidad_por_etiqueta("GRUB", intentos=6)
                
                stream_flash_image_direct(
                    url_grub_hf, letra_grub, 
                    progress_callback=progreso_grub, abort_check=lambda: self.abortar_proceso, 
                    method=metodo_ext
                )
                self.after(0, lambda: self.alternar_gif_descarga(False))
                detener_cronometro("Inyección Bootloader GRUB")
                paso_actual += 1

            # PASO CACHYOS SISTEMA
            if "cachy_part" in pasos_activos:
                iniciar_cronometro("Creación Partición CachyOS")
                if self.abortar_proceso: raise InterruptedError()
                actualizar_progreso_paso(0.0, "Generando partición CachyOS...")
                
                margen_seguridad = 0.15 if not preservar_espacio else 0.0
                tamano_seguro_cachy = max(1.0, cachy_gb - margen_seguridad)
                
                crear_particion_adicional(disk_index=disk_index, size_gb=tamano_seguro_cachy, label="CachyOS", fs="ntfs")
                letra_cachy = esperar_unidad_por_etiqueta("CachyOS", intentos=12, retardo=2)
                if not letra_cachy: raise RuntimeError("Windows tardó demasiado en asignar letra a 'CachyOS'.")
                detener_cronometro("Creación Partición CachyOS")
                paso_actual += 1

            # PASO VOLCADO SECTORIAL CACHYOS
            if "cachy_extract" in pasos_activos:
                iniciar_cronometro("Volcado Sistema CachyOS")
                if self.abortar_proceso: raise InterruptedError()
                self.after(0, lambda: self.alternar_gif_descarga(True))
                actualizar_progreso_paso(0.0, "Volcado sectorial de CachyOS...")
                
                sabor_elegido = config.get("cachy_flavor", "kde")
                if sabor_elegido == "hyprland":
                    try: url_cachy_hf = MIRRORS_DATA["cachyos_images"]["hyprland"]["mirrors"][0]["url"]
                    except KeyError: url_cachy_hf = "AQUI_IRÁ_EL_FUTURO_LINK_DE_HYPRLAND"
                else:
                    try: url_cachy_hf = MIRRORS_DATA["cachyos_images"]["sistema"]["mirrors"][0]["url"]
                    except KeyError: url_cachy_hf = "https://huggingface.co/datasets/HollowDrive/HollowDrive/resolve/main/hollowdrive_cachy_sistema.img"
                
                t_start_cachy = time.time()
                def progreso_cachy(bytes_read, total_bytes, fase, override_start=None):
                    pct, msg = generar_mensaje_progreso("CachyOS (Btrfs)", bytes_read, total_bytes, t_start_cachy, fase, override_start)
                    actualizar_progreso_paso(pct, msg)

                if not letra_cachy: letra_cachy = encontrar_letra_por_etiqueta_ps("CachyOS") or esperar_unidad_por_etiqueta("CachyOS", intentos=6)
                
                stream_flash_image_direct(
                    url_cachy_hf, letra_cachy, 
                    progress_callback=progreso_cachy, abort_check=lambda: self.abortar_proceso, 
                    method=metodo_ext
                )
                self.after(0, lambda: self.alternar_gif_descarga(False))
                detener_cronometro("Volcado Sistema CachyOS")

            self.after(0, lambda: self.p_total.set(1.0))
            self.after(0, lambda: self.p_task.set(1.0))
            
            tiempo_total = time.time() - t_inicio_global
            limpiar_temporales()
            self.after(0, lambda: self.mostrar_popup_exito(tiempo_total, registro_tiempos))

        except InterruptedError:
            limpiar_temporales()
            self.after(0, lambda: messagebox.showinfo("PROCESO CANCELADO", "Instalación abortada."))
            self.after(0, lambda: self.lbl_status.configure(text="CANCELADO", text_color="#aa3333"))
        except RuntimeError as e:
            limpiar_temporales()
            msg = str(e)
            self.after(0, lambda err_text=msg: messagebox.showerror("ERROR DE CONEXIÓN", err_text))
            self.after(0, lambda: self.p_total.set(0.0))
            self.after(0, lambda: self.p_task.set(0.0))
            if getattr(self, "compartir_errores", False): self.enviar_reporte_error("RuntimeError", msg)
        except Exception as e:
            limpiar_temporales()
            msg = str(e)
            logging.error(f"CRASH FATAL: {msg}", exc_info=True)
            
            # Notificar en la interfaz del programa
            self.after(0, lambda err_text=msg: messagebox.showerror("ERROR FATAL", f"Fallo de sistema:\n{err_text}"))
            self.after(0, lambda: self.p_total.set(0.0))
            self.after(0, lambda: self.p_task.set(0.0))
            
            # Enviar notificación automática a Discord
            self.enviar_reporte_error("System Crash / Unpack Error", msg)
            
        finally:
            self.en_proceso = False
            self.after(0, lambda: self.cambiar_gif(None))
            self.after(0, lambda: self.bloquear_ui(False))
            self.after(0, lambda: self.alternar_modo_instalacion(False))

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
        if self.instalar_cachy.get():
            self.f_cachy_opts.pack(fill="x", pady=5) # Aparecen las opciones de escritorio
            self.f_row_c.pack(fill="x", padx=20, pady=5, before=self.canvas)
        else:
            self.f_cachy_opts.pack_forget() # Desaparecen
            self.f_row_c.pack_forget()
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
            except Exception: pass
            self.gif_after_id = None
            
        if frames: 
            self.reproducir_gif(self.lbl_gif, frames, delay=80)
        else: 
            # [CORREGIDO] Usar la imagen fantasma en lugar de None
            if hasattr(self, 'dummy_img'):
                self.lbl_gif.configure(image=self.dummy_img)
                self.lbl_gif.image = self.dummy_img

    def animar_zoom(self, attr_img, attr_size, base_size, zoom_size, entrar):
        anim_key = f"{attr_img}_anim"
        prev_anim = getattr(self, anim_key, None)
        if prev_anim: self.after_cancel(prev_anim)
        
        tw, th = zoom_size if entrar else base_size
        
        def step():
            cw, ch = getattr(self, attr_size)
            if cw == tw and ch == th: return
            step_w = max(1, abs(tw - cw) // 4) * (1 if tw > cw else -1)
            step_h = max(1, abs(th - ch) // 4) * (1 if th > ch else -1)
            nw, nh = cw + step_w, ch + step_h
            if (step_w > 0 and nw >= tw) or (step_w < 0 and nw <= tw): nw = tw
            if (step_h > 0 and nh >= th) or (step_h < 0 and nh <= th): nh = th
            setattr(self, attr_size, (nw, nh))
            getattr(self, attr_img).configure(size=(nw, nh))
            anim_id = self.after(15, step)
            setattr(self, anim_key, anim_id)
            
        step()

    def abrir_info_ht_isos(self):
        v = self.creventana_info_base("INFORMACIÓN: AÑADIR ISOs", 640, 390)
        frame_interno = ctk.CTkFrame(v, fg_color="transparent")
        frame_interno.pack(expand=True, fill="both", padx=25, pady=20)
        ctk.CTkLabel(frame_interno, text="CD GESTOR DE IMÁGENES ISO", font=("Impact", 28), text_color=AZUL_CIAN).pack(pady=(0, 15))
        info = ("Esta función permite volcar imágenes de sistemas operativos (.iso) directamente a la carpeta /HOLLOWDRIVE/OSimages/ de tu unidad HollowDrive.\n\n"
                "• No requiere formatear la unidad.\n"
                "• Ventoy detectará automáticamente las ISOs añadidas al arrancar.\n"
                "• Puedes arrastrar los archivos directamente a la casilla o pulsar el botón (+).")
        ctk.CTkLabel(frame_interno, text=info, font=("Segoe UI", 16), justify="left", wraplength=560).pack(pady=5)
        ctk.CTkButton(frame_interno, text="ENTENDIDO", font=("Segoe UI", 13, "bold"), fg_color=AZUL_ELECTRICO, height=40, width=160, command=v.destroy).pack(pady=(15, 0))
        v.update(); v.grab_set()

    def abrir_info_ht_packs(self):
        v = self.creventana_info_base("INFORMACIÓN: INYECCIÓN DE PAQUETES", 660, 400)
        frame_interno = ctk.CTkFrame(v, fg_color="transparent")
        frame_interno.pack(expand=True, fill="both", padx=25, pady=20)
        ctk.CTkLabel(frame_interno, text="📦 INYECCIÓN DE CONTENIDO", font=("Impact", 28), text_color=AZUL_CIAN).pack(pady=(0, 15))
        info = ("Te permite descargar e inyectar paquetes pesados en un USB que ya ha sido creado anteriormente:\n\n"
                "• Batocera OS (.img): Actualiza o restaura el sistema de emulación base.\n"
                "• Pack ROMs: Inyecta el paquete de juegos y BIOS en la partición correspondiente.\n"
                "• Pack HollowDrive: Descarga el conjunto completo de utilidades de rescate.")
        ctk.CTkLabel(frame_interno, text=info, font=("Segoe UI", 16), justify="left", wraplength=580).pack(pady=5)
        ctk.CTkButton(frame_interno, text="ENTENDIDO", font=("Segoe UI", 13, "bold"), fg_color=AZUL_ELECTRICO, height=40, width=160, command=v.destroy).pack(pady=(15, 0))
        v.update(); v.grab_set()

    def abrir_info_ht_cachy(self):
        v = self.creventana_info_base("INFORMACIÓN: GESTIÓN CACHYOS", 660, 400)
        frame_interno = ctk.CTkFrame(v, fg_color="transparent")
        frame_interno.pack(expand=True, fill="both", padx=25, pady=20)
        ctk.CTkLabel(frame_interno, text="🚀 GESTOR CACHYOS Y PARTICIONES", font=("Impact", 28), text_color=COLOR_CACHY).pack(pady=(0, 15))
        info = ("Herramienta de mantenimiento específica para el sistema operativo CachyOS:\n\n"
                "• Reinstalar / Actualizar: Reflashea la partición de sistema y el arranque GRUB sin tocar la partición principal de Ventoy.\n"
                "• Instalación en Espacio Libre: Si tu USB tiene espacio sin asignar, crea las particiones necesarias e instala CachyOS en dicho espacio.")
        ctk.CTkLabel(frame_interno, text=info, font=("Segoe UI", 16), justify="left", wraplength=580).pack(pady=5)
        ctk.CTkButton(frame_interno, text="ENTENDIDO", font=("Segoe UI", 13, "bold"), fg_color=AZUL_ELECTRICO, height=40, width=160, command=v.destroy).pack(pady=(15, 0))
        v.update(); v.grab_set()

    def crear_barra_tarea_dinamica(self, id_tarea, titulo_inicial, color=AZUL_CIAN):
        """ Crea una nueva barra de progreso dedicada en el contenedor con scroll de HollowTools """
        if not hasattr(self, 'tareas_activas'):
            self.tareas_activas = {}

        if id_tarea in self.tareas_activas:
            self.tareas_activas[id_tarea].destruir()

        self.en_proceso = True

        if not self.footer.winfo_ismapped():
            self.footer.pack(fill="x", side="bottom", padx=20, pady=10)

        if not self.f_progress.winfo_ismapped():
            self.f_progress.pack(side="left", fill="both", expand=True, padx=(0, 10))

        self.lbl_status.pack_forget()
        self.p_task.pack_forget()
        self.p_total.pack_forget()

        if not self.f_tasks_scroll.winfo_ismapped():
            self.f_tasks_scroll.pack(fill="both", expand=True, side="left", padx=0, pady=0)

        item = ItemTareaProgreso(self.f_tasks_scroll, id_tarea, titulo_inicial, color_barra=color)
        self.tareas_activas[id_tarea] = item

        if not self.btn_cancel.winfo_ismapped():
            self.btn_cancel.pack(side="right", padx=10)

        self.update_idletasks()
        return item

    def actualizar_barra_tarea_dinamica(self, id_tarea, progreso, texto):
        """ Actualiza el porcentaje y estado de una barra específica """
        if hasattr(self, 'tareas_activas') and id_tarea in self.tareas_activas:
            self.after(0, lambda: self.tareas_activas[id_tarea].actualizar(progreso, texto))

    def eliminar_barra_tarea_dinamica(self, id_tarea):
        """ Elimina la barra al finalizar el proceso """
        if hasattr(self, 'tareas_activas') and id_tarea in self.tareas_activas:
            self.after(0, lambda: self.tareas_activas.pop(id_tarea).destruir())
            self.after(100, self._comprobar_tareas_restantes)

    def _comprobar_tareas_restantes(self):
        if hasattr(self, 'tareas_activas') and not self.tareas_activas:
            self.en_proceso = False
            self.bloquear_ui(False)
            self.alternar_modo_instalacion(False)
            
            self.f_tasks_scroll.pack_forget()
            self.p_task.pack(fill="x", padx=5, pady=2)
            self.p_total.pack(fill="x", padx=5, pady=2)

if __name__ == "__main__":
    if os.name == 'nt' and not es_administrador():
        root = tk.Tk()
        root.withdraw()
        messagebox.showwarning("PERMISOS REQUERIDOS", "Savin Super USB necesita permisos de administrador para gestionar los discos.")
        root.destroy()
        try: ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        except Exception as e: print(f"Error elevando permisos: {e}")
        sys.exit()

    app = SavinOceanicCommand()
    app.mainloop()