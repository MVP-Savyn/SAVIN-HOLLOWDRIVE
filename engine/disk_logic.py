import subprocess
import json
import os
import time

def obtener_unidades_usb(incluir_internos=False):
    unidades_validas = []
    try:
        # 1. Identificar letra de sistema (C:) para el bloqueo absoluto
        drive_sistema = os.environ.get('SystemDrive', 'C:').replace(':', '').upper()

        # 2. SCRIPT DE POWERSHELL
        # Definimos el script como una sola cadena limpia
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
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=False)
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
            # Solo consideramos externo si el bus es USB o SD
            es_externo_real = d.get('IsUSB') == True

            # Si Incluir Internos está OFF y no es USB, saltamos
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
            except:
                continue

    except Exception as e:
        print(f"Error en el backend: {e}")
        
    return unidades_validas

def instalar_ventoy(disk_index, reserved_space_gb, ventoy_dir="tools/ventoy", progress_callback=None):
    """
    Instala Ventoy en el disco físico (disk_index) reservando el espacio indicado
    al final del disco (en GB) para otros sistemas como CachyOS o Batocera.
    Mapea el progreso leyendo 'cli_percent.txt' en tiempo real.
    """
    # 1. Limpieza de archivos de control previos para evitar lecturas "fantasma"
    percent_path = os.path.join(ventoy_dir, "cli_percent.txt")
    done_path = os.path.join(ventoy_dir, "cli_done.txt")
    log_path = os.path.join(ventoy_dir, "cli_log.txt")

    for path in [percent_path, done_path, log_path]:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception as e:
                print(f"[-] No se pudo limpiar {path}: {e}")

    # 2. Verificar existencia de Ventoy2Disk.exe
    exe_path = os.path.join(ventoy_dir, "Ventoy2Disk.exe")
    if not os.path.exists(exe_path):
        raise FileNotFoundError(f"No se encontró Ventoy2Disk.exe en: {ventoy_dir}")

    # Convertir espacio reservado a MB (Ventoy CLI trabaja en MB)
    reserved_mb = int(reserved_space_gb * 1024)

    # 3. Construir comando CLI de Ventoy
    # VTOYCLI /I -> Instalar
    # /PhyDrive:X -> Disco físico destino
    # /GPT -> Estilo de particionado GPT (ideal para UEFI moderno)
    # /NOUSBCheck -> Omitimos chequeo para evitar falsos negativos (nuestro backend ya lo validó)
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

    # 4. Ejecución oculta (sin levantar ventanas de CMD molestas)
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
        text=True
    )

    # 5. Bucle de monitorización del progreso real
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
                                # Escalar el progreso de Ventoy (de 0 a 90% para dejar margen a la post-instalación)
                                scaled_progress = int(5 + (percent * 0.85))
                                progress_callback(scaled_progress, f"Instalando estructura Ventoy... {percent}%")
            except Exception:
                pass  # Previene caídas si intentamos leer justo mientras Ventoy escribe
        time.sleep(0.5)

    # Espera de seguridad para asegurar escrituras en disco
    time.sleep(1)

    # 6. Comprobación del resultado final
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
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
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
    # 1. Capturar las letras de unidad que tiene el disco ANTES de crear la nueva
    letras_antes = obtener_letras_de_disco(disk_index)

    size_mb = int(size_gb * 1024)
    
    # Construcción de comandos para diskpart
    commands = [
        f"select disk {disk_index}"
    ]
    if size_mb > 0:
        commands.append(f"create partition primary size={size_mb}")
    else:
        commands.append("create partition primary")  # Usa todo el espacio restante
        
    # Solo formateamos si el sistema de archivos es compatible con Windows
    if fs and fs.lower() not in ["raw", "none"]:
        commands.append(f"format fs={fs} quick label=\"{label}\"")
    
    # IMPORTANTE: Forzamos 'assign' en ambos casos para que Windows le asigne letra libre
    commands.append("assign")

    script_content = "\n".join(commands)
    temp_script = f"temp_diskpart_{label}.txt"
    
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
            startupinfo=startupinfo
        )
        
        if res.returncode != 0:
            raise RuntimeError(f"Diskpart falló al crear partición {label}:\n{res.stderr}\n{res.stdout}")
        
        # Le damos un margen de 2 segundos a Windows para montar físicamente la unidad y asignar la letra
        time.sleep(2)
        
        # 2. Capturar las letras de unidad DESPUÉS de la partición
        letras_despues = obtener_letras_de_disco(disk_index)
        
        # Encontrar cuál es la letra nueva
        letras_nuevas = letras_despues - letras_antes
        if letras_nuevas:
            letra_detectada = list(letras_nuevas)[0]
            print(f"[+] Letra asignada dinámicamente para {label}: {letra_detectada}:")
            return letra_detectada
            
        # Fallback de seguridad en caso de desfase del sistema
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
        raise FileNotFoundError(f"No se encontró la imagen de CachyOS en: {ruta_imagen}")

    # En Windows, para escribir sobre una partición cruda apuntamos al volumen: \\.\E:
    letra_unidad = letra_unidad.replace(":", "").replace("\\", "").upper()
    dispositivo_destino = f"\\\\.\\{letra_unidad}:"
    
    exe_path = os.path.join(dd_dir, "dd.exe")
    if not os.path.exists(exe_path):
        raise FileNotFoundError(f"No se encontró dd.exe en: {dd_dir}")

    # Obtener tamaño total de la imagen para calcular el progreso
    total_bytes = os.path.getsize(ruta_imagen)
    
    # dd.exe if=imagen.img of=\\.\E: bs=4M --progress
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
        progress_callback(0, "Iniciando volcado de imagen CachyOS...")

    # dd escribe su progreso por stderr en tiempo real
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        startupinfo=startupinfo,
        text=True,
        bufsize=1
    )

    while True:
        linea = process.stderr.readline()
        if not linea and process.poll() is not None:
            break
            
        if linea:
            linea_clean = linea.strip()
            # dd para Windows suele escupir líneas con números de bytes acumulados
            partes = linea_clean.split()
            if partes and partes[0].isdigit():
                try:
                    bytes_escritos = int(partes[0])
                    porcentaje = int((bytes_escritos / total_bytes) * 100)
                    
                    if progress_callback:
                        progress_callback(porcentaje, f"Volcando CachyOS... {porcentaje}% ({round(bytes_escritos/(1024**2), 1)} MB)")
                except:
                    pass

    process.wait()
    if process.returncode != 0:
        error_output = process.stderr.read()
        raise RuntimeError(f"Error durante el volcado con dd:\n{error_output}")

    if progress_callback:
        progress_callback(100, "¡Volcado de CachyOS completado con éxito!")
    return True