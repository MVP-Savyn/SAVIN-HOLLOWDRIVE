import subprocess
import json
import os

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