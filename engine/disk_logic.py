import subprocess
import json
import os
import time
import logging

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))

def obtener_unidades_usb(incluir_internos=False):
    unidades_validas = []
    try:
        # 1. Identificar letra de sistema (C:) para el bloqueo absoluto
        drive_sistema = os.environ.get('SystemDrive', 'C:').replace(':', '').upper()

        # 2. SCRIPT DE POWERSHELL
        ps_script = (
            '[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; '
            '$resultado = Get-Disk | ForEach-Object { '
                '$disk = $_; '
                '$volumenes = ($disk | Get-Partition | Get-Volume -ErrorAction SilentlyContinue); '
                '$letras = ($volumenes.DriveLetter) -join ","; '
                '$nombre = $disk.FriendlyName; '
                'if (!$nombre) { $nombre = $disk.Model } '
                '[PSCustomObject]@{ '
                    'Index = $disk.Number; '
                    'Model = $nombre; '
                    'Size  = $disk.Size; '
                    'Bus   = $disk.BusType; '
                    'Letras = $letras; '
                    'IsUSB = ($disk.BusType -eq "USB" -or $disk.BusType -eq "SD"); '
                '} '
            '}; '
            '$resultado | ConvertTo-Json'
        )
        
        cmd = ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', ps_script]
        
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=False,
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        stdout, _ = process.communicate()
        resultado_raw = stdout.decode('utf-8', errors='ignore').strip()
        
        if not resultado_raw or resultado_raw == "null": 
            return []
            
        datos = json.loads(resultado_raw)
        discos = [datos] if isinstance(datos, dict) else datos

        for d in discos:
            idx = d.get('Index')
            model = str(d.get('Model', 'Disco Desconocido')).strip()
            letras_str = str(d.get('Letras', ''))
            letras_lista = [l.strip() for l in letras_str.split(',') if l.strip()]
            
            # --- FILTRO 1: BLOQUEO TOTAL DE C: ---
            if drive_sistema in letras_lista:
                continue
            
            # --- FILTRO 2: ¿ES REALMENTE EXTERNO? ---
            es_externo_real = d.get('IsUSB') == True

            if not incluir_internos and not es_externo_real:
                continue

            try:
                size_gb = round(int(d.get('Size', 0)) / (1024**3), 2)
                if size_gb < 1: continue

                str_letras = f" ({', '.join(letras_lista)})" if letras_lista else " (Sin letras)"
                tipo = "[EXT]" if es_externo_real else "[INT]"

                unidades_validas.append({
                    "device": idx,
                    "label": model,
                    "size": size_gb,
                    "display": f"{tipo} {model}{str_letras} - {size_gb} GB"
                })
            except Exception:
                continue

    except Exception as e:
        print(f"Error en el backend de discos: {e}")
        
    return unidades_validas

def obtener_estructura_disco_ps(disk_index):
    """ Retorna la lista de particiones físicas del disco con su tamaño, etiqueta y letra """
    try:
        cmd = (f'Get-Partition -DiskNumber {disk_index} | ForEach-Object {{ '
               f'$p = $_; $v = Get-Volume -Partition $p -ErrorAction SilentlyContinue; '
               f'[PSCustomObject]@{{"Number"=$p.PartitionNumber; "Size"=[math]::Round($p.Size/1GB, 2); '
               f'"Letter"=$p.DriveLetter; "Label"=$v.FileSystemLabel; "Type"=$p.Type}} }} | ConvertTo-Json')
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", cmd], 
            startupinfo=si, 
            creationflags=subprocess.CREATE_NO_WINDOW, 
            text=True, 
            errors="ignore"
        )
        if not out.strip(): return []
        data = json.loads(out)
        return [data] if isinstance(data, dict) else data
    except Exception as e:
        logging.error(f"Error analizando estructura de disco {disk_index}: {e}")
        return []

