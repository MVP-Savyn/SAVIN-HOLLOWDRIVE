import os
import json
import time
import logging
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "usb_history.json")

# Perfiles empíricos de hardware base (tiempos en segundos y tasas en MB/s)
# Modelado a partir de instalaciones completas y características físicas de memoria NAND USB
HARDWARE_PROFILES = {
    "usb2_legacy": {
        "label": "USB 2.0 Estándar / Genérico",
        "ventoy_sec": 42,
        "settle_sec": 7,
        "grub_part_sec": 12,
        "cachy_part_sec": 28,
        "v_tar_mb_s": 6.8,          # Extracción TAR multiparte con miles de archivos pequeños
        "v_single_file_mb_s": 8.8,   # Batocera .img continuo en sistema de archivos
        "v_flash_small_mb_s": 10.5,  # GRUB volcado crudo sectorial (aprovecha caché SLC)
        "v_flash_large_mb_s": 5.80   # CachyOS volcado continuo con decaimiento térmico en USB 2.0
    },
    "usb3_standard": {
        "label": "USB 3.0 / 3.2 Gen 1 Estándar (SanDisk Ultra, Kingston Exodia)",
        "ventoy_sec": 21,
        "settle_sec": 7,
        "grub_part_sec": 10,
        "cachy_part_sec": 26,
        "v_tar_mb_s": 8.73,         # Calibrado de log real: 8260.4 MB en 946s
        "v_single_file_mb_s": 9.70,  # Calibrado de log real: 4720.0 MB en 486s
        "v_flash_small_mb_s": 16.17, # Calibrado de log real: 512.7 MB en 31.7s
        "v_flash_large_mb_s": 8.50   # CachyOS volcado continuo con decaimiento térmico en USB 3.0
    },
    "usb3_fast": {
        "label": "USB 3.1 / 3.2 Alta Velocidad (Samsung BAR Plus, SanDisk Extreme)",
        "ventoy_sec": 14,
        "settle_sec": 5,
        "grub_part_sec": 8,
        "cachy_part_sec": 16,
        "v_tar_mb_s": 22.0,
        "v_single_file_mb_s": 35.0,
        "v_flash_small_mb_s": 45.0,
        "v_flash_large_mb_s": 30.0
    },
    "external_ssd": {
        "label": "SSD Externo / NVMe USB",
        "ventoy_sec": 8,
        "settle_sec": 4,
        "grub_part_sec": 5,
        "cachy_part_sec": 10,
        "v_tar_mb_s": 50.0,
        "v_single_file_mb_s": 80.0,
        "v_flash_small_mb_s": 90.0,
        "v_flash_large_mb_s": 80.0
    }
}

# Tamaños nominales de paquetes (MB)
PACKAGE_SIZES_MB = {
    "pack_hollow": 8260.4,
    "batocera_img": 4720.0,
    "grub_boot": 512.7,
    "cachyos_img": 9346.0,
    "ventoy_base_tar": 2.5
}


