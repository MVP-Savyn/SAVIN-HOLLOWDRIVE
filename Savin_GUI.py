import os
import sys
import time
from datetime import datetime
import json
import logging
import threading
import ctypes
from ctypes import wintypes
import subprocess
import requests
import urllib3
import socketserver
from wsgiref.simple_server import WSGIServer
# Ampliar el backlog de conexiones TCP de 5 a 128 para evitar net::ERR_CONNECTION_REFUSED
# en Microsoft WebView2 cuando solicita simultáneamente decenas de assets (scripts, CSS, fuentes, imágenes)
socketserver.TCPServer.request_queue_size = 128
WSGIServer.request_queue_size = 128

import bottle
import webview

from bridge_api import BridgeApi

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =====================================================================
# 📋 CAPTURA INTEGRAL DE TERMINAL Y LOGGING
# =====================================================================

if hasattr(sys, 'frozen') or '__compiled__' in globals():
    BASE_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LOGS_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

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
    def __init__(self, original_stream, log_file_path):
        self.original_stream = original_stream
        self.log_file_path = log_file_path
        self._f = open(log_file_path, "a", encoding="utf-8", buffering=1)

    def write(self, message):
        if self.original_stream is not None:
            try:
                self.original_stream.write(message)
                self.original_stream.flush()
            except Exception: pass
        if self._f and not self._f.closed:
            try:
                self._f.write(message)
                self._f.flush()
            except Exception: pass

    def flush(self):
        if self.original_stream is not None:
            try: self.original_stream.flush()
            except Exception: pass
        if self._f and not self._f.closed:
            try: self._f.flush()
            except Exception: pass

    def isatty(self):
        return getattr(self.original_stream, "isatty", lambda: False)()

_orig_stdout = sys.__stdout__ if sys.__stdout__ is not None else sys.stdout
_orig_stderr = sys.__stderr__ if sys.__stderr__ is not None else sys.stderr

sys.stdout = TerminalCaptureStream(_orig_stdout, archivo_log)
sys.stderr = TerminalCaptureStream(_orig_stderr, archivo_log)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