def instalar_ventoy(disk_index, reserved_space_gb, ventoy_dir="tools/ventoy", progress_callback=None):
    """
    Instala Ventoy en el disco físico (disk_index) reservando el espacio indicado
    al final del disco (en GB) para otros sistemas como CachyOS o Batocera.
    Mapea el progreso leyendo 'cli_percent.txt' en tiempo real.
    """
    percent_path = os.path.join(ventoy_dir, "cli_percent.txt")
    done_path = os.path.join(ventoy_dir, "cli_done.txt")
    log_path = os.path.join(ventoy_dir, "cli_log.txt")

    for path in [percent_path, done_path, log_path]:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception as e:
                print(f"[-] No se pudo limpiar {path}: {e}")

    exe_path = os.path.join(ventoy_dir, "Ventoy2Disk.exe")
    if not os.path.exists(exe_path):
        raise FileNotFoundError(f"No se encontró Ventoy2Disk.exe en: {ventoy_dir}")

    reserved_mb = int(reserved_space_gb * 1024)

    cmd = [
        exe_path,
        "VTOYCLI",
        "/I",
        f"/PhyDrive:{disk_index}",
        "/GPT",
        "/NOUSBCheck"
    ]
    if reserved_mb > 0:
        cmd.append(f"/R:{reserved_mb}")

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE

    if progress_callback:
        progress_callback(5, "Iniciando formateador de Ventoy...")

    process = subprocess.Popen(
        cmd,
        cwd=ventoy_dir,
        startupinfo=startupinfo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW
    )

    last_percent = -1
    while process.poll() is None:
        if os.path.exists(percent_path):
            try:
                with open(percent_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content.isdigit():
                        percent = int(content)
                        if percent != last_percent:
                            last_percent = percent
                            if progress_callback:
                                scaled_progress = int(5 + (percent * 0.85))
                                progress_callback(scaled_progress, f"Instalando estructura Ventoy... {percent}%")
            except Exception:
                pass
        time.sleep(0.5)

    time.sleep(1)

    success = False
    if os.path.exists(done_path):
        try:
            with open(done_path, "r", encoding="utf-8") as f:
                if f.read().strip() == "0":
                    success = True
        except Exception:
            pass

    if not os.path.exists(done_path):
        success = (process.returncode == 0)

    if not success:
        error_msg = "Error desconocido de Ventoy."
        if os.path.exists(log_path):
            try:
                with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                    error_msg = f.read()
            except Exception:
                pass
        raise RuntimeError(f"Fallo en Ventoy2Disk:\n{error_msg}")

    if progress_callback:
        progress_callback(90, "Estructura de Ventoy instalada con éxito.")
    return True

def obtener_letras_de_disco(disk_index):
    """
    Retorna un conjunto (set) de letras de unidad (ej. {'D', 'E'})
    asociadas al disco físico especificado.
    """
    try:
        ps_script = (
            f"Get-Partition -DiskNumber {disk_index} | "
            "Get-Volume -ErrorAction SilentlyContinue | "
            "ForEach-Object { $_.DriveLetter }"
        )
        cmd = ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', ps_script]
        
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        
        process = subprocess.Popen(
            cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True,
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        stdout, _ = process.communicate()
        
        letras = set()
        for line in stdout.splitlines():
            letra = line.strip().upper()
            if letra and len(letra) == 1 and letra.isalpha():
                letras.add(letra)
        return letras
    except Exception as e:
        print(f"Error detectando letras para disco {disk_index}: {e}")
        return set()

def crear_particion_adicional(disk_index, size_gb, label, fs="fat32"):
    """
    Crea una partición primaria en el espacio no asignado (reservado) 
    utilizando diskpart en segundo plano de manera silenciosa.
    Si fs es None o "raw", crea la partición pero no la formatea (RAW).
    Retorna la letra de unidad que Windows le ha asignado dinámicamente.
    """
    letras_antes = obtener_letras_de_disco(disk_index)

    size_mb = int(size_gb * 1024)
    commands = [f"select disk {disk_index}"]
    if size_mb > 0:
        commands.append(f"create partition primary size={size_mb}")
    else:
        commands.append("create partition primary")
        
    if fs and fs.lower() not in ["raw", "none"]:
        commands.append(f"format fs={fs} quick label=\"{label}\"")
    
    commands.append("assign")

    script_content = "\n".join(commands)
    temp_script = os.path.join(ENGINE_DIR, f"temp_diskpart_{label}.txt")
    
    try:
        with open(temp_script, "w") as f:
            f.write(script_content)

        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

        res = subprocess.run(
            ["diskpart", "/s", temp_script],
            capture_output=True,
            text=True,
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        
        if res.returncode != 0:
            raise RuntimeError(f"Diskpart falló al crear partición {label}:\n{res.stderr}\n{res.stdout}")
        
        time.sleep(2)
        
        letras_despues = obtener_letras_de_disco(disk_index)
        letras_nuevas = letras_despues - letras_antes
        if letras_nuevas:
            letra_detectada = list(letras_nuevas)[0]
            print(f"[+] Letra asignada dinámicamente para {label}: {letra_detectada}:")
            return letra_detectada
            
        if letras_despues:
            return sorted(list(letras_despues))[-1]
            
        return None
            
    finally:
        if os.path.exists(temp_script):
            os.remove(temp_script)

def volcar_imagen_dd(ruta_imagen, letra_unidad, dd_dir="tools", progress_callback=None):
    """
    Vuelca una imagen (.img) directamente sobre la partición detectada (ej. 'E')
    utilizando un binario de dd para Windows.
    Mapea el progreso de la copia calculando el tamaño procesado.
    """
    if not os.path.exists(ruta_imagen):
        raise FileNotFoundError(f"No se encontró la imagen en: {ruta_imagen}")

    letra_unidad = letra_unidad.replace(":", "").replace("\\", "").upper()
    dispositivo_destino = f"\\\\.\\{letra_unidad}:"
    
    exe_path = os.path.join(dd_dir, "dd.exe")
    if not os.path.exists(exe_path):
        raise FileNotFoundError(f"No se encontró dd.exe en: {dd_dir}")

    total_bytes = os.path.getsize(ruta_imagen)
    cmd = [
        exe_path,
        f"if={ruta_imagen}",
        f"of={dispositivo_destino}",
        "bs=4M",
        "--progress"
    ]

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE

    if progress_callback:
        progress_callback(0, "Iniciando volcado de imagen...")

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        startupinfo=startupinfo,
        text=True,
        bufsize=1,
        creationflags=subprocess.CREATE_NO_WINDOW
    )

    while True:
        linea = process.stderr.readline()
        if not linea and process.poll() is not None:
            break
            
        if linea:
            linea_clean = linea.strip()
            partes = linea_clean.split()
            if partes and partes[0].isdigit():
                try:
                    bytes_escritos = int(partes[0])
                    porcentaje = int((bytes_escritos / total_bytes) * 100)
                    if progress_callback:
                        progress_callback(porcentaje, f"Volcando... {porcentaje}% ({round(bytes_escritos/(1024**2), 1)} MB)")
                except Exception:
                    pass

    process.wait()
    if process.returncode != 0:
        error_output = process.stderr.read()
        raise RuntimeError(f"Error durante el volcado con dd:\n{error_output}")

    if progress_callback:
        progress_callback(100, "¡Volcado completado con éxito!")
    return True