import customtkinter as ctk
from ui.theme import AZUL_CARD, AZUL_ELECTRICO, AZUL_SUAVE

class WizardNav(ctk.CTkFrame):
    """
    Barra de navegación inferior estandarizada para los pasos del Asistente (Wizard).
    Estructura:
      [ ⬅ Atrás ]  ---  [ Indicador de Paso ]  ---  [ Siguiente ➡ ]
    """
    def __init__(
        self,
        master,
        step_number,
        total_steps,
        step_title="",
        on_back=None,
        on_next=None,
        on_info=None,
        recursos=None,
        **kwargs
    ):
        super().__init__(master, fg_color=AZUL_CARD, corner_radius=12, height=54, border_width=1, border_color="#1e293b", **kwargs)
        self.pack_propagate(False)

        self.on_back = on_back
        self.on_next = on_next

        # 1. Botón [ ⬅ Atrás ]
        self.btn_back = ctk.CTkButton(
            self,
            text="⬅ Atrás",
            font=("Segoe UI", 12, "bold"),
            fg_color="#1e293b",
            hover_color="#334155",
            text_color="#f8fafc",
            width=110,
            height=38,
            corner_radius=8,
            cursor="hand2",
            command=self.on_back
        )
        self.btn_back.pack(side="left", padx=(12, 10), pady=8)

        # 2. Indicador Central de Progreso
        f_mid = ctk.CTkFrame(self, fg_color="transparent")
        f_mid.pack(side="left", fill="both", expand=True)

        txt_step = f"PASO {step_number} DE {total_steps}"
        if step_title:
            txt_step += f"  •  {step_title.upper()}"

        self.lbl_step = ctk.CTkLabel(
            f_mid,
            text=txt_step,
            font=("Segoe UI", 11, "bold"),
            text_color=AZUL_SUAVE
        )
        self.lbl_step.pack(anchor="center", pady=15)

        # 3. Botón [ Siguiente ➡ ]
        self.btn_next = ctk.CTkButton(
            self,
            text="Siguiente ➡",
            font=("Segoe UI", 13, "bold"),
            fg_color=AZUL_ELECTRICO,
            hover_color="#0046c7",
            text_color="#ffffff",
            width=130,
            height=38,
            corner_radius=8,
            cursor="hand2",
            command=self.on_next
        )
        self.btn_next.pack(side="right", padx=(10, 12), pady=8)

    def set_next_enabled(self, enabled=True):
        self.btn_next.configure(state="normal" if enabled else "disabled")

    def set_next_text(self, text):
        self.btn_next.configure(text=text)

    def set_step(self, step_number, total_steps, step_title=""):
        txt = f"PASO {step_number} DE {total_steps}"
        if step_title:
            txt += f"  •  {step_title.upper()}"
        self.lbl_step.configure(text=txt)
