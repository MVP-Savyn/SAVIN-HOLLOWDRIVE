import os
import json
import logging
import requests
from engine.installer_backend import (
    descargar_y_extraer_pack_generico,
    encontrar_letra_por_etiqueta_ps,
    obtener_o_asignar_letras_cachyos_grub
)
from engine.disk_logic import obtener_estructura_disco_ps

class AddonsManager:
    """
    Gestor de Catálogos y Paquetes Addons de la Comunidad.
    Permite cargar catálogos desde archivos .json locales o URLs remotas,
    validar su esquema, resolver las particiones de destino e inyectar
    paquetes (multisectoriales o individuales).
    """

    @staticmethod
    def cargar_catalogo(origen):
        """
        Carga un catálogo JSON desde una URL o ruta local.
        Retorna (exito: bool, datos_o_error: dict|str).
        """
        if not origen or not isinstance(origen, str):
            return False, "Origen inválido especificado."

        origen = origen.strip()

        try:
            if origen.startswith("http://") or origen.startswith("https://"):
                logging.info(f"🌐 [ADDONS] Descargando catálogo remoto desde: {origen}")
                res = requests.get(origen, timeout=12, verify=False)
                res.raise_for_status()
                datos = res.json()
            else:
                if not os.path.exists(origen):
                    return False, f"El archivo no existe: '{origen}'"
                logging.info(f"📂 [ADDONS] Leyendo catálogo local: {origen}")
                with open(origen, "r", encoding="utf-8") as f:
                    datos = json.load(f)

            es_valido, err = AddonsManager.validar_catalogo(datos)
            if not es_valido:
                return False, err

            return True, datos

        except json.JSONDecodeError as e:
            return False, f"Error de sintaxis en el archivo JSON: {e}"
        except requests.RequestException as e:
            return False, f"Error al descargar el catálogo remoto: {e}"
        except Exception as e:
            return False, f"Fallo procesando el catálogo: {e}"

    @staticmethod
    def validar_catalogo(datos):
        """
        Valida que el diccionario cumpla el esquema requerido:
        catalog_name, version, packs [id, name, format, target_partition, target_path, parts]
        """
        if not isinstance(datos, dict):
            return False, "El archivo JSON debe contener un objeto raíz."

        if "catalog_name" not in datos or "packs" not in datos:
            return False, "Faltan claves obligatorias ('catalog_name' o 'packs') en el JSON."

        packs = datos.get("packs", [])
        if not isinstance(packs, list):
            return False, "La clave 'packs' debe ser una lista de paquetes."

        for idx, p in enumerate(packs, 1):
            if not isinstance(p, dict):
                return False, f"El paquete #{idx} no tiene un formato válido."
            for campo in ["id", "name", "format", "target_partition", "target_path", "parts"]:
                if campo not in p:
                    return False, f"El paquete '{p.get('name', f'#{idx}')}' no define el campo requerido '{campo}'."
            if not isinstance(p["parts"], list) or len(p["parts"]) == 0:
                return False, f"El paquete '{p.get('name')}' debe tener al menos una parte en 'parts'."

        return True, "Catálogo válido"

    @staticmethod
    def resolver_ruta_destino(target_partition, target_path, disco_info=None):
        """
        Resuelve la ruta absoluta final en el USB según la partición objetivo especificada.
        Soporta etiquetas como HOLLOWDRIVE, VENTOY, BATOCERA, CACHYOS, o letras de disco.
        """
        target_part_upper = target_partition.strip().upper()
        letra_base = None

        # 1. Si se especificó una unidad fija de Windows (ej. "E:", "E:\")
        if len(target_partition) <= 3 and target_partition[0].isalpha() and ":" in target_partition:
            letra_base = f"{target_partition[0].upper()}:\\"

        # 2. Búsqueda por disco específico si disco_info está disponible
        if not letra_base and disco_info:
            dev_idx = disco_info.get("device")
            letras_disco = disco_info.get("letras", [])

            if target_part_upper in ("HOLLOWDRIVE", "VENTOY"):
                for l in letras_disco:
                    letra_candidata = f"{l.rstrip(':')}:\\"
                    if os.path.exists(os.path.join(letra_candidata, "HOLLOWDRIVE")) or os.path.exists(letra_candidata):
                        letra_base = letra_candidata
                        break

            elif target_part_upper == "CACHYOS" and dev_idx is not None:
                _, letra_c = obtener_o_asignar_letras_cachyos_grub(dev_idx)
                if letra_c:
                    letra_base = letra_c

        # 3. Búsqueda global por etiqueta de volumen
        if not letra_base:
            if target_part_upper in ("HOLLOWDRIVE", "VENTOY"):
                letra_base = encontrar_letra_por_etiqueta_ps("HOLLOWDRIVE") or encontrar_letra_por_etiqueta_ps("Ventoy")
            elif target_part_upper == "CACHYOS":
                letra_base = encontrar_letra_por_etiqueta_ps("CachyOS")
            elif target_part_upper == "GRUB":
                letra_base = encontrar_letra_por_etiqueta_ps("GRUB")
            else:
                letra_base = encontrar_letra_por_etiqueta_ps(target_partition)

        if not letra_base:
            # Fallback en caso de que HOLLOWDRIVE esté en disco_info
            if disco_info and disco_info.get("letras"):
                letra_base = f"{disco_info['letras'][0]}:\\"
            else:
                raise RuntimeError(
                    f"No se pudo encontrar la partición destino '{target_partition}'. "
                    f"Asegúrate de que el USB esté insertado y montado en Windows."
                )

        # Limpiar y concatenar target_path
        clean_rel = target_path.strip("/\\")
        destino_final = os.path.join(letra_base, clean_rel)
        return destino_final, letra_base

    @staticmethod
    def instalar_pack_addon(pack_dict, disco_info=None, method="ram", progress_callback=None, abort_check=None):
        """
        Descarga e inyecta un paquete individual resolviendo su destino dinámicamente.
        """
        t_partition = pack_dict.get("target_partition", "HOLLOWDRIVE")
        t_path = pack_dict.get("target_path", "")
        nombre = pack_dict.get("name", "Pack Addon")

        destino_final, letra_base = AddonsManager.resolver_ruta_destino(t_partition, t_path, disco_info)

        fmt = pack_dict.get("format", "tar_multipart")
        if fmt in ("tar_multipart", "tar"):
            os.makedirs(destino_final, exist_ok=True)
            target_out = destino_final
        else:
            os.makedirs(os.path.dirname(destino_final), exist_ok=True)
            target_out = destino_final

        logging.info(f"📥 [ADDONS] Inyectando '{nombre}' en: {target_out}")

        descargar_y_extraer_pack_generico(
            pack_data=pack_dict,
            target_dir_or_file=target_out,
            method=method,
            progress_callback=progress_callback,
            abort_check=abort_check
        )

        return True, destino_final
