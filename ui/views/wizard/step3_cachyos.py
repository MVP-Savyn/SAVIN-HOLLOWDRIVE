import customtkinter as ctk
from engine.i18n import t
from ui.theme import COLOR_CACHY, CTkToolTip
from ui.components.wizard_nav import WizardNav
from ui.components.video_player import EmbeddedVideoLoop

class Step3CachyosView(ctk.CTkFrame):
    """
    Paso 4 de 5: CachyOS.
    Orden estricto solicitado:
      1. Título (el PNG) a la izquierda de la I grande (sin reborde).
      2. ¿Instalar sistema portable? (switch).
      3. Vídeo en bucle ocupando el ancho.
      4. Selección entre Hyprland y KDE.
    """
    def __init__(self, master, state, recursos, on_next, on_back, on_open_modal=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.state = state
        self.recursos = recursos
        self.on_next_flow = on_next
        self.on_back_flow = on_back
        self.on_open_modal = on_open_modal

        # 1 y 2. Header Superior: Logo PNG + Switch a la izquierda, Botón [ ℹ ] a la derecha
        f_header = ctk.CTkFrame(self, fg_color="transparent")
        f_header.pack(fill="x", padx=30, pady=(10, 4))

        f_head_left = ctk.CTkFrame(f_header, fg_color="transparent")
        f_head_left.pack(side="left", fill="y")

        # 1. Título (El PNG)
        logo_cachy = recursos.get("logo_cachy")
        if logo_cachy:
            lbl_title_img = ctk.CTkLabel(f_head_left, image=logo_cachy, text="")
            lbl_title_img.pack(side="left", padx=(0, 16))
        else:
            lbl_title = ctk.CTkLabel(
                f_head_left,
                text="CACHYOS",
                font=("Segoe UI", 22, "bold"),
                text_color=COLOR_CACHY
            )
            lbl_title.pack(side="left", padx=(0, 16))

        # 2. ¿Instalar sistema portable?
        self.var_cachy = ctk.BooleanVar(value=self.state.instalar_cachy)
        self.sw_cachy = ctk.CTkSwitch(
            f_head_left,
            text="¿Instalar sistema portable?",
            font=("Segoe UI", 14, "bold"),
            variable=self.var_cachy,
            progress_color=COLOR_CACHY,
            command=self._al_cambiar_cachy
        )
        self.sw_cachy.pack(side="left")

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
            command=lambda: self.on_open_modal("cachyos") if self.on_open_modal else None
        )
        self.btn_info.pack(side="right")
        CTkToolTip(self.btn_info, "Información detallada sobre CachyOS", delay_ms=300)

        # 3. Vídeo en Bucle Ocupando el Ancho (640x310)
        self.video_player = EmbeddedVideoLoop(
            self,
            video_basename="cachy",
            width=640,
            height=310
        )
        self.video_player.pack(pady=(4, 6))

        # 4. Selección entre Hyprland y KDE
        f_flavor = ctk.CTkFrame(self, fg_color="transparent")
        f_flavor.pack(pady=(0, 6))

        self.var_flavor = ctk.StringVar(value=self.state.cachy_flavor)

        self.r_hypr = ctk.CTkRadioButton(
            f_flavor,
            text="Hyprland (Recomendado)",
            variable=self.var_flavor,
            value="hyprland",
            font=("Segoe UI", 13, "bold"),
            command=self._al_cambiar_flavor
        )
        self.r_hypr.pack(side="left", padx=(0, 24))

        self.r_kde = ctk.CTkRadioButton(
            f_flavor,
            text="KDE Plasma (Próximamente)",
            variable=self.var_flavor,
            value="kde",
            font=("Segoe UI", 13),
            state="disabled",
            command=self._al_cambiar_flavor
        )
        self.r_kde.pack(side="left")

        # 5. Barra de Navegación Inferior (Paso 4 de 5)
        self.nav = WizardNav(
            self,
            step_number=4,
            total_steps=5,
            step_title="CachyOS",
            on_back=self._retroceder,
            on_next=self._avanzar,
            recursos=recursos
        )
        self.nav.pack(side="bottom", fill="x", padx=30, pady=(0, 15))

    def iniciar_video(self):
        self.video_player.iniciar()

    def detener_video(self):
        self.video_player.detener()

    def _al_cambiar_cachy(self):
        self.state.instalar_cachy = self.var_cachy.get()
        self.state.cachy_flavor = self.var_flavor.get()
        self.state.rebalancear()

    def _al_cambiar_flavor(self):
        flavor = self.var_flavor.get()
        self.state.cachy_flavor = flavor
        if flavor == "kde":
            self.video_player.cambiar_video("kde")
        else:
            self.video_player.cambiar_video("cachy")

    def _retroceder(self):
        self.detener_video()
        self.state.instalar_cachy = self.var_cachy.get()
        self.state.cachy_flavor = self.var_flavor.get()
        self.state.rebalancear()
        if self.on_back_flow:
            self.on_back_flow()

    def _avanzar(self):
        self.detener_video()
        self.state.instalar_cachy = self.var_cachy.get()
        self.state.cachy_flavor = self.var_flavor.get()
        self.state.rebalancear()
        if self.on_next_flow:
            self.on_next_flow()
