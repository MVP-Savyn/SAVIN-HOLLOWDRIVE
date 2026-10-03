# Gestor de Estado Central (WizardState)

class WizardState:
    """
    Almacena las selecciones del usuario a lo largo de todo el asistente (Wizard Flow)
    y provee métodos para restablecer valores por defecto y rebalancear particiones.
    """

    def __init__(self):
        self.listeners = []
        self.tamanos_reales = {"bato_64": 4.60, "bato_32": 1.0, "pack_hollow": 8.66}
        self.tamanos_formateados = {"bato_64": "4.60GB", "bato_32": "1GB", "pack_hollow": "8.66GB"}
        self.reset()

    def reset(self):
        """ Restablece todas las selecciones a sus valores por defecto """
        self.selected_disk = None
        self.mostrar_internos = False
        self.metodo_descarga = "ram"  # "ram" o "disco"

        # Opciones Batocera
        self.instalar_bato = False
        self.bato_64_act = True
        self.bato_32_act = False
        self.descargar_pack_hollow = True

        # Opciones CachyOS
        self.instalar_cachy = False
        self.cachy_flavor = "hyprland"  # "hyprland" o "kde"

        # Opciones Particionamiento
        self.preservar_espacio = False
        self.gb_totales = 0.0
        self.val_hollow_gb = 150.0
        self.val_cachy_gb = 100.0
        self.val_libre_gb = 0.0
        self.min_cachy = 20.0

        self.notificar_cambio()

    def set_disk(self, disk_dict):
        self.selected_disk = disk_dict
        if disk_dict:
            self.gb_totales = float(disk_dict.get("size", disk_dict.get("size_gb", 0.0)))
        else:
            self.gb_totales = 0.0
        self.rebalancear()
        self.notificar_cambio()

    def add_listener(self, callback):
        if callback not in self.listeners:
            self.listeners.append(callback)

    def remove_listener(self, callback):
        if callback in self.listeners:
            self.listeners.remove(callback)

    def notificar_cambio(self):
        for cb in self.listeners:
            try:
                cb(self)
            except Exception:
                pass

    def rebalancear(self):
        """ Recalcula las particiones mínimas y proporciones según las opciones activas """
        total = self.gb_totales
        if total <= 0:
            return

        base_h = 10.0 if self.descargar_pack_hollow else 3.0
        gb_bato = (self.tamanos_reales.get("bato_64", 0.0) if self.bato_64_act else 0.0) if self.instalar_bato else 0.0
        min_h = base_h + gb_bato

        if self.instalar_cachy:
            if self.val_cachy_gb < 20.0:
                self.val_cachy_gb = 20.0
            if self.val_hollow_gb + self.val_cachy_gb + self.val_libre_gb > total:
                self.val_hollow_gb = max(min_h, round(total - self.val_cachy_gb - self.val_libre_gb, 1))
        else:
            self.val_cachy_gb = 0.0
            if not self.preservar_espacio:
                self.val_hollow_gb = total
                self.val_libre_gb = 0.0

    def toggle_preservar_espacio(self):
        total = self.gb_totales
        if total <= 0:
            return

        if self.preservar_espacio:
            margen_libre = max(5.0, round(total * 0.15, 1))
            if self.instalar_cachy:
                if self.val_cachy_gb - margen_libre >= 20.0:
                    self.val_cachy_gb = round(self.val_cachy_gb - margen_libre, 1)
                    self.val_libre_gb = margen_libre
                else:
                    self.val_libre_gb = margen_libre
                    self.val_hollow_gb = max(10.0, round(total - self.val_cachy_gb - self.val_libre_gb, 1))
            else:
                self.val_libre_gb = margen_libre
                self.val_hollow_gb = max(10.0, round(total - self.val_cachy_gb - self.val_libre_gb, 1))
        else:
            if self.instalar_cachy:
                self.val_cachy_gb = round(total - self.val_hollow_gb, 1)
            else:
                self.val_hollow_gb = total
            self.val_libre_gb = 0.0

        self.notificar_cambio()