def unhandled_exception_handler(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.critical("CRASH NO CONTROLADO (sys.excepthook):", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = unhandled_exception_handler

# =====================================================================
# 🖥️ COMPATIBILIDAD DPI EN WINDOWS
# =====================================================================
if os.name == 'nt':
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception: pass

def es_administrador():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

VERSION_ACTUAL = "12.5"
logging.info(f"=== INICIANDO HOLLOWDRIVE V{VERSION_ACTUAL} (MOTOR PYWEBVIEW) ===")
logging.info(f"Ruta base del programa: {BASE_DIR}")
logging.info(f"Archivo de registro: {archivo_log}")

# =====================================================================
# 🌐 GESTIÓN DE SERVIDOR LOCAL BOTTLE (ASSETS & VÍDEO CON RANGE 206)
# =====================================================================
def crear_servidor_app():
    app = bottle.Bottle()

    frontend_dir = os.path.join(BASE_DIR, "frontend")
    media_dir = os.path.join(BASE_DIR, "media")
    docs_dir = os.path.join(BASE_DIR, "docs")
    assets_dir = os.path.join(docs_dir, "assets")

    @app.route('/')
    def index():
        return bottle.static_file('index.html', root=frontend_dir, headers={'Cache-Control': 'no-cache, must-revalidate'})

    @app.route('/favicon.ico')
    def serve_favicon():
        return bottle.static_file('hollowdrive.ico', root=media_dir, headers={'Cache-Control': 'public, max-age=86400'})

    @app.route('/css/<filepath:path>')
    def serve_css(filepath):
        return bottle.static_file(filepath, root=os.path.join(frontend_dir, 'css'), headers={'Cache-Control': 'no-cache, must-revalidate'})

    @app.route('/js/<filepath:path>')
    def serve_js(filepath):
        return bottle.static_file(filepath, root=os.path.join(frontend_dir, 'js'), headers={'Cache-Control': 'no-cache, must-revalidate'})

    @app.route('/media/<filepath:path>')
    def serve_media(filepath):
        return bottle.static_file(filepath, root=media_dir, headers={'Cache-Control': 'public, max-age=86400'})

    @app.route('/docs/<filepath:path>')
    def serve_docs(filepath):
        return bottle.static_file(filepath, root=docs_dir, headers={'Cache-Control': 'public, max-age=86400'})

    @app.route('/assets/<filepath:path>')
    def serve_assets(filepath):
        return bottle.static_file(filepath, root=assets_dir, headers={'Cache-Control': 'public, max-age=86400'})

    return app

def iniciar_watchdog():
    try:
        watchdog_script = os.path.join(BASE_DIR, "engine", "watchdog.py")
        if os.path.exists(watchdog_script):
            flags = 0
            if os.name == 'nt' and hasattr(subprocess, 'CREATE_NO_WINDOW'):
                flags = subprocess.CREATE_NO_WINDOW
            subprocess.Popen(
                [sys.executable, watchdog_script, str(os.getpid()), archivo_log],
                creationflags=flags
            )
            logging.info(f"✔ Proceso Watchdog iniciado para PID {os.getpid()}")
    except Exception as e:
        logging.warning(f"No se pudo iniciar el Watchdog: {e}")

# =====================================================================
# 🚀 ARRANQUE DE LA APLICACIÓN
# =====================================================================
def main():
    iniciar_watchdog()
    api = BridgeApi()
    server_app = crear_servidor_app()

    window = webview.create_window(
        title=f"HOLLOWDRIVE // V{VERSION_ACTUAL}",
        url=server_app,
        js_api=api,
        width=1060,
        height=860,
        min_size=(940, 700),
        frameless=True,
        easy_drag=False,
        background_color='#05080c'
    )

    api.set_window(window)

    def on_closing():
        if api.is_installing():
            MB_YESNO = 0x00000004
            MB_ICONWARNING = 0x00000030
            IDYES = 6
            if os.name == 'nt':
                res = ctypes.windll.user32.MessageBoxW(
                    None,
                    "Los datos del USB ya se han borrado.\n\n¿Estás seguro de que deseas cancelar la instalación y salir?",
                    "HollowDrive - Instalación en Curso",
                    MB_YESNO | MB_ICONWARNING
                )
                if res == IDYES:
                    api.cancel_installation()
                    return True
                else:
                    return False
            else:
                api.cancel_installation()
                return True
        return True

    def aplicar_esquinas_redondeadas():
        try:
            if os.name == 'nt' and hasattr(window, 'native') and window.native:
                hwnd = window.native.Handle.ToInt64()
                # Windows 11 DWM: Forzar esquinas redondeadas en ventana frameless (DWMWCP_ROUND = 2)
                DWMWA_WINDOW_CORNER_PREFERENCE = 33
                DWMWCP_ROUND = 2
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    ctypes.c_void_p(hwnd),
                    wintypes.DWORD(DWMWA_WINDOW_CORNER_PREFERENCE),
                    ctypes.byref(ctypes.c_int(DWMWCP_ROUND)),
                    ctypes.sizeof(ctypes.c_int)
                )
                logging.info("✔ Esquinas redondeadas aplicadas a la ventana vía DWM")
        except Exception as e:
            logging.warning(f"No se pudieron configurar esquinas redondeadas DWM: {e}")

    window.events.shown += aplicar_esquinas_redondeadas
    window.events.closing += on_closing

    # Directorio de datos y caché persistente para Microsoft WebView2
    # Evita la condición de carrera con tempfile.TemporaryDirectory() que causa E_ABORT (0x80004004)
    storage_dir = os.environ.get('HOLLOWDRIVE_STORAGE_DIR') or os.path.join(os.environ.get('LOCALAPPDATA', BASE_DIR), 'HollowDrive', 'webview_data')
    try:
        os.makedirs(storage_dir, exist_ok=True)
    except Exception as e:
        logging.warning(f"No se pudo asegurar directorio de datos webview: {e}")
        storage_dir = None

    debug_mode = '--debug' in sys.argv or os.environ.get('HOLLOWDRIVE_DEBUG') == '1'
    webview.settings['OPEN_DEVTOOLS_IN_DEBUG'] = False
    if os.environ.get('WEBVIEW_REMOTE_DEBUGGING_PORT'):
        try:
            webview.settings['REMOTE_DEBUGGING_PORT'] = int(os.environ.get('WEBVIEW_REMOTE_DEBUGGING_PORT'))
        except Exception:
            pass

    # Iniciar bucle principal de pywebview
    webview.start(
        debug=debug_mode,
        private_mode=False,
        storage_path=storage_dir,
        gui='edgechromium'
    )

if __name__ == '__main__':
    main()