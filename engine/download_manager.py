import os
import requests
import zipfile
import shutil

def obtener_link_ventoy():
    """Busca la última versión de Ventoy en la API de GitHub."""
    try:
        api_url = "https://api.github.com/repos/ventoy/Ventoy/releases/latest"
        response = requests.get(api_url, timeout=10)
        data = response.json()
        
        for asset in data['assets']:
            if "windows.zip" in asset['name']:
                return asset['browser_download_url'], asset['name']
    except Exception as e:
        print(f"Error buscando Ventoy: {e}")
    return None, None

def descargar_y_extraer_ventoy(progress_callback=None):
    """Descarga y descomprime Ventoy con progreso real."""
    url, filename = obtener_link_ventoy()
    if not url: return False

    tools_dir = os.path.join("engine", "tools")
    os.makedirs(tools_dir, exist_ok=True)
    zip_path = os.path.join(tools_dir, filename)

    try:
        # Abrimos el grifo de datos
        response = requests.get(url, stream=True)
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        # Abrimos el archivo local para guardar lo que bajamos
        with open(zip_path, 'wb') as f:
            for data in response.iter_content(chunk_size=8192):
                downloaded += len(data)
                f.write(data)
                if progress_callback and total_size > 0:
                    # Cálculo real: bytes recibidos / totales
                    progreso = downloaded / total_size
                    progress_callback(progreso)

        # Una vez descargado al 100%, extraemos
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(tools_dir)
        
        os.remove(zip_path)
        return True
    except Exception as e:
        print(f"Error descargando: {e}")
        return False