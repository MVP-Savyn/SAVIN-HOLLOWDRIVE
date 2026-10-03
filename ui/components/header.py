import tkinter as tk
import customtkinter as ctk
import engine.i18n as i18n
from ui.theme import AZUL_CARD, AZUL_CIAN, CTkToolTip

class AppHeader(ctk.CTkFrame):
    """
    Cabecera superior unificada de la pantalla principal (HUB).
    Estructura:
      - Centro: Título/Logo de HollowDrive con selector de idioma DEBAJO.
      - Derecha: Botón de Información [ ℹ ] en grande.
    """
    def __init__(self, master, recursos, on_info_click, on_language_change=None, **kwargs):
        super().__init__(master, fg_color="transparent", height=175, **kwargs)
        self.recursos = recursos
        self.on_info_click = on_info_click
        self.on_language_change = on_language_change

        self.pack_propagate(False)

        # 1. Botón Información [ ℹ ] (A la derecha, sin reborde, circular perfecto)
        img_info = recursos.get("img_info")
        self.btn_info = ctk.CTkButton(
            self,
            image=img_info,
            text="" if img_info else "ℹ",
            width=48,
            height=48,
            fg_color="transparent",
            hover_color="#182234",
            border_width=0,
            corner_radius=24,
            cursor="hand2",
            command=self.on_info_click
        )
        self.btn_info.place(relx=0.94, rely=0.45, anchor="center")
        CTkToolTip(self.btn_info, "Información del Proyecto y Tutorial", delay_ms=300)

        # 2. Contenedor Central: Logo HollowDrive + Selector de Idioma DEBAJO
        f_center = ctk.CTkFrame(self, fg_color="transparent")
        f_center.place(relx=0.5, rely=0.5, anchor="center")

        logo_maker = recursos.get("logo_maker")
        if logo_maker:
            lbl_m = ctk.CTkLabel(f_center, image=logo_maker, text="")
            lbl_m.pack(anchor="center", pady=(0, 2))
        else:
            lbl_m = ctk.CTkLabel(f_center, text="HOLLOWDRIVE", font=("Impact", 28), text_color=AZUL_CIAN[1])
            lbl_m.pack(anchor="center", pady=(0, 2))

        # Selector de Idioma ubicado justo DEBAJO del logo
        saved_lang = i18n.get_current_language()
        init_name = i18n.LANGUAGE_NAMES.get(saved_lang, "Español")
        self.btn_idioma = ctk.CTkButton(
            f_center,
            text=f"🌐 {init_name} ▾",
            font=("Segoe UI", 11, "bold"),
            fg_color="#090d12",
            hover_color="#1e293b",
            text_color=AZUL_CIAN,
            border_width=1,
            border_color="#1e293b",
            height=28,
            width=135,
            corner_radius=8,
            cursor="hand2",
            command=self.mostrar_menu_idioma
        )
        self.btn_idioma.pack(anchor="center", pady=(2, 0))

        self.menu_idioma = tk.Menu(
            self.btn_idioma,
            tearoff=0,
            bg="#0f172a",
            fg="#38bdf8",
            activebackground="#1e293b",
            activeforeground="#ffffff",
            font=("Segoe UI", 11, "bold"),
            bd=1,
            relief="solid"
        )
        for lang_item in i18n.get_available_languages():
            code = lang_item['code']
            name = lang_item['name']
            self.menu_idioma.add_command(
                label=f"  {name}  ",
                command=lambda c=code, n=name: self._seleccionar_idioma(c, n)
            )

    def mostrar_menu_idioma(self):
        try:
            x = self.btn_idioma.winfo_rootx()
            y = self.btn_idioma.winfo_rooty() + self.btn_idioma.winfo_height() + 2
            self.menu_idioma.post(x, y)
        except Exception:
            pass

    def _seleccionar_idioma(self, code, name):
        i18n.set_language(code)
        self.btn_idioma.configure(text=f"🌐 {name} ▾")
        if self.on_language_change:
            self.on_language_change(code)
