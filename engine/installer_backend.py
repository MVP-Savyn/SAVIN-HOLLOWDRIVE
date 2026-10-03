import os
import sys
import time
import re
import json
import queue
import shutil
import tarfile
import logging
import threading
import subprocess
import ctypes
from ctypes import wintypes
from urllib.parse import urlparse
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

GB_GRUB = 0.512

if hasattr(sys, 'frozen') or '__compiled__' in globals():
    BASE_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from engine.disk_logic import (
    obtener_estructura_disco_ps,
    ejecutar_powershell_seguro,
    instalar_ventoy,
    crear_particion_adicional,
    _disk_query_lock
)
from engine.time_estimator import UsbTimeEstimator

# =====================================================================
# ⚡ ESTIMACIÓN Y CONTROL DE TIEMPO / FLUJO
# =====================================================================

def formatear_eta(segundos):
    if segundos <= 0 or segundos > 86400:
        return "--:--"
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
                if self.abort_check and self.abort_check():
                    break
                if chunk:
                    self.q.put(chunk)
        except Exception as e:
            self.error = e
        finally:
            self.q.put(None)

    def read(self, size=-1):
        if self.abort_check and self.abort_check():
            raise InterruptedError("Extracción cancelada.")

        if size == -1:
            data = self.leftover
            self.leftover = b""
            while not self.finished:
                chunk = self.q.get()
                if chunk is None:
                    self.finished = True
                    if self.error:
                        raise self.error
                    break
                data += chunk
                self.bytes_read += len(chunk)
            return data

        while len(self.leftover) < size and not self.finished:
            if self.abort_check and self.abort_check():
                raise InterruptedError("Extracción cancelada.")
            chunk = self.q.get()
            if chunk is None:
                self.finished = True
                if self.error:
                    raise self.error
                break
            self.leftover += chunk

        data = self.leftover[:size]
        self.leftover = self.leftover[size:]
        self.bytes_read += len(data)

        if self.progress_callback and (self.bytes_read - self.last_reported_bytes > 5 * 1024 * 1024):
            self.last_reported_bytes = self.bytes_read
            self.progress_callback(self.bytes_read, self.total_size, "Extrayendo al vuelo")

        return data


# =====================================================================
# 🛠️ UTILIDADES DE SISTEMA Y RECURSOS
# =====================================================================

def resource_path(relative_path):
    if "NUITKA_ONEFILE_DIRECTORY" in os.environ:
        base_path = os.environ["NUITKA_ONEFILE_DIRECTORY"]
    elif hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = BASE_DIR
    return os.path.join(base_path, relative_path)


def obtener_ruta_7z():
    posibles_rutas = [
        resource_path(os.path.join("engine", "resources", "7z.exe")),
        resource_path(os.path.join("engine", "7z.exe")),
        os.path.join(BASE_DIR, "engine", "resources", "7z.exe"),
        os.path.join(BASE_DIR, "engine", "7z.exe"),
        "7z.exe"
    ]
    for ruta in posibles_rutas:
        if os.path.exists(ruta):
            return ruta
    return None


def agregar_exclusion_antivirus(ruta_o_unidad):
    if os.name == 'nt':
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
        if match_raw:
            token = match_raw.group(1)

    if token and len(token) > 2:
        res = session.get(url, params={'id': file_id, 'confirm': token}, stream=True)

    if 'text/html' in res.headers.get('Content-Type', ''):
        body_snip = res.text[:1000] if hasattr(res, 'text') else ""
        if "quotaExceeded" in body_snip or "cuota" in body_snip.lower():
            raise RuntimeError("Google Drive: Límite de cuota de descarga excedido para este archivo público.")
        raise RuntimeError("Google Drive bloqueó el acceso directo o el archivo no está disponible.")

    return res


# =====================================================================
# 🌊 STREAMING RESILIENTE Y MULTIPARTE (ENCADENADO A 7-ZIP)
# =====================================================================

def generar_stream_resiliente_v2(url, chunk_size=512 * 1024, abort_check=None):
    """
    Descarga una URL mediante stream HTTP con reanudación automática Range
    y hasta 8 reintentos ante desconexiones.
    """
    if not url or not isinstance(url, str) or not url.startswith("http"):
        raise ValueError(f"URL no válida: '{url}'")

    session = requests.Session()
    session.verify = False

    headers_base = {
        "User-Agent": "HollowDrive-Installer/1.2",
        "Connection": "keep-alive",
        "Accept-Encoding": "identity"
    }

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
                raise InterruptedError("Operación abortada por el usuario.")

            req_headers = {}
            if bytes_read > 0:
                req_headers["Range"] = f"bytes={bytes_read}-"
                logging.info(f"🔄 [RED] Reanudando descarga desde byte {bytes_read} ({bytes_read / (1024**2):.1f} MB)...")

            try:
                with session.get(url, headers=req_headers, stream=True, timeout=(6.0, 15.0)) as response:
                    if bytes_read > 0 and response.status_code not in (200, 206):
                        raise RuntimeError(f"El servidor rechazó el rango HTTP (Status: {response.status_code})")
                    response.raise_for_status()

                    retries = 0

                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if abort_check and abort_check():
                            raise InterruptedError("Operación abortada por el usuario.")

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


