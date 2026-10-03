import customtkinter as ctk
from engine.i18n import t
from ui.theme import AZUL_CIAN, CTkToolTip
from ui.components.wizard_nav import WizardNav
from ui.components.video_player import EmbeddedVideoLoop

class Step2BatoceraView(ctk.CTkFrame):
    """
    Paso 3 de 5: Batocera.
    Estructura:
      - Header: Título y switch a la izquierda de la I grande (sin reborde).
      - Centro: Vídeo batocera.mp4 en bucle ocupando el ancho.
      - Subtexto: Explicación de la imagen bootable para jugar desde cualquier ordenador.
      - Inferior: Navegación estándar.
    """
    def __init__(self, master, state, recursos, on_next, on_back, on_open_modal=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.state = state
        self.recursos = recursos
        self.on_next_flow = on_next
        self.on_back_flow = on_back
        self.on_open_modal = on_open_modal

        # 1. Header Superior: Título + Switch a la izquierda, Botón [ ℹ ] a la derecha
        f_header = ctk.CTkFrame(self, fg_color="transparent")
        f_header.pack(fill="x", padx=30, pady=(12, 6))

        # Bloque izquierdo: Título + Switch en fila
        f_head_left = ctk.CTkFrame(f_header, fg_color="transparent")
        f_head_left.pack(side="left", fill="y")

        lbl_title = ctk.CTkLabel(
            f_head_left,
            text="¿Instalar Batocera?",
            font=("Segoe UI", 22, "bold"),
            text_color=AZUL_CIAN[1]
        )
        lbl_title.pack(side="left", padx=(0, 18))

        self.var_bato = ctk.BooleanVar(value=self.state.instalar_bato)
        tam_bato = self.state.tamanos_formateados.get('bato_64', '4.60 GB')
        self.sw_bato = ctk.CTkSwitch(
            f_head_left,
            text=f"Activar ({tam_bato})",
            font=("Segoe UI", 14, "bold"),
            variable=self.var_bato,
            progress_color=AZUL_CIAN,
            command=self._al_cambiar_bato
        )
        self.sw_bato.pack(side="left")

        # Botón [ ℹ ] arriba a la derecha: circular, sin reborde, botón limpio
        img_info = recursos.get("img_info")
        self.btn_info = ctk.CTkButton(
            f_header,
            image=img_info,
            text="" if img_info else "ℹ",
            width=44,
            height=44,
            fg_color="transparent",
            hover_color="#182234",
            border_width=0,
            corner_radius=22,
            cursor="hand2",
            command=lambda: self.on_open_modal("batocera") if self.on_open_modal else None
        )
        self.btn_info.pack(side="right")
        CTkToolTip(self.btn_info, "Información detallada sobre Batocera", delay_ms=300)

        # 2. Vídeo en Bucle Ocupando el Ancho (640x330)
        self.video_player = EmbeddedVideoLoop(
            self,
            video_basename="batocera",
            width=640,
            height=330
        )
        self.video_player.pack(pady=(4, 6))

        # Subtexto explicativo solicitado
        lbl_subtext = ctk.CTkLabel(
            self,
            text="Esta opción descargará una imagen bootable de Batocera con la que podrás jugar desde cualquier ordenador",
            font=("Segoe UI", 11),
            text_color="#94a3b8"
        )
        lbl_subtext.pack(pady=(0, 6))

        # 3. Barra de Navegación Inferior (Paso 3 de 5)
        self.nav = WizardNav(
            self,
            step_number=3,
            total_steps=5,
            step_title="Batocera",
            on_back=self._retroceder,
            on_next=self._avanzar,
            recursos=recursos
        )
        self.nav.pack(side="bottom", fill="x", padx=30, pady=(0, 15))

    def iniciar_video(self):
        self.video_player.iniciar()

    def detener_video(self):
        self.video_player.detener()

    def _al_cambiar_bato(self):
        act = self.var_bato.get()
        self.state.instalar_bato = act
        self.state.bato_64_act = act
        self.state.rebalancear()

    def _retroceder(self):
        self.detener_video()
        act = self.var_bato.get()
        self.state.instalar_bato = act
        self.state.bato_64_act = act
        self.state.rebalancear()
        if self.on_back_flow:
            self.on_back_flow()

    def _avanzar(self):
        self.detener_video()
        act = self.var_bato.get()
        self.state.instalar_bato = act
        self.state.bato_64_act = act
        self.state.rebalancear()
        if self.on_next_flow:
            self.on_next_flow()