class UsbTimeEstimator:
    """
    Algoritmo predictivo de estimación de tiempos para HollowDrive.
    Calcula con precisión matemática la duración de cada proceso individual antes de comenzar,
    y computa el tiempo global restante de forma desacoplada de la velocidad puntual instantánea.
    Aprende continuamente de instalaciones reales y persiste el historial por modelo de USB.
    """

    def __init__(self):
        self.history = self._load_history()

    def _load_history(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logging.warning(f"No se pudo cargar {HISTORY_FILE}: {e}")

        # Base de datos pre-calibrada inicial con la prueba en vivo del hardware real
        initial_history = {
            "USB SanDisk 3.2Gen1 USB": {
                "tier": "usb3_standard",
                "samples": 1,
                "last_date": "2026-10-02 04:11:03",
                "ventoy_sec": 21,
                "settle_sec": 7,
                "grub_part_sec": 10,
                "cachy_part_sec": 26,
                "v_tar_mb_s": 8.73,
                "v_single_file_mb_s": 9.70,
                "v_flash_small_mb_s": 16.17,
                "v_flash_large_mb_s": 11.55
            }
        }
        self._save_history(initial_history)
        return initial_history

    def _save_history(self, data):
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Error guardando {HISTORY_FILE}: {e}")

    def classify_usb(self, model_name, bus_type="USB", size_gb=0):
        """ Clasifica el dispositivo en una categoría de hardware predictiva """
        name = (model_name or "").upper()
        bus = (bus_type or "").upper()

        if any(w in name for w in ["SSD", "NVME", "PSSD", "PORTABLE SSD", "SAMSUNG T", "CRUCIAL X"]) or bus in ["NVME", "SATA"]:
            return "external_ssd"
        if any(w in name for w in ["BAR PLUS", "EXTREME", "DT MAX", "PRO", "ULTRA LUXE"]) or "3.2 GEN 2" in name:
            return "usb3_fast"
        if any(w in name for w in ["3.2", "3.1", "3.0", "ULTRA", "EXODIA", "CRUZER", "SANDISK", "KINGSTON", "KIOXIA"]):
            return "usb3_standard"
        if size_gb > 0 and size_gb <= 16:
            return "usb2_legacy"
        return "usb3_standard" if "USB" in bus else "usb2_legacy"

    def get_profile(self, model_name, bus_type="USB", size_gb=0):
        """ Obtiene el perfil de velocidad (histórico aprendido o perfil base) """
        clean_model = (model_name or "").strip()
        # 1. Búsqueda exacta en historial
        if clean_model and clean_model in self.history:
            return self.history[clean_model], "learned"

        # 2. Búsqueda parcial en historial
        for k, v in self.history.items():
            if clean_model and (k.lower() in clean_model.lower() or clean_model.lower() in k.lower()):
                return v, "learned_approx"

        # 3. Clasificación heurística
        tier = self.classify_usb(clean_model, bus_type, size_gb)
        base = HARDWARE_PROFILES.get(tier, HARDWARE_PROFILES["usb3_standard"]).copy()
        base["tier"] = tier
        return base, tier

    def probe_network_speed(self, mirrors_data=None):
        """ Realiza una micro-prueba no intrusiva (1-2 MB) contra el CDN Cloudflare R2 para medir ancho de banda real """
        url = None
        if mirrors_data:
            try:
                url = mirrors_data["hollowdrive_pack"]["mirrors"][0]["url"]
            except Exception:
                pass
        if not url:
            url = "https://pub-b872cd561e404a9599c943c6705afe9e.r2.dev/HollowdrivePackV1.tar"

        try:
            bytes_read = 0
            t_start = None
            with requests.get(url, stream=True, timeout=3.5, verify=False) as resp:
                if resp.status_code in [200, 206]:
                    t_start = time.time()
                    for chunk in resp.iter_content(chunk_size=256 * 1024):
                        bytes_read += len(chunk)
                        if bytes_read >= 3 * 1024 * 1024 or (time.time() - t_start) > 1.2:
                            break
            if t_start:
                dt = time.time() - t_start
                if dt > 0.05 and bytes_read > 256 * 1024:
                    mb_s = round((bytes_read / (1024 * 1024)) / dt, 2)
                    logging.info(f"[TIME_ESTIMATOR] Micro-sondeo de red puro: {mb_s} MB/s ({bytes_read/(1024*1024):.1f}MB en {dt:.2f}s)")
                    return max(5.0, min(150.0, mb_s))
        except Exception as e:
            logging.debug(f"[TIME_ESTIMATOR] Fallback en sondeo de red: {e}")
        return 35.0

    def probe_usb_write_speed(self, drive_letter):
        """
        Sondeo físico de escritura directa (fsync) en la ventana de preparación (10-15s).
        Escribe un bloque continuo de hasta 48MB con sincronización forzada al medio físico,
        saturando la caché SLC volátil del controlador para capturar la velocidad sostenida real
        de las celdas NAND del dispositivo.
        """
        if not drive_letter or not os.path.exists(drive_letter):
            return None

        target_path = os.path.join(drive_letter, ".hollow_calib.tmp")
        chunk_size = 1024 * 1024  # 1 MB
        chunk = b"H" * chunk_size
        target_mb = 48
        written_mb = 0

        try:
            t0 = time.time()
            with open(target_path, "wb", buffering=0) as f:
                for _ in range(target_mb):
                    f.write(chunk)
                    written_mb += 1
                    # Si el dispositivo es lento (ej: USB 2.0 a 4 MB/s), cortamos tras 8-10s para no exceder la ventana
                    if (time.time() - t0) >= 10.0 and written_mb >= 8:
                        break
                f.flush()
                os.fsync(f.fileno())
            dt = time.time() - t0
            if os.path.exists(target_path):
                try:
                    os.remove(target_path)
                except Exception:
                    pass

            if dt > 0.05 and written_mb >= 4:
                measured_mb_s = round(written_mb / dt, 2)
                logging.info(f"[TIME_ESTIMATOR] Calibración física exhaustiva en {drive_letter}: {written_mb}MB en {dt:.2f}s -> {measured_mb_s} MB/s sostenidos")
                return max(2.5, min(350.0, measured_mb_s))
        except Exception as e:
            logging.debug(f"[TIME_ESTIMATOR] Error en calibración USB {drive_letter}: {e}")
            try:
                if os.path.exists(target_path):
                    os.remove(target_path)
            except Exception:
                pass
        return None

    def build_plan(self, config, usb_info=None, network_speed_mb_s=None, measured_usb_mb_s=None):
        """
        Construye el plan maestro paso a paso con los tiempos estimados de cada proceso.
        Calcula la duración analítica de cada paso que aún no ha comenzado,
        adaptándose al ancho de banda real y al perfil de hardware o al micro-sondeo físico.
        """
        usb_info = usb_info or {}
        model = usb_info.get("model") or config.get("usb_model", "USB Genérico")
        bus = usb_info.get("bus_type", "USB")
        size_gb = usb_info.get("size_gb", 0)

        if measured_usb_mb_s and measured_usb_mb_s > 0:
            k_usb = float(measured_usb_mb_s)
            # Matriz Universal de Ratios Físicos (desacoplada de marcas / histórico):
            v_tar_raw = max(2.5, round(k_usb * 0.91, 2))         # Pack TAR: miles de archivos pequeños (-9%)
            v_single_raw = max(3.0, round(k_usb * 1.00, 2))      # Batocera: archivo secuencial único (100%)
            v_flash_small_raw = max(4.0, round(k_usb * 1.45, 2)) # GRUB: bloque pequeño aprovechando caché SLC (+45%)
            v_flash_large_raw = max(2.5, round(k_usb * 0.84, 2)) # CachyOS: gran volcado con decaimiento térmico (-16%)
            source = "micro_probed_physical"
            tier = self.classify_usb(model, bus, size_gb)
            profile = {
                "tier": tier,
                "ventoy_sec": 14,
                "settle_sec": 5,
                "grub_part_sec": 10,
                "cachy_part_sec": 26,
                "v_tar_mb_s": v_tar_raw,
                "v_single_file_mb_s": v_single_raw,
                "v_flash_small_mb_s": v_flash_small_raw,
                "v_flash_large_mb_s": v_flash_large_raw
            }
        else:
            profile, source = self.get_profile(model, bus, size_gb)
            tier = profile.get("tier", "usb3_standard")
            v_tar_raw = float(profile.get("v_tar_mb_s", 8.73))
            v_single_raw = float(profile.get("v_single_file_mb_s", 9.70))
            v_flash_small_raw = float(profile.get("v_flash_small_mb_s", 16.17))
            v_flash_large_raw = float(profile.get("v_flash_large_mb_s", 8.50))

        descargar_pack_hollow = config.get("descargar_pack_hollow", True)
        instalar_bato = config.get("instalar_bato", False)
        instalar_cachy = config.get("instalar_cachy", False)
        metodo = config.get("metodo_descarga", "ram")

        v_net = float(network_speed_mb_s or config.get("network_speed_mb_s", 30.0))

        # En modo clásico (descarga a SSD + volcado a USB): se suma tiempo de red + tiempo de extracción
        if metodo == "disco":
            time_pack = round((PACKAGE_SIZES_MB["pack_hollow"] / v_net) + (PACKAGE_SIZES_MB["pack_hollow"] / (v_tar_raw * 1.2)))
            time_bato = round((PACKAGE_SIZES_MB["batocera_img"] / v_net) + (PACKAGE_SIZES_MB["batocera_img"] / v_single_raw))
            time_grub = round((PACKAGE_SIZES_MB["grub_boot"] / v_net) + (PACKAGE_SIZES_MB["grub_boot"] / v_flash_small_raw))
            time_cachy = round((PACKAGE_SIZES_MB["cachyos_img"] / v_net) + (PACKAGE_SIZES_MB["cachyos_img"] / v_flash_large_raw))
        else:
            time_pack = round(PACKAGE_SIZES_MB["pack_hollow"] / min(v_net, v_tar_raw))
            time_bato = round(PACKAGE_SIZES_MB["batocera_img"] / min(v_net, v_single_raw))
            time_grub = round(PACKAGE_SIZES_MB["grub_boot"] / min(v_net, v_flash_small_raw))
            time_cachy = round(PACKAGE_SIZES_MB["cachyos_img"] / min(v_net, v_flash_large_raw))

        steps = []
        step_num = 1

        # Paso 1: Ventoy Core
        ventoy_dur = int(profile.get("ventoy_sec", 21)) + int(profile.get("settle_sec", 7))
        steps.append({
            "step_num": step_num,
            "id": "ventoy",
            "name": "Estructura Core (Ventoy)",
            "title": "Estructura Core (Ventoy)",
            "est_sec": ventoy_dur,
            "type": "disk_format"
        })
        step_num += 1

        # Paso 2: Pack HollowDrive o Ventoy Base
        if descargar_pack_hollow:
            steps.append({
                "step_num": step_num,
                "id": "pack_hollow",
                "name": "Pack Utils HollowDrive",
                "title": "Pack Utils HollowDrive",
                "est_sec": time_pack,
                "type": "download_extract"
            })
            step_num += 1
        else:
            steps.append({
                "step_num": step_num,
                "id": "ventoy_base",
                "name": "Configuración Base Ventoy",
                "title": "Configuración Base Ventoy",
                "est_sec": 4,
                "type": "local_extract"
            })
            step_num += 1

        # Paso 3: Batocera OS
        if instalar_bato:
            steps.append({
                "step_num": step_num,
                "id": "batocera_img",
                "name": "Sistema Batocera OS",
                "title": "Sistema Batocera OS",
                "est_sec": time_bato,
                "type": "download_file"
            })
            step_num += 1

        # Pasos 4 & 5: GRUB Particionado + Inyección
        if instalar_cachy:
            grub_part_dur = int(profile.get("grub_part_sec", 10))
            steps.append({
                "step_num": step_num,
                "id": "grub_part",
                "name": "Creación Bootloader GRUB",
                "title": "Creación Bootloader GRUB",
                "est_sec": grub_part_dur,
                "type": "diskpart"
            })
            step_num += 1

            steps.append({
                "step_num": step_num,
                "id": "grub_extract",
                "name": "Inyección Bootloader GRUB",
                "title": "Inyección Bootloader GRUB",
                "est_sec": time_grub,
                "type": "raw_flash"
            })
            step_num += 1

            # Pasos 6 & 7: CachyOS Particionado + Volcado
            cachy_part_dur = int(profile.get("cachy_part_sec", 26))
            steps.append({
                "step_num": step_num,
                "id": "cachy_part",
                "name": "Creación Partición CachyOS",
                "title": "Creación Partición CachyOS",
                "est_sec": cachy_part_dur,
                "type": "diskpart"
            })
            step_num += 1

            steps.append({
                "step_num": step_num,
                "id": "cachy_extract",
                "name": "Volcado Sistema CachyOS",
                "title": "Volcado Sistema CachyOS",
                "est_sec": time_cachy,
                "type": "raw_flash"
            })
            step_num += 1

        total_est_sec = sum(s["est_sec"] for s in steps)

        return {
            "usb_model": model,
            "usb_tier": tier,
            "profile_source": source,
            "total_steps": len(steps),
            "total_est_sec": total_est_sec,
            "steps": steps
        }

    def record_completion(self, usb_model, records, total_duration):
        """
        Guarda las métricas reales de la instalación completada y actualiza
        el modelo predictivo para futuras ejecuciones en este u otros USBs similares.
        """
        if not usb_model or not records:
            return

        model_key = usb_model.strip()
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        existing = self.history.get(model_key, {})
        samples = existing.get("samples", 0) + 1

        # Factores de aprendizaje: ponderación exponencial suave
        alpha = 0.4 if samples > 1 else 1.0

        def blend(old_val, new_val):
            if old_val is None or old_val <= 0:
                return round(float(new_val), 2)
            return round(float(old_val) * (1.0 - alpha) + float(new_val) * alpha, 2)

        entry = existing.copy()
        entry["samples"] = samples
        entry["last_date"] = now_str
        entry["tier"] = existing.get("tier", self.classify_usb(model_key))

        # Actualizar tiempos medidos
        if "Estructura Core (Ventoy)" in records:
            entry["ventoy_sec"] = blend(entry.get("ventoy_sec"), records["Estructura Core (Ventoy)"])
        if "Creación Bootloader GRUB" in records:
            entry["grub_part_sec"] = blend(entry.get("grub_part_sec"), records["Creación Bootloader GRUB"])
        if "Creación Partición CachyOS" in records:
            entry["cachy_part_sec"] = blend(entry.get("cachy_part_sec"), records["Creación Partición CachyOS"])

        # Actualizar velocidades calculadas
        if "Pack Utils HollowDrive" in records and records["Pack Utils HollowDrive"] > 0:
            speed = PACKAGE_SIZES_MB["pack_hollow"] / records["Pack Utils HollowDrive"]
            entry["v_tar_mb_s"] = blend(entry.get("v_tar_mb_s"), speed)

        if "Sistema Batocera OS" in records and records["Sistema Batocera OS"] > 0:
            speed = PACKAGE_SIZES_MB["batocera_img"] / records["Sistema Batocera OS"]
            entry["v_single_file_mb_s"] = blend(entry.get("v_single_file_mb_s"), speed)

        if "Inyección Bootloader GRUB" in records and records["Inyección Bootloader GRUB"] > 0:
            speed = PACKAGE_SIZES_MB["grub_boot"] / records["Inyección Bootloader GRUB"]
            entry["v_flash_small_mb_s"] = blend(entry.get("v_flash_small_mb_s"), speed)

        if "Volcado Sistema CachyOS" in records and records["Volcado Sistema CachyOS"] > 0:
            speed = PACKAGE_SIZES_MB["cachyos_img"] / records["Volcado Sistema CachyOS"]
            entry["v_flash_large_mb_s"] = blend(entry.get("v_flash_large_mb_s"), speed)

        self.history[model_key] = entry
        self._save_history(self.history)
        logging.info(f"[TIME_ESTIMATOR] Perfil actualizado para '{model_key}' (muestras={samples})")