def generar_stream_multi_parte(urls, chunk_size=4 * 1024 * 1024, abort_check=None):
    """
    Itera secuencialmente sobre una lista de URLs (ej. .001 a .005) emitiendo
    un flujo continuo ininterrumpido de bytes (yield chunk).
    Calcula el tamaño acumulado total antes de comenzar.
    """
    total_size_acumulado = 0
    tamanos_partes = []

    session = requests.Session()
    session.verify = False

    for u in urls:
        try:
            head_res = session.head(u, allow_redirects=True, timeout=5.0)
            sz = int(head_res.headers.get('Content-Length', 0)) or 0
        except Exception:
            sz = 0
        tamanos_partes.append(sz)
        total_size_acumulado += sz

    def multi_generator():
        for idx, u in enumerate(urls, 1):
            logging.info(f"📦 [MULTIPARTE] Conectando a parte {idx}/{len(urls)}: {u}")
            stream_gen, _ = generar_stream_resiliente_v2(u, chunk_size=chunk_size, abort_check=abort_check)
            for chunk in stream_gen:
                if abort_check and abort_check():
                    raise InterruptedError("Extracción multiparte cancelada.")
                yield chunk

    return multi_generator(), total_size_acumulado if total_size_acumulado > 0 else None


def descargar_y_extraer_pack_generico(
    pack_data,
    target_dir_or_file,
    method="ram",
    progress_callback=None,
    abort_check=None
):
    """
    Motor genérico de descarga y extracción.
    Soporta:
      - format == "tar_multipart": lista de URLs en 'parts', descomprime directo con 7-Zip vía stdin
      - format == "single_file": una o varias URLs, descarga a target_dir_or_file
    """
    fmt = pack_data.get("format", "tar_multipart")
    parts = pack_data.get("parts", [])
    urls = [p["url"] if isinstance(p, dict) else str(p) for p in parts]

    if not urls:
        raise ValueError("No se encontraron URLs de descarga en el paquete especificado.")

    nombre_pack = pack_data.get("name", "Paquete")

    if fmt in ("tar_multipart", "tar"):
        os.makedirs(target_dir_or_file, exist_ok=True)
        ruta_7z = obtener_ruta_7z()

        if ruta_7z:
            cmd = [ruta_7z, "x", "-si", "-ttar", f"-o{target_dir_or_file}", "-y"]
        else:
            cmd = ["tar", "-xf", "-", "-C", target_dir_or_file]

        if method == "ram":
            logging.info(f"🚀 [MOTOR RAM] Descomprimiendo '{nombre_pack}' al vuelo con {len(urls)} partes...")
            stream_gen, total_size = generar_stream_multi_parte(urls, chunk_size=4 * 1024 * 1024, abort_check=abort_check)

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
            eta_calc = ETACalculator(total_size) if total_size else None
            last_ui_update = 0.0

            try:
                for chunk in stream_gen:
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
                            pct = (bytes_read / total_size) if total_size else 0.0
                            msg = f"{nombre_pack} | {mb_s:.1f} MB/s | Faltan: {formatear_eta(eta_sec)}" if mb_s else f"{nombre_pack} | Extrayendo..."
                            progress_callback(bytes_read, total_size or bytes_read, pct, msg)

                proc.stdin.close()
                proc.wait()

                if proc.returncode != 0:
                    err = proc.stderr.read().decode('utf-8', errors='ignore')
                    raise RuntimeError(f"Error en extracción 7-Zip (código {proc.returncode}): {err}")

                if progress_callback:
                    progress_callback(bytes_read, total_size or bytes_read, 1.0, f"✔ {nombre_pack} completado con éxito")

            except Exception as e:
                proc.kill()
                raise e

        else:
            # Modo Disco (Fallback para conexiones inestables)
            logging.info(f"💾 [MODO DISCO] Descargando '{nombre_pack}' secuencialmente a disco temporal...")
            temp_dir = os.path.join(BASE_DIR, "engine", "temp_downloads")
            os.makedirs(temp_dir, exist_ok=True)
            archivos_temporales = []

            try:
                for idx, u in enumerate(urls, 1):
                    if abort_check and abort_check():
                        raise InterruptedError()
                    nombre_tmp = f"part_{idx:03d}.tmp"
                    dest_tmp = os.path.join(temp_dir, nombre_tmp)
                    archivos_temporales.append(dest_tmp)

                    stream_gen, sz_part = generar_stream_resiliente_v2(u, chunk_size=2 * 1024 * 1024, abort_check=abort_check)
                    bytes_p = 0
                    eta_part = ETACalculator(sz_part) if sz_part else None

                    with open(dest_tmp, "wb") as f_out:
                        for chunk in stream_gen:
                            if abort_check and abort_check():
                                raise InterruptedError()
                            f_out.write(chunk)
                            bytes_p += len(chunk)
                            if progress_callback and eta_part:
                                mb_s, eta_sec = eta_part.update(bytes_p)
                                msg = f"Descargando parte {idx}/{len(urls)}: {mb_s:.1f} MB/s | Faltan: {formatear_eta(eta_sec)}"
                                progress_callback(bytes_p, sz_part, bytes_p / sz_part if sz_part else 0.5, msg)

                logging.info("✔ Todas las partes descargadas a disco. Descomprimiendo con 7-Zip...")
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

                for f_path in archivos_temporales:
                    with open(f_path, "rb") as f_in:
                        while True:
                            if abort_check and abort_check():
                                proc.kill()
                                raise InterruptedError()
                            b = f_in.read(4 * 1024 * 1024)
                            if not b:
                                break
                            proc.stdin.write(b)
                            proc.stdin.flush()

                proc.stdin.close()
                proc.wait()

                if proc.returncode != 0:
                    err = proc.stderr.read().decode('utf-8', errors='ignore')
                    raise RuntimeError(f"Fallo al extraer desde disco: {err}")

            finally:
                for f_tmp in archivos_temporales:
                    if os.path.exists(f_tmp):
                        try:
                            os.remove(f_tmp)
                        except Exception:
                            pass

    elif fmt == "single_file":
        url = urls[0]
        os.makedirs(os.path.dirname(target_dir_or_file), exist_ok=True)
        stream_gen, total_size = generar_stream_resiliente_v2(url, chunk_size=2 * 1024 * 1024, abort_check=abort_check)
        eta_calc = ETACalculator(total_size) if total_size else None
        bytes_read = 0
        last_ui_update = 0.0

        with open(target_dir_or_file, "wb") as f_out:
            for chunk in stream_gen:
                if abort_check and abort_check():
                    raise InterruptedError()
                f_out.write(chunk)
                f_out.flush()
                bytes_read += len(chunk)

                now = time.time()
                if progress_callback and eta_calc and (now - last_ui_update >= 0.8):
                    last_ui_update = now
                    mb_s, eta_sec = eta_calc.update(bytes_read)
                    pct = (bytes_read / total_size) if total_size else 0.0
                    msg = f"{nombre_pack}: {mb_s:.1f} MB/s | Faltan: {formatear_eta(eta_sec)}"
                    progress_callback(bytes_read, total_size, pct, msg)

        if progress_callback:
            progress_callback(bytes_read, total_size, 1.0, f"✔ {nombre_pack} guardado con éxito.")


def stream_extract_tar(url_or_id=None, target_dir="", dest_dir=None, is_gdrive=False,
                       progress_callback=None, abort_check=None, method="ram",
                       custom_stream=None, custom_total_size=None):
    """ Envoltura compatible hacia atrás para paquetes tar simples """
    directorio_destino = dest_dir or target_dir
    os.makedirs(directorio_destino, exist_ok=True)

    pack_data = {
        "name": "Extracción Tar",
        "format": "tar_multipart",
        "parts": [{"url": url_or_id}] if url_or_id else []
    }

    def adapt_cb(b_read, t_size, pct, msg):
        if progress_callback:
            progress_callback(b_read, t_size, msg)

    descargar_y_extraer_pack_generico(
        pack_data=pack_data,
        target_dir_or_file=directorio_destino,
        method=method,
        progress_callback=adapt_cb,
        abort_check=abort_check
    )


def stream_download_file_direct(url_or_id, dest_path, is_gdrive=False, progress_callback=None, abort_check=None):
    pack_data = {
        "name": os.path.basename(dest_path),
        "format": "single_file",
        "parts": [{"url": url_or_id}]
    }

    def adapt_cb(b_read, t_size, pct, msg):
        if progress_callback:
            progress_callback(b_read, t_size, msg)

    descargar_y_extraer_pack_generico(
        pack_data=pack_data,
        target_dir_or_file=dest_path,
        method="ram",
        progress_callback=adapt_cb,
        abort_check=abort_check
    )


def stream_flash_image_direct(url, letra_unidad, progress_callback=None, abort_check=None, method="ram"):
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
        logging.info(f"[FLASH RAM] Volcado directo al volumen físico: {ruta_raw}")
        if progress_callback:
            progress_callback(0, 100, "Conectando al servidor...")

        stream_gen, total_size = generar_stream_resiliente_v2(url, chunk_size=512 * 1024, abort_check=abort_check)

        handle = kernel32.CreateFileW(
            ruta_raw, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE,
            None, OPEN_EXISTING, FILE_FLAG_NO_BUFFERING, None
        )
        if handle == INVALID_HANDLE_VALUE or handle == 0:
            handle = kernel32.CreateFileW(
                ruta_raw, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE,
                None, OPEN_EXISTING, 0, None
            )
            if handle == INVALID_HANDLE_VALUE or handle == 0:
                raise PermissionError(f"Windows denegó el acceso físico al volumen {ruta_raw}.")

        MAX_COLA = 256
        cola_bloques = queue.Queue(maxsize=MAX_COLA)
        error_red = []

        def hilo_descarga_red():
            try:
                for chunk in stream_gen:
                    cola_bloques.put(chunk)
            except Exception as ex:
                error_red.append(ex)
            finally:
                cola_bloques.put(None)

        t_red = threading.Thread(target=hilo_descarga_red, daemon=True)
        t_red.start()

        if progress_callback:
            progress_callback(0, total_size or 100, "Llenando búfer de RAM...")
        while cola_bloques.qsize() < 64 and t_red.is_alive():
            if abort_check and abort_check():
                raise InterruptedError("Flasheo abortado durante precarga.")
            if error_red:
                raise error_red[0]
            time.sleep(0.05)

        try:
            bytes_returned = wintypes.DWORD(0)
            kernel32.DeviceIoControl(handle, FSCTL_LOCK_VOLUME, None, 0, None, 0, ctypes.byref(bytes_returned), None)
            kernel32.DeviceIoControl(handle, FSCTL_DISMOUNT_VOLUME, None, 0, None, 0, ctypes.byref(bytes_returned), None)

            bytes_escritos = 0
            eta_calc = ETACalculator(total_size) if total_size else None
            last_ui_update = 0.0

            while True:
                if abort_check and abort_check():
                    raise InterruptedError("Flasheo abortado por el usuario.")
                if error_red:
                    raise error_red[0]

                bloque = cola_bloques.get()
                if bloque is None:
                    break

                if len(bloque) % 4096 != 0:
                    bloque += b'\x00' * (4096 - (len(bloque) % 4096))

                written = wintypes.DWORD(0)
                exito = kernel32.WriteFile(handle, bloque, len(bloque), ctypes.byref(written), None)
                if not exito:
                    raise IOError(f"Error de escritura en sector físico: Win32 Code {kernel32.GetLastError()}")

                bytes_escritos += written.value

                now = time.time()
                if progress_callback and eta_calc and (now - last_ui_update >= 0.8):
                    last_ui_update = now
                    mb_s, eta_sec = eta_calc.update(bytes_escritos)
                    if mb_s is not None:
                        progress_callback(bytes_escritos, total_size, f"{mb_s:.1f} MB/s | Faltan: {formatear_eta(eta_sec)}")
        finally:
            kernel32.CloseHandle(handle)

    else:
        # Modo Disco SSD
        temp_dir = os.path.join(BASE_DIR, "engine", "temp_downloads")
        os.makedirs(temp_dir, exist_ok=True)
        temp_img = os.path.join(temp_dir, "temp_flash.img")

        stream_gen, total_size = generar_stream_resiliente_v2(url, chunk_size=2 * 1024 * 1024, abort_check=abort_check)
        bytes_net = 0
        eta_calc_net = ETACalculator(total_size) if total_size else None
        last_ui_update = 0.0

        with open(temp_img, "wb") as f_out:
            for chunk in stream_gen:
                if abort_check and abort_check():
                    if os.path.exists(temp_img):
                        os.remove(temp_img)
                    raise InterruptedError("Descarga a SSD abortada.")
                if chunk:
                    f_out.write(chunk)
                    bytes_net += len(chunk)
                    now = time.time()
                    if progress_callback and eta_calc_net and (now - last_ui_update >= 0.8):
                        last_ui_update = now
                        mb_s, eta_sec = eta_calc_net.update(bytes_net)
                        if mb_s is not None:
                            progress_callback(bytes_net, total_size, f"Descargando a SSD: {mb_s:.1f} MB/s | Faltan: {formatear_eta(eta_sec)}")

        handle = kernel32.CreateFileW(
            ruta_raw, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE,
            None, OPEN_EXISTING, FILE_FLAG_NO_BUFFERING, None
        )
        if handle == INVALID_HANDLE_VALUE or handle == 0:
            handle = kernel32.CreateFileW(
                ruta_raw, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE,
                None, OPEN_EXISTING, 0, None
            )
            if handle == INVALID_HANDLE_VALUE or handle == 0:
                if os.path.exists(temp_img):
                    os.remove(temp_img)
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
                        raise InterruptedError("Flasheo desde SSD abortado.")

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
                    if progress_callback and eta_calc_flash and (now - last_ui_update >= 0.8):
                        last_ui_update = now
                        mb_s, eta_sec = eta_calc_flash.update(bytes_escritos)
                        if mb_s is not None:
                            progress_callback(bytes_escritos, total_size, f"Flasheando desde SSD: {mb_s:.1f} MB/s | Faltan: {formatear_eta(eta_sec)}")
        finally:
            kernel32.CloseHandle(handle)
            if os.path.exists(temp_img):
                try:
                    os.remove(temp_img)
                except Exception:
                    pass


# =====================================================================
# 💿 DETECCIÓN Y MANIPULACIÓN DE PARTICIONES
# =====================================================================

def encontrar_letra_por_etiqueta_ps(label, disk_index=None):
    if disk_index is not None:
        try:
            particiones = obtener_estructura_disco_ps(disk_index)
            for p in particiones:
                lbl = (p.get("Label") or "").strip().upper()
                if lbl == label.strip().upper():
                    letra = p.get("Letter")
                    if letra:
                        return f"{letra}:\\"
        except Exception as e:
            logging.warning(f"Error buscando partición en disco {disk_index}: {e}")

    try:
        if disk_index is not None:
            cmd = (f'[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; '
                   f'Get-Partition -DiskNumber {disk_index} | ForEach-Object {{ '
                   f'$v = Get-Volume -Partition $_ -ErrorAction SilentlyContinue; '
                   f'if ($v -and $v.FileSystemLabel -eq "{label}") {{ $_.DriveLetter }} }}')
        else:
            cmd = (f'[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; '
                   f'Get-Volume | Where-Object {{$_.FileSystemLabel -eq "{label}"}} | '
                   f'Select-Object -ExpandProperty DriveLetter')
        output = ejecutar_powershell_seguro(cmd)
        clean_output = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', output).strip()
        letters = re.findall(r'[A-Za-z]', clean_output)
        if letters:
            return f"{letters[0].upper()}:\\"
    except Exception as e:
        logging.error(f"Error detectando volumen '{label}': {e}")
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
        if not free_letter:
            return None

        script = f"select disk {disk_index}\nselect partition {part_number}\nassign letter={free_letter}\nrescan\n"
        script_path = os.path.join(BASE_DIR, "engine", "assign_temp.txt")
        with open(script_path, "w") as f:
            f.write(script)

        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        with _disk_query_lock:
            subprocess.run(["diskpart", "/s", script_path], startupinfo=si, creationflags=subprocess.CREATE_NO_WINDOW)

        if os.path.exists(script_path):
            os.remove(script_path)
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
            if letra:
                letra_grub = f"{letra}:\\"
            else:
                letra_grub = asignar_letra_particion_ps(disk_index, num)
        elif "CACHY" in lbl or (size >= 5.0 and num != 1):
            if letra:
                letra_cachy = f"{letra}:\\"
            else:
                letra_cachy = asignar_letra_particion_ps(disk_index, num)

    if not letra_grub:
        letra_grub = encontrar_letra_por_etiqueta_ps("GRUB", disk_index=disk_index)
    if not letra_cachy:
        letra_cachy = encontrar_letra_por_etiqueta_ps("CachyOS", disk_index=disk_index)

    return letra_grub, letra_cachy


