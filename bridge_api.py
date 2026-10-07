import os
import sys
import json
import time
import logging
import threading
import socket
import webbrowser
import ctypes
import webview
from engine.disk_logic import (
    obtener_unidades_usb,
    obtener_estructura_disco_ps,
    crear_particion_adicional,
    _disk_query_lock
)
from engine.installer_backend import (
    ejecutar_instalacion_hollowdrive,
    encontrar_letra_por_etiqueta_ps,
    asignar_letra_particion_ps,
    obtener_o_asignar_letras_cachyos_grub,
    eliminar_particiones_cachy_diskpart,
    copiar_iso_ultrarrapido,
    stream_download_file_direct,
    stream_extract_tar,
    stream_flash_image_direct
)
from engine.addons_manager import AddonsManager
import engine.i18n as i18n

class BridgeApi:
    """
    Puente de comunicación bidireccional entre JavaScript (Pywebview) y el motor Python.
    Expositor de métodos asíncronos y emisor de eventos reactivos a la UI.
    """
    def __init__(self):
        self._window = None
        self._abort_install = False
        self._install_thread = None
        self._addons_thread = None
        self._abort_addons = False
        self._tools_thread = None
        self._abort_tools = False
        self._iso_thread = None
        self._abort_iso = False
        self._packages_thread = None
        self._abort_packages = False
        self._cachy_thread = None
        self._abort_cachy = False
        self._disks_cache = {}
        self._disks_cache_lock = threading.Lock()
        self._disks_active_event = None
        self._disks_active_key = None
        self._iniciar_escuchador_usb()

    def set_window(self, window):
        self._window = window
        self._is_maximized = False

    def window_minimize(self):
        if self._window:
            try:
                self._window.minimize()
            except Exception as e:
                logging.error(f"Error minimizando ventana: {e}")

    def _apply_dwm_rounding(self):
        try:
            if os.name == 'nt' and self._window and hasattr(self._window, 'native') and self._window.native:
                hwnd = self._window.native.Handle.ToInt64()
                # 33 = DWMWA_WINDOW_CORNER_PREFERENCE, 2 = DWMWCP_ROUND
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    ctypes.c_void_p(hwnd),
                    ctypes.c_ulong(33),
                    ctypes.byref(ctypes.c_int(2)),
                    ctypes.sizeof(ctypes.c_int)
                )
        except Exception:
            pass

    def window_toggle_maximize(self):
        if self._window:
            try:
                if getattr(self, '_is_maximized', False):
                    self._window.restore()
                    self._is_maximized = False
                    self._apply_dwm_rounding()
                else:
                    self._window.maximize()
                    self._is_maximized = True
                return {"success": True, "is_maximized": self._is_maximized}
            except Exception as e:
                logging.error(f"Error alternando maximizado de ventana: {e}")
                return {"success": False, "error": str(e)}
        return {"success": False}

    def window_maximize(self):
        if self._window:
            try:
                self._window.maximize()
                self._is_maximized = True
                return {"success": True, "is_maximized": True}
            except Exception as e:
                logging.error(f"Error maximizando ventana: {e}")
                return {"success": False, "error": str(e)}
        return {"success": False}

    def window_start_drag(self):
        try:
            if os.name == 'nt' and self._window and hasattr(self._window, 'native') and self._window.native:
                hwnd = self._window.native.Handle.ToInt64()
                ctypes.windll.user32.ReleaseCapture()
                # WM_SYSCOMMAND = 0x0112, SC_MOVE + HTCAPTION = 0xF012
                ctypes.windll.user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0112, 0xF012, 0)
                return {"success": True}
        except Exception as e:
            logging.error(f"Error iniciando arrastre nativo: {e}")
        return {"success": False}

    def window_start_resize(self, edge="BOTTOM_RIGHT"):
        try:
            if os.name == 'nt' and self._window and hasattr(self._window, 'native') and self._window.native:
                hwnd = self._window.native.Handle.ToInt64()
                ctypes.windll.user32.ReleaseCapture()
                edge_map = {
                    "LEFT": 0xF001,
                    "RIGHT": 0xF002,
                    "TOP": 0xF003,
                    "TOP_LEFT": 0xF004,
                    "TOP_RIGHT": 0xF005,
                    "BOTTOM": 0xF006,
                    "BOTTOM_LEFT": 0xF007,
                    "BOTTOM_RIGHT": 0xF008,
                    "NORTH_WEST": 0xF008,
                    "NORTH_EAST": 0xF007,
                    "SOUTH_WEST": 0xF005,
                    "SOUTH_EAST": 0xF004,
                }
                cmd = edge_map.get(str(edge).upper(), 0xF008)
                ctypes.windll.user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0112, cmd, 0)
                return {"success": True}
        except Exception as e:
            logging.error(f"Error iniciando redimensionamiento nativo: {e}")
        return {"success": False}

    def window_move(self, x, y):
        if self._window:
            try:
                if os.name == 'nt' and hasattr(self._window, 'native') and self._window.native:
                    hwnd = self._window.native.Handle.ToInt64()
                    scale = getattr(self._window.native, '_scale', 1.0)
                    x_phys = int(int(x) * scale)
                    y_phys = int(int(y) * scale)
                    # SWP_NOSIZE (0x0001) | SWP_NOZORDER (0x0004) | SWP_NOACTIVATE (0x0010) = 0x0015
                    ctypes.windll.user32.SetWindowPos(
                        ctypes.c_void_p(hwnd),
                        None,
                        x_phys,
                        y_phys,
                        0,
                        0,
                        0x0015
                    )
                    return {"success": True}
                else:
                    self._window.move(int(x), int(y))
                    return {"success": True}
            except Exception as e:
                logging.error(f"Error moviendo ventana: {e}")
                return {"success": False, "error": str(e)}
        return {"success": False}

    def window_get_state(self):
        is_max = getattr(self, '_is_maximized', False)
        try:
            from webview.platforms.winforms import BrowserView
            browser = BrowserView.instances.get(self._window.uid)
            if browser:
                import System.Windows.Forms as WinForms
                is_max = (browser.WindowState == WinForms.FormWindowState.Maximized)
                self._is_maximized = is_max
        except Exception:
            pass
        return {
            "is_maximized": is_max,
            "width": getattr(self._window, 'width', 1060) if self._window else 1060,
            "height": getattr(self._window, 'height', 860) if self._window else 860
        }

    def window_unmaximize(self, screen_x=None, screen_y=None):
        if self._window:
            try:
                self._window.restore()
                self._is_maximized = False
                self._apply_dwm_rounding()
                time.sleep(0.02)
                target_w = getattr(self._window, 'width', 1060) or 1060
                if screen_x is not None and screen_y is not None:
                    new_x = max(0, int(screen_x - (target_w / 2)))
                    new_y = max(0, int(screen_y - 20))
                    self._window.move(new_x, new_y)
                    return {"success": True, "x": new_x, "y": new_y, "width": target_w, "is_maximized": False}
                return {"success": True, "width": target_w, "is_maximized": False}
            except Exception as e:
                logging.error(f"Error desmaximizando ventana: {e}")
                return {"success": False, "error": str(e)}
        return {"success": False}

    def window_resize(self, width, height, fix_point="NORTH_WEST"):
        if self._window:
            try:
                w = max(940, int(width))
                h = max(680, int(height))
                if os.name == 'nt' and hasattr(self._window, 'native') and self._window.native:
                    native = self._window.native
                    hwnd = native.Handle.ToInt64()
                    scale = getattr(native, '_scale', 1.0)
                    phys_w = int(w * scale)
                    phys_h = int(h * scale)
                    x = native.Location.X
                    y = native.Location.Y
                    cur_w = native.Width
                    cur_h = native.Height

                    fp_str = str(fix_point).upper()
                    if "EAST" in fp_str:
                        x = x + cur_w - phys_w
                    if "SOUTH" in fp_str:
                        y = y + cur_h - phys_h

                    # SWP_NOZORDER (0x0004) | SWP_NOACTIVATE (0x0010) = 0x0014
                    ctypes.windll.user32.SetWindowPos(
                        ctypes.c_void_p(hwnd),
                        None,
                        int(x),
                        int(y),
                        phys_w,
                        phys_h,
                        0x0014
                    )
                    return {"success": True, "width": w, "height": h}
                else:
                    from webview.window import FixPoint
                    fp = FixPoint.NORTH | FixPoint.WEST
                    if fix_point == "NORTH_EAST":
                        fp = FixPoint.NORTH | FixPoint.EAST
                    elif fix_point == "SOUTH_WEST":
                        fp = FixPoint.SOUTH | FixPoint.WEST
                    elif fix_point == "SOUTH_EAST":
                        fp = FixPoint.SOUTH | FixPoint.EAST
                    self._window.resize(w, h, fix_point=fp)
                    return {"success": True, "width": w, "height": h}
            except Exception as e:
                logging.error(f"Error redimensionando ventana: {e}")
                return {"success": False, "error": str(e)}
        return {"success": False}

    def window_close(self):
        if self._window:
            try:
                if self.is_installing():
                    MB_YESNO = 0x00000004
                    MB_ICONWARNING = 0x00000030
                    IDYES = 6
                    res = ctypes.windll.user32.MessageBoxW(
                        None,
                        "Hay una instalación de HollowDrive en curso.\n¿Estás seguro de que deseas salir y abortar?",
                        "Instalación en curso",
                        MB_YESNO | MB_ICONWARNING
                    )
                    if res != IDYES:
                        return
                self._window.destroy()
            except Exception as e:
                logging.error(f"Error cerrando ventana: {e}")

    def is_installing(self):
        return bool(self._install_thread and self._install_thread.is_alive() and not self._abort_install)

    def is_tools_running(self):
        return bool(self._tools_thread and self._tools_thread.is_alive() and not self._abort_tools)

    def _iniciar_escuchador_usb(self):
        def loop():
            mask_anterior = 0
            if os.name == 'nt':
                try:
                    mask_anterior = ctypes.windll.kernel32.GetLogicalDrives()
                except Exception:
                    pass

            while True:
                time.sleep(1.5)
                if self._window is None:
                    continue
                if self._install_thread and self._install_thread.is_alive():
                    continue
                if os.name == 'nt':
                    try:
                        mask_actual = ctypes.windll.kernel32.GetLogicalDrives()
                        if mask_actual != mask_anterior:
                            mask_anterior = mask_actual
                            logging.info(f"[BRIDGE] Cambio en unidades USB detectado (mask={mask_actual})")
                            self._emit_event("usb_hotplug", {"mask": mask_actual})
                    except Exception:
                        pass
        t = threading.Thread(target=loop, daemon=True)
        t.start()

    # =========================================================================
    # 🌐 UTILIDADES Y SISTEMA
    # =========================================================================
    def get_info(self):
        return {
            "version": "12.5 BETA",
            "app_name": "HOLLOWDRIVE",
            "os": sys.platform
        }

    def open_external_url(self, url):
        return self.open_url(url)

    def open_url(self, url):
        try:
            webbrowser.open_new_tab(url)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_folder(self, path):
        try:
            if os.name == 'nt' and os.path.exists(path):
                os.startfile(path)
                return {"success": True}
            return {"success": False, "error": "Ruta no encontrada"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_hollowdrive_folder(self):
        try:
            from engine.installer_backend import encontrar_letra_por_etiqueta_ps
            letra = encontrar_letra_por_etiqueta_ps("HOLLOWDRIVE") or encontrar_letra_por_etiqueta_ps("Ventoy")
            if letra and os.path.exists(letra):
                os.startfile(letra)
                return {"success": True, "path": letra}
            return {"success": False, "error": "No se detectó ninguna unidad HOLLOWDRIVE conectada"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def check_internet(self):
        try:
            endpoints = [("1.1.1.1", 53), ("8.8.8.8", 53), ("www.google.com", 80)]
            for host, port in endpoints:
                try:
                    s = socket.create_connection((host, port), timeout=2.0)
                    s.close()
                    return {"connected": True}
                except Exception:
                    continue
            return {"connected": False}
        except Exception as e:
            return {"connected": False, "error": str(e)}

    # =========================================================================
    # 🌐 IDIOMAS E INTERNACIONALIZACIÓN
    # =========================================================================
    def get_languages(self):
        return {
            "current": i18n.get_current_language(),
            "available": i18n.get_available_languages()
        }

    def set_language(self, lang_code):
        code = str(lang_code).lower()
        i18n.set_current_language(code)
        return {
            "current": code,
            "strings": i18n._catalogs.get(code, i18n._catalogs.get("es", {}))
        }

    def get_translations(self, lang_code=None):
        code = (lang_code or i18n.get_current_language()).lower()
        return {
            "lang": code,
            "strings": i18n._catalogs.get(code, i18n._catalogs.get("es", {}))
        }

    # =========================================================================
    # 💾 DETECCIÓN Y GESTIÓN DE DISCOS
    # =========================================================================
    def get_disks(self, include_internal=False):
        now = time.time()
        cache_key = bool(include_internal)
        active_event = None
        with self._disks_cache_lock:
            cached = self._disks_cache.get(cache_key)
            if cached and (now - cached['time']) < 2.0:
                return cached['data']
            if self._disks_active_event is not None and self._disks_active_key == cache_key:
                active_event = self._disks_active_event
            else:
                self._disks_active_event = threading.Event()
                self._disks_active_key = cache_key

        if active_event is not None:
            active_event.wait(timeout=10)
            with self._disks_cache_lock:
                cached = self._disks_cache.get(cache_key)
                if cached:
                    return cached['data']

        try:
            disks = obtener_unidades_usb(incluir_internos=include_internal)
            logging.info(f"[BRIDGE] Unidades detectadas (internos={include_internal}): {len(disks)}")
            res = {"success": True, "disks": disks}
            with self._disks_cache_lock:
                self._disks_cache[cache_key] = {'time': time.time(), 'data': res}
            return res
        except Exception as e:
            logging.error(f"[BRIDGE] Error detectando unidades: {e}")
            return {"success": False, "error": str(e), "disks": []}
        finally:
            with self._disks_cache_lock:
                if self._disks_active_event and self._disks_active_key == cache_key:
                    self._disks_active_event.set()
                    self._disks_active_event = None
                    self._disks_active_key = None

    # =========================================================================
    # 📦 CATÁLOGO DE HERRAMIENTAS (MODAL [ℹ])
    # =========================================================================
    def get_tools_catalog(self):
        """Retorna las 6 categorías exhaustivas de herramientas integradas en el Kit"""
        return [
            {
                "id": "antivirus",
                "title": "Antivirus & Detección",
                "icon": "/docs/media/images/antivirus.png",
                "desc": "Soluciones de desinfección en arranque seguro para eliminar malware persistente.",
                "tools": [
                    {"name": "Malwarebytes.iso", "desc": "Escaneo y desinfección avanzada de amenazas", "url": "https://www.malwarebytes.com/"}
                ]
            },
            {
                "id": "backups",
                "title": "Backups y Clonación",
                "icon": "/docs/media/images/backup.png",
                "desc": "Clonación sector a sector, creación y restauración de imágenes de discos enteros.",
                "tools": [
                    {"name": "AOMEI_Backupper_Technician_Plus_8.4.0.iso", "desc": "Copia de seguridad y migración a SSD", "url": "https://www.ubackup.com/"},
                    {"name": "clonezilla-live-3.3.1-35-amd64.iso", "desc": "Clonación bare-metal masiva y ultrarrápida", "url": "https://clonezilla.org/"},
                    {"name": "rescuezilla-2.6.2-64bit.resolute.iso", "desc": "Interfaz visual intuitiva de Clonezilla", "url": "https://rescuezilla.com/"}
                ]
            },
            {
                "id": "liveos",
                "title": "Sistemas Live & Rescate",
                "icon": "/docs/media/images/liveos.png",
                "desc": "Entornos Windows PE y Linux completos ejecutables directamente en memoria RAM.",
                "tools": [
                    {"name": "HBCD_PE_x64.iso (Hiren's BootCD PE)", "desc": "El navajazo suizo con cientos de utilidades de diagnóstico", "url": "https://hirensbootcd.org/"}
                ]
            },
            {
                "id": "partition",
                "title": "Gestión de Particiones",
                "icon": "/docs/media/images/partition.png",
                "desc": "Redimensionamiento, conversión MBR/GPT, formateo y reparación de tablas de particiones.",
                "tools": [
                    {"name": "gparted-live-1.8.1-2-amd64.iso", "desc": "Gestor de particiones estándar en GNU/Linux", "url": "https://gparted.org/"},
                    {"name": "PartAssist_WinPE_Technician_10.11.0.iso", "desc": "AOMEI Partition Assistant versión WinPE", "url": "https://www.diskpart.com/"}
                ]
            },
            {
                "id": "supergrub",
                "title": "Rescate de Arranque",
                "icon": "/docs/media/images/supergrub.png",
                "desc": "Reparación y arranque forzado de sistemas operativos que no inician.",
                "tools": [
                    {"name": "Super_GRUB2_Disk.efi", "desc": "Arranque directo de particiones EFI rotas", "url": "https://www.supergrubdisk.org/"},
                    {"name": "Super_GRUB2_Disk.iso", "desc": "Modo BIOS Legacy y compatibilidad universal", "url": "https://www.supergrubdisk.org/"}
                ]
            },
            {
                "id": "osimages",
                "title": "Tus Propias ISOs",
                "icon": "/docs/media/images/osimages.png",
                "desc": "Espacio libre para copiar cualquier instalador de Windows, Linux o utilidades.",
                "tools": [
                    {"name": "Directorio nativo Ventoy", "desc": "Solo arrastra cualquier archivo .iso/.img a la partición", "url": "https://www.ventoy.net/"}
                ]
            }
        ]

    # =========================================================================
    # ⚡ PROCESO DE INSTALACIÓN HOLLOWDRIVE
    # =========================================================================
    def start_installation(self, config):
        """
        Inicia el proceso completo en un hilo independiente.
        `config` contiene:
          - disk_index: int
          - cachy_gb: float
          - hollow_gb: float
          - gb_totales: float
          - preservar_espacio: bool
          - instalar_cachy: bool
          - descargar_pack_hollow: bool
          - instalar_bato: bool
          - cachy_flavor: 'hyprland' | 'sistema' / 'kde'
          - metodo_descarga: 'ram' | 'disco'
        """
        if self._install_thread and self._install_thread.is_alive():
            return {"success": False, "error": "Ya hay una instalación en curso"}

        self._abort_install = False

        def worker():
            callbacks = {
                'on_status': lambda msg, level="info": self._emit_event("status", {"message": msg, "level": level}),
                'on_task_progress': lambda p: self._emit_event("task_progress", {"progress": p}),
                'on_total_progress': lambda p: self._emit_event("total_progress", {"progress": p}),
                'on_step': lambda cur, tot, title, est_sec=0: self._emit_event("step", {"current": cur, "total": tot, "title": title, "est_sec": est_sec}),
                'on_gif': lambda act: self._emit_event("gif", {"active": act}),
                'on_time_plan': lambda plan: self._emit_event("time_plan", plan),
                'on_success': lambda t, rec: self._emit_event("success", {"time": t, "records": rec}),
                'on_error': lambda err_t, msg: self._emit_event("error", {"type": err_t, "message": msg}),
                'on_cancel': lambda: self._emit_event("cancel", {})
            }

            try:
                if not config.get("usb_model"):
                    try:
                        for u in obtener_unidades_usb(incluir_internos=True):
                            if u.get("device") == config.get("disk_index"):
                                config["usb_model"] = u.get("label", "")
                                break
                    except Exception:
                        pass

                logging.info(f"[BRIDGE] Iniciando instalación con configuración: {config}")
                mirrors_data = {}
                try:
                    base_dir = os.path.dirname(os.path.abspath(__file__))
                    mpath = os.path.join(base_dir, "engine", "mirrors.json")
                    if os.path.exists(mpath):
                        with open(mpath, "r", encoding="utf-8") as f:
                            mirrors_data = json.load(f)
                except Exception as me:
                    logging.warning(f"[BRIDGE] No se pudo cargar mirrors.json: {me}")

                ejecutar_instalacion_hollowdrive(
                    config=config,
                    callbacks=callbacks,
                    abort_check=lambda: self._abort_install,
                    mirrors_data=mirrors_data
                )
            except Exception as e:
                logging.error(f"[BRIDGE] Error crítico en worker de instalación: {e}")
                callbacks['on_error'](type(e).__name__, str(e))

        self._install_thread = threading.Thread(target=worker, daemon=True)
        self._install_thread.start()
        return {"success": True}

    def cancel_installation(self):
        self._abort_install = True
        return {"success": True}

    # =========================================================================
    # 🧩 GESTIÓN DE ADDONS
    # =========================================================================
    def pick_file_dialog(self, title="Seleccionar Catálogo JSON", file_types=("Archivos JSON (*.json)", "*.json")):
        if not self._window:
            return None
        try:
            result = self._window.create_file_dialog(
                dialog_type=webview.OPEN_DIALOG,
                allow_multiple=False,
                file_types=(file_types,)
            )
            if result and len(result) > 0:
                return result[0]
            return None
        except Exception as e:
            logging.error(f"[BRIDGE] Error en file dialog: {e}")
            return None

    def load_addons_catalog(self, source):
        try:
            exito, resultado = AddonsManager.cargar_catalogo(source)
            if exito:
                return {"success": True, "catalog": resultado}
            return {"success": False, "error": str(resultado)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def inject_addons(self, pack_list, disco_info):
        """
        Descarga e inyecta secuencialmente una lista de paquetes addons seleccionados.
        """
        if self._addons_thread and self._addons_thread.is_alive():
            return {"success": False, "error": "Ya hay una inyección de addons en curso"}

        self._abort_addons = False

        def worker():
            total = len(pack_list)
            for idx, pack in enumerate(pack_list, 1):
                if self._abort_addons:
                    self._emit_event("addons_cancel", {})
                    return

                pack_name = pack.get("name", "Paquete")
                self._emit_event("addons_step", {
                    "current": idx,
                    "total": total,
                    "pack_name": pack_name
                })

                def on_progress(read, tot, msg):
                    pct = read / tot if tot else 0.5
                    self._emit_event("addons_progress", {
                        "progress": pct,
                        "bytes_read": read,
                        "total_bytes": tot,
                        "message": msg
                    })

                exito, err = AddonsManager.inyectar_paquete(
                    pack=pack,
                    disco_info=disco_info,
                    progress_callback=on_progress,
                    abort_check=lambda: self._abort_addons
                )

                if not exito:
                    self._emit_event("addons_error", {"pack": pack_name, "error": err})
                    return

            self._emit_event("addons_success", {"total_injected": total})

        self._addons_thread = threading.Thread(target=worker, daemon=True)
        self._addons_thread.start()
        return {"success": True}

    def cancel_addons(self):
        self._abort_addons = True
        return {"success": True}

    # =========================================================================
    # 🛠️ MÓDULO HOLLOWTOOLS (MANTENIMIENTO, ISOs, PAQUETES Y CACHYOS)
    # =========================================================================
    def get_hollow_disks(self):
        try:
            res = self.get_disks(include_internal=False)
            if not res or not res.get("success"):
                return {"success": False, "disks": [], "error": res.get("error", "Error consultando discos") if res else "Error"}
            disks = res.get("disks", [])
            hollow_disks = [d for d in disks if d.get("is_hollow")]
            return {"success": True, "disks": hollow_disks if hollow_disks else disks}
        except Exception as e:
            logging.error(f"[BRIDGE] Error en get_hollow_disks: {e}")
            return {"success": False, "disks": [], "error": str(e)}

    def get_disk_partitions_info(self, disk_index):
        try:
            particiones = obtener_estructura_disco_ps(disk_index)
            tiene_cachy = any((p.get("Label") or "").upper() == "CACHYOS" for p in particiones)
            puedes_actualizar = tiene_cachy or (len(particiones) >= 2)

            size_hollow = 0.0
            for p in particiones:
                lbl = (p.get("Label") or "").upper()
                if p.get("Number") == 1 or lbl in ["HOLLOWDRIVE", "VENTOY"]:
                    size_hollow = float(p.get("Size", 0.0))
                    break
            if size_hollow == 0.0 and particiones:
                size_hollow = float(particiones[0].get("Size", 0.0))

            disks = obtener_unidades_usb(incluir_internos=True)
            target_disk = next((d for d in disks if d.get("device") == disk_index), None)
            total_disk_gb = float(target_disk.get("size", 64.0)) if target_disk else 64.0
            espacio_derecha = max(0.0, total_disk_gb - size_hollow)

            return {
                "success": True,
                "partitions": particiones,
                "size_hollow": size_hollow,
                "total_disk_gb": total_disk_gb,
                "espacio_derecha": round(espacio_derecha, 2),
                "tiene_cachy": tiene_cachy,
                "puedes_actualizar": puedes_actualizar
            }
        except Exception as e:
            logging.error(f"[BRIDGE] Error en get_disk_partitions_info: {e}")
            return {"success": False, "error": str(e), "partitions": []}

    def pick_iso_files(self):
        if not self._window:
            return []
        try:
            result = self._window.create_file_dialog(
                dialog_type=webview.OPEN_DIALOG,
                allow_multiple=True,
                file_types=("Archivos ISO (*.iso)",)
            )
            return list(result) if result else []
        except Exception as e:
            logging.error(f"[BRIDGE] Error en pick_iso_files: {e}")
            return []

    def get_files_info(self, file_paths):
        """Devuelve nombres y tamaños formateados de una lista de archivos para la cola de ISOs."""
        results = []
        if not isinstance(file_paths, list):
            return results
        for p in file_paths:
            try:
                if p and os.path.exists(p) and os.path.isfile(p):
                    sz = os.path.getsize(p)
                    if sz >= 1024 * 1024 * 1024:
                        sz_str = f"{sz / (1024 * 1024 * 1024):.2f} GB"
                    elif sz >= 1024 * 1024:
                        sz_str = f"{sz / (1024 * 1024):.1f} MB"
                    else:
                        sz_str = f"{sz / 1024:.1f} KB"
                    results.append({
                        "path": p,
                        "name": os.path.basename(p),
                        "size_bytes": sz,
                        "size_str": sz_str
                    })
                else:
                    results.append({
                        "path": p,
                        "name": os.path.basename(p) if p else "Desconocido",
                        "size_bytes": 0,
                        "size_str": "Desconocido"
                    })
            except Exception as e:
                logging.error(f"[BRIDGE] Error en get_files_info para {p}: {e}")
                results.append({
                    "path": p,
                    "name": os.path.basename(p) if p else "Error",
                    "size_bytes": 0,
                    "size_str": "Error"
                })
        return results

    def copy_isos(self, disk_index, file_paths):
        if self._iso_thread and self._iso_thread.is_alive():
            return {"success": False, "error": "Ya hay una copia de ISOs en curso"}

        if not file_paths:
            return {"success": False, "error": "No se proporcionaron archivos ISO para copiar"}

        self._abort_iso = False

        def worker():
            try:
                letra = encontrar_letra_por_etiqueta_ps("HOLLOWDRIVE", disk_index) or encontrar_letra_por_etiqueta_ps("Ventoy", disk_index)
                if not letra:
                    parts = obtener_estructura_disco_ps(disk_index)
                    for p in parts:
                        if p.get("Number") == 1 and p.get("Letter"):
                            letra = f"{p['Letter']}:\\"
                            break
                if not letra:
                    letra = asignar_letra_particion_ps(disk_index, 1)

                if not letra:
                    self._emit_event("tools_error", {
                        "task": "copy_isos",
                        "error": "No se pudo encontrar ni asignar letra para HOLLOWDRIVE"
                    })
                    return

                letra_clean = letra.rstrip("\\").rstrip("/")
                destino_osimages = os.path.join(letra_clean, "HOLLOWDRIVE", "OSimages")
                os.makedirs(destino_osimages, exist_ok=True)

                total_files = len(file_paths)
                exitosos = 0

                for idx, iso_path in enumerate(file_paths, 1):
                    if self._abort_iso:
                        self._emit_event("tools_cancel", {"task": "copy_isos"})
                        return

                    nombre_iso = os.path.basename(iso_path)
                    ruta_dst = os.path.join(destino_osimages, nombre_iso)
                    t_start = time.time()

                    def cb(bytes_trans, total_bytes):
                        elapsed = time.time() - t_start
                        mb_s = (bytes_trans / (1024 * 1024)) / elapsed if elapsed > 0 else 0
                        pct_file = bytes_trans / total_bytes if total_bytes > 0 else 0
                        pct_global = (idx - 1 + pct_file) / total_files
                        self._emit_event("tools_progress", {
                            "task": "copy_isos",
                            "current": idx,
                            "total": total_files,
                            "filename": nombre_iso,
                            "progress": pct_global,
                            "mb_s": round(mb_s, 1),
                            "message": f"Copiando ({idx}/{total_files}): {nombre_iso} ({pct_file*100:.1f}%)"
                        })

                    copiar_iso_ultrarrapido(
                        iso_path, ruta_dst,
                        callback_progreso=cb,
                        abort_check=lambda: self._abort_iso
                    )
                    exitosos += 1

                self._emit_event("tools_success", {
                    "task": "copy_isos",
                    "message": f"¡{exitosos} archivo(s) ISO volcado(s) con éxito en:\n{destino_osimages}!"
                })
            except InterruptedError:
                self._emit_event("tools_cancel", {"task": "copy_isos"})
            except Exception as e:
                logging.error(f"[BRIDGE] Error en copy_isos worker: {e}")
                self._emit_event("tools_error", {"task": "copy_isos", "error": str(e)})

        self._iso_thread = threading.Thread(target=worker, daemon=True)
        self._iso_thread.start()
        return {"success": True}

    def inject_tools_packages(self, disk_index, install_bato=True, install_pack=True):
        if self._packages_thread and self._packages_thread.is_alive():
            return {"success": False, "error": "Ya hay una inyección de paquetes en curso"}

        if not (install_bato or install_pack):
            return {"success": False, "error": "Selecciona al menos un paquete para inyectar"}

        self._abort_packages = False

        def worker():
            try:
                letra = encontrar_letra_por_etiqueta_ps("HOLLOWDRIVE", disk_index) or encontrar_letra_por_etiqueta_ps("Ventoy", disk_index)
                if not letra:
                    parts = obtener_estructura_disco_ps(disk_index)
                    for p in parts:
                        if p.get("Number") == 1 and p.get("Letter"):
                            letra = f"{p['Letter']}:\\"
                            break
                if not letra:
                    letra = asignar_letra_particion_ps(disk_index, 1)

                if not letra:
                    self._emit_event("tools_error", {
                        "task": "inject_packages",
                        "error": "No se encontró la partición 'HOLLOWDRIVE'"
                    })
                    return

                base_dir = os.path.dirname(os.path.abspath(__file__))
                mpath = os.path.join(base_dir, "engine", "mirrors.json")
                mirrors_data = {}
                if os.path.exists(mpath):
                    try:
                        with open(mpath, "r", encoding="utf-8") as f:
                            mirrors_data = json.load(f)
                    except Exception: pass

                if install_bato and not self._abort_packages:
                    ruta_bato = os.path.join(letra, "HOLLOWDRIVE", "BATOCERUMEN")
                    os.makedirs(ruta_bato, exist_ok=True)
                    dest = os.path.join(ruta_bato, "batocera.img")
                    url_bato = mirrors_data.get("batocera", {}).get("x86_64", {}).get("mirrors", [{}])[0].get(
                        "url", "https://updates.batocera.org/x86_64/stable/last/batocera-x86_64-41-20250220.img.gz"
                    )
                    is_gdrive = "drive.google.com" in url_bato

                    def prog_bato(read_b, tot_b, fase="Descargando"):
                        pct = read_b / tot_b if tot_b else 0.5
                        scaled_pct = pct * 0.5 if install_pack else pct
                        self._emit_event("tools_progress", {
                            "task": "inject_packages",
                            "progress": scaled_pct,
                            "message": f"Batocera OS ({pct*100:.1f}%): {fase}"
                        })

                    stream_download_file_direct(
                        url_bato, dest, is_gdrive=is_gdrive,
                        progress_callback=prog_bato,
                        abort_check=lambda: self._abort_packages
                    )

                if install_pack and not self._abort_packages:
                    url_pack = mirrors_data.get("hollowdrive_pack", {}).get("mirrors", [{}])[0].get(
                        "url", "https://pub-b872cd561e404a9599c943c6705afe9e.r2.dev/HollowdrivePackV1.tar"
                    )
                    def prog_pack(read_b, tot_b, fase="Extrayendo", *args):
                        pct = read_b / tot_b if tot_b else 0.5
                        base_pct = 0.5 if install_bato else 0.0
                        scale = 0.5 if install_bato else 1.0
                        self._emit_event("tools_progress", {
                            "task": "inject_packages",
                            "progress": base_pct + (pct * scale),
                            "message": f"Pack HollowDrive ({pct*100:.1f}%): {fase}"
                        })

                    stream_extract_tar(
                        url_or_id=url_pack,
                        target_dir=letra,
                        dest_dir=letra,
                        is_gdrive=False,
                        progress_callback=prog_pack,
                        abort_check=lambda: self._abort_packages
                    )

                if not self._abort_packages:
                    self._emit_event("tools_success", {
                        "task": "inject_packages",
                        "message": "¡Los paquetes seleccionados se han inyectado correctamente en HOLLOWDRIVE!"
                    })
            except InterruptedError:
                self._emit_event("tools_cancel", {"task": "inject_packages"})
            except Exception as e:
                logging.error(f"[BRIDGE] Error en inject_tools_packages worker: {e}")
                self._emit_event("tools_error", {"task": "inject_packages", "error": str(e)})

        self._packages_thread = threading.Thread(target=worker, daemon=True)
        self._packages_thread.start()
        return {"success": True}

    def cachyos_tools_action(self, disk_index, action_type, flavor="hyprland", size_gb=20.0):
        if self._cachy_thread and self._cachy_thread.is_alive():
            return {"success": False, "error": "Ya hay una operación de CachyOS en curso"}

        self._abort_cachy = False

        def worker():
            try:
                base_dir = os.path.dirname(os.path.abspath(__file__))
                mpath = os.path.join(base_dir, "engine", "mirrors.json")
                mirrors_data = {}
                if os.path.exists(mpath):
                    try:
                        with open(mpath, "r", encoding="utf-8") as f:
                            mirrors_data = json.load(f)
                    except Exception: pass

                if action_type == "instalar":
                    self._emit_event("tools_progress", {
                        "task": "cachyos", "progress": 0.05,
                        "message": "Preparando particiones para CachyOS..."
                    })
                    eliminar_particiones_cachy_diskpart(disk_index)
                    time.sleep(1.5)
                    GB_GRUB = 0.512
                    crear_particion_adicional(disk_index=disk_index, size_gb=GB_GRUB, label="GRUB", fs="fat32")
                    time.sleep(1.5)
                    tamano_seguro_cachy = max(1.0, float(size_gb) - GB_GRUB - 0.15)
                    crear_particion_adicional(disk_index=disk_index, size_gb=tamano_seguro_cachy, label="CachyOS", fs="ntfs")
                    time.sleep(2.0)

                letra_grub = None
                letra_cachy = None
                for _ in range(8):
                    if self._abort_cachy:
                        raise InterruptedError()
                    lg, lc = obtener_o_asignar_letras_cachyos_grub(disk_index)
                    if lg and lc:
                        letra_grub, letra_cachy = lg, lc
                        break
                    time.sleep(1.5)

                if not (letra_grub and letra_cachy):
                    self._emit_event("tools_error", {
                        "task": "cachyos",
                        "error": "No se pudieron asignar las letras de unidad de GRUB y CachyOS"
                    })
                    return

                cachy_cfg = mirrors_data.get("cachyos_images", {})
                if flavor == "hyprland":
                    url_grub = cachy_cfg.get("efi_grub_hyprland", {}).get("mirrors", [{}])[0].get("url")
                    url_cachy = cachy_cfg.get("hyprland", {}).get("mirrors", [{}])[0].get("url")
                else:
                    url_grub = cachy_cfg.get("efi_grub", {}).get("mirrors", [{}])[0].get("url")
                    url_cachy = cachy_cfg.get("sistema", {}).get("mirrors", [{}])[0].get("url")

                if not url_grub:
                    url_grub = "https://pub-b872cd561e404a9599c943c6705afe9e.r2.dev/grub_boot.img"
                if not url_cachy:
                    url_cachy = "https://pub-a129edcf7e704b7b925dfafc7a876a15.r2.dev/cachyos_system.img"

                self._emit_event("tools_progress", {"task": "cachyos", "progress": 0.15, "message": "Flasheando GRUB Bootloader..."})

                def prog_grub(written, total, info="Flasheando", *args):
                    pct = written / total if total and total > 0 else 0.5
                    self._emit_event("tools_progress", {
                        "task": "cachyos",
                        "progress": 0.15 + (pct * 0.25),
                        "message": f"GRUB Bootloader ({pct*100:.1f}%): {info}"
                    })

                stream_flash_image_direct(
                    url_grub, letra_grub,
                    progress_callback=prog_grub,
                    abort_check=lambda: self._abort_cachy,
                    method="ram"
                )

                self._emit_event("tools_progress", {"task": "cachyos", "progress": 0.40, "message": "Flasheando CachyOS Ext4..."})

                def prog_cachy(written, total, info="Flasheando", *args):
                    pct = written / total if total and total > 0 else 0.5
                    self._emit_event("tools_progress", {
                        "task": "cachyos",
                        "progress": 0.40 + (pct * 0.60),
                        "message": f"CachyOS Ext4 ({pct*100:.1f}%): {info}"
                    })

                stream_flash_image_direct(
                    url_cachy, letra_cachy,
                    progress_callback=prog_cachy,
                    abort_check=lambda: self._abort_cachy,
                    method="ram"
                )

                if not self._abort_cachy:
                    verb = "instalado" if action_type == "instalar" else "actualizado"
                    self._emit_event("tools_success", {
                        "task": "cachyos",
                        "message": f"¡CachyOS ha sido {verb} con éxito en la unidad!"
                    })
            except InterruptedError:
                self._emit_event("tools_cancel", {"task": "cachyos"})
            except Exception as e:
                logging.error(f"[BRIDGE] Error en cachyos_tools_action worker: {e}")
                self._emit_event("tools_error", {"task": "cachyos", "error": str(e)})

        self._cachy_thread = threading.Thread(target=worker, daemon=True)
        self._cachy_thread.start()
        return {"success": True}

    def cancel_tools_action(self, task_type=None):
        if task_type == "copy_isos":
            self._abort_iso = True
        elif task_type == "inject_packages":
            self._abort_packages = True
        elif task_type == "cachyos":
            self._abort_cachy = True
        else:
            self._abort_iso = True
            self._abort_packages = True
            self._abort_cachy = True
            self._abort_tools = True
        return {"success": True}

    def is_tools_running(self):
        iso_run = bool(self._iso_thread and self._iso_thread.is_alive())
        pack_run = bool(self._packages_thread and self._packages_thread.is_alive())
        cachy_run = bool(self._cachy_thread and self._cachy_thread.is_alive())
        return {
            "running": iso_run or pack_run or cachy_run,
            "copy_isos": iso_run,
            "inject_packages": pack_run,
            "cachyos": cachy_run
        }

    # =========================================================================
    # ⚡ EMISIÓN DE EVENTOS HACIA JAVASCRIPT
    # =========================================================================
    def _emit_event(self, event_name, payload):
        if not self._window:
            return
        try:
            clean_json = json.dumps(payload)
            js_code = f"window.hollowdrive && window.hollowdrive.handleEvent('{event_name}', {clean_json});"
            self._window.evaluate_js(js_code)
        except Exception as e:
            logging.debug(f"[BRIDGE] Error emitiendo evento '{event_name}' a JS: {e}")

    def log_frontend(self, level, message):
        lvl = str(level).lower()
        if lvl in ('error', 'critical'):
            logging.error(f"[FRONTEND] {message}")
        elif lvl in ('warn', 'warning'):
            logging.warning(f"[FRONTEND] {message}")
        else:
            logging.info(f"[FRONTEND] {message}")
        return True
