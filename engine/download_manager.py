import os
import re
import json
import requests
import zipfile
import tarfile

# Ruta absoluta del directorio 'engine'
ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))

def cargar_mirrors():
    """ Carga el archivo mirrors.json de forma segura utilizando la ruta absoluta del módulo """
    ruta_json = os.path.join(ENGINE_DIR, "mirrors.json")
    try:
        with open(ruta_json, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error cargando mirrors.json desde el motor: {e}")
        return None

def extraer_id_drive(url):
    """
    Extrae el ID único de un archivo de Google Drive desde cualquier formato de enlace.
    Soporta links de /file/d/ID/view, uc?id=ID, etc.
    """
    match = re.search(r'(?:id=|\/d\/|detail\/)([a-zA-Z0-9-_]{33,45})', url)
    return match.group(1) if match else None

def obtener_tamano_drive(file_id):
    """
    Bypassea la pantalla de advertencia de virus de Google Drive
    y obtiene el tamaño real en bytes sin descargar el archivo.
    """
    url_base = "https://docs.google.com/uc?export=download"
    session = requests.Session()
    
    try:
        # 1. Primer intento (stream=True para no descargar el cuerpo del archivo)
        response = session.get(url_base, params={'id': file_id}, stream=True, timeout=6)
        
        # 2. Buscamos si Google ha soltado la cookie de advertencia
        token = None
        for key, value in session.cookies.items():
            if key.startswith('download_warning'):
                token = value
                break
        
        # 3. Si existía la cookie, confirmamos
        if token:
            response = session.get(url_base, params={'id': file_id, 'confirm': token}, stream=True, timeout=6)
            
        size = response.headers.get('content-length')
        response.close()
        
        if size:
            return int(size)
            
    except Exception as e:
        print(f"Error obteniendo tamaño de Drive para ID {file_id}: {e}")
    return None

def obtener_tamano_link(url):
    """
    Detecta si el enlace es de Google Drive o un servidor directo (como Cloudflare R2)
    y obtiene su tamaño online de forma óptima.
    """
    if "drive.google.com" in url:
        file_id = extraer_id_drive(url)
        if file_id:
            return obtener_tamano_drive(file_id)
        return None
        
    try:
        response = requests.head(url, allow_redirects=True, timeout=4)
        if response.status_code == 200:
            size = response.headers.get('content-length')
            if size:
                return int(size)
    except Exception as e:
        print(f"Error HEAD en {url}: {e}")
    return None

def resolver_tamano_pack(clave_pack, subclave=None):
    """
    Busca el tamaño real de un pack consultando directamente el mirror prioritario.
    Si falla todo, usa el fallback de seguridad de mirrors.json.
    """
    data = cargar_mirrors()
    if not data:
        return 0
        
    pack = data.get(clave_pack, {})
    if subclave:
        pack = pack.get(subclave, {})
        
    mirrors = pack.get("mirrors", [])
    
    for m in sorted(mirrors, key=lambda x: x.get("priority", 99)):
        url = m.get("url")
        size_online = obtener_tamano_link(url)
        if size_online:
            print(f"-> Tamaño detectado online para {clave_pack}: {size_online} bytes.")
            return size_online
                
    fallback_size = pack.get("size_bytes", 0)
    print(f"-> Usando tamaño local predefinido para {clave_pack}: {fallback_size} bytes.")
    return fallback_size

def formatear_tamano(bytes_size):
    """ Convierte bytes a formato legible (GB o MB) para la GUI """
    if not bytes_size or bytes_size <= 0:
        return "0 GB"
    gb = bytes_size / (1024 ** 3)
    if gb >= 0.1:
        return f"{gb:.1f} GB"
    mb = bytes_size / (1024 ** 2)
    return f"{mb:.1f} MB"

def descargar_archivo(url, destino, callback_progreso=None):
    """
    Descarga un archivo con soporte para bypass de límite/aviso de virus de Google Drive,
    notificando el progreso de la descarga en tiempo real a la GUI.
    """
    session = requests.Session()
    is_drive = "drive.google.com" in url
    file_id = extraer_id_drive(url) if is_drive else None
    
    try:
        if is_drive and file_id:
            url_base = "https://docs.google.com/uc?export=download"
            response = session.get(url_base, params={'id': file_id}, stream=True, timeout=(6.0, 15.0))
            
            token = None
            for key, value in session.cookies.items():
                if key.startswith('download_warning'):
                    token = value
                    break
            
            if token:
                response = session.get(url_base, params={'id': file_id, 'confirm': token}, stream=True, timeout=(6.0, 15.0))
        else:
            response = session.get(url, stream=True, timeout=(6.0, 15.0))
            
        response.raise_for_status()
        
        total_size = response.headers.get('content-length')
        total_size = int(total_size) if total_size else None
        
        os.makedirs(os.path.dirname(os.path.abspath(destino)), exist_ok=True)
        
        bytes_descargados = 0
        with open(destino, 'wb') as f:
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if chunk:
                    f.write(chunk)
                    bytes_descargados += len(chunk)
                    
                    if callback_progreso and total_size:
                        progreso = bytes_descargados / total_size
                        callback_progreso(progreso, bytes_descargados, total_size)
                        
        return True
    except Exception as e:
        print(f"Error crítico en la descarga de {url}: {e}")
        return False

def descargar_y_extraer_ventoy(progress_callback=None):
    """
    Busca la configuración de Ventoy en mirrors.json, lo descarga en un directorio 
    temporal y lo extrae directamente dentro de la carpeta 'engine'.
    """
    data = cargar_mirrors()
    url_ventoy = None
    
    if data and "ventoy" in data:
        pack_ventoy = data["ventoy"]
        mirrors = pack_ventoy.get("mirrors", [])
        if mirrors:
            mirrors_ordenados = sorted(mirrors, key=lambda x: x.get("priority", 99))
            url_ventoy = mirrors_ordenados[0].get("url")
            
    if not url_ventoy:
        url_ventoy = "https://github.com/ventoy/Ventoy/releases/download/v1.0.99/ventoy-1.0.99-windows.zip"
        print(f"-> 'ventoy' no detectado en mirrors.json. Usando fallback oficial: {url_ventoy}")

    temp_dir = os.path.join(ENGINE_DIR, "temp_downloads")
    os.makedirs(temp_dir, exist_ok=True)
    nombre_archivo = url_ventoy.split("/")[-1].split("?")[0]
    ruta_destino_zip = os.path.join(temp_dir, nombre_archivo)
    
    print(f"-> Descargando Ventoy desde: {url_ventoy}")
    exito_descarga = descargar_archivo(url_ventoy, ruta_destino_zip, progress_callback)
    
    if not exito_descarga:
        print("Error: Falló la descarga de Ventoy.")
        return False
        
    ruta_extraccion = ENGINE_DIR
    print(f"-> Extrayendo {nombre_archivo} en '{ruta_extraccion}'...")
    try:
        if nombre_archivo.endswith(".zip"):
            with zipfile.ZipFile(ruta_destino_zip, 'r') as zip_ref:
                zip_ref.extractall(ruta_extraccion)
        elif nombre_archivo.endswith((".tar.gz", ".tgz")):
            with tarfile.open(ruta_destino_zip, 'r:gz') as tar_ref:
                tar_ref.extractall(ruta_extraccion)
        else:
            print("Error: El formato de compresión de Ventoy no es compatible (.zip o .tar.gz).")
            return False
            
        print("-> ¡Ventoy se ha descargado y extraído correctamente!")
        return True
        
    except Exception as e:
        print(f"Error crítico durante la extracción de Ventoy: {e}")
        return False
    finally:
        if os.path.exists(ruta_destino_zip):
            try:
                os.remove(ruta_destino_zip)
            except Exception:
                pass