def eliminar_particiones_cachy_diskpart(disk_index):
    """
    Elimina limpiamente todas las particiones existentes de CachyOS y GRUB
    dejando intactas la partición 1 (HOLLOWDRIVE/Ventoy) y la partición EFI de Ventoy (VTOYEFI).
    Borra en orden descendente para evitar colisiones de numeración en Diskpart.
    """
    try:
        particiones = obtener_estructura_disco_ps(disk_index)
        to_delete = []
        for p in particiones:
            num = p.get("Number")
            if not num or num == 1:
                continue
            lbl = (p.get("Label") or "").upper()
            size = float(p.get("Size") or 0.0)

            # Proteger siempre HOLLOWDRIVE y la partición EFI de Ventoy
            if lbl in ["HOLLOWDRIVE", "VENTOY", "VTOYEFI"] or "VTOY" in lbl:
                continue
            if size < 0.1 and "GRUB" not in lbl:
                # Partición de arranque EFI de Ventoy (~32MB)
                continue

            # Cualquier otra partición (GRUB, CachyOS, ext4, etc.)
            to_delete.append(num)

        # Si no se detectaron por etiqueta pero hay particiones más allá de la 2:
        if not to_delete:
            for p in particiones:
                num = p.get("Number")
                if num and num > 2 and num not in to_delete:
                    to_delete.append(num)

        # Orden descendente (ej: [4, 3])
        to_delete.sort(reverse=True)

        if to_delete:
            logging.info(f"[DISKPART] Eliminando particiones antiguas de CachyOS/GRUB en disco {disk_index}: {to_delete}")
            script_path = os.path.join(BASE_DIR, "engine", "del_cachy.txt")
            lines = [f"select disk {disk_index}\n"]
            for num in to_delete:
                lines.append(f"select partition {num}\n")
                lines.append("delete partition override\n")
            lines.append("rescan\n")

            with open(script_path, "w") as f:
                f.writelines(lines)

            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = subprocess.SW_HIDE
            subprocess.run(["diskpart", "/s", script_path], startupinfo=si, creationflags=subprocess.CREATE_NO_WINDOW)
            if os.path.exists(script_path):
                try: os.remove(script_path)
                except Exception: pass
            time.sleep(2.0)

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
                    try:
                        os.remove(destino)
                    except Exception:
                        pass
                raise InterruptedError("Copia cancelada por el usuario.")

            chunk = f_src.read(buffer_size)
            if not chunk:
                break
            f_dst.write(chunk)
            bytes_copiados += len(chunk)
            if callback_progreso:
                callback_progreso(bytes_copiados, total_size)


# =====================================================================
# 🚀 ORQUESTADOR PRINCIPAL DE INSTALACIÓN (DESACOPLADO DE TKINTER)
# =====================================================================

