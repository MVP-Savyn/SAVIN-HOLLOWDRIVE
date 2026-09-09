import os
import sys
import time
from datetime import datetime

# =====================================================================
# 📋 CAPTURA INTEGRAL DE TERMINAL Y LOGGING DESDE EL PRIMER INSTANTE
# =====================================================================

if hasattr(sys, 'frozen') or '__compiled__' in globals():
    BASE_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LOGS_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

# Rotación de logs: conservar únicamente los 5 archivos más recientes
try:
    archivos_logs = [
        os.path.join(LOGS_DIR, f) for f in os.listdir(LOGS_DIR)
        if f.endswith(".log")
    ]
    archivos_logs.sort(key=os.path.getmtime)
    while len(archivos_logs) > 4:
        f_antiguo = archivos_logs.pop(0)
        try: os.remove(f_antiguo)
        except Exception: pass
except Exception:
    pass

timestamp_inicio = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
archivo_log = os.path.join(LOGS_DIR, f"hollowdrive_{timestamp_inicio}.log")

class TerminalCaptureStream:
    """
    Captura TODO lo que sale por la terminal (print, stdout, stderr, errores)
    en tiempo real de principio a fin, escribiéndolo simultáneamente en pantalla y en el archivo log.
    """
    def __init__(self, original_stream, log_file_path):
        self.original_stream = original_stream
        self.log_file_path = log_file_path
        self._f = open(log_file_path, "a", encoding="utf-8", buffering=1)

    def write(self, message):
        if self.original_stream is not None:
            try:
                self.original_stream.write(message)
                self.original_stream.flush()
            except Exception:
                pass
        if self._f and not self._f.closed:
            try:
                self._f.write(message)
                self._f.flush()
            except Exception:
                pass

    def flush(self):
        if self.original_stream is not None:
            try:
                self.original_stream.flush()
            except Exception:
                pass
        if self._f and not self._f.closed:
            try:
                self._f.flush()
            except Exception:
                pass

    def isatty(self):
        return getattr(self.original_stream, "isatty", lambda: False)()

_orig_stdout = sys.__stdout__ if sys.__stdout__ is not None else sys.stdout
_orig_stderr = sys.__stderr__ if sys.__stderr__ is not None else sys.stderr

sys.stdout = TerminalCaptureStream(_orig_stdout, archivo_log)
sys.stderr = TerminalCaptureStream(_orig_stderr, archivo_log)

import logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def unhandled_exception_handler(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.critical("CRASH NO CONTROLADO (sys.excepthook):", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = unhandled_exception_handler

import threading
if hasattr(threading, 'excepthook'):
    def thread_exception_handler(args):
        if issubclass(args.exc_type, KeyboardInterrupt):
            return
        logging.critical(f"CRASH EN HILO [{args.thread.name}] (threading.excepthook):", exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
    threading.excepthook = thread_exception_handler

import io
import queue
import shutil  
import webbrowser
import subprocess
import re
import tarfile
import requests
import json
import ctypes
from urllib.parse import urlparse
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Token de Acceso Hugging Face (Requerido para evitar límites anónimos en la CDN)
HF_TOKEN = "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"
from ctypes import wintypes
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

import engine.i18n as i18n
from engine.i18n import t

# Importaciones del motor local
from engine.download_manager import descargar_y_extraer_ventoy, resolver_tamano_pack
try:
    from engine.download_manager import formatted_size as formatear_tamano
except ImportError:
    from engine.download_manager import formatear_tamano
from engine.disk_logic import (
    iniciar_escuchador_usb as iniciar_escuchador_usb_engine,
    obtener_unidades_usb,
    instalar_ventoy,
    crear_particion_adicional,
    obtener_estructura_disco_ps,
    ejecutar_powershell_seguro,
    _disk_query_lock
)

GITHUB_REPO = "MVP-Savyn/SAVIN-HOLLOWDRIVE"
URL_MIRRORS_GITHUB = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/engine/mirrors.json"

class CTkToolTip:
    """
    Muestra un tooltip flotante cuando el usuario mantiene el cursor sobre un widget
    durante el tiempo especificado (500ms por defecto).
    """
    def __init__(self, widget, text="Recargar", delay_ms=500):
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

def hacer_combobox_clicable_total(combobox):
    """
    Permite abrir y contraer (toggle) el menú desplegable al hacer clic sobre cualquier
    parte del control (caja de entrada, flecha o fondo) con cursor hand2 de forma totalmente segura.
    Si el menú ya está desplegado, el clic lo contrae en lugar de volver a abrirlo desde cero.
    """
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
        # Si el menú se acaba de cerrar (por este mismo clic del usuario que lo contrae), no volver a desplegar
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
# 🛠️ UTILIDADES GLOBALES DE SISTEMA Y ENTORNO (COLUMNA 0)
# =====================================================================

def es_administrador():
    """ Comprueba si la aplicación tiene privilegios de Administrador en Windows """
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

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
    """
    Resuelve la ruta a los recursos internos empaquetados por Nuitka (--onefile)
    o el entorno de desarrollo local.
    """
    if "NUITKA_ONEFILE_DIRECTORY" in os.environ:
        base_path = os.environ["NUITKA_ONEFILE_DIRECTORY"]
    elif hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
        
    return os.path.join(base_path, relative_path)

if hasattr(sys, 'frozen') or '__compiled__' in globals():
    BASE_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CARPETA_MEDIA = resource_path("media")

def asegurar_herramientas_externas():
    """
    Garantiza que la carpeta engine/ (con Ventoy y 7-Zip) exista físicamente
    junto al ejecutable, extrayéndola del interior del .exe en el primer arranque.
    """
    destino_engine = os.path.join(BASE_DIR, "engine")
    
    if os.path.exists(destino_engine):
        for root, dirs, files in os.walk(destino_engine):
            for f in files:
                if f.lower() == "ventoy2disk.exe":
                    return root

    origen_engine = resource_path("engine")
    
    if os.path.exists(origen_engine) and os.path.normpath(origen_engine).lower() != os.path.normpath(destino_engine).lower():
        logging.info(f"📦 [DESPLIEGUE] Copiando recursos desde {origen_engine} hacia {destino_engine}...")
        try:
            os.makedirs(destino_engine, exist_ok=True)
            shutil.copytree(origen_engine, destino_engine, dirs_exist_ok=True)
            logging.info(f"✔ [DESPLIEGUE] Carpeta engine desplegada con éxito en: {destino_engine}")
        except Exception as e:
            logging.error(f"Error desplegando engine: {e}")

    if os.path.exists(destino_engine):
        for root, dirs, files in os.walk(destino_engine):
            for f in files:
                if f.lower() == "ventoy2disk.exe":
                    return root

    return None

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

# --- CONFIGURACIÓN ESTÉTICA ADAPTATIVA (CLARO / OSCURO) ---
ctk.set_appearance_mode("Dark")

AZUL_FONDO = ("#e2e8f0", "#05080a")
AZUL_CARD = ("#ffffff", "#0d1117")
AZUL_CARD_INNER = ("#f1f5f9", "#090d12")
AZUL_CIAN = ("#0284c7", "#00d4ff")
AZUL_ELECTRICO = ("#2563eb", "#005eff")
AZUL_SUAVE = ("#1d4ed8", "#70a1ff")
COLOR_BORDE = ("#cbd5e1", "#1e293b")

COLOR_HOLLOW = "#2563eb"
COLOR_CACHY  = "#10b981"
COLOR_LIMINE = "#64748b"
COLOR_LIBRE  = "#1e293b"
VERDE_EXITO = "#2ecc71"
MODO_DEBUG = True

def _calc_brillo(hex_color, factor=1.35):
    try:
        h = hex_color.lstrip('#')
        rgb = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
        return "#{:02x}{:02x}{:02x}".format(*[min(255, max(0, int(c * factor))) for c in rgb])
    except Exception:
        return hex_color

def _calc_sombra(hex_color, factor=0.65):
    try:
        h = hex_color.lstrip('#')
        rgb = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
        return "#{:02x}{:02x}{:02x}".format(*[min(255, max(0, int(c * factor))) for c in rgb])
    except Exception:
        return hex_color

def color_canvas_actual():
    """ Devuelve el color de fondo en formato string simple para los Canvas de Tkinter """
    return AZUL_CARD[0] if ctk.get_appearance_mode() == "Light" else AZUL_CARD[1]

# =====================================================================
# ⚡ MOTOR DE EXTRACCIÓN, RED Y ALMACENAMIENTO (COLUMNA 0)
# =====================================================================

def formatear_eta(segundos):
    """ Convierte segundos a formato hh:mm:ss o mm:ss """
    if segundos <= 0 or segundos > 86400: return "--:--"
    mins, secs = divmod(int(segundos), 60)
    hrs, mins = divmod(mins, 60)
    return f"{hrs:02d}:{mins:02d}:{secs:02d}" if hrs > 0 else f"{mins:02d}:{secs:02d}"

class ETACalculator:
    def __init__(self, total_bytes, window_size=5.0):
        self.total_bytes = total_bytes
        self.history = [(time.time(), 0)]
        self.window_size = window_size
        self.last_speed = 0.0

    def update(self, bytes_actuales):
        now = time.time()
        self.history.append((now, bytes_actuales))
        
        while len(self.history) > 1 and (now - self.history[0][0]) > self.window_size:
            self.history.pop(0)

        dt = now - self.history[0][0]
        db = bytes_actuales - self.history[0][1]
        
        if dt > 0:
            self.last_speed = (db / (1024 * 1024)) / dt
        
        if self.total_bytes and self.last_speed > 0:
            bytes_restantes = max(0, self.total_bytes - bytes_actuales)
            eta_sec = (bytes_restantes / (1024 * 1024)) / self.last_speed
        else:
            eta_sec = 0

        return self.last_speed, eta_sec

class AsyncBufferStream(object):
    def __init__(self, response, progress_callback=None, total_size=None, abort_check=None):
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

def obtener_ruta_7z():
    """ Localiza el binario de consola 7z.exe en engine/resources """
    posibles_rutas = [
        resource_path(os.path.join("engine", "resources", "7z.exe")),
        resource_path(os.path.join("engine", "7z.exe")),
        "7z.exe"
    ]
    for ruta in posibles_rutas:
        if os.path.exists(ruta):
            return ruta
    return None

def agregar_exclusion_antivirus(ruta_o_unidad):
    """ Añade la unidad/carpeta a las exclusiones de Windows Defender vía PowerShell """
    if os.name == 'nt' and es_administrador():
        try:
            cmd = f'powershell -Command "Add-MpPreference -ExclusionPath \'{ruta_o_unidad}\'"'
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = subprocess.SW_HIDE
            subprocess.run(cmd, shell=True, startupinfo=si, creationflags=subprocess.CREATE_NO_WINDOW)
            logging.info(f"Exclusión de Windows Defender añadida para: {ruta_o_unidad}")
        except Exception as e:
            logging.warning(f"No se pudo añadir la exclusión del antivirus: {e}")

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

def generar_stream_resiliente_v2(url, chunk_size=512*1024, abort_check=None):
    """
    Motor de Red de Flujo Continuo:
    Descarga una parte completa con bypass de certificados interceptados por antivirus (session.verify = False).
    """
    if not url or not isinstance(url, str) or not url.startswith("http"):
        raise ValueError(f"URL no válida: '{url}'")

    domain = urlparse(url).netloc
    is_hf = "huggingface.co" in domain

    session = requests.Session()
    session.verify = False

    headers_base = {
        "User-Agent": "HollowDrive-Installer/1.1", 
        "Connection": "keep-alive",
        "Accept-Encoding": "identity"
    }
    if is_hf and HF_TOKEN:
        headers_base["Authorization"] = f"Bearer {HF_TOKEN}"

    session.headers.update(headers_base)

    try:
        head_res = session.head(url, allow_redirects=True, timeout=6.0)
        total_size = int(head_res.headers.get('Content-Length', 0)) or None
    except Exception:
        total_size = None

    def stream_generator():
        bytes_read = 0
        retries = 0
        max_retries = 8

        while True:
            if abort_check and abort_check():
                raise InterruptedError()

            req_headers = {}
            if bytes_read > 0:
                req_headers["Range"] = f"bytes={bytes_read}-"
                logging.info(f"🔄 [RED] Reanudando descarga desde byte {bytes_read} ({bytes_read / (1024**2):.1f} MB)...")

            try:
                with session.get(url, headers=req_headers, stream=True, timeout=(6.0, 12.0)) as response:
                    if bytes_read > 0 and response.status_code not in (200, 206):
                        raise RuntimeError(f"El servidor rechazó el rango HTTP (Status: {response.status_code})")
                    response.raise_for_status()

                    retries = 0

                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if abort_check and abort_check():
                            raise InterruptedError()

                        if chunk:
                            bytes_read += len(chunk)
                            yield chunk

                    logging.info(f"✔ Parte descargada con éxito ({bytes_read / (1024**2):.1f} MB).")
                    return

            except (requests.RequestException, RuntimeError, TimeoutError) as e:
                if hasattr(e, 'response') and e.response is not None and e.response.status_code == 416:
                    return

                retries += 1
                if retries > max_retries:
                    raise RuntimeError(f"Conexión de red fallida tras {max_retries} intentos: {e}")
                
                logging.warning(f"⚠️ [RED] Pausa de red detectada ({e}). Reintentando {retries}/{max_retries} en 2s...")
                time.sleep(2)

    return stream_generator(), total_size

def stream_extract_tar(url_or_id=None, target_dir="", dest_dir=None, is_gdrive=False, 
                       progress_callback=None, abort_check=None, method="ram", 
                       custom_stream=None, custom_total_size=None):
    directorio_destino = dest_dir or target_dir
    os.makedirs(directorio_destino, exist_ok=True)

    ruta_7z = obtener_ruta_7z()
    
    if ruta_7z:
        cmd = [ruta_7z, "x", "-si", "-ttar", f"-o{directorio_destino}", "-y"]
    else:
        cmd = ["tar", "-xf", "-", "-C", directorio_destino]

    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = subprocess.SW_HIDE

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        startupinfo=si,
        creationflags=subprocess.CREATE_NO_WINDOW
    )

    bytes_read = 0
    total_size = custom_total_size

    if custom_stream:
        stream = custom_stream
    elif is_gdrive or (url_or_id and "drive.google.com" in url_or_id):
        match = re.search(r'/d/([a-zA-Z0-9_-]+)', url_or_id) if url_or_id else None
        file_id = match.group(1) if match else url_or_id
        res = obtener_stream_gdrive(file_id)
        if res.status_code != 200:
            raise RuntimeError(f"Fallo de conexión GDrive: HTTP {res.status_code}")
        total_size = total_size or int(res.headers.get('Content-Length', 0)) or None
        stream = res.iter_content(chunk_size=8 * 1024 * 1024)
    else:
        stream, total_size_net = generar_stream_resiliente_v2(
            url_or_id, chunk_size=8 * 1024 * 1024, abort_check=abort_check
        )
        total_size = total_size or total_size_net

    eta_calc = ETACalculator(total_size) if total_size else None
    last_ui_update = 0.0

    try:
        for chunk in stream:
            if abort_check and abort_check():
                proc.kill()
                raise InterruptedError("Extracción cancelada por el usuario.")

            if chunk:
                proc.stdin.write(chunk)
                proc.stdin.flush()
                bytes_read += len(chunk)

                now = time.perf_counter()
                if progress_callback and (now - last_ui_update >= 0.5):
                    last_ui_update = now
                    mb_s, eta_sec = eta_calc.update(bytes_read) if eta_calc else (None, None)
                    msg = f"Extrayendo (7-Zip): {mb_s:.1f} MB/s | Faltan: {formatear_eta(eta_sec)}" if mb_s else "Extrayendo datos a USB..."
                    progress_callback(bytes_read, total_size or bytes_read, msg)

        proc.stdin.close()
        proc.wait()

        if proc.returncode != 0:
            err = proc.stderr.read().decode('utf-8', errors='ignore')
            raise RuntimeError(f"Error en extracción (código {proc.returncode}): {err}")

    except Exception as e:
        proc.kill()
        raise e

def stream_download_file_direct(url_or_id, dest_path, is_gdrive=False, progress_callback=None, abort_check=None):
    if is_gdrive:
        match = re.search(r'/d/([a-zA-Z0-9_-]+)', url_or_id)
        file_id = match.group(1) if match else url_or_id
        response = obtener_stream_gdrive(file_id)
        if response.status_code != 200: raise RuntimeError(f"Fallo HTTP {response.status_code}")
        total_size = int(response.headers.get('Content-Length', 0)) or None
        stream, eta_calc = response.iter_content(chunk_size=2*1024*1024), ETACalculator(total_size) if total_size else None
    else:
        stream, total_size = generar_stream_resiliente_v2(url_or_id, chunk_size=2*1024*1024, abort_check=abort_check)
        eta_calc = ETACalculator(total_size) if total_size else None

    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    bytes_read = 0
    last_ui_update = 0.0

    with open(dest_path, "wb") as f:
        for chunk in stream:
            if abort_check and abort_check(): raise InterruptedError()
            f.write(chunk)
            f.flush()
            bytes_read += len(chunk)
            
            now = time.time()
            if progress_callback and eta_calc and (now - last_ui_update >= 1.0):
                last_ui_update = now
                mb_s, eta_sec = eta_calc.update(bytes_read)
                if mb_s is not None:
                    progress_callback(bytes_read, total_size, f"Descargando: {mb_s:.1f} MB/s | Faltan: {formatear_eta(eta_sec)}")
                    
        if progress_callback:
            progress_callback(bytes_read, total_size, "Descarga completada, vaciando búferes...")

def stream_flash_image_direct(url, letra_unidad, progress_callback=None, abort_check=None, method="ram"):
    """ Volcado RAW con precarga en RAM y diagnóstico calibrado """
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
        logging.info("=======================================================")
        logging.info(f"[DIAGNÓSTICO RAM] Iniciando Stream Directo a USB: {ruta_raw}")
        logging.info("=======================================================")

        if progress_callback: progress_callback(0, 100, "Conectando al servidor...")
        
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
                
                if dt_write > 0.8 or t_wait_queue > 2.5:
                    q_level = cola_bloques.qsize()
                    if dt_write > 0.8:
                        logging.warning(f"[{pct:5.1f}%] [RAM -> USB] {bytes_escritos/(1024*1024):.0f} MB | WriteFile lento: {dt_write*1000:5.0f} ms | Cola: {q_level:3d}/{MAX_COLA}")
                    elif t_wait_queue > 2.5:
                        logging.warning(f"[{pct:5.1f}%] [RAM -> USB] {bytes_escritos/(1024*1024):.0f} MB | Parón de Red: esperó {t_wait_queue:.2f}s | Cola: {q_level:3d}/{MAX_COLA}")
                elif i_bloque % 50 == 0:
                    logging.info(f"[{pct:5.1f}%] [RAM -> USB] {bytes_escritos/(1024*1024):.0f} MB | WriteFile: {dt_write*1000:5.0f} ms | Cola: {cola_bloques.qsize():3d}/{MAX_COLA}")

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
        logging.info("=======================================================")
        logging.info(f"[DIAGNÓSTICO SSD] Iniciando descarga previa a disco para: {ruta_raw}")
        logging.info("=======================================================")

        temp_dir = os.path.join(BASE_DIR, "engine", "temp_downloads")
        os.makedirs(temp_dir, exist_ok=True)
        temp_img = os.path.join(temp_dir, "temp_flash.img")

        stream_gen, total_size = generar_stream_resiliente_v2(url, chunk_size=2*1024*1024, abort_check=abort_check)

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
        cmd = f'[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; Get-Volume | Where-Object {{$_.FileSystemLabel -eq "{label}"}} | Select-Object -ExpandProperty DriveLetter'
        output = ejecutar_powershell_seguro(cmd)
        clean_output = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', output).strip()
        if clean_output and len(clean_output) == 1 and clean_output.isalpha():
            return f"{clean_output.upper()}:\\"
    except Exception as e: logging.error(f"Error detectando volumen '{label}': {e}")
    return None

def asignar_letra_particion_ps(disk_index, part_number):
    try:
        cmd_used = "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; Get-Volume | Select-Object -ExpandProperty DriveLetter"
        out = ejecutar_powershell_seguro(cmd_used)
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
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        with _disk_query_lock:
            subprocess.run(["diskpart", "/s", script_path], startupinfo=si, creationflags=subprocess.CREATE_NO_WINDOW)
        if os.path.exists(script_path): os.remove(script_path)
        time.sleep(1.5)
        return f"{free_letter}:\\"
    except Exception as e:
        logging.error(f"Fallo asignando letra a disco {disk_index} part {part_number}: {e}")
        return None

def obtener_o_asignar_letras_cachyos_grub(disk_index):
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
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    total_size = os.path.getsize(origen)
    bytes_copiados = 0

    with open(origen, "rb") as f_src, open(destino, "wb") as f_dst:
        buffer_size = 2 * 1024 * 1024
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
# 🖥️ COMPONENTES DE INTERFAZ Y CLASE PRINCIPAL
# =====================================================================

class ItemTareaProgreso:
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

    def after(self, ms, func=None, *args):
        try:
            if self.winfo_exists():
                return super().after(ms, func, *args)
        except Exception:
            pass
        return None

    def __init__(self):
        super().__init__()
        self.title(f"SAVIN SUPER_USB // V{VERSION_ACTUAL}")
        
        self.update_idletasks()
        self.geometry(f"1000x895+{(self.winfo_screenwidth() // 2) - 500}+{(self.winfo_screenheight() // 2) - 447}")
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

        # Valores de particiones para la barra interactiva unificada
        self.val_hollow_gb = 150.0
        self.val_cachy_gb = 100.0
        self.val_libre_gb = 0.0
        self._active_handle = None
        self._pos_h1 = 0
        self._pos_h2 = 0

        # Adaptadores para que el instalador de fondo siga leyendo .get() sin tocar nada
        class _ValHolder:
            def __init__(self, getter): self.getter = getter
            def get(self): return self.getter()
            def set(self, v): pass
            def configure(self, **kw): pass

        self.slider_h = _ValHolder(lambda: self.val_hollow_gb)
        self.slider_c = _ValHolder(lambda: self.val_cachy_gb)
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
        self.attributes("-alpha", 1.0)
        
        self.cargar_recursos() 
        self.setup_ui()
        self.actualizar_textos_idioma()
        
        if HAS_WINDND:
            self.after(500, lambda: enganchar_drag_drop_global_win32(self.winfo_id(), self.al_arrastrar_archivos_iso))

        self.actualizar_estados_bato()
        self.actualizar_estados_cachy()
        self.refrescar_discos()
        self._iniciar_escuchador_usb_timer()
        self.iniciar_watchdog()

        self.iniciar_carga_tamanos_reales()
        
        asegurar_herramientas_externas()
        self.bloquear_ui(False)
        self.after(250, self.abrir_ventana_info)
        
        self.protocol("WM_DELETE_WINDOW", self.cerrar_aplicacion)
        self.after(1000, lambda: threading.Thread(target=self.comprobar_actualizaciones, daemon=True).start())
        self.after(1500, self.preguntar_telemetria_errores)

    def descargar_y_extraer_batocera_pack(self, ruta_destino_batocera, callback_progreso_externo=None):
        games_section = getattr(self, "mirrors", {}).get("batocera_games", MIRRORS_DATA.get("batocera_games", {}))
        mirrors_list = games_section.get("parts", games_section.get("mirrors", []))
        urls = [m["url"] for m in mirrors_list if isinstance(m, dict) and "url" in m]
        
        if not urls:
            raise ValueError("No se encontraron URLs válidas para batocera_games en mirrors.json")

        modo = self.metodo_descarga.get() if hasattr(self, "metodo_descarga") else "ram"
        total_size = int(self.tamanos_reales.get("pack_bato", 37.8) * (1024**3))

        def progreso_ui(bytes_read, t_size, msg):
            pct = bytes_read / t_size if t_size and t_size > 0 else 0
            if callback_progreso_externo:
                callback_progreso_externo(pct, msg)
            elif hasattr(self, 'tareas_activas') and "pack_bato" in self.tareas_activas:
                task = self.tareas_activas["pack_bato"]
                self.after(0, lambda: task.actualizar(pct, msg))

        if modo == "disco":
            temp_dir = os.path.join(BASE_DIR, "engine", "temp_downloads")
            os.makedirs(temp_dir, exist_ok=True)
            archivos_temporales = []

            try:
                bytes_totales_descargados = 0
                eta_calc = ETACalculator(total_size)
                
                for idx, url in enumerate(urls, start=1):
                    if getattr(self, "abortar_proceso", False):
                        raise InterruptedError()
                    
                    nombre_parte = f"batocera_part_{idx}.tmp"
                    dest_path = os.path.join(temp_dir, nombre_parte)
                    archivos_temporales.append(dest_path)
                    
                    logging.info(f"💾 Descargando parte {idx}/{len(urls)} a disco: {url}")
                    
                    stream_gen, _ = generar_stream_resiliente_v2(
                        url, 
                        abort_check=lambda: getattr(self, "abortar_proceso", False)
                    )
                    
                    with open(dest_path, "wb") as f_out:
                        for chunk in stream_gen:
                            if getattr(self, "abortar_proceso", False):
                                raise InterruptedError()
                            f_out.write(chunk)
                            bytes_totales_descargados += len(chunk)
                            mb_s, eta_sec = eta_calc.update(bytes_totales_descargados)
                            if mb_s is not None:
                                progreso_ui(bytes_totales_descargados, total_size, f"Descargando ({idx}/{len(urls)}): {mb_s:.1f} MB/s | Faltan: {formatear_eta(eta_sec)}")

                def stream_desde_disco():
                    for temp_file in archivos_temporales:
                        with open(temp_file, "rb") as f_in:
                            while True:
                                if getattr(self, "abortar_proceso", False):
                                    return
                                buf = f_in.read(4 * 1024 * 1024)
                                if not buf:
                                    break
                                yield buf

                stream_extract_tar(
                    target_dir=ruta_destino_batocera,
                    progress_callback=progreso_ui,
                    abort_check=lambda: getattr(self, "abortar_proceso", False),
                    method="ram",
                    custom_stream=stream_desde_disco(),
                    custom_total_size=total_size
                )

            finally:
                for temp_file in archivos_temporales:
                    if os.path.exists(temp_file):
                        try: os.remove(temp_file)
                        except Exception: pass

        else:
            def stream_multi_parte():
                for index, url in enumerate(urls, start=1):
                    logging.info(f"🔗 Extrayendo al vuelo parte {index}/{len(urls)}")
                    stream_gen, _ = generar_stream_resiliente_v2(
                        url, 
                        abort_check=lambda: getattr(self, "abortar_proceso", False)
                    )
                    for chunk in stream_gen:
                        if getattr(self, "abortar_proceso", False):
                            return
                        yield chunk

            stream_extract_tar(
                target_dir=ruta_destino_batocera,
                progress_callback=progreso_ui,
                abort_check=lambda: getattr(self, "abortar_proceso", False),
                method="ram", 
                custom_stream=stream_multi_parte(),
                custom_total_size=total_size
            )

    def verificar_conexion_servidores(self):
        urls = ["https://huggingface.co", "https://pub-988eebcee5e94631a55af8a89d12129d.r2.dev"]
        for u in urls:
            try:
                r = requests.head(u, timeout=3)
                if r.status_code < 500: return True
            except Exception: continue
        return False

    def verificar_herramientas(self):
        engine_path = resource_path("engine")
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
            except Exception: pass
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
        v = self.creventana_info_base(t("modals.ventoy_core_title"), 640, 420)
        frame_interno = ctk.CTkFrame(v, fg_color="transparent")
        frame_interno.pack(expand=True, fill="both", padx=25, pady=20)
        ctk.CTkLabel(frame_interno, text=t("modals.ventoy_core_header"), font=("Impact", 28), text_color=AZUL_CIAN).pack(pady=(0, 15))
        ctk.CTkLabel(frame_interno, text=t("modals.ventoy_core_body"), font=("Segoe UI", 16), justify="center", wraplength=560).pack(pady=5)
        
        f_botones = ctk.CTkFrame(frame_interno, fg_color="transparent")
        f_botones.pack(pady=(20, 0))
        ctk.CTkButton(f_botones, text=f"{t('modals.initial.visit')} Ventoy", font=("Segoe UI", 13, "bold"), fg_color=AZUL_CARD, border_width=1, border_color=AZUL_CIAN, height=42, width=180, command=lambda: self.abrir_url("https://www.ventoy.net")).pack(side="left", padx=10)
        ctk.CTkButton(f_botones, text=t("modals.btn_close"), font=("Segoe UI", 13, "bold"), fg_color=AZUL_ELECTRICO, height=42, width=140, command=v.destroy).pack(side="left", padx=10)
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

    def iniciar_watchdog(self):
        try:
            watchdog_script = os.path.join(BASE_DIR, "engine", "watchdog.py")
            if os.path.exists(watchdog_script):
                subprocess.Popen(
                    [sys.executable, watchdog_script, str(os.getpid()), archivo_log],
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                logging.info(f"✔ Proceso Watchdog de soporte iniciado para PID {os.getpid()}")
        except Exception as e:
            logging.warning(f"No se pudo iniciar el proceso Watchdog: {e}")

    def _iniciar_escuchador_usb_timer(self):
        if os.name != 'nt': return
        try:
            self._mask_drives_anterior = ctypes.windll.kernel32.GetLogicalDrives()
        except Exception:
            self._mask_drives_anterior = 0
        self.after(1500, self._escuchar_usb_timer)

    def _escuchar_usb_timer(self):
        if not self.winfo_exists(): return
        try:
            mask_actual = ctypes.windll.kernel32.GetLogicalDrives()
            if hasattr(self, '_mask_drives_anterior') and mask_actual != self._mask_drives_anterior:
                self._mask_drives_anterior = mask_actual
                self.auto_refrescar_unidades_usb()
        except Exception:
            pass
        finally:
            if not getattr(self, 'en_proceso', False):
                self.after(1500, self._escuchar_usb_timer)

    def auto_refrescar_unidades_usb(self):
        if getattr(self, 'en_proceso', False):
            return
        if getattr(self, '_refrescando_discos', False):
            return
        self.refrescar_discos()
        if hasattr(self, 'refrescar_discos_hollowtools'):
            self.refrescar_discos_hollowtools()

    def ocultar_interfaz_instalador(self):
        if hasattr(self, 'main_container'):
            try:
                self.main_container.pack_forget()
            except Exception:
                pass
        if hasattr(self, 'footer') and not getattr(self, 'en_proceso', False):
            try:
                self.footer.pack_forget()
            except Exception:
                pass

    def refrescar_discos(self):
        if getattr(self, 'en_proceso', False):
            return

        self.combo_disk.configure(values=[t("selector.searching")])
        self.combo_disk.set(t("selector.searching"))
        self.ocultar_interfaz_instalador()
        if getattr(self, '_refrescando_discos', False):
            return
        self._refrescando_discos = True
        self.btn_refresh.configure(state="disabled")
        incluir_internos = self.mostrar_internos.get()
        
        def run():
            try:
                discos = obtener_unidades_usb(incluir_internos=incluir_internos)
                self.after(0, lambda: self._finalizar_refresco_discos(discos))
            except Exception:
                self.after(0, lambda: self._finalizar_refresco_discos([]))
                
        threading.Thread(target=run, daemon=True).start()

    def al_seleccionar_disco(self, seleccion=None):
        if not seleccion:
            seleccion = self.combo_disk.get()
        self.activar_interfaz_completa(seleccion)

    def _finalizar_refresco_discos(self, discos):
        self._refrescando_discos = False
        self.lista_discos_reales = discos
        if not getattr(self, 'en_proceso', False):
            self.btn_refresh.configure(state="normal")
        self.ocultar_interfaz_instalador()
        if not self.lista_discos_reales:
            self.combo_disk.configure(values=[t("selector.no_units")])
            self.combo_disk.set(t("selector.no_units"))
        else:
            nombres = [d["display"] for d in self.lista_discos_reales]
            self.combo_disk.configure(values=nombres)
            self.combo_disk.set(t("selector.select_placeholder"))

    def abrir_url(self, url): webbrowser.open_new_tab(url)

    def crear_boton_info(self, master, comando):
        """ Vuelve al diseño original transparente con el triángulo """
        return ctk.CTkButton(
            master, 
            image=getattr(self, 'img_triangulo', None), 
            text="" if getattr(self, 'img_triangulo', None) else "▲",
            width=30, height=30, 
            fg_color="transparent", 
            hover_color="#122d3d", 
            command=comando
        )

    def abrir_info_barra(self):
        """ Explicación exclusiva de la rueda del ratón, con letra grande y sin emoticonos """
        v = self.creventana_info_base("AJUSTE DE PRECISIÓN", 500, 240)
        f_in = ctk.CTkFrame(v, fg_color="transparent")
        f_in.pack(expand=True, fill="both", padx=25, pady=20)

        ctk.CTkLabel(
            f_in, 
            text="AJUSTE CON RUEDA DEL RATÓN", 
            font=("Segoe UI", 17, "bold"), 
            text_color=AZUL_CIAN
        ).pack(pady=(0, 16))
        
        f_txt = ctk.CTkFrame(f_in, fg_color="transparent")
        f_txt.pack(fill="x", padx=10)

        t1 = "○  Gira la rueda del ratón sobre una maneta: Ajusta de 1 en 1 GB exacto."
        t2 = "○  Mantén pulsado Shift y gira la rueda: Ajusta en pasos de 0.1 GB."

        ctk.CTkLabel(f_txt, text=t1, font=("Segoe UI", 14), justify="left", anchor="w").pack(fill="x", pady=6)
        ctk.CTkLabel(f_txt, text=t2, font=("Segoe UI", 14), justify="left", anchor="w").pack(fill="x", pady=6)

        ctk.CTkButton(
            f_in, 
            text="ENTENDIDO", 
            font=("Segoe UI", 13, "bold"), 
            fg_color=AZUL_ELECTRICO, 
            height=36, 
            width=140, 
            command=v.destroy
        ).pack(pady=(20, 0))
        v.update(); v.grab_set()
    
    def alternar_modo_instalacion(self, en_progreso=True):
        self.en_proceso = en_progreso
        if en_progreso:
            if hasattr(self, 'btn_start') and self.btn_start.winfo_exists():
                self.btn_start.pack_forget()

            if not self.f_progress.winfo_ismapped():
                self.f_progress.pack(side="left", fill="both", expand=True, padx=(0, 10))

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
        # En alternar_modo_instalacion (alrededor de la línea 715):
            if getattr(self, 'pestana_actual', 'instalador') == 'instalador':
                if hasattr(self, 'btn_start') and self.btn_start.winfo_exists():
                    self.btn_start.pack(side="bottom", pady=(2, 6))

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

    def mostrar_info_particion(self, key):
        tit = t(f"storage.legend_{key}", size="").replace(" ()", "").strip()
        msg = t(f"storage.desc_{key}")
        self.mostrar_info(tit, msg)

    def mostrar_info(self, titulo, mensaje): messagebox.showinfo(titulo, mensaje)

    def cerrar_aplicacion(self):
        if self.en_proceso:
            if not messagebox.askyesno("⚠️ PROCESO EN CURSO", "¿Estás seguro de que quieres salir?\nLa instalación se interrumpirá."): return  
            self.abortar_proceso = True
        try: self.after_cancel(self.animacion_id)
        except Exception: pass
        try: self.after_cancel(self.gif_after_id)
        except Exception: pass
        try: self.after_cancel(self.gif_break_id)
        except Exception: pass
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
        url_webhook = "https://hollowdrive-reporter.samucalata.workers.dev"

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
        if getattr(self, 'en_proceso', False):
            return

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
            self.logo_batocera = ctk.CTkImage(light_image=img_bato, dark_image=img_bato, size=(165, 115))
            self.bato_size = (165, 115)
        except Exception: self.logo_batocera = None
        
        try: 
            img_cachy = Image.open(os.path.join(path_media, "cachy.png"))
            self.logo_cachy = ctk.CTkImage(light_image=img_cachy, dark_image=img_cachy, size=(260, 72))
            self.cachy_size = (260, 72)
        except Exception: self.logo_cachy = None
        try: 
            img_savin = Image.open(os.path.join(path_media, "Savin-2.png"))
            self.logo_savin = ctk.CTkImage(light_image=img_savin, dark_image=img_savin, size=(240, 135))
        except Exception: self.logo_savin = None
        try: 
            img_maker = Image.open(os.path.join(path_media, "HollowDrive-2.png"))
            self.logo_maker = ctk.CTkImage(light_image=img_maker, dark_image=img_maker, size=(520, 310))
        except Exception: self.logo_maker = None
        try: 
            pil_instalar = Image.open(os.path.join(path_media, "instalar.png"))
            self.img_instalar = ctk.CTkImage(light_image=pil_instalar, dark_image=pil_instalar, size=(480, 112))
        except Exception: self.img_instalar = None
        try: 
            pil_image = Image.open(os.path.join(path_media, "descarga-morada.png"))
            self.img_descarga_data = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=(350, 350))
        except Exception: self.img_descarga_data = None
        try: 
            pil_reload = Image.open(os.path.join(path_media, "reload.png"))
            self.img_reload = ctk.CTkImage(light_image=pil_reload, dark_image=pil_reload, size=(32, 32))
        except Exception: self.img_reload = None
        try: 
            img_isos_pil = Image.open(os.path.join(path_media, "ISOs.png"))
            self.img_isos = ctk.CTkImage(light_image=img_isos_pil, dark_image=img_isos_pil, size=(150, 150))
            self.isos_size = (150, 150)
        except Exception:
            self.img_isos = None

        self.frames_linterna = self.cargar_gif_pil(os.path.join(CARPETA_MEDIA, "hollow-linterna.gif"), size=(70, 70), espejo=True)
        self.frames_breakdance = self.cargar_gif_pil(os.path.join(CARPETA_MEDIA, "breakdance.gif"), size=None)
        self.dummy_img = ctk.CTkImage(Image.new("RGBA", (1, 1), (0, 0, 0, 0)), size=(1, 1))

    def al_clicar_pack_batocera(self):
        if self.descargar_pack_bato.get(): self.abrir_info_roms()
        self.rebalancear()

    def abrir_info_motor(self):
        v = self.creventana_info_base(t("modals.motor_title"), 740, 540)
        frame_interno = ctk.CTkFrame(v, fg_color="transparent")
        frame_interno.pack(expand=True, fill="both", padx=25, pady=20)
        ctk.CTkLabel(frame_interno, text=t("modals.motor_header"), font=("Impact", 30), text_color=AZUL_CIAN).pack(pady=(0, 10))
        ctk.CTkLabel(frame_interno, text=t("modals.motor_body"), font=("Segoe UI", 15), justify="left", wraplength=660).pack(pady=5)
        ctk.CTkButton(frame_interno, text=t("modals.btn_close"), font=("Segoe UI", 14, "bold"), fg_color=AZUL_ELECTRICO, height=42, width=180, command=v.destroy).pack(pady=(15, 0))
        v.update(); v.grab_set()

    def iniciar_carga_tamanos_reales(self): 
        threading.Thread(target=self.cargar_tamanos_reales_hilo, daemon=True).start()

    def consultar_tamano(self, clave, default_bytes):
        for var in [clave, clave.replace("bato", "batocera")]:
            try:
                tam_bytes = resolver_tamano_pack(var)
                if tam_bytes and tam_bytes > 0: return tam_bytes
            except Exception: continue
        return default_bytes

    def abrir_info_roms(self):
        v = self.creventana_info_base(t("modals.legal_title"), 620, 360)
        v.configure(fg_color="#1a0a0a") 
        frame_interno = ctk.CTkFrame(v, fg_color="transparent")
        frame_interno.pack(expand=True, fill="both", padx=25, pady=20)
        ctk.CTkLabel(frame_interno, text=t("modals.legal_header"), font=("Impact", 32), text_color="#ff4d4d").pack(pady=(0, 15))
        ctk.CTkLabel(frame_interno, text=t("modals.legal_body"), font=("Segoe UI", 15), justify="center", wraplength=550).pack(pady=10)
        ctk.CTkButton(frame_interno, text=t("modals.legal_accept"), font=("Segoe UI", 14, "bold"), fg_color="#444", height=40, width=220, command=v.destroy).pack(pady=(15, 0))
        v.update(); v.grab_set()

    def abrir_info_pack_hollow(self):
        v = self.creventana_info_base(t("modals.pack_hollow_title"), 640, 420)
        frame_interno = ctk.CTkFrame(v, fg_color="transparent")
        frame_interno.pack(expand=True, fill="both", padx=25, pady=20)
        ctk.CTkLabel(frame_interno, text=t("modals.pack_hollow_header"), font=("Impact", 24), text_color=AZUL_CIAN).pack(pady=(0, 15))
        ctk.CTkLabel(frame_interno, text=t("modals.pack_hollow_body"), font=("Segoe UI", 15), justify="left", wraplength=560).pack(pady=5)
        ctk.CTkButton(frame_interno, text=t("modals.btn_close"), font=("Segoe UI", 14, "bold"), fg_color=AZUL_ELECTRICO, height=40, width=180, command=v.destroy).pack(pady=(15, 0))
        v.update(); v.grab_set()

    def cargar_tamanos_reales_hilo(self):
        fallbacks = {"bato_64": 4.60*(1024**3), "bato_32": 1.0*(1024**3), "pack_bato": 37.8*(1024**3), "pack_hollow": 8.66*(1024**3)}
        for clave, fb_val in fallbacks.items():
            tam_bytes = self.consultar_tamano(clave, fb_val)
            self.tamanos_reales[clave] = tam_bytes / (1024**3) 
            try: self.tamanos_formateados[clave] = formatear_tamano(tam_bytes)
            except Exception: self.tamanos_formateados[clave] = f"{self.tamanos_reales[clave]:.2f}GB"
        self.after(0, self.actualizar_labels_ui_con_tamanos_reales)

    def actualizar_labels_ui_con_tamanos_reales(self):
        if hasattr(self, 'ch_b64'):
            self.ch_b64.configure(text=t("batocera.arch_64", size=self.tamanos_formateados['bato_64']))
        if hasattr(self, 'ch_b32'):
            self.ch_b32.configure(text=t("batocera.arch_32"))
        if hasattr(self, 'ch_pack_bato'):
            self.ch_pack_bato.configure(text=t("batocera.pack_bato", size=self.tamanos_formateados['pack_bato']))
        if hasattr(self, 'ch_pack_hollow'):
            self.ch_pack_hollow.configure(text=t("batocera.pack_hollow", size=self.tamanos_formateados['pack_hollow']))
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
        
        try: 
            img_t_pil = Image.open(os.path.join(CARPETA_MEDIA, "triangulo.png"))
            self.img_triangulo = ctk.CTkImage(light_image=img_t_pil, dark_image=img_t_pil, size=(30, 30))
        except Exception: 
            self.img_triangulo = None

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

        saved_lang = i18n.get_current_language()
        init_name = i18n.LANGUAGE_NAMES.get(saved_lang, "Español")
        init_label = f"{init_name} ▾"
        self.btn_idioma = ctk.CTkButton(
            self.nav_bar,
            text=f" {init_label}",
            command=self.mostrar_menu_idioma,
            font=("Segoe UI", 12, "bold"),
            fg_color="transparent",
            hover_color="#1e293b",
            text_color=AZUL_CIAN,
            width=130,
            height=30,
            cursor="hand2"
        )
        self.btn_idioma.pack(side="right", padx=10, pady=5)

        self.menu_idioma = tk.Menu(
            self.btn_idioma,
            tearoff=0,
            bg="#0f172a",
            fg="#38bdf8",
            activebackground="#1e293b",
            activeforeground="#ffffff",
            font=("Segoe UI", 11, "bold"),
            bd=1,
            relief="solid"
        )
        for lang_item in i18n.get_available_languages():
            code = lang_item['code']
            name = lang_item['name']
            self.menu_idioma.add_command(
                label=f"  {name}  ",
                command=lambda c=code: self.al_cambiar_idioma(c)
            )
        
        self._last_lang_close_time = 0.0

        # --- SELECTOR DE DISCOS ---
        self.f_selection = ctk.CTkFrame(self, fg_color=AZUL_CARD, border_width=1, border_color=AZUL_ELECTRICO)
        self.f_selection.pack(fill="x", padx=20, pady=(0, 5)) 
        self.lbl_select_disk = ctk.CTkLabel(self.f_selection, text=t("selector.title"), font=("Segoe UI", 14, "italic"), text_color=AZUL_SUAVE)
        self.lbl_select_disk.pack(pady=(6,0))
        
        f_combo = ctk.CTkFrame(self.f_selection, fg_color="transparent")
        f_combo.pack(pady=10)
        self.combo_disk = ctk.CTkComboBox(f_combo, values=[t("selector.searching")], width=450, command=self.al_seleccionar_disco)
        self.combo_disk.set(t("selector.searching"))
        self.combo_disk.pack(side="left", padx=10)
        self.widgets_interactivos.append(self.combo_disk)
        hacer_combobox_clicable_total(self.combo_disk)

        self.btn_refresh = ctk.CTkButton(f_combo, image=getattr(self, 'img_reload', None), text="" if getattr(self, 'img_reload', None) else "🔄", width=44, height=44, fg_color="transparent", hover_color="#1e293b", cursor="hand2", command=self.refrescar_discos)
        self.btn_refresh.pack(side="left", padx=5)
        self.tooltip_refresh = CTkToolTip(self.btn_refresh, t("tooltips.reload"), delay_ms=500)
        self.widgets_interactivos.append(self.btn_refresh)

        self.sw_internos = ctk.CTkCheckBox(f_combo, text=t("selector.show_internal"), variable=self.mostrar_internos, command=self.toggle_discos_internos, text_color="#aa3333", font=("Segoe UI", 11, "bold"))
        self.sw_internos.pack(side="left", padx=10)
        self.widgets_interactivos.append(self.sw_internos)

        # --- CONTENEDOR INSTALADOR MAESTRO ---
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")

        # =====================================================================
        # 🚀 BOTÓN INSTALAR FIJO (Sin zoom para no empujar nada hacia arriba)
        # =====================================================================
        if getattr(self, 'img_instalar', None):
            self.btn_start = ctk.CTkButton(
                self.main_container, 
                image=self.img_instalar, 
                text="", 
                fg_color="transparent", 
                hover_color="#0e1726", 
                corner_radius=20,
                width=490,
                height=114, 
                cursor="hand2",
                command=self.confirmar_inicio
            )
            # Sin animación de tamaño: tamaño fijo y estable
        else:
            self.btn_start = ctk.CTkButton(
                self.main_container, 
                text="🚀 COMENZAR INSTALACIÓN", 
                font=("Segoe UI", 15, "bold"), 
                fg_color=AZUL_ELECTRICO, 
                hover_color="#0046c7", 
                width=440,
                height=48, 
                corner_radius=12,
                command=self.confirmar_inicio
            )
        self.btn_start.pack(side="bottom", pady=(2, 6))
        self.widgets_interactivos.append(self.btn_start)

        # =====================================================================
        # 🎚️ PANEL DE PARTICIONES INVISIBLE (Sin recuadro)
        # =====================================================================
        self.p_bottom = ctk.CTkFrame(self.main_container, fg_color="transparent", border_width=0)
        self.p_bottom.pack(side="bottom", fill="x", padx=0, pady=(2, 4))

        f_sw_row = ctk.CTkFrame(self.p_bottom, fg_color="transparent")
        f_sw_row.pack(fill="x", padx=20, pady=(4, 2))

        f_sw_center = ctk.CTkFrame(f_sw_row, fg_color="transparent")
        f_sw_center.pack(anchor="center")

        self.sw_preservar = ctk.CTkSwitch(
            f_sw_center, text=t("motor.preserve_space"), 
            variable=self.preservar_espacio, 
            command=self.toggle_preservar_espacio, 
            progress_color=AZUL_ELECTRICO,
            font=("Segoe UI", 12, "bold")
        )
        self.sw_preservar.pack(side="left", padx=(0, 6))
        self.widgets_interactivos.append(self.sw_preservar)

        self.btn_info_barra = self.crear_boton_info(f_sw_center, self.abrir_info_barra)
        self.btn_info_barra.pack(side="left")
        CTkToolTip(self.btn_info_barra, "Ajuste con rueda del ratón", delay_ms=400)

        self.canvas_wrap = ctk.CTkFrame(self.p_bottom, fg_color="transparent")
        self.canvas_wrap.pack(fill="x", padx=20, pady=(2, 4))

        bg_canvas_fondo = AZUL_FONDO[0] if ctk.get_appearance_mode() == "Light" else AZUL_FONDO[1]
        self.canvas = tk.Canvas(
            self.canvas_wrap, 
            height=85, 
            bg=bg_canvas_fondo, 
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

        # =====================================================================
        # 📦 PANELES SUPERIORES (50/50 BLOQUEADO)
        # =====================================================================
        self.f_panels = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.f_panels.pack(side="top", fill="both", expand=True, pady=(0, 4))

        self.f_panels.grid_columnconfigure(0, weight=1, uniform="columna_panel")
        self.f_panels.grid_columnconfigure(1, weight=1, uniform="columna_panel")
        self.f_panels.grid_rowconfigure(0, weight=1)

        # ---------------------------------------------------------------------
        # 🔵 PANEL IZQUIERDO: MOTOR + BATOCERA Y PACKS ABAJO
        # ---------------------------------------------------------------------
        self.p_left = ctk.CTkFrame(self.f_panels, fg_color=AZUL_CARD, corner_radius=15, border_width=1, border_color="#222")
        self.p_left.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=0)

        # Motor de extracción
        self.f_motor = ctk.CTkFrame(self.p_left, fg_color=AZUL_CARD_INNER, corner_radius=8, border_width=1, border_color=COLOR_BORDE)
        self.f_motor.pack(fill="x", padx=15, pady=(10, 6))
        f_motor_h = ctk.CTkFrame(self.f_motor, fg_color="transparent")
        f_motor_h.pack(fill="x", padx=10, pady=4)
        self.lbl_motor = ctk.CTkLabel(f_motor_h, text=t("motor.title"), font=("Consolas", 12, "bold"), text_color=AZUL_CIAN)
        self.lbl_motor.pack(side="left")
        self.crear_boton_info(f_motor_h, self.abrir_info_motor).pack(side="right")
        
        f_radios = ctk.CTkFrame(self.f_motor, fg_color="transparent")
        f_radios.pack(fill="x", padx=10, pady=(0, 6))
        self.r_motor_ram = ctk.CTkRadioButton(f_radios, text=t("motor.ram"), variable=self.metodo_descarga, value="ram", font=("Segoe UI", 11))
        self.r_motor_ram.pack(side="left", padx=(0, 10))
        self.r_motor_disco = ctk.CTkRadioButton(f_radios, text=t("motor.disk"), variable=self.metodo_descarga, value="disco", font=("Segoe UI", 11))
        self.r_motor_disco.pack(side="left")
        self.widgets_interactivos.extend([self.r_motor_ram, self.r_motor_disco])

        # Fila Batocera
        f_bato_row = ctk.CTkFrame(self.p_left, fg_color="transparent")
        f_bato_row.pack(fill="both", expand=True, padx=15, pady=(4, 6))

        # Columna izquierda
        f_bato_left = ctk.CTkFrame(f_bato_row, fg_color="transparent")
        f_bato_left.pack(side="left", fill="both", expand=True)

        # Switch Batocera (Arriba)
        self.f_bato_h = ctk.CTkFrame(f_bato_left, fg_color="transparent")
        self.f_bato_h.pack(side="top", fill="x", pady=(2, 2))
        self.sw_bato = ctk.CTkSwitch(self.f_bato_h, text=t("batocera.switch"), font=("Segoe UI", 12, "bold"), variable=self.instalar_bato, command=self.actualizar_estados_bato, progress_color=AZUL_CIAN)
        self.sw_bato.pack(side="left")
        self.widgets_interactivos.append(self.sw_bato)
        self.crear_boton_info(self.f_bato_h, self.abrir_info_batocera).pack(side="left", padx=5)

        # Opciones Batocera (Aparecen entre el switch y los packs sin empujar nada hacia abajo)
        self.f_bato_opts = ctk.CTkFrame(f_bato_left, fg_color="transparent")
        self.ch_b64 = ctk.CTkCheckBox(self.f_bato_opts, text="Batocera 64bits (4.6 GB)", variable=self.bato_64_act, command=self.rebalancear)
        self.ch_b64.pack(pady=2, padx=4, anchor="w")
        self.ch_b32 = ctk.CTkCheckBox(self.f_bato_opts, text="Batocera 32bits (Próximamente)", variable=self.bato_32_act, command=self.rebalancear, state="disabled")
        self.ch_b32.pack(pady=2, padx=4, anchor="w")
        self.widgets_interactivos.append(self.ch_b64)

        # 2- PACKS ABAJO DEL TODO DESDE EL PRINCIPIO (side="bottom" para no saltar)
        f_packs_container = ctk.CTkFrame(
            f_bato_left, 
            fg_color=AZUL_CARD_INNER, 
            corner_radius=10, 
            border_width=1, 
            border_color="#1e293b"
        )
        # pady=(4, 14) separa la pastilla de la curva inferior del panel
        f_packs_container.pack(side="bottom", anchor="w", padx=2, pady=(4, 14))

        f_pack_bato = ctk.CTkFrame(f_packs_container, fg_color="transparent")
        f_pack_bato.pack(fill="x", padx=8, pady=3)
        self.ch_pack_bato = ctk.CTkCheckBox(f_pack_bato, text="PACK BATOCERA (37.8 GB)", variable=self.descargar_pack_bato, command=self.al_clicar_pack_batocera)
        self.ch_pack_bato.pack(side="left", anchor="w")
        self.widgets_interactivos.append(self.ch_pack_bato)
        self.crear_boton_info(f_pack_bato, self.abrir_info_roms).pack(side="left", padx=4)

        f_pack_hollow = ctk.CTkFrame(f_packs_container, fg_color="transparent")
        f_pack_hollow.pack(fill="x", padx=8, pady=3)
        self.ch_pack_hollow = ctk.CTkCheckBox(f_pack_hollow, text="PACK HOLLOWDRIVE (8.7 GB)", variable=self.descargar_pack_hollow, command=self.rebalancear)
        self.ch_pack_hollow.pack(side="left", anchor="w")
        self.widgets_interactivos.append(self.ch_pack_hollow)
        self.crear_boton_info(f_pack_hollow, self.abrir_info_pack_hollow).pack(side="left", padx=4)

        # Mando Batocera a la derecha
        if getattr(self, 'logo_batocera', None):
            f_bato_logo_container = ctk.CTkFrame(f_bato_row, width=175, height=140, fg_color="transparent")
            f_bato_logo_container.pack(side="right", padx=(8, 0), pady=(0, 0))
            f_bato_logo_container.pack_propagate(False)
            
            lbl_img_bato = ctk.CTkLabel(f_bato_logo_container, image=self.logo_batocera, text="", cursor="hand2")
            lbl_img_bato.place(relx=0.5, rely=0.5, anchor="center")
            lbl_img_bato.bind("<Button-1>", lambda e: self.abrir_url("https://batocera.org"))
            lbl_img_bato.bind("<Enter>", lambda e: self.animar_zoom('logo_batocera', 'bato_size', (165, 115), (175, 122), True))
            lbl_img_bato.bind("<Leave>", lambda e: self.animar_zoom('logo_batocera', 'bato_size', (165, 115), (175, 122), False))

        # ---------------------------------------------------------------------
        # 🟢 PANEL DERECHO: CACHYOS (3- Con zoom que crece al pasar el ratón)
        # ---------------------------------------------------------------------
        self.p_right = ctk.CTkFrame(self.f_panels, fg_color=AZUL_CARD, corner_radius=15, border_width=1, border_color="#222")
        self.p_right.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=0)

        f_cachy_master = ctk.CTkFrame(self.p_right, fg_color="transparent")
        f_cachy_master.pack(fill="x", padx=15, pady=(10, 10))
        
        if getattr(self, 'logo_cachy', None):
            f_cachy_logo_container = ctk.CTkFrame(f_cachy_master, width=290, height=76, fg_color="transparent")
            f_cachy_logo_container.pack(pady=(4, 6))
            f_cachy_logo_container.pack_propagate(False)
            
            lbl_img_cachy = ctk.CTkLabel(f_cachy_logo_container, image=self.logo_cachy, text="", cursor="hand2")
            lbl_img_cachy.place(relx=0.5, rely=0.5, anchor="center")
            lbl_img_cachy.bind("<Button-1>", lambda e: self.abrir_url("https://cachyos.org"))
            # 3- Zoom correcto: mide 260x72 y crece a 285x79
            lbl_img_cachy.bind("<Enter>", lambda e: self.animar_zoom('logo_cachy', 'cachy_size', (260, 72), (285, 79), True))
            lbl_img_cachy.bind("<Leave>", lambda e: self.animar_zoom('logo_cachy', 'cachy_size', (260, 72), (285, 79), False))

        f_cachy_h = ctk.CTkFrame(f_cachy_master, fg_color="transparent")
        f_cachy_h.pack(fill="x", pady=(4, 6))
        self.sw_cachy = ctk.CTkSwitch(f_cachy_h, text=t("cachyos.switch"), font=("Segoe UI", 12, "bold"), variable=self.instalar_cachy, command=self.actualizar_estados_cachy, progress_color=AZUL_CIAN)
        self.sw_cachy.pack(side="left")
        self.widgets_interactivos.append(self.sw_cachy)
        self.crear_boton_info(f_cachy_h, self.abrir_info_cachyos).pack(side="left", padx=5)

        self.cachy_flavor = ctk.StringVar(value="hyprland")
        self.f_cachy_opts = ctk.CTkFrame(f_cachy_master, fg_color=AZUL_CARD_INNER, corner_radius=8)
        
        f_kde = ctk.CTkFrame(self.f_cachy_opts, fg_color="transparent")
        f_kde.pack(fill="x", padx=10, pady=1)
        self.r_kde = ctk.CTkRadioButton(
            f_kde, 
            text=f"{t('cachyos.kde')} (Próximamente)", 
            variable=self.cachy_flavor, 
            value="kde", 
            font=("Segoe UI", 12),
            state="disabled"
        )
        self.r_kde.pack(side="left", pady=2)
        self.crear_boton_info(f_kde, self.abrir_info_kde).pack(side="right")

        f_hypr = ctk.CTkFrame(self.f_cachy_opts, fg_color="transparent")
        f_hypr.pack(fill="x", padx=10, pady=1)
        self.r_hypr = ctk.CTkRadioButton(f_hypr, text=t("cachyos.hyprland"), variable=self.cachy_flavor, value="hyprland", font=("Segoe UI", 12))
        self.r_hypr.pack(side="left", pady=2)
        self.crear_boton_info(f_hypr, self.abrir_info_hyprland).pack(side="right")

        self.widgets_interactivos.append(self.r_hypr)

        # =====================================================================
        # 🛠️ PANEL MÓDULO HOLLOWTOOLS
        # =====================================================================
        self.hollow_tools_container = ctk.CTkFrame(self, fg_color="transparent")

        f_ht_top = ctk.CTkFrame(self.hollow_tools_container, fg_color=AZUL_CARD, corner_radius=12, border_width=1, border_color="#222")
        f_ht_top.pack(fill="x", padx=5, pady=(0, 10))
        
        self.lbl_ht_title = ctk.CTkLabel(f_ht_top, text=t("hollowtools.header_title"), font=("Impact", 22), text_color=AZUL_CIAN)
        self.lbl_ht_title.pack(pady=(10, 2))
        
        f_combo_ht = ctk.CTkFrame(f_ht_top, fg_color="transparent")
        f_combo_ht.pack(pady=(2, 10))
        self.combo_ht_disk = ctk.CTkComboBox(f_combo_ht, values=["Buscando HOLLOWDRIVES..."], width=460, font=("Segoe UI", 12), command=self.al_seleccionar_disco_hollowtools)
        self.combo_ht_disk.pack(side="left", padx=10)
        hacer_combobox_clicable_total(self.combo_ht_disk)
        self.btn_ht_refresh = ctk.CTkButton(f_combo_ht, image=getattr(self, 'img_reload', None), text="" if getattr(self, 'img_reload', None) else "🔄", width=44, height=44, fg_color="transparent", hover_color="#1e293b", cursor="hand2", command=self.refrescar_discos_hollowtools)
        self.btn_ht_refresh.pack(side="left", padx=5)
        self.tooltip_ht_refresh = CTkToolTip(self.btn_ht_refresh, t("tooltips.reload"), delay_ms=500)
        self.f_ht_grid = ctk.CTkFrame(self.hollow_tools_container, fg_color="transparent")

        # TARJETA 1: GESTOR DE ISOs
        self.card_iso = ctk.CTkFrame(self.f_ht_grid, fg_color=AZUL_CARD, corner_radius=15, border_width=1, border_color="#222")
        self.card_iso.pack(side="left", fill="both", expand=True, padx=4)

        f_head_iso = ctk.CTkFrame(self.card_iso, fg_color="transparent")
        f_head_iso.pack(fill="x", padx=12, pady=(12, 4))
        self.lbl_card_iso = ctk.CTkLabel(f_head_iso, text=t("hollowtools.card_iso_title"), font=("Segoe UI", 16, "bold"), text_color=AZUL_CIAN)
        self.lbl_card_iso.pack(side="left")
        self.crear_boton_info(f_head_iso, self.abrir_info_ht_isos).pack(side="right")

        self.f_drop_area = ctk.CTkFrame(self.card_iso, fg_color="#090d12", corner_radius=12, border_width=1, border_color="#1e293b")
        self.f_drop_area.pack(fill="both", expand=True, padx=12, pady=10)

        self.lbl_drag_msg = ctk.CTkLabel(self.f_drop_area, text=t("hollowtools.drop_msg"), font=("Segoe UI", 12), text_color=AZUL_SUAVE, justify="center")
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

        # TARJETA 2: PAQUETES
        card_content = ctk.CTkFrame(self.f_ht_grid, fg_color=AZUL_CARD, corner_radius=15, border_width=1, border_color="#222")
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

        # TARJETA 3: CACHYOS
        card_cachy = ctk.CTkFrame(self.f_ht_grid, fg_color=AZUL_CARD, corner_radius=15, border_width=1, border_color="#222")
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

        self.ht_cachy_flavor = ctk.StringVar(value="hyprland")
        self.f_ht_flavor = ctk.CTkFrame(f_body_cachy, fg_color="#0d141c", corner_radius=8)
        self.f_ht_flavor.pack(fill="x", pady=5)

        ctk.CTkLabel(self.f_ht_flavor, text="Entorno:", font=("Segoe UI", 11, "bold"), text_color=AZUL_SUAVE).pack(side="left", padx=(10, 5), pady=6)

        r_ht_kde = ctk.CTkRadioButton(
            self.f_ht_flavor, 
            text="KDE Plasma (Próximamente)", 
            variable=self.ht_cachy_flavor, 
            value="kde", 
            font=("Segoe UI", 11),
            state="disabled"
        )
        r_ht_kde.pack(side="left", padx=5, pady=5)

        r_ht_hypr = ctk.CTkRadioButton(self.f_ht_flavor, text="Hyprland", variable=self.ht_cachy_flavor, value="hyprland", font=("Segoe UI", 11))
        r_ht_hypr.pack(side="left", padx=5, pady=5)

        self.f_slider_sec = ctk.CTkFrame(f_body_cachy, fg_color="#090d12", corner_radius=10, border_width=1, border_color="#1e293b")
        self.f_slider_sec.pack(fill="x", pady=5)

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

        # COMPARATIVA VISUAL (ANTES / DESPUÉS)
        self.f_ht_preview = ctk.CTkFrame(self.hollow_tools_container, fg_color=AZUL_CARD, corner_radius=12, border_width=1, border_color="#222")

        f_p1 = ctk.CTkFrame(self.f_ht_preview, fg_color="transparent")
        f_p1.pack(fill="x", padx=12, pady=(6, 2))
        ctk.CTkLabel(f_p1, text="ANTES", font=("Segoe UI", 13, "bold"), text_color=AZUL_SUAVE).pack(side="left")
        self.lbl_ht_bar_actual_info = ctk.CTkLabel(f_p1, text="", font=("Consolas", 13, "bold"), text_color="#ffffff")
        self.lbl_ht_bar_actual_info.pack(side="right")
        self.canvas_ht_actual = tk.Canvas(self.f_ht_preview, height=26, bg=color_canvas_actual(), highlightthickness=0, borderwidth=0)
        self.canvas_ht_actual.pack(fill="x", padx=12, pady=(0, 2))

        self.lbl_ht_arrow = ctk.CTkLabel(self.f_ht_preview, text="⬇      ⬇      ⬇      ⬇      ⬇      ⬇      ⬇      ⬇", font=("Segoe UI", 12, "bold"), text_color=AZUL_CIAN)
        self.lbl_ht_arrow.pack(pady=1)

        f_p2 = ctk.CTkFrame(self.f_ht_preview, fg_color="transparent")
        f_p2.pack(fill="x", padx=12, pady=(2, 2))
        ctk.CTkLabel(f_p2, text="DESPUÉS", font=("Segoe UI", 13, "bold"), text_color=COLOR_CACHY).pack(side="left")
        self.lbl_ht_bar_futuro_info = ctk.CTkLabel(f_p2, text="", font=("Consolas", 13, "bold"), text_color="#ffffff")
        self.lbl_ht_bar_futuro_info.pack(side="right")
        self.canvas_ht_futuro = tk.Canvas(self.f_ht_preview, height=26, bg=color_canvas_actual(), highlightthickness=0, borderwidth=0)
        self.canvas_ht_futuro.pack(fill="x", padx=12, pady=(0, 8))

        # =====================================================================
        # FOOTER / PIE DE PÁGINA CON MULTI-BARRA DINÁMICA
        # =====================================================================
        self.footer = ctk.CTkFrame(self, fg_color="transparent")

        self.lbl_gif = ctk.CTkLabel(self.footer, text="")
        self.lbl_gif.pack(side="left", padx=10)

        self.f_progress = ctk.CTkFrame(self.footer, fg_color="transparent")

        self.lbl_status = ctk.CTkLabel(self.f_progress, text="ESPERANDO INICIO...", font=("Consolas", 12, "bold"), text_color=AZUL_SUAVE)
        self.lbl_status.pack(anchor="w", padx=5, pady=(2, 2))

        self.p_task = ctk.CTkProgressBar(self.f_progress, height=8, progress_color=AZUL_CIAN)
        self.p_task.set(0)
        self.p_task.pack(fill="x", padx=5, pady=2)

        self.p_total = ctk.CTkProgressBar(self.f_progress, height=8, progress_color=AZUL_ELECTRICO)
        self.p_total.set(0)
        self.p_total.pack(fill="x", padx=5, pady=2)
        
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
            
            # En cambiar_pestana (alrededor de la línea 1025):
            if not self.en_proceso:
                if hasattr(self, 'btn_start') and self.btn_start.winfo_exists():
                    self.btn_start.pack(side="bottom", pady=(2, 6))
                self.btn_start.pack(side="top", pady=(2, 4))
                self.f_progress.pack_forget()
                self.btn_cancel.pack_forget()
                
            self.btn_modo_installer.configure(fg_color=AZUL_ELECTRICO, text_color="white")
            self.btn_modo_tools.configure(fg_color="transparent", text_color=AZUL_CIAN)
        else:
            self.f_selection.pack_forget()
            self.main_container.pack_forget()
            
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

    def ocultar_interfaz_hollowtools(self):
        if hasattr(self, 'f_ht_grid'):
            try:
                self.f_ht_grid.pack_forget()
            except Exception:
                pass
        if hasattr(self, 'f_ht_preview'):
            try:
                self.f_ht_preview.pack_forget()
            except Exception:
                pass

    def refrescar_discos_hollowtools(self):
        self.combo_ht_disk.configure(values=[t("hollowtools.searching")])
        self.combo_ht_disk.set(t("hollowtools.searching"))
        self.ocultar_interfaz_hollowtools()
        if getattr(self, '_refrescando_ht', False):
            return
        self._refrescando_ht = True
        self.btn_ht_refresh.configure(state="disabled")
        
        def run():
            try:
                unidades = obtener_unidades_usb(incluir_internos=False)
                filtradas = [u for u in unidades if u.get("is_hollow")]
            except Exception as ex:
                logging.warning(f"Aviso escaneando unidades HollowTools: {ex}")
                filtradas = []

            self.after(0, lambda: self._finalizar_refresco_ht(filtradas))
            
        threading.Thread(target=run, daemon=True).start()

    def _finalizar_refresco_ht(self, discos):
        self._refrescando_ht = False
        self.lista_discos_hollow = discos
        self.btn_ht_refresh.configure(state="normal")
        self.ocultar_interfaz_hollowtools()
        if not discos:
            self.combo_ht_disk.configure(values=[t("hollowtools.no_units")])
            self.combo_ht_disk.set(t("hollowtools.no_units"))
        else:
            nombres = [d["display"] for d in discos]
            self.combo_ht_disk.configure(values=nombres)
            self.combo_ht_disk.set(t("selector.select_placeholder"))

    def al_seleccionar_disco_hollowtools(self, seleccion=None):
        if not seleccion:
            seleccion = self.combo_ht_disk.get()
        if not seleccion or any(k in seleccion for k in ["---", "Buscando", "NO SE DETECTAN", "Searching", "Select", "Selecciona", t("hollowtools.searching"), t("hollowtools.no_units"), t("selector.select_placeholder")]):
            self.ocultar_interfaz_hollowtools()
            return

        disco = next((d for d in getattr(self, 'lista_discos_hollow', []) if d.get("display") == seleccion), None)
        if not disco:
            self.ocultar_interfaz_hollowtools()
            return
            
        if hasattr(self, 'f_ht_grid') and not self.f_ht_grid.winfo_ismapped():
            self.f_ht_grid.pack(fill="both", expand=True, padx=0, pady=0)
        if hasattr(self, 'f_ht_preview') and not self.f_ht_preview.winfo_ismapped():
            self.f_ht_preview.pack(fill="x", padx=5, pady=(10, 0))
        
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
            self.bloquear_ui(False)
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
            
            self.canvas_ht_actual.create_rectangle(x, 0, x + pix, 26, fill=color, outline="#05080a")
            
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
        self.crear_barra_tarea_dinamica(id_sys, "Paso 3/3: Volcado CachyOS Ext4 (en espera)", color=COLOR_CACHY)

        def hilo():
            try:
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
                sabor_ht = getattr(self, 'ht_cachy_flavor', ctk.StringVar(value="kde")).get()
                if sabor_ht == "hyprland":
                    url_grub = MIRRORS_DATA["cachyos_images"]["efi_grub_hyprland"]["mirrors"][0]["url"]
                    url_cachy = MIRRORS_DATA["cachyos_images"]["hyprland"]["mirrors"][0]["url"]
                else:
                    url_grub = MIRRORS_DATA["cachyos_images"]["efi_grub"]["mirrors"][0]["url"]
                    url_cachy = MIRRORS_DATA["cachyos_images"]["sistema"]["mirrors"][0]["url"]

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

                self.actualizar_barra_tarea_dinamica(id_sys, 0.0, "Flasheando CachyOS Ext4...")
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
                self.actualizar_barra_tarea_dinamica(id_sys, 1.0, "✔ CachyOS Ext4 completado")

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
                    def prog_pack_b(pct, msg):
                        self.actualizar_barra_tarea_dinamica(id_tarea, pct, f"Pack ROMs: {msg}")
        
                    self.descargar_y_extraer_batocera_pack(
                        letra_hollow,
                        callback_progreso_externo=prog_pack_b
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
            v = self.creventana_info_base(t("modals.cachy_manage_title"), 540, 360)
            f_in = ctk.CTkFrame(v, fg_color="transparent")
            f_in.pack(expand=True, fill="both", padx=20, pady=20)

            ctk.CTkLabel(f_in, text=t("modals.cachy_manage_header"), font=("Impact", 28), text_color=COLOR_CACHY).pack(pady=(0, 10))
            msg = t("modals.cachy_manage_body")
            ctk.CTkLabel(f_in, text=msg, font=("Segoe UI", 15), justify="center", wraplength=480).pack(pady=10)

            def opt_actualizar():
                v.destroy()
                self._ejecutar_flasheo_cachy(letra_grub, letra_cachy)

            def opt_borrar():
                v.destroy()
                if messagebox.askyesno(t("modals.cachy_del_confirm_title"), t("modals.cachy_del_confirm_msg")):
                    if eliminar_particiones_cachy_diskpart(disco["device"]):
                        messagebox.showinfo(t("modals.cachy_del_confirm_title"), t("modals.cachy_del_success"))
                        self.refrescar_discos_hollowtools()
                    else:
                        messagebox.showerror("ERROR", "Error")

            ctk.CTkButton(f_in, text=t("modals.cachy_opt_update"), font=("Segoe UI", 12, "bold"), fg_color=AZUL_ELECTRICO, height=40, command=opt_actualizar).pack(fill="x", pady=5)
            ctk.CTkButton(f_in, text=t("modals.cachy_opt_delete"), font=("Segoe UI", 12, "bold"), fg_color="#aa3333", height=40, command=opt_borrar).pack(fill="x", pady=5)
            ctk.CTkButton(f_in, text=t("modals.btn_close"), font=("Segoe UI", 11), fg_color="#333", height=30, command=v.destroy).pack(pady=5)
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
                metodo = self.metodo_descarga.get()
                sabor_ht = getattr(self, 'ht_cachy_flavor', ctk.StringVar(value="kde")).get()
                if sabor_ht == "hyprland":
                    url_grub = MIRRORS_DATA["cachyos_images"]["efi_grub_hyprland"]["mirrors"][0]["url"]
                    url_cachy = MIRRORS_DATA["cachyos_images"]["hyprland"]["mirrors"][0]["url"]
                else:
                    url_grub = MIRRORS_DATA["cachyos_images"]["efi_grub"]["mirrors"][0]["url"]
                    try: url_cachy = MIRRORS_DATA["cachyos_images"]["sistema"]["mirrors"][0]["url"]
                    except KeyError: url_cachy = "https://huggingface.co/datasets/HollowDrive/HollowDrive/resolve/main/hollowdrive_cachy_sistema.img"

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

                self.actualizar_barra_tarea_dinamica(id_sys, 0.0, "Paso 2/2: Preparando CachyOS Ext4...")

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
        v = self.creventana_info_base(t("modals.batocera_title"), 640, 360)
        frame_interno = ctk.CTkFrame(v, fg_color="transparent")
        frame_interno.pack(expand=True, fill="both", padx=25, pady=20)
        ctk.CTkLabel(frame_interno, text=t("modals.batocera_header"), font=("Impact", 30), text_color=AZUL_CIAN).pack(pady=(0, 15))
        ctk.CTkLabel(frame_interno, text=t("modals.batocera_body"), font=("Segoe UI", 16), justify="center", wraplength=560).pack(pady=5)
        ctk.CTkButton(frame_interno, text=t("modals.btn_close"), font=("Segoe UI", 14, "bold"), fg_color=AZUL_ELECTRICO, height=42, width=180, command=v.destroy).pack(pady=(15, 0))
        v.update(); v.grab_set()

    def abrir_info_cachyos(self):
        v = self.creventana_info_base(t("modals.cachyos_title"), 700, 500)
        frame_interno = ctk.CTkFrame(v, fg_color="transparent")
        frame_interno.pack(expand=True, fill="both", padx=25, pady=20)
        ctk.CTkLabel(frame_interno, text=t("modals.cachyos_header"), font=("Impact", 30), text_color=COLOR_CACHY).pack(pady=(0, 15))
        ctk.CTkLabel(frame_interno, text=t("modals.cachyos_body"), font=("Segoe UI", 15), justify="center", wraplength=620).pack(pady=5)
        
        # Mensaje de apoyo para futuros sistemas
        f_apoyo = ctk.CTkFrame(frame_interno, fg_color=AZUL_CARD_INNER, corner_radius=8, border_width=1, border_color="#1e293b")
        f_apoyo.pack(fill="x", pady=(12, 5), padx=10)
        ctk.CTkLabel(
            f_apoyo,
            text="🌟 Si se apoya el proyecto, en futuras actualizaciones añadiré más sistemas operativos independientes para elegir.",
            font=("Segoe UI", 12, "italic"),
            text_color=AZUL_CIAN,
            justify="center",
            wraplength=580
        ).pack(padx=12, pady=8)

        ctk.CTkButton(frame_interno, text=t("modals.btn_close"), font=("Segoe UI", 14, "bold"), fg_color=AZUL_ELECTRICO, height=40, width=180, command=v.destroy).pack(pady=(15, 0))
        v.update(); v.grab_set()
        
    def abrir_info_kde(self):
        v = self.creventana_info_base(t("modals.kde_title"), 540, 300)
        f = ctk.CTkFrame(v, fg_color="transparent")
        f.pack(expand=True, fill="both", padx=25, pady=20)
        ctk.CTkLabel(f, text=t("modals.kde_header"), font=("Impact", 26), text_color=AZUL_CIAN).pack(pady=(0, 10))
        ctk.CTkLabel(f, text=t("modals.kde_body"), font=("Segoe UI", 16), justify="center", wraplength=480).pack(pady=5)
        ctk.CTkButton(f, text=t("modals.btn_close"), font=("Segoe UI", 13, "bold"), fg_color=AZUL_ELECTRICO, height=40, command=v.destroy).pack(pady=(15,0))
        v.update(); v.grab_set()

    def abrir_info_hyprland(self):
        v = self.creventana_info_base(t("modals.hyprland_title"), 620, 340)
        f = ctk.CTkFrame(v, fg_color="transparent")
        f.pack(expand=True, fill="both", padx=25, pady=20)
        ctk.CTkLabel(f, text=t("modals.hyprland_header"), font=("Impact", 26), text_color=COLOR_CACHY).pack(pady=(0, 10))
        ctk.CTkLabel(f, text=t("modals.hyprland_body"), font=("Segoe UI", 16), justify="center", wraplength=550).pack(pady=5)
        ctk.CTkButton(f, text=t("modals.btn_close"), font=("Segoe UI", 13, "bold"), fg_color=AZUL_ELECTRICO, height=40, command=v.destroy).pack(pady=(15,0))
        v.update(); v.grab_set()

    def abrir_ventana_info(self):
        v = self.creventana_info_base(t("modals.initial.title"), 760, 780)
        
        scroll_container = ctk.CTkScrollableFrame(v, fg_color="transparent")
        scroll_container.pack(expand=True, fill="both", padx=15, pady=15)

        ctk.CTkLabel(scroll_container, text=t("modals.initial.header"), font=("Impact", 38), text_color=AZUL_CIAN).pack(pady=(5, 5))

        ctk.CTkLabel(
            scroll_container, 
            text=t("modals.initial.welcome"), 
            font=("Segoe UI", 15),
            text_color=("#0284c7", "#38bdf8"),
            wraplength=660, 
            justify="center"
        ).pack(padx=20, pady=(5, 15))

        ctk.CTkLabel(scroll_container, text=t("modals.initial.video_prompt"), font=("Consolas", 15, "bold"), text_color=AZUL_SUAVE).pack(pady=(5, 5))
        url_video_youtube = "https://youtu.be/oHg5SJYRHA0?si=7nL_H5sIWuiLM4dp"

        f_video = ctk.CTkFrame(scroll_container, fg_color=AZUL_CARD, border_width=2, border_color=AZUL_ELECTRICO, width=480, height=270, corner_radius=15)
        f_video.pack_propagate(False)
        f_video.pack(pady=8)

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

        ctk.CTkLabel(scroll_container, text=t("modals.initial.platforms"), font=("Consolas", 15, "bold"), text_color=AZUL_SUAVE).pack(pady=(15, 5))
        f_social = ctk.CTkFrame(scroll_container, fg_color="transparent")
        f_social.pack(pady=5)

        socials = [
            ("💬 DISCORD", "https://discord.gg/HJvgmCRpGm"), 
            ("📂 GITHUB", "https://github.com/MVP-Savyn"), 
            ("📺 YOUTUBE", "https://youtube.com/@T0xicArea")
        ]
        for texto, url in socials:
            ctk.CTkButton(
                f_social, text=texto, font=("Consolas", 12, "bold"), 
                fg_color=AZUL_CARD, border_width=1, border_color=AZUL_ELECTRICO, 
                width=140, height=35, command=lambda u=url: webbrowser.open_new_tab(u)
            ).pack(side="left", padx=6)

        ctk.CTkLabel(scroll_container, text=t("modals.initial.resources"), font=("Consolas", 15, "bold"), text_color=AZUL_SUAVE).pack(pady=(20, 5))

        credits_licencias = [
            ("VENTOY CORE (GNU GPLv3)", "https://github.com/ventoy/Ventoy"),
            ("7-ZIP ENGINE (GNU LGPL)", "https://www.7-zip.org"),
            ("CACHY OS (GNU GPLv3)", "https://cachyos.org"),
            ("BATOCERA LINUX (GPLv2)", "https://batocera.org")
        ]

        f_credits = ctk.CTkFrame(scroll_container, fg_color=AZUL_CARD, corner_radius=10, border_width=1, border_color=COLOR_BORDE)
        f_credits.pack(fill="x", padx=40, pady=8)

        for name, link in credits_licencias:
            row = ctk.CTkFrame(f_credits, fg_color="transparent")
            row.pack(fill="x", padx=15, pady=4)
            ctk.CTkLabel(row, text=f"• {name}", font=("Consolas", 12, "bold")).pack(side="left")
            ctk.CTkButton(
                row, text=t("modals.initial.code_web"), width=105, height=22, font=("Segoe UI", 10, "bold"),
                fg_color=AZUL_ELECTRICO, command=lambda l=link: webbrowser.open_new_tab(l)
            ).pack(side="right")

        lbl_legal = ctk.CTkLabel(
            f_credits,
            text=t("modals.initial.third_party_notice"),
            font=("Segoe UI", 10, "italic"),
            text_color="#888888",
            wraplength=600,
            justify="center"
        )
        lbl_legal.pack(padx=10, pady=(6, 8))

        f_medicat = ctk.CTkFrame(scroll_container, fg_color="#181824", border_width=1, border_color=AZUL_ELECTRICO, corner_radius=8)
        f_medicat.pack(fill="x", padx=40, pady=(10, 10))

        lbl_thanks = ctk.CTkLabel(
            f_medicat, 
            text=t("modals.initial.thanks"), 
            font=("Consolas", 11, "italic"), 
            text_color="#dddddd", 
            wraplength=520
        )
        lbl_thanks.pack(pady=8, padx=15)

        ctk.CTkButton(
            scroll_container, 
            text=t("modals.initial.enter_btn"), 
            font=("Segoe UI", 13, "bold"), 
            fg_color=AZUL_ELECTRICO, 
            width=240, 
            height=38, 
            command=v.destroy
        ).pack(pady=(15, 10))
        
        v.update()
        v.grab_set()

    def activar_interfaz_completa(self, seleccion):
        if not seleccion:
            return
        if "---" in seleccion or "Buscando" in seleccion or "NO SE DETECTAN" in seleccion or t("selector.searching") in seleccion or t("selector.no_units") in seleccion or t("selector.select_placeholder") in seleccion:
            return

        disco_elegido = next((d for d in getattr(self, 'lista_discos_reales', []) if d.get("display") == seleccion), None)
        if disco_elegido:
            self.gb_totales = float(disco_elegido.get("size", disco_elegido.get("size_gb", 0.0)))

        self.footer.pack(fill="x", side="bottom", padx=20, pady=(0, 2))
        self.main_container.pack(fill="both", expand=True, padx=20, pady=(2, 0))
        
        if self.preservar_espacio.get():
            self.val_libre_gb = max(5.0, round(self.gb_totales * 0.15, 1))
            self.val_hollow_gb = max(10.0, round(self.gb_totales - self.val_libre_gb, 1))
        else:
            self.val_hollow_gb = self.gb_totales
            self.val_libre_gb = 0.0
        self.val_cachy_gb = 0.0
        
        self.rebalancear()

    def alternar_gif_descarga(self, activo=True):
        if getattr(self, 'abortar_proceso', False):
            self.after(0, lambda: self.cambiar_gif(None))
            return

        if activo: 
            self.after(0, lambda: self.cambiar_gif(self.frames_breakdance))
        else: 
            self.after(0, lambda: self.cambiar_gif(self.frames_linterna))

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
            "cachy_flavor": getattr(self, 'cachy_flavor', ctk.StringVar(value="kde")).get()
        }

        self.hilo_instalacion = threading.Thread(target=self.proceso_instalacion_background, args=(config,), daemon=True)
        self.hilo_instalacion.start()

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

    def mostrar_popup_exito(self, t_total, tiempos):
        v = self.creventana_info_base(t("modals.success_title"), 500, 480)
        f_in = ctk.CTkFrame(v, fg_color="transparent")
        f_in.pack(expand=True, fill="both", padx=20, pady=20)

        mins_t, secs_t = divmod(int(t_total), 60)
        horas_t, mins_t = divmod(mins_t, 60)
        tiempo_str = f"{horas_t:02d}:{mins_t:02d}:{secs_t:02d}" if horas_t > 0 else f"{mins_t:02d}:{secs_t:02d}"

        ctk.CTkLabel(f_in, text=t("modals.success_header"), font=("Impact", 38), text_color=VERDE_EXITO).pack(pady=(0, 5))
        ctk.CTkLabel(f_in, text=t("modals.success_duration", time=tiempo_str), font=("Segoe UI", 18, "bold"), text_color=AZUL_CIAN).pack(pady=(0, 15))

        f_grid = ctk.CTkScrollableFrame(f_in, fg_color="#0d141c", height=200, corner_radius=10, border_width=1, border_color="#222")
        f_grid.pack(fill="x", pady=5)

        for nombre, dur in tiempos.items():
            m, s = divmod(int(dur), 60)
            row = ctk.CTkFrame(f_grid, fg_color="transparent")
            row.pack(fill="x", pady=4, padx=10)
            ctk.CTkLabel(row, text=nombre, font=("Segoe UI", 13)).pack(side="left")
            ctk.CTkLabel(row, text=f"{m:02d}m {s:02d}s", font=("Consolas", 13, "bold"), text_color="#aaaaaa").pack(side="right")

        ctk.CTkButton(f_in, text=t("modals.btn_finish"), font=("Segoe UI", 14, "bold"), fg_color=AZUL_ELECTRICO, height=40, width=200, command=v.destroy).pack(pady=(20, 0))
        v.update(); v.grab_set()

    def notificar_actualizacion(self, nueva_version, url_descarga):
        msg = f"¡Hay una nueva versión disponible de HollowDrive ({nueva_version})!\n\n¿Deseas descargarla e instalarla ahora automáticamente?"

        if messagebox.askyesno("ACTUALIZACIÓN DETECTADA", msg):
            self.bloquear_ui(True)
            self.lbl_status.configure(text="DESCARGANDO NUEVA VERSIÓN... POR FAVOR ESPERA", text_color=AZUL_CIAN)
            threading.Thread(target=self.ejecutar_auto_update, args=(url_descarga,), daemon=True).start()

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
            
            ventoy_dir = asegurar_herramientas_externas()
            if not ventoy_dir:
                engine_base = os.path.join(BASE_DIR, "engine")
                if os.path.exists(engine_base):
                    for root, dirs, files in os.walk(engine_base):
                        for f in files:
                            if f.lower() == "ventoy2disk.exe":
                                ventoy_dir = root
                                break
                        if ventoy_dir: break

            if not ventoy_dir: 
                raise RuntimeError("No se pudo localizar ni desplegar Ventoy2Disk.exe en la carpeta engine.")

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

                if "MB/s" in fase_str:
                    return pct, f"{nombre_tarea} | {pct*100:.1f}% | {fase_str}"

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
                        subprocess.run(f"label {letra[:2]} HOLLOWDRIVE", shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
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

            if letra_hollow:
                agregar_exclusion_antivirus(letra_hollow)
            else:
                raise RuntimeError("No se detectó la letra de unidad física para HOLLOWDRIVE.")

            # PASO PACK ROMS BATOCERA
            if "pack_bato" in pasos_activos:
                iniciar_cronometro("Pack Roms Batocera")
                if self.abortar_proceso: raise InterruptedError()
                self.after(0, lambda: self.alternar_gif_descarga(True))
                actualizar_progreso_paso(0.0, "Descargando e inyectando Pack Batocera...")
                
                self.descargar_y_extraer_batocera_pack(
                    letra_hollow, 
                    callback_progreso_externo=actualizar_progreso_paso
                )

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
                actualizar_progreso_paso(0.0, "Localizando configuración base...")
                
                ruta_tar_local = resource_path(os.path.join("engine", "resources", "ventoy.tar"))
                if not os.path.exists(ruta_tar_local):
                    raise RuntimeError(f"No se encontró el archivo base de Ventoy en: {ruta_tar_local}")

                try:
                    with tarfile.open(ruta_tar_local, "r") as tar:
                        miembros = tar.getmembers()
                        total_m = len(miembros)
                        for idx, member in enumerate(miembros):
                            if self.abortar_proceso: raise InterruptedError()
                            try:
                                tar.extract(member, path=letra_hollow, filter='data')
                            except TypeError:
                                tar.extract(member, path=letra_hollow)
                                
                            pct = (idx + 1) / total_m
                            actualizar_progreso_paso(pct, f"Inyectando base local: {member.name[:30]} ({idx+1}/{total_m})")
                except Exception as e: 
                    raise RuntimeError(f"Fallo al desempaquetar la configuración interna:\n{e}")
                    
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
                
                sabor_elegido = config.get("cachy_flavor", "kde")
                if sabor_elegido == "hyprland":
                    url_grub_hf = MIRRORS_DATA["cachyos_images"]["efi_grub_hyprland"]["mirrors"][0]["url"]
                else:
                    try: url_grub_hf = MIRRORS_DATA["cachyos_images"]["efi_grub"]["mirrors"][0]["url"]
                    except KeyError: url_grub_hf = "https://huggingface.co/datasets/HollowDrive/HollowDrive/resolve/main/hollowdrive_cachy_efi.img"
                
                t_start_grub = time.time()
                def progreso_grub(bytes_read, total_bytes, fase, override_start=None):
                    pct, msg = generar_mensaje_progreso("Arranque GRUB", bytes_read, total_bytes, t_start_grub, fase, override_start)
                    actualizar_progreso_paso(pct, msg)

                if not letra_grub: letra_grub = encontrar_letra_por_etiqueta_ps("GRUB") or esperar_unidad_por_etiqueta("GRUB", intentos=6)
                
                stream_flash_image_direct(
                    url_grub_hf, letra_grub, 
                    progress_callback=progreso_grub, 
                    abort_check=lambda: self.abortar_proceso, 
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
                    url_cachy_hf = MIRRORS_DATA["cachyos_images"]["hyprland"]["mirrors"][0]["url"]
                else:
                    try: url_cachy_hf = MIRRORS_DATA["cachyos_images"]["sistema"]["mirrors"][0]["url"]
                    except KeyError: url_cachy_hf = "https://huggingface.co/datasets/HollowDrive/HollowDrive/resolve/main/hollowdrive_cachy_sistema.img"
                
                t_start_cachy = time.time()
                def progreso_cachy(bytes_read, total_bytes, fase, override_start=None):
                    pct, msg = generar_mensaje_progreso("CachyOS (Ext4)", bytes_read, total_bytes, t_start_cachy, fase, override_start)
                    actualizar_progreso_paso(pct, msg)

                if not letra_cachy: letra_cachy = encontrar_letra_por_etiqueta_ps("CachyOS") or esperar_unidad_por_etiqueta("CachyOS", intentos=6)
                
                stream_flash_image_direct(
                    url_cachy_hf, letra_cachy, 
                    progress_callback=progreso_cachy, 
                    abort_check=lambda: self.abortar_proceso, 
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
            self.after(0, lambda err_text=msg: messagebox.showerror("ERROR FATAL", f"Fallo de sistema:\n{err_text}"))
            self.after(0, lambda: self.p_total.set(0.0))
            self.after(0, lambda: self.p_task.set(0.0))
            self.enviar_reporte_error("System Crash / Unpack Error", msg)
            
        finally:
            self.en_proceso = False
            self.after(0, lambda: self.cambiar_gif(None))
            self.after(0, lambda: self.bloquear_ui(False))
            self.after(0, lambda: self.alternar_modo_instalacion(False))

    # =====================================================================
    # 🎚️ LÓGICA Y DIBUJO DE LA BARRA UNIFICADA CON MANETAS
    # =====================================================================

    def _coords_bar(self):
        """ Delimita la barra horizontal fina de 14px """
        w = self.canvas.winfo_width()
        pad_x = 24
        y1, y2 = 18, 32  # Barra fina de 14px
        return pad_x, max(pad_x + 30, w - pad_x), y1, y2

    def _dibujar_maneta(self, x, hy1, hy2, glow_color):
        """ Dibuja una maneta vertical ultrafina (5px) con resplandor neón """
        self.canvas.create_line(x, hy1 + 3, x, hy2 - 3, width=8, capstyle="round", fill=glow_color)
        self.canvas.create_line(x, hy1 + 3, x, hy2 - 3, width=6, capstyle="round", fill="#05080a")
        self.canvas.create_line(x, hy1 + 3, x, hy2 - 3, width=4, capstyle="round", fill="#ffffff")
        self.canvas.create_line(x, hy1 + 7, x, hy2 - 7, width=1.5, capstyle="round", fill="#64748b")

    def _formato_gb(self, val):
        """ Omite el .0 si es entero; solo muestra decimales si realmente los hay """
        val_r = round(val, 1)
        if val_r == int(val_r):
            return f"{int(val_r)} GB"
        return f"{val_r:.1f} GB"

    def _ajustar_maneta_delta(self, handle_idx, delta_gb):
        total = self.gb_totales
        if total <= 0: return

        base_h = 10.0 if self.descargar_pack_hollow.get() else 3.0
        val_pack = self.tamanos_reales.get("pack_bato", 0.0) if self.descargar_pack_bato.get() else 0.0
        gb_bato = (self.tamanos_reales.get("bato_64", 0.0) if self.bato_64_act.get() else 0.0) if self.instalar_bato.get() else 0.0
        min_h = base_h + val_pack + gb_bato
        min_c = 20.0 if self.instalar_cachy.get() else 0.0
        min_libre = 5.0 if self.preservar_espacio.get() else 0.0

        if handle_idx == 1:
            if self.instalar_cachy.get():
                max_h = total - min_c - (self.val_libre_gb if self.preservar_espacio.get() else 0.0)
                self.val_hollow_gb = max(min_h, min(max_h, round(self.val_hollow_gb + delta_gb, 1)))
                if self.preservar_espacio.get():
                    self.val_cachy_gb = round(total - self.val_hollow_gb - self.val_libre_gb, 1)
                else:
                    self.val_cachy_gb = round(total - self.val_hollow_gb, 1)
            else:
                max_h = total - min_libre
                self.val_hollow_gb = max(min_h, min(max_h, round(self.val_hollow_gb + delta_gb, 1)))
                self.val_libre_gb = round(total - self.val_hollow_gb, 1) if self.preservar_espacio.get() else 0.0

        elif handle_idx == 2 and self.instalar_cachy.get() and self.preservar_espacio.get():
            max_pos = total - min_libre
            pos_act = self.val_hollow_gb + self.val_cachy_gb
            nueva_pos = max(self.val_hollow_gb + min_c, min(max_pos, round(pos_act + delta_gb, 1)))
            self.val_cachy_gb = round(nueva_pos - self.val_hollow_gb, 1)
            self.val_libre_gb = round(total - nueva_pos, 1)

        self.actualizar_barra_visual()

    def _on_bar_wheel(self, event):
        tiene_h1 = (self.instalar_cachy.get() and self.val_cachy_gb > 0) or (self.preservar_espacio.get() and self.val_libre_gb >= 0.1)
        tiene_h2 = self.instalar_cachy.get() and self.preservar_espacio.get() and (self.val_libre_gb >= 0.1)
        if not tiene_h1 and not tiene_h2: return

        d1 = abs(event.x - getattr(self, '_pos_h1', -999)) if tiene_h1 else 999
        d2 = abs(event.x - getattr(self, '_pos_h2', -999)) if tiene_h2 else 999

        handle = 1 if d1 <= d2 else 2
        paso = 0.1 if (event.state & 0x0001) else 1.0
        delta = paso if event.delta > 0 else -paso
        self._ajustar_maneta_delta(handle, delta)

    def _on_bar_key_left(self, event):
        tiene_h1 = (self.instalar_cachy.get() and self.val_cachy_gb > 0) or (self.preservar_espacio.get() and self.val_libre_gb >= 0.1)
        if not tiene_h1: return
        paso = 0.1 if (event.state & 0x0001) else 1.0
        handle = getattr(self, '_active_handle', 1) or 1
        self._ajustar_maneta_delta(handle, -paso)

    def _on_bar_key_right(self, event):
        tiene_h1 = (self.instalar_cachy.get() and self.val_cachy_gb > 0) or (self.preservar_espacio.get() and self.val_libre_gb >= 0.1)
        if not tiene_h1: return
        paso = 0.1 if (event.state & 0x0001) else 1.0
        handle = getattr(self, '_active_handle', 1) or 1
        self._ajustar_maneta_delta(handle, paso)

    def actualizar_barra_visual(self, *args):
        """ Dibuja la barra horizontal ancha con su leyenda siempre visible """
        if not hasattr(self, 'canvas') or not self.canvas.winfo_exists():
            return
        w = self.canvas.winfo_width()
        if w <= 20:
            self.after(60, self.actualizar_barra_visual)
            return

        self.canvas.delete("all")
        total = self.gb_totales
        if total <= 0: return

        x_start, x_end, y1, y2 = self._coords_bar()
        ancho_util = x_end - x_start
        r_bar = 7
        y_mid = (y1 + y2) // 2

        # 1. Riel base fino
        self.canvas.create_line(x_start + r_bar, y_mid, x_end - r_bar, y_mid, width=16, capstyle="round", fill="#1e293b")
        self.canvas.create_line(x_start + r_bar, y_mid, x_end - r_bar, y_mid, width=14, capstyle="round", fill="#0f172a")

        # 2. Proporciones
        pix_h = max(2, int((self.val_hollow_gb / total) * ancho_util))
        pix_c = int((self.val_cachy_gb / total) * ancho_util) if self.instalar_cachy.get() else 0

        x_h_end = min(x_end, x_start + pix_h)
        x_c_end = min(x_end, x_h_end + pix_c)

        tiene_cachy = self.instalar_cachy.get() and pix_c > 0
        tiene_libre = self.preservar_espacio.get() and (x_c_end < x_end)
        
        # Validación de manetas visibles
        tiene_h1 = tiene_cachy or self.preservar_espacio.get()
        tiene_h2 = tiene_cachy and self.preservar_espacio.get()

        # 3. Segmentos de color
        if not tiene_cachy and not tiene_libre:
            self.canvas.create_line(x_start + r_bar, y_mid, x_end - r_bar, y_mid, width=14, capstyle="round", fill=COLOR_HOLLOW)
        else:
            self.canvas.create_oval(x_start, y1, x_start + (2 * r_bar), y2, fill=COLOR_HOLLOW, outline="")
            self.canvas.create_rectangle(x_start + r_bar, y1, x_h_end, y2, fill=COLOR_HOLLOW, outline="")

            if tiene_cachy:
                if tiene_libre:
                    self.canvas.create_rectangle(x_h_end, y1, x_c_end, y2, fill=COLOR_CACHY, outline="")
                else:
                    self.canvas.create_rectangle(x_h_end, y1, x_end - r_bar, y2, fill=COLOR_CACHY, outline="")
                    self.canvas.create_oval(x_end - (2 * r_bar), y1, x_end, y2, fill=COLOR_CACHY, outline="")

            if tiene_libre:
                x_l_start = x_c_end if tiene_cachy else x_h_end
                self.canvas.create_rectangle(x_l_start, y1, x_end - r_bar, y2, fill=COLOR_LIBRE, outline="")
                self.canvas.create_oval(x_end - (2 * r_bar), y1, x_end, y2, fill=COLOR_LIBRE, outline="")

        # 4. Manetas: si no existen, su posición se fija en -999 (imposible de tocar)
        hy1, hy2 = 10, 40
        if tiene_h1:
            self._pos_h1 = x_h_end
            self._dibujar_maneta(self._pos_h1, hy1, hy2, "#00d4ff")
        else:
            self._pos_h1 = -999

        if tiene_h2:
            self._pos_h2 = x_c_end
            self._dibujar_maneta(self._pos_h2, hy1, hy2, "#10b981")
        else:
            self._pos_h2 = -999

        # 5. 1- LEYENDA CENTRADA MATEMÁTICAMENTE (Midiendo el bloque exacto)
        legend_items = [
            ("Hollowdrive", self._formato_gb(self.val_hollow_gb), "#00d4ff", "#0284c7")
        ]
        if tiene_cachy:
            legend_items.append(("Cachyos", self._formato_gb(self.val_cachy_gb), "#10b981", "#059669"))
        if tiene_libre:
            legend_items.append(("Libre", self._formato_gb(self.val_libre_gb), "#94a3b8", "#475569"))

        n_items = len(legend_items)
        y_legend = 60

        for i, (nombre, gb_str, col_txt, col_dot) in enumerate(legend_items):
            cx = (w * (i + 1)) / (n_items + 1)
            texto_unificado = f"{nombre}   {gb_str}"

            # 1. Medir el texto para centrar la unidad completa (LED + texto)
            t_id = self.canvas.create_text(cx, y_legend, text=texto_unificado, font=("Segoe UI", 13, "bold"), fill=col_txt, anchor="center")
            bbox = self.canvas.bbox(t_id)

            if bbox:
                t_w = bbox[2] - bbox[0]
                ancho_total = 20 + t_w
                inicio_x = cx - (ancho_total / 2)

                # Reposicionar texto y dibujar el LED a su izquierda
                self.canvas.coords(t_id, inicio_x + 20, y_legend)
                self.canvas.itemconfig(t_id, anchor="w")

                led_x = inicio_x + 6
                self.canvas.create_oval(led_x - 6, y_legend - 6, led_x + 6, y_legend + 6, fill="#0b1320", outline=col_dot, width=2)
                self.canvas.create_oval(led_x - 2, y_legend - 2, led_x + 2, y_legend + 2, fill=col_txt, outline="")

    def _on_bar_hover(self, event):
        """ Solo activa el cursor de arrastre si una maneta existe físicamente """
        pos1 = getattr(self, '_pos_h1', -999)
        pos2 = getattr(self, '_pos_h2', -999)

        d1 = abs(event.x - pos1) if pos1 > 0 else 999
        d2 = abs(event.x - pos2) if pos2 > 0 else 999

        if d1 <= 10 or d2 <= 10:
            self.canvas.configure(cursor="sb_h_double_arrow")
        else:
            self.canvas.configure(cursor="")

    def _on_bar_click(self, event):
        """ Candado estricto: no permite agarrar manetas invisibles o fuera de rango """
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
            self._active_handle = None  # Nunca se activa nada si se pulsa fuera o no hay manetas

    def _on_bar_drag(self, event):
        if not getattr(self, '_active_handle', None):
            return
        total = self.gb_totales
        if total <= 0: return

        x_start, x_end, _, _ = self._coords_bar()
        ancho_util = x_end - x_start
        mouse_x = max(x_start, min(x_end, event.x))
        gb_raw = ((mouse_x - x_start) / ancho_util) * total

        gb_cursor = round(gb_raw, 1) if (event.state & 0x0001) else round(gb_raw)

        base_h = 10.0 if self.descargar_pack_hollow.get() else 3.0
        val_pack = self.tamanos_reales.get("pack_bato", 0.0) if self.descargar_pack_bato.get() else 0.0
        gb_bato = (self.tamanos_reales.get("bato_64", 0.0) if self.bato_64_act.get() else 0.0) if self.instalar_bato.get() else 0.0
        min_h = base_h + val_pack + gb_bato
        min_c = 20.0 if self.instalar_cachy.get() else 0.0
        min_libre = 5.0 if self.preservar_espacio.get() else 0.0

        if self._active_handle == 1:
            if self.instalar_cachy.get():
                max_h = total - min_c - (self.val_libre_gb if self.preservar_espacio.get() else 0.0)
                nueva_h = max(min_h, min(max_h, gb_cursor))
                self.val_hollow_gb = round(nueva_h, 1)

                if self.preservar_espacio.get():
                    self.val_cachy_gb = round(total - self.val_hollow_gb - self.val_libre_gb, 1)
                else:
                    self.val_cachy_gb = round(total - self.val_hollow_gb, 1)
                    self.val_libre_gb = 0.0
            else:
                max_h = total - min_libre
                nueva_h = max(min_h, min(max_h, gb_cursor))
                self.val_hollow_gb = round(nueva_h, 1)
                self.val_libre_gb = round(total - self.val_hollow_gb, 1) if self.preservar_espacio.get() else 0.0
                self.val_cachy_gb = 0.0

        elif self._active_handle == 2:
            min_pos_gb = self.val_hollow_gb + min_c
            max_pos_gb = total - min_libre
            nuevo_pos = max(min_pos_gb, min(max_pos_gb, gb_cursor))

            self.val_cachy_gb = round(nuevo_pos - self.val_hollow_gb, 1)
            self.val_libre_gb = round(total - nuevo_pos, 1)

        self.actualizar_barra_visual()

    def _on_bar_release(self, event):
        self._active_handle = None

    def toggle_preservar_espacio(self):
        """ Controla la reserva de espacio libre al conmutar el switch """
        if self.gb_totales <= 0:
            return
        total = self.gb_totales

        if self.preservar_espacio.get():
            # Reserva un ~15% inicial para espacio libre recortándolo de Cachy o Hollow
            margen_libre = max(5.0, round(total * 0.15, 1))
            if self.instalar_cachy.get():
                if self.val_cachy_gb - margen_libre >= 20.0:
                    self.val_cachy_gb = round(self.val_cachy_gb - margen_libre, 1)
                    self.val_libre_gb = margen_libre
                else:
                    self.val_libre_gb = margen_libre
                    self.val_hollow_gb = max(10.0, round(total - self.val_cachy_gb - self.val_libre_gb, 1))
            else:
                self.val_libre_gb = margen_libre
                self.val_hollow_gb = max(10.0, round(total - self.val_libre_gb, 1))
        else:
            # Al apagar el switch, llena el disco al 100% (Libre = 0)
            if self.instalar_cachy.get():
                self.val_cachy_gb = round(total - self.val_hollow_gb, 1)
            else:
                self.val_hollow_gb = total
            self.val_libre_gb = 0.0

        self.actualizar_barra_visual()

    def rebalancear(self, source=None):
        """ Recalcula los mínimos y sincroniza las variables al cambiar cualquier checkbox """
        if self.gb_totales <= 0:
            return
        total = self.gb_totales

        base_h = 10.0 if self.descargar_pack_hollow.get() else 3.0
        val_pack = self.tamanos_reales.get("pack_bato", 0.0) if self.descargar_pack_bato.get() else 0.0
        gb_bato = (self.tamanos_reales.get("bato_64", 0.0) if self.bato_64_act.get() else 0.0) if self.instalar_bato.get() else 0.0
        min_h = base_h + val_pack + gb_bato

        # Bloqueo del pack de Batocera si no cabe en el disco
        espacio_restante = total - min_h - (20.0 if self.instalar_cachy.get() else 0.0)
        if self.instalar_bato.get():
            if espacio_restante >= self.tamanos_reales.get("pack_bato", 37.8):
                self.ch_pack_bato.configure(state="normal")
            else:
                self.descargar_pack_bato.set(False)
                self.ch_pack_bato.configure(state="disabled")

        # Ajuste de proporciones iniciales
        if self.instalar_cachy.get():
            if self.val_cachy_gb < 20.0:
                self.val_cachy_gb = 20.0
            if self.val_hollow_gb + self.val_cachy_gb + self.val_libre_gb > total:
                self.val_hollow_gb = max(min_h, round(total - self.val_cachy_gb - self.val_libre_gb, 1))
        else:
            self.val_cachy_gb = 0.0
            if not self.preservar_espacio.get():
                self.val_hollow_gb = total
                self.val_libre_gb = 0.0

        self.actualizar_barra_visual()

    def actualizar_estados_bato(self):
        """ Despliega las opciones de Batocera 64/32 bits encima de los packs """
        activado = self.instalar_bato.get()
        if activado:
            try:
                # Se empaqueta justo tras el switch de Batocera y antes de los packs
                self.f_bato_opts.pack(fill="x", pady=(2, 4), after=self.f_bato_h)
            except Exception:
                try: self.f_bato_opts.pack(fill="x", pady=(2, 4))
                except Exception: pass
        else:
            try: self.f_bato_opts.pack_forget()
            except Exception: pass
        self.rebalancear()

    def actualizar_estados_cachy(self):
        activado = self.instalar_cachy.get()
        if activado:
            try: self.f_cachy_opts.pack(fill="x", pady=2)
            except Exception: pass
        else:
            try: self.f_cachy_opts.pack_forget()
            except Exception: pass
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
        v = self.creventana_info_base(t("modals.ht_isos_title"), 640, 390)
        frame_interno = ctk.CTkFrame(v, fg_color="transparent")
        frame_interno.pack(expand=True, fill="both", padx=25, pady=20)
        ctk.CTkLabel(frame_interno, text=t("modals.ht_isos_header"), font=("Impact", 28), text_color=AZUL_CIAN).pack(pady=(0, 15))
        ctk.CTkLabel(frame_interno, text=t("modals.ht_isos_body"), font=("Segoe UI", 15), justify="left", wraplength=560).pack(pady=5)
        ctk.CTkButton(frame_interno, text=t("modals.btn_close"), font=("Segoe UI", 13, "bold"), fg_color=AZUL_ELECTRICO, height=40, width=160, command=v.destroy).pack(pady=(15, 0))
        v.update(); v.grab_set()

    def abrir_info_ht_packs(self):
        v = self.creventana_info_base(t("modals.ht_packs_title"), 660, 400)
        frame_interno = ctk.CTkFrame(v, fg_color="transparent")
        frame_interno.pack(expand=True, fill="both", padx=25, pady=20)
        ctk.CTkLabel(frame_interno, text=t("modals.ht_packs_header"), font=("Impact", 28), text_color=AZUL_CIAN).pack(pady=(0, 15))
        ctk.CTkLabel(frame_interno, text=t("modals.ht_packs_body"), font=("Segoe UI", 15), justify="left", wraplength=580).pack(pady=5)
        ctk.CTkButton(frame_interno, text=t("modals.btn_close"), font=("Segoe UI", 13, "bold"), fg_color=AZUL_ELECTRICO, height=40, width=160, command=v.destroy).pack(pady=(15, 0))
        v.update(); v.grab_set()

    def abrir_info_ht_cachy(self):
        v = self.creventana_info_base(t("modals.ht_cachy_title"), 660, 400)
        frame_interno = ctk.CTkFrame(v, fg_color="transparent")
        frame_interno.pack(expand=True, fill="both", padx=25, pady=20)
        ctk.CTkLabel(frame_interno, text=t("modals.ht_cachy_header"), font=("Impact", 28), text_color=COLOR_CACHY).pack(pady=(0, 15))
        ctk.CTkLabel(frame_interno, text=t("modals.ht_cachy_body"), font=("Segoe UI", 15), justify="left", wraplength=580).pack(pady=5)
        ctk.CTkButton(frame_interno, text=t("modals.btn_close"), font=("Segoe UI", 13, "bold"), fg_color=AZUL_ELECTRICO, height=40, width=160, command=v.destroy).pack(pady=(15, 0))
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

    def mostrar_menu_idioma(self):
        """ Despliega el menú de idiomas con flechita o lo contrae si ya está abierto """
        now = time.time()
        if (now - getattr(self, "_last_lang_close_time", 0.0)) < 0.35:
            return
        try:
            x = self.btn_idioma.winfo_rootx()
            y = self.btn_idioma.winfo_rooty() + self.btn_idioma.winfo_height() + 4
            self.menu_idioma.post(x, y)
        except Exception:
            pass
        finally:
            self._last_lang_close_time = time.time()

    def al_cambiar_idioma(self, seleccion):
        """ Callback cuando el usuario selecciona un nuevo idioma en el menú desplegable """
        codigo = seleccion.lower().strip()
        i18n.set_current_language(codigo)
        if hasattr(self, 'btn_idioma'):
            nombre = i18n.LANGUAGE_NAMES.get(codigo, codigo.upper())
            self.btn_idioma.configure(text=f" {nombre} ▾")
        self.actualizar_textos_idioma()

    def actualizar_textos_idioma(self):
        """ Actualiza en tiempo real todos los textos de la interfaz sin reiniciar """
        self.title(t("app.title", version=VERSION_ACTUAL))

        # Pestañas y selector
        if hasattr(self, 'btn_modo_installer'):
            self.btn_modo_installer.configure(text=t("nav.installer"))
        if hasattr(self, 'btn_modo_tools'):
            self.btn_modo_tools.configure(text=t("nav.tools"))
        if hasattr(self, 'lbl_select_disk'):
            self.lbl_select_disk.configure(text=t("selector.title"))
        if hasattr(self, 'sw_internos'):
            self.sw_internos.configure(text=t("selector.show_internal"))
        if hasattr(self, 'tooltip_refresh'):
            self.tooltip_refresh.text = t("tooltips.reload")

        # Combobox selector de discos instalador
        if hasattr(self, 'combo_disk'):
            curr_val = self.combo_disk.get()
            if not getattr(self, 'lista_discos_reales', []):
                self.combo_disk.configure(values=[t("selector.no_units")])
                self.combo_disk.set(t("selector.no_units"))
            elif any(k in curr_val for k in ["---", "Buscando", "Searching", "NO SE DETECTAN", "NO DRIVES", "Selecciona", "Select"]):
                nombres = [d["display"] for d in self.lista_discos_reales]
                self.combo_disk.configure(values=nombres)
                self.combo_disk.set(t("selector.select_placeholder"))

        # Batocera & CachyOS
        if hasattr(self, 'sw_bato'):
            self.sw_bato.configure(text=t("batocera.switch"))
        self.actualizar_labels_ui_con_tamanos_reales()
        if hasattr(self, 'sw_cachy'):
            self.sw_cachy.configure(text=t("cachyos.switch"))
        if hasattr(self, 'r_kde'):
            self.r_kde.configure(text=f"{t('cachyos.kde')} (Próximamente)")
        if hasattr(self, 'r_hypr'):
            self.r_hypr.configure(text=t("cachyos.hyprland"))

        # Motor de extracción
        if hasattr(self, 'lbl_motor'):
            self.lbl_motor.configure(text=t("motor.title"))
        if hasattr(self, 'r_motor_ram'):
            self.r_motor_ram.configure(text=t("motor.ram"))
        if hasattr(self, 'r_motor_disco'):
            self.r_motor_disco.configure(text=t("motor.disk"))
        if hasattr(self, 'sw_preservar'):
            self.sw_preservar.configure(text=t("motor.preserve_space"))

        # Botón principal
        if hasattr(self, 'btn_start') and not getattr(self, 'img_instalar', None):
            self.btn_start.configure(text=t("install_btn.text"))

        # HollowTools
        if hasattr(self, 'lbl_ht_title'):
            self.lbl_ht_title.configure(text=t("hollowtools.header_title"))
        if hasattr(self, 'tooltip_ht_refresh'):
            self.tooltip_ht_refresh.text = t("tooltips.reload")
        if hasattr(self, 'btn_ht_refresh') and not getattr(self, 'img_reload', None):
            self.btn_ht_refresh.configure(text="🔄")
        if hasattr(self, 'lbl_drag_msg'):
            self.lbl_drag_msg.configure(text=t("hollowtools.drop_msg"))
        if hasattr(self, 'lbl_card_iso'):
            self.lbl_card_iso.configure(text=t("hollowtools.card_iso_title"))
        if hasattr(self, 'lbl_card_packs'):
            self.lbl_card_packs.configure(text=t("hollowtools.card_packs_title"))
        if hasattr(self, 'lbl_card_cachy'):
            self.lbl_card_cachy.configure(text=t("hollowtools.card_cachy_title"))
        if hasattr(self, 'btn_ht_inject_bato'):
            self.btn_ht_inject_bato.configure(text=t("hollowtools.btn_inject_bato"))
        if hasattr(self, 'btn_ht_inject_packs'):
            self.btn_ht_inject_packs.configure(text=t("hollowtools.btn_inject_packs"))
        if hasattr(self, 'combo_ht_disk'):
            curr_ht = self.combo_ht_disk.get()
            if not getattr(self, 'lista_discos_hollow', []):
                self.combo_ht_disk.configure(values=[t("hollowtools.no_units")])
                self.combo_ht_disk.set(t("hollowtools.no_units"))
            elif any(k in curr_ht for k in ["---", "Buscando", "Searching", "NO SE DETECTAN", "NO DRIVES", "Selecciona", "Select"]):
                nombres_ht = [d["display"] for d in self.lista_discos_hollow]
                self.combo_ht_disk.configure(values=nombres_ht)
                self.combo_ht_disk.set(t("selector.select_placeholder"))

        # Rebalancear para refrescar la barra visual y las leyendas
        self.rebalancear()

    def animar_despliegue(self, widget, mostrar, altura_max, before_widget=None, pack_kwargs=None, on_finish=None):
        """
        Despliega u oculta suavemente un contenedor interpolando su altura (efecto acordeón fluido)
        forzando el refresco de idletasks para evitar artefactos visuales o duplicación de elementos.
        """
        anim_attr = f"_anim_slide_{id(widget)}"
        prev_id = getattr(self, anim_attr, None)
        if prev_id:
            try: self.after_cancel(prev_id)
            except Exception: pass

        pasos = 8
        intervalo = 12

        if mostrar:
            widget.pack_propagate(False)
            widget.configure(height=0)

            if not widget.winfo_ismapped():
                kwargs = pack_kwargs or {"fill": "x", "pady": 4}
                if before_widget:
                    widget.pack(**kwargs, before=before_widget)
                else:
                    widget.pack(**kwargs)

            def paso_expandir(paso=1):
                if not widget.winfo_exists(): return
                t = paso / pasos
                ease = 1 - (1 - t) * (1 - t)
                h = max(1, int(altura_max * ease))
                widget.configure(height=h)
                try: self.update_idletasks()
                except Exception: pass

                if paso < pasos:
                    setattr(self, anim_attr, self.after(intervalo, lambda: paso_expandir(paso + 1)))
                else:
                    widget.pack_propagate(True)
                    widget.configure(height=altura_max)
                    setattr(self, anim_attr, None)
                    try: 
                        self.update_idletasks()
                        if hasattr(self, 'rebalancear'): self.rebalancear()
                    except Exception: pass
                    if on_finish: on_finish()

            paso_expandir()

        else:
            if not widget.winfo_ismapped():
                return

            h_inicio = widget.winfo_height() or altura_max
            widget.pack_propagate(False)

            def paso_contraer(paso=1):
                if not widget.winfo_exists(): return
                t = paso / pasos
                ease = t * t
                h = max(0, int(h_inicio * (1 - ease)))
                widget.configure(height=h)
                try: self.update_idletasks()
                except Exception: pass

                if paso < pasos:
                    setattr(self, anim_attr, self.after(intervalo, lambda: paso_contraer(paso + 1)))
                else:
                    widget.pack_forget()
                    widget.pack_propagate(True)
                    setattr(self, anim_attr, None)
                    try:
                        self.update_idletasks()
                        if hasattr(self, 'rebalancear'): self.rebalancear()
                    except Exception: pass
                    if on_finish: on_finish()

            paso_contraer()

if __name__ == "__main__":
    if os.name == 'nt' and not es_administrador():
        root = tk.Tk()
        root.withdraw()
        
        respuesta = messagebox.askyesno(
            "PERMISOS REQUERIDOS",
            "Para obtener la MÁXIMA VELOCIDAD de instalación e I/O de archivos pequeños, "
            "se recomienda ejecutar HollowDrive como Administrador.\n\n"
            "¿Deseas reiniciar la aplicación con permisos de Administrador?"
        )
        root.destroy()
        
        if respuesta:
            try:
                ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
                sys.exit()
            except Exception as e:
                print(f"Error al elevar permisos: {e}")

    app = SavinOceanicCommand()
    app.mainloop()