import customtkinter as ctk
from ui.theme import AZUL_ELECTRICO, COLOR_CACHY

class HubView(ctk.CTkFrame):
    """
    Pantalla 1: El HUB Principal.
    Diseño limpio, directo y minimalista con 3 botones principales centrados.
    """
    def __init__(self, master, on_start_wizard, on_open_tools, on_open_addons=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_start_wizard = on_start_wizard
        self.on_open_tools = on_open_tools
        self.on_open_addons = on_open_addons

        # Contenedor centralizado vertical y horizontalmente
        f_center = ctk.CTkFrame(self, fg_color="transparent")
        f_center.place(relx=0.5, rely=0.5, anchor="center")

        # 1. Botón HOLLOWDRIVE (Crear USB)
        btn_hollow = ctk.CTkButton(
            f_center,
            text="HOLLOWDRIVE (Crear USB)",
            font=("Segoe UI", 16, "bold"),
            fg_color=AZUL_ELECTRICO,
            hover_color="#0046c7",
            width=520,
            height=58,
            corner_radius=12,
            cursor="hand2",
            command=self.on_start_wizard
        )
        btn_hollow.pack(pady=12)

        # 2. Botón HOLLOWTOOLS
        btn_tools = ctk.CTkButton(
            f_center,
            text="HOLLOWTOOLS",
            font=("Segoe UI", 16, "bold"),
            fg_color=COLOR_CACHY,
            hover_color="#059669",
            width=520,
            height=58,
            corner_radius=12,
            cursor="hand2",
            command=self.on_open_tools
        )
        btn_tools.pack(pady=12)

        # 3. Botón ADDONS (Próximamente)
        btn_addons = ctk.CTkButton(
            f_center,
            text="ADDONS (Próximamente)",
            font=("Segoe UI", 16, "bold"),
            fg_color="#182234",
            text_color="#64748b",
            state="disabled",
            width=520,
            height=58,
            corner_radius=12
        )
        btn_addons.pack(pady=12)