def ejecutar_instalacion_hollowdrive(config, callbacks, abort_check=None, mirrors_data=None):
    """
    Ejecuta el proceso completo de formateo, particionado y flasheo.
    Se comunica con la UI exclusivamente a través del diccionario 'callbacks':
      - callbacks['on_status'](mensaje, color)
      - callbacks['on_task_progress'](float 0.0 - 1.0)
      - callbacks['on_total_progress'](float 0.0 - 1.0)
      - callbacks['on_step'](paso_actual, total_pasos, titulo)
      - callbacks['on_gif'](bool)
      - callbacks['on_success'](tiempo_total, tiempos_dict)
      - callbacks['on_error'](tipo_error, mensaje)
      - callbacks['on_cancel']()
    """
    if not mirrors_data:
        try:
            mpath = os.path.join(BASE_DIR, "engine", "mirrors.json")
            if os.path.exists(mpath):
                with open(mpath, "r", encoding="utf-8") as f:
                    mirrors_data = json.load(f)
        except Exception as me:
            logging.warning(f"No se pudo cargar mirrors.json local: {me}")
    mirrors_data = mirrors_data or {}
    t_inicio_global = time.time()
    registro_tiempos = {}
    step_starts = {}

    def iniciar_cronometro(nombre):
        step_starts[nombre] = time.time()

    def detener_cronometro(nombre):
        if nombre in step_starts:
            registro_tiempos[nombre] = time.time() - step_starts[nombre]

    def limpiar_temporales():
        temp_dir = os.path.join(BASE_DIR, "engine", "temp_downloads")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        try:
            import gc
            gc.collect()
        except Exception:
            pass

    try:
        disk_index = config["disk_index"]
        cachy_gb = config["cachy_gb"]
        hollow_gb = config["hollow_gb"]
        gb_totales = config["gb_totales"]
        preservar_espacio = config["preservar_espacio"]
        instalar_cachy = config["instalar_cachy"]
        descargar_pack_hollow = config["descargar_pack_hollow"]
        instalar_bato = config["instalar_bato"]
        metodo_ext = config.get("metodo_descarga", "ram")
        cachy_flavor = config.get("cachy_flavor", "hyprland")

        espacio_reservado_gb = (gb_totales - hollow_gb) if preservar_espacio else (cachy_gb + GB_GRUB if instalar_cachy else 0.0)

        # 1. Localizar Ventoy2Disk
        ventoy_dir = None
        engine_base = os.path.join(BASE_DIR, "engine")
        if os.path.exists(engine_base):
            for root, dirs, files in os.walk(engine_base):
                for f in files:
                    if f.lower() == "ventoy2disk.exe":
                        ventoy_dir = root
                        break
                if ventoy_dir:
                    break

        if not ventoy_dir:
            raise RuntimeError("No se encontró Ventoy2Disk.exe en la carpeta engine.")

        def esperar_unidad_por_etiqueta(etiqueta, intentos=6, retardo=2):
            for i in range(intentos):
                if abort_check and abort_check():
                    raise InterruptedError()
                callbacks.get('on_status', lambda m, c: None)(f"Esperando montaje de '{etiqueta}' ({i+1}/{intentos})...", "suave")
                letra = encontrar_letra_por_etiqueta_ps(etiqueta, disk_index=disk_index)
                if letra:
                    return letra
                time.sleep(retardo)
            return None

        # Pasos activos
        pasos_activos = ["ventoy"]
        if descargar_pack_hollow:
            pasos_activos.append("pack_hollow")
        else:
            pasos_activos.append("ventoy_base")

        if instalar_bato:
            pasos_activos.append("batocera_img")
        if instalar_cachy:
            pasos_activos.extend(["grub_part", "grub_extract", "cachy_part", "cachy_extract"])

        total_pasos = len(pasos_activos)
        paso_actual = 1

        # Estimador algorítmico inteligente de tiempos y hardware USB
        estimator = UsbTimeEstimator()
        usb_info = {
            "model": config.get("usb_model", ""),
            "bus_type": config.get("bus_type", "USB"),
            "size_gb": gb_totales
        }
        # Micro-sondeo adaptativo no intrusivo de red en tiempo real (<300ms)
        net_speed = estimator.probe_network_speed(mirrors_data)
        time_plan = estimator.build_plan(config, usb_info, network_speed_mb_s=net_speed)
        callbacks.get('on_time_plan', lambda p: None)(time_plan)

        def notificar_paso(nombre_paso, titulo_ui, step_id=None):
            iniciar_cronometro(nombre_paso)
            dur_est = 60
            for s in time_plan.get("steps", []):
                if (step_id and s.get("id") == step_id) or s.get("name") == nombre_paso or s.get("step_num") == paso_actual:
                    dur_est = s.get("est_sec", 60)
                    break
            callbacks.get('on_step', lambda cur, tot, title, est=0: None)(paso_actual, total_pasos, titulo_ui, dur_est)

        def reportar_progreso(prog_interno, texto_paso):
            total_est = time_plan.get("total_est_sec", 1) or 1
            sec_prev = sum(s["est_sec"] for s in time_plan.get("steps", [])[:paso_actual - 1])
            steps_list = time_plan.get("steps", [])
            sec_cur = steps_list[paso_actual - 1]["est_sec"] if (paso_actual - 1) < len(steps_list) else 1
            prog_global = min(1.0, max(0.0, (sec_prev + (prog_interno * sec_cur)) / total_est))

            callbacks.get('on_task_progress', lambda p: None)(prog_interno)
            callbacks.get('on_total_progress', lambda p: None)(prog_global)
            callbacks.get('on_status', lambda m, c: None)(f"Paso {paso_actual}/{total_pasos}: {texto_paso}", "normal")

        # PASO 1: VENTOY
        notificar_paso("Estructura Core (Ventoy)", "Estructura Core (Ventoy)", "ventoy")
        reportar_progreso(0.0, "Ejecutando particionamiento Ventoy...")

        def progreso_ventoy(porcentaje, mensaje):
            if abort_check and abort_check():
                raise InterruptedError()
            reportar_progreso(porcentaje / 100.0, f"Ventoy: {mensaje}")

        instalar_ventoy(disk_index=disk_index, reserved_space_gb=espacio_reservado_gb, ventoy_dir=ventoy_dir, progress_callback=progreso_ventoy)
        detener_cronometro("Estructura Core (Ventoy)")
        paso_actual += 1

        callbacks.get('on_status', lambda m, c: None)("Asentando almacenamiento...", "cian")
        time.sleep(5)

        # Rescan
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
        except Exception:
            pass

        time.sleep(2)

        # Detectar letra HOLLOWDRIVE
        letra_hollow = None
        for _ in range(12):
            if abort_check and abort_check():
                raise InterruptedError()
            letra = encontrar_letra_por_etiqueta_ps("Ventoy", disk_index=disk_index) or encontrar_letra_por_etiqueta_ps("HOLLOWDRIVE", disk_index=disk_index)
            if letra:
                if encontrar_letra_por_etiqueta_ps("Ventoy", disk_index=disk_index) is not None:
                    subprocess.run(f"label {letra[:2]} HOLLOWDRIVE", shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    time.sleep(1.5)
                    letra_hollow = encontrar_letra_por_etiqueta_ps("HOLLOWDRIVE", disk_index=disk_index) or letra
                else:
                    letra_hollow = letra
                break
            time.sleep(2)

        if not letra_hollow:
            particiones = obtener_estructura_disco_ps(disk_index)
            for p in particiones:
                if p.get("Number") == 1:
                    letra_p = p.get("Letter")
                    if letra_p:
                        letra_hollow = f"{letra_p}:\\"
                    else:
                        letra_hollow = asignar_letra_particion_ps(disk_index, 1)
                    break

        if letra_hollow:
            agregar_exclusion_antivirus(letra_hollow)

            # Ventana de preparación (10-15s): Sondeo físico de velocidad sostenida directa a NAND
            try:
                reportar_progreso(0.0, "Calibrando velocidad de almacenamiento...")
                measured_k = estimator.probe_usb_write_speed(letra_hollow)
                if measured_k:
                    logging.info(f"[CALIBRACIÓN FÍSICA] USB calibrado en ventana de preparación: K_usb = {measured_k} MB/s")
                    calibrated_plan = estimator.build_plan(
                        config, usb_info, network_speed_mb_s=net_speed, measured_usb_mb_s=measured_k
                    )
                    time_plan = calibrated_plan
                    callbacks.get('on_time_plan', lambda p: None)(calibrated_plan)
                time.sleep(1.5)  # Asentamiento de buffer y I/O
            except Exception as e_calib:
                logging.debug(f"[CALIBRACIÓN FÍSICA] Fallback al perfil base: {e_calib}")
        else:
            raise RuntimeError("No se detectó la letra de unidad física para HOLLOWDRIVE.")

        # PASO 2: PACK HOLLOWDRIVE O BASE
        if "pack_hollow" in pasos_activos:
            notificar_paso("Pack Utils HollowDrive", "Pack Utils HollowDrive", "pack_hollow")
            if abort_check and abort_check():
                raise InterruptedError()
            callbacks.get('on_gif', lambda b: None)(True)
            reportar_progreso(0.0, "Descargando Pack HollowDrive...")

            try:
                url_pack_hollow = mirrors_data["hollowdrive_pack"]["mirrors"][0]["url"]
            except KeyError:
                url_pack_hollow = "https://pub-b872cd561e404a9599c943c6705afe9e.r2.dev/HollowdrivePackV1.tar"

            pack_hollow_obj = {
                "name": "Pack HollowDrive",
                "format": "tar_multipart",
                "parts": [{"url": url_pack_hollow}]
            }

            def prog_pack_cb(b_read, t_size, pct, msg):
                reportar_progreso(pct, msg)

            descargar_y_extraer_pack_generico(
                pack_data=pack_hollow_obj,
                target_dir_or_file=letra_hollow,
                method=metodo_ext,
                progress_callback=prog_pack_cb,
                abort_check=abort_check
            )
            callbacks.get('on_gif', lambda b: None)(False)
            detener_cronometro("Pack Utils HollowDrive")
            paso_actual += 1

        elif "ventoy_base" in pasos_activos:
            notificar_paso("Configuración Base Ventoy", "Configuración Base Ventoy", "ventoy_base")
            if abort_check and abort_check():
                raise InterruptedError()
            reportar_progreso(0.0, "Localizando configuración base...")

            ruta_tar_local = resource_path(os.path.join("engine", "resources", "ventoy.tar"))
            if not os.path.exists(ruta_tar_local):
                raise RuntimeError(f"No se encontró el archivo base de Ventoy en: {ruta_tar_local}")

            with tarfile.open(ruta_tar_local, "r") as tar:
                miembros = tar.getmembers()
                total_m = len(miembros)
                for idx, member in enumerate(miembros):
                    if abort_check and abort_check():
                        raise InterruptedError()
                    try:
                        tar.extract(member, path=letra_hollow, filter='data')
                    except TypeError:
                        tar.extract(member, path=letra_hollow)
                    reportar_progreso((idx + 1) / total_m, f"Inyectando base: {member.name[:25]}")

            detener_cronometro("Configuración Base Ventoy")
            paso_actual += 1

        # PASO 3: BATOCERA OS
        if "batocera_img" in pasos_activos:
            notificar_paso("Sistema Batocera OS", "Sistema Batocera OS", "batocera_img")
            if abort_check and abort_check():
                raise InterruptedError()
            callbacks.get('on_gif', lambda b: None)(True)

            ruta_batocerumen = os.path.join(letra_hollow, "HOLLOWDRIVE", "BATOCERUMEN")
            os.makedirs(ruta_batocerumen, exist_ok=True)
            archivo_dest_bato = os.path.join(ruta_batocerumen, "batocera.img")

            try:
                url_bato = mirrors_data["batocera_base"]["mirrors"][0]["url"]
            except KeyError:
                url_bato = "https://pub-988eebcee5e94631a55af8a89d12129d.r2.dev/batocerumen.img"

            bato_pack_obj = {
                "name": "Batocera OS",
                "format": "single_file",
                "parts": [{"url": url_bato}]
            }

            def prog_bato_cb(b_read, t_size, pct, msg):
                reportar_progreso(pct, msg)

            descargar_y_extraer_pack_generico(
                pack_data=bato_pack_obj,
                target_dir_or_file=archivo_dest_bato,
                method="ram",
                progress_callback=prog_bato_cb,
                abort_check=abort_check
            )
            callbacks.get('on_gif', lambda b: None)(False)
            detener_cronometro("Sistema Batocera OS")
            paso_actual += 1

        # PASO 4: GRUB BOOTLOADER
        if "grub_part" in pasos_activos:
            notificar_paso("Creación Bootloader GRUB", "Creación Bootloader GRUB", "grub_part")
            if abort_check and abort_check():
                raise InterruptedError()
            reportar_progreso(0.0, "Creando partición GRUB...")
            crear_particion_adicional(disk_index=disk_index, size_gb=GB_GRUB, label="GRUB", fs="fat32")
            letra_grub = esperar_unidad_por_etiqueta("GRUB", intentos=12, retardo=2)
            if not letra_grub:
                raise RuntimeError("Windows tardó demasiado en asignar letra a 'GRUB'.")
            detener_cronometro("Creación Bootloader GRUB")
            paso_actual += 1

        if "grub_extract" in pasos_activos:
            notificar_paso("Inyección Bootloader GRUB", "Inyección Bootloader GRUB", "grub_extract")
            if abort_check and abort_check():
                raise InterruptedError()
            callbacks.get('on_gif', lambda b: None)(True)
            reportar_progreso(0.0, "Flasheando GRUB Bootloader...")

            if cachy_flavor == "hyprland":
                try:
                    url_grub_hf = mirrors_data["cachyos_images"]["efi_grub_hyprland"]["mirrors"][0]["url"]
                except (KeyError, IndexError, TypeError):
                    url_grub_hf = "https://pub-b872cd561e404a9599c943c6705afe9e.r2.dev/grub_boot.img"
            else:
                try:
                    url_grub_hf = mirrors_data["cachyos_images"]["efi_grub"]["mirrors"][0]["url"]
                except (KeyError, IndexError, TypeError):
                    url_grub_hf = "https://pub-b872cd561e404a9599c943c6705afe9e.r2.dev/grub_boot.img"

            letra_grub = letra_grub or encontrar_letra_por_etiqueta_ps("GRUB", disk_index=disk_index)

            def prog_grub_flash(b_read, t_size, msg):
                pct = b_read / t_size if t_size else 0.5
                reportar_progreso(pct, f"GRUB: {msg}")

            stream_flash_image_direct(
                url_grub_hf, letra_grub,
                progress_callback=prog_grub_flash,
                abort_check=abort_check,
                method=metodo_ext
            )
            callbacks.get('on_gif', lambda b: None)(False)
            detener_cronometro("Inyección Bootloader GRUB")
            paso_actual += 1

        # PASO 5: CACHYOS PARTITION & FLASH
        if "cachy_part" in pasos_activos:
            notificar_paso("Creación Partición CachyOS", "Creación Partición CachyOS", "cachy_part")
            if abort_check and abort_check():
                raise InterruptedError()
            reportar_progreso(0.0, "Creando partición CachyOS...")

            margen_seguridad = 0.15 if not preservar_espacio else 0.0
            tamano_seguro_cachy = max(1.0, cachy_gb - margen_seguridad)

            crear_particion_adicional(disk_index=disk_index, size_gb=tamano_seguro_cachy, label="CachyOS", fs="ntfs")
            letra_cachy = esperar_unidad_por_etiqueta("CachyOS", intentos=12, retardo=2)
            if not letra_cachy:
                raise RuntimeError("Windows tardó demasiado en asignar letra a 'CachyOS'.")
            detener_cronometro("Creación Partición CachyOS")
            paso_actual += 1

        if "cachy_extract" in pasos_activos:
            notificar_paso("Volcado Sistema CachyOS", "Volcado Sistema CachyOS", "cachy_extract")
            if abort_check and abort_check():
                raise InterruptedError()
            callbacks.get('on_gif', lambda b: None)(True)
            reportar_progreso(0.0, "Volcado sectorial CachyOS...")

            if cachy_flavor == "sistema":
                try:
                    url_cachy_hf = mirrors_data["cachyos_images"]["sistema"]["mirrors"][0]["url"]
                except (KeyError, IndexError, TypeError):
                    url_cachy_hf = "https://pub-a129edcf7e704b7b925dfafc7a876a15.r2.dev/cachyos_system.img"
            else:
                try:
                    url_cachy_hf = mirrors_data["cachyos_images"]["hyprland"]["mirrors"][0]["url"]
                except (KeyError, IndexError, TypeError):
                    url_cachy_hf = "https://pub-a129edcf7e704b7b925dfafc7a876a15.r2.dev/cachyos_system.img"

            letra_cachy = letra_cachy or encontrar_letra_por_etiqueta_ps("CachyOS", disk_index=disk_index)

            def prog_cachy_flash(b_read, t_size, msg):
                pct = b_read / t_size if t_size else 0.5
                reportar_progreso(pct, f"CachyOS: {msg}")

            stream_flash_image_direct(
                url_cachy_hf, letra_cachy,
                progress_callback=prog_cachy_flash,
                abort_check=abort_check,
                method=metodo_ext
            )
            callbacks.get('on_gif', lambda b: None)(False)
            detener_cronometro("Volcado Sistema CachyOS")

        callbacks.get('on_total_progress', lambda p: None)(1.0)
        callbacks.get('on_task_progress', lambda p: None)(1.0)
        tiempo_total = time.time() - t_inicio_global
        limpiar_temporales()
        try:
            estimator.record_completion(config.get("usb_model", ""), registro_tiempos, tiempo_total)
        except Exception as ee:
            logging.warning(f"No se pudo guardar métricas en time_estimator: {ee}")
        callbacks.get('on_success', lambda t, r: None)(tiempo_total, registro_tiempos)

    except InterruptedError:
        limpiar_temporales()
        callbacks.get('on_cancel', lambda: None)()
    except Exception as e:
        limpiar_temporales()
        callbacks.get('on_error', lambda t, m: None)(type(e).__name__, str(e))
