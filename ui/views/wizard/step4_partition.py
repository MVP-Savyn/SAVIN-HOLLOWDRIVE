import threading
from tkinter import messagebox
import customtkinter as ctk
from engine.i18n import t
from ui.theme import (
    AZUL_CARD, AZUL_CARD_INNER, AZUL_CIAN, AZUL_ELECTRICO,
    COLOR_BORDE, CTkToolTip
)
from ui.components.partition_canvas import PartitionCanvas
from ui.components.progress_panel import ProgressPanel
from ui.components.wizard_nav import WizardNav

class Step4PartitionView(ctk.CTkFrame):
    """
    Paso 5 de 5: Particionado & Volcado Final.
    Sin título, con mensaje de asignación de espacio, switch de preservar centrado,
    motor de extracción, barra interactiva de particiones y botón de instalación.
    """
    def __init__(self, master, state, recursos, on_back, on_open_modal, on_execute_install, on_cancel_install, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.state = state
        self.recursos = recursos
        self.on_back_flow = on_back
        self.on_open_modal = on_open_modal
        self.on_execute_install = on_execute_install
        self.on_cancel_install = on_cancel_install

        self.en_instalacion = False

        # Tarjeta Central de Particionado
        self.f_card = ctk.CTkFrame(
            self,
            fg_color=AZUL_CARD,
            corner_radius=16,
            border_width=1,
            border_color="#1e293b"
        )
        self.f_card.pack(fill="both", expand=True, padx=30, pady=(15, 10))

        # 1. Mensaje de asignación de espacio solicitado
        lbl_msg = ctk.CTkLabel(
            self.f_card,
            text="Selecciona cuánto espacio quieres asignar a cada componente",
            font=("Segoe UI", 16, "bold"),
            text_color=AZUL_CIAN[1]
        )
        lbl_msg.pack(pady=(16, 8))

        # 2. Selector de Motor de Descompresión y Extracción
        self.f_engine_box = ctk.CTkFrame(
            self.f_card,
            fg_color=AZUL_CARD_INNER,
            corner_radius=12,
            border_width=1,
            border_color=COLOR_BORDE
        )
        self.f_engine_box.pack(fill="x", padx=30, pady=(0, 10))

        f_eng_head = ctk.CTkFrame(self.f_engine_box, fg_color="transparent")
        f_eng_head.pack(fill="x", padx=16, pady=(8, 2))

        ctk.CTkLabel(
            f_eng_head,
            text="MOTOR DE DESCOMPRESIÓN Y EXTRACCIÓN:",
            font=("Consolas", 12, "bold"),
            text_color=AZUL_CIAN[1]
        ).pack(side="left")

        img_triangulo = recursos.get("img_triangulo")
        btn_eng_info = ctk.CTkButton(
            f_eng_head,
            image=img_triangulo,
            text="" if img_triangulo else "ℹ",
            width=28,
            height=28,
            fg_color="transparent",
            hover_color="#1e293b",
            command=lambda: self.on_open_modal("motor") if self.on_open_modal else None
        )
        btn_eng_info.pack(side="right")
        CTkToolTip(btn_eng_info, "Diferencias entre Asíncrono en RAM y Clásico en Disco", delay_ms=300)

        f_radios = ctk.CTkFrame(self.f_engine_box, fg_color="transparent")
        f_radios.pack(fill="x", padx=16, pady=(2, 10))

        self.var_motor = ctk.StringVar(value=self.state.metodo_descarga)
        self.r_ram = ctk.CTkRadioButton(
            f_radios,
            text="Asíncrono en RAM (Streaming ultra-rápido en memoria)",
            variable=self.var_motor,
            value="ram",
            font=("Segoe UI", 12, "bold"),
            command=self._cambiar_motor
        )
        self.r_ram.pack(side="left", padx=(0, 24))

        self.r_disco = ctk.CTkRadioButton(
            f_radios,
            text="Clásico en Disco (Descarga previa a carpeta temporal)",
            variable=self.var_motor,
            value="disco",
            font=("Segoe UI", 12),
            command=self._cambiar_motor
        )
        self.r_disco.pack(side="left")

        # 3. Switch Preservar Espacio Libre (Centrado horizontalmente)
        f_top_sw = ctk.CTkFrame(self.f_card, fg_color="transparent")
        f_top_sw.pack(pady=(4, 8))

        self.var_preservar = ctk.BooleanVar(value=self.state.preservar_espacio)
        self.sw_preservar = ctk.CTkSwitch(
            f_top_sw,
            text=t("motor.preserve_space"),
            font=("Segoe UI", 13, "bold"),
            variable=self.var_preservar,
            progress_color=AZUL_ELECTRICO,
            command=self._al_cambiar_preservar
        )
        self.sw_preservar.pack(side="left")

        btn_info_barra = ctk.CTkButton(
            f_top_sw,
            image=img_triangulo,
            text="" if img_triangulo else "ℹ",
            width=28,
            height=28,
            fg_color="transparent",
            hover_color="#1e293b",
            command=lambda: self.on_open_modal("barra") if self.on_open_modal else None
        )
        btn_info_barra.pack(side="left", padx=8)
        CTkToolTip(btn_info_barra, "Ajuste de precisión con rueda del ratón", delay_ms=300)

        # 4. Barra Visual Interactiva de Particiones
        self.partition_bar = PartitionCanvas(
            self.f_card,
            state=self.state,
            on_change_callback=self._al_cambiar_particiones
        )
        self.partition_bar.pack(fill="x", padx=25, pady=(4, 12))

        # 5. Botón Gigante de Instalación
        img_instalar = recursos.get("img_instalar")
        if img_instalar:
            self.btn_start = ctk.CTkButton(
                self.f_card,
                image=img_instalar,
                text="",
                fg_color="transparent",
                hover_color="#0e1726",
                corner_radius=14,
                width=420,
                height=76,
                cursor="hand2",
                command=self._confirmar_inicio
            )
        else:
            self.btn_start = ctk.CTkButton(
                self.f_card,
                text="COMENZAR INSTALACIÓN",
                font=("Segoe UI", 16, "bold"),
                fg_color=AZUL_ELECTRICO,
                hover_color="#0046c7",
                height=50,
                corner_radius=10,
                cursor="hand2",
                command=self._confirmar_inicio
            )
        self.btn_start.pack(pady=(4, 14))

        # Panel de Progreso (Inicialmente oculto)
        self.progress_panel = ProgressPanel(
            self,
            on_cancel=self.on_cancel_install
        )

        # 6. Barra de Navegación Inferior (Paso 5 de 5)
        self.nav = WizardNav(
            self,
            step_number=5,
            total_steps=5,
            step_title="Particionado & Volcado",
            on_back=self._retroceder,
            on_next=None,
            recursos=recursos
        )
        self.nav.pack(side="bottom", fill="x", padx=30, pady=(0, 15))
        self.nav.btn_next.pack_forget()

    def activar_vista(self):
        """ Sincroniza estado de opciones y barra de particionado al entrar al paso """
        self.var_motor.set(self.state.metodo_descarga)
        self.var_preservar.set(self.state.preservar_espacio)
        self.state.rebalancear()
        self.partition_bar.actualizar()

    def _cambiar_motor(self):
        self.state.metodo_descarga = self.var_motor.get()

    def _al_cambiar_preservar(self):
        self.state.preservar_espacio = self.var_preservar.get()
        self.state.toggle_preservar_espacio()
        self.partition_bar.actualizar()

    def _al_cambiar_particiones(self):
        pass

    def _retroceder(self):
        if self.en_instalacion:
            messagebox.showwarning("PROCESO EN CURSO", "No puedes retroceder mientras la instalación está ejecutándose.")
            return
        if self.on_back_flow:
            self.on_back_flow()

    def _confirmar_inicio(self):
        disco = self.state.selected_disk
        if not disco:
            messagebox.showerror("Error", "No hay ninguna unidad seleccionada.")
            return

        disp = disco.get("display", "USB")
        if messagebox.askyesno(
            "CONFIRMACIÓN DE INSTALACIÓN",
            f"¿Deseas iniciar la instalación real de HollowDrive en:\n'{disp}'?\n\n"
            f"⚠️ ¡TODOS LOS DATOS DEL DISCO SELECCIONADO SERÁN ELIMINADOS!"
        ):
            self.iniciar_modo_progreso()
            if self.on_execute_install:
                self.on_execute_install()

    def iniciar_modo_progreso(self):
        self.en_instalacion = True
        self.btn_start.configure(state="disabled")
        self.sw_preservar.configure(state="disabled")
        self.r_ram.configure(state="disabled")
        self.r_disco.configure(state="disabled")
        self.partition_bar.set_bloqueado(True)
        self.nav.btn_back.configure(state="disabled")

        self.progress_panel.reset()
        self.progress_panel.pack(fill="x", padx=30, pady=(4, 8), before=self.nav)

    def finalizar_modo_progreso(self):
        self.en_instalacion = False
        self.btn_start.configure(state="normal")
        self.sw_preservar.configure(state="normal")
        self.r_ram.configure(state="normal")
        self.r_disco.configure(state="normal")
        self.partition_bar.set_bloqueado(False)
        self.nav.btn_back.configure(state="normal")
        self.progress_panel.pack_forget()
