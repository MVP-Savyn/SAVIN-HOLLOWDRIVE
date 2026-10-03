import threading
from tkinter import messagebox
import customtkinter as ctk
from engine.disk_logic import obtener_unidades_usb
from engine.i18n import t
from ui.theme import AZUL_CIAN, CTkToolTip, hacer_combobox_clicable_total
from ui.components.wizard_nav import WizardNav

class Step1UsbEngineView(ctk.CTkFrame):
    """
    Paso 1 de 5: Selección de Unidad USB con título directo y selector centrado.
    """
    def __init__(self, master, state, recursos, on_next, on_back, on_open_modal=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.state = state
        self.recursos = recursos
        self.on_next_flow = on_next
        self.on_back_flow = on_back
        self.on_open_modal = on_open_modal

        self.lista_discos = []
        self._refrescando = False

        # Contenedor centralizado vertical y horizontalmente
        f_center = ctk.CTkFrame(self, fg_color="transparent")
        f_center.place(relx=0.5, rely=0.46, anchor="center")

        # Título solicitado
        lbl_title = ctk.CTkLabel(
            f_center,
            text="¿Dónde quieres instalar HollowDrive?",
            font=("Segoe UI", 24, "bold"),
            text_color=AZUL_CIAN[1]
        )
        lbl_title.pack(pady=(0, 24))

        # Fila de Selector USB + Botón Refrescar
        f_combo_row = ctk.CTkFrame(f_center, fg_color="transparent")
        f_combo_row.pack(pady=(0, 18))

        self.combo_disk = ctk.CTkComboBox(
            f_combo_row,
            values=[t("selector.searching")],
            width=580,
            height=50,
            font=("Segoe UI", 14, "bold"),
            command=self._al_seleccionar_combo
        )
        self.combo_disk.pack(side="left", padx=(0, 10))
        hacer_combobox_clicable_total(self.combo_disk)

        img_reload = recursos.get("img_reload")
        self.btn_refresh = ctk.CTkButton(
            f_combo_row,
            image=img_reload,
            text="" if img_reload else "🔄",
            width=50,
            height=50,
            fg_color="#1e293b",
            hover_color="#334155",
            corner_radius=10,
            cursor="hand2",
            command=self.refrescar_unidades
        )
        self.btn_refresh.pack(side="left")
        CTkToolTip(self.btn_refresh, "Volver a escanear unidades de almacenamiento", delay_ms=300)

        # Checkbox Discos Internos
        self.var_internos = ctk.BooleanVar(value=self.state.mostrar_internos)
        self.ch_internos = ctk.CTkCheckBox(
            f_center,
            text="Mostrar discos internos del sistema (⚠️ Alto riesgo de formatear tu disco de Windows)",
            variable=self.var_internos,
            font=("Segoe UI", 12, "bold"),
            text_color="#ef4444",
            checkbox_height=20,
            checkbox_width=20,
            command=self._toggle_internos
        )
        self.ch_internos.pack(pady=(4, 0))

        # Barra de Navegación Inferior (Paso 1 de 5)
        self.nav = WizardNav(
            self,
            step_number=1,
            total_steps=5,
            step_title="Unidad USB",
            on_back=self._retroceder,
            on_next=self._avanzar,
            recursos=recursos
        )
        self.nav.pack(side="bottom", fill="x", padx=30, pady=(0, 15))
        self.nav.set_next_enabled(False)

        # Iniciar escaneo inicial de unidades
        self.refrescar_unidades()

    def _retroceder(self):
        self.state.reset()
        if self.on_back_flow:
            self.on_back_flow()

    def _avanzar(self):
        sel = self.combo_disk.get()
        disco = next((d for d in self.lista_discos if d.get("display") == sel), None)
        if not disco:
            messagebox.showerror("Error", "Debes seleccionar una unidad de almacenamiento válida.")
            return

        if "[INT]" in sel or self.var_internos.get():
            dialog = ctk.CTkInputDialog(
                text=f"⚠️ ¡ATENCIÓN: HAS SELECCIONADO UN DISCO INTERNO! ⚠️\n\n"
                     f"Se van a BORRAR todas las particiones de:\n'{disco['display']}'.\n\n"
                     f"Escribe 'BORRAR' en mayúsculas para continuar:",
                title="Doble Candado de Seguridad"
            )
            res = dialog.get_input()
            if res != "BORRAR":
                messagebox.showerror("CANCELADO", "Confirmación de seguridad no superada.")
                return

        self.state.set_disk(disco)
        if self.on_next_flow:
            self.on_next_flow()

    def _al_seleccionar_combo(self, seleccion):
        if not seleccion or any(k in seleccion for k in ["---", "Buscando", "NO SE DETECTAN", "Searching"]):
            self.nav.set_next_enabled(False)
            self.state.selected_disk = None
            return

        disco = next((d for d in self.lista_discos if d.get("display") == seleccion), None)
        if disco:
            self.state.set_disk(disco)
            self.nav.set_next_enabled(True)
        else:
            self.nav.set_next_enabled(False)

    def _toggle_internos(self):
        self.state.mostrar_internos = self.var_internos.get()
        self.refrescar_unidades()

    def refrescar_unidades(self):
        if self._refrescando:
            return
        self._refrescando = True
        self.btn_refresh.configure(state="disabled")
        self.combo_disk.configure(values=[t("selector.searching")])
        self.combo_disk.set(t("selector.searching"))
        self.nav.set_next_enabled(False)

        incluir_internos = self.var_internos.get()

        def run():
            try:
                discos = obtener_unidades_usb(incluir_internos=incluir_internos)
            except Exception:
                discos = []

            def finalizar():
                if not self.winfo_exists():
                    return
                self._refrescando = False
                self.btn_refresh.configure(state="normal")
                self.lista_discos = discos

                if not discos:
                    self.combo_disk.configure(values=[t("selector.no_units")])
                    self.combo_disk.set(t("selector.no_units"))
                    self.nav.set_next_enabled(False)
                else:
                    nombres = [d["display"] for d in discos]
                    self.combo_disk.configure(values=nombres)

                    if self.state.selected_disk and any(d["device"] == self.state.selected_disk.get("device") for d in discos):
                        disp = self.state.selected_disk.get("display")
                        self.combo_disk.set(disp)
                        self._al_seleccionar_combo(disp)
                    else:
                        self.combo_disk.set(t("selector.select_placeholder"))
                        self.nav.set_next_enabled(False)

            self.after(0, finalizar)

        threading.Thread(target=run, daemon=True).start()
