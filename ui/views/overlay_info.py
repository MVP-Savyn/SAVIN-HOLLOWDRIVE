import os
import webbrowser
import tkinter as tk
from PIL import Image
import customtkinter as ctk
import engine.i18n as i18n
from engine.i18n import t
from ui.theme import (
    AZUL_FONDO, AZUL_CARD, AZUL_CIAN, AZUL_ELECTRICO,
    AZUL_SUAVE, COLOR_BORDE
)

class OverlayInfoView(ctk.CTkFrame):
    """
    Pantalla 0: Capa integrada de Bienvenida e Información.
    Se muestra al iniciar la aplicación sobre la ventana principal.
    Incluye selector de idioma, video tutorial, redes sociales, botón de entrada a HollowDrive
    (ubicado POR ENCIMA de licencias y créditos) y sección de agradecimientos.
    """
    def __init__(self, master, recursos, on_enter_hub, on_language_change=None, **kwargs):
        super().__init__(master, fg_color=AZUL_FONDO[1], corner_radius=0, **kwargs)
        self.recursos = recursos
        self.on_enter_hub = on_enter_hub
        self.on_language_change = on_language_change

        # 0. Barra Superior de Idioma
        f_top_bar = ctk.CTkFrame(self, fg_color="transparent")
        f_top_bar.pack(fill="x", padx=30, pady=(10, 0))

        saved_lang = i18n.get_current_language()
        init_name = i18n.LANGUAGE_NAMES.get(saved_lang, "Español")
        self.btn_idioma = ctk.CTkButton(
            f_top_bar,
            text=f"🌐 {init_name} ▾",
            font=("Segoe UI", 12, "bold"),
            fg_color="#090d12",
            hover_color="#1e293b",
            text_color=AZUL_CIAN,
            border_width=1,
            border_color=AZUL_ELECTRICO,
            height=32,
            cursor="hand2",
            command=self.mostrar_menu_idioma
        )
        self.btn_idioma.pack(side="right")

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

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(expand=True, fill="both", padx=20, pady=(5, 15))

        # 1. Título y Bienvenida
        ctk.CTkLabel(
            scroll,
            text=t("modals.initial.header"),
            font=("Impact", 36),
            text_color=AZUL_CIAN
        ).pack(pady=(5, 4))

        ctk.CTkLabel(
            scroll,
            text=t("modals.initial.welcome"),
            font=("Segoe UI", 14),
            text_color=("#0284c7", "#38bdf8"),
            wraplength=680,
            justify="center"
        ).pack(padx=20, pady=(2, 10))

        # 2. Reproductor de Video Tutorial
        ctk.CTkLabel(
            scroll,
            text=t("modals.initial.video_prompt"),
            font=("Consolas", 14, "bold"),
            text_color=AZUL_SUAVE
        ).pack(pady=(4, 4))

        url_video_youtube = "https://youtu.be/oHg5SJYRHA0?si=7nL_H5sIWuiLM4dp"
        f_video = ctk.CTkFrame(
            scroll,
            fg_color=AZUL_CARD,
            border_width=2,
            border_color=AZUL_ELECTRICO,
            width=460,
            height=250,
            corner_radius=14
        )
        f_video.pack_propagate(False)
        f_video.pack(pady=6)

        # Miniatura o fondo
        miniatura_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "miniatura.png")
        if os.path.exists(miniatura_path):
            try:
                img_raw = Image.open(miniatura_path)
                img_ctk = ctk.CTkImage(light_image=img_raw, dark_image=img_raw, size=(460, 250))
                lbl_fondo = ctk.CTkLabel(f_video, text="", image=img_ctk, corner_radius=14)
                lbl_fondo.place(relx=0.5, rely=0.5, anchor="center")
            except Exception:
                pass

        img_play = recursos.get("img_play")
        lbl_play = ctk.CTkLabel(
            f_video,
            text="" if img_play else "▶",
            image=img_play,
            font=("Consolas", 55, "bold"),
            text_color="#ffffff",
            fg_color="transparent",
            cursor="hand2"
        )
        lbl_play.place(relx=0.5, rely=0.5, anchor="center")
        lbl_play.bind("<Button-1>", lambda e: webbrowser.open_new_tab(url_video_youtube))

        # 3. Plataformas / Redes Sociales
        ctk.CTkLabel(
            scroll,
            text=t("modals.initial.platforms"),
            font=("Consolas", 14, "bold"),
            text_color=AZUL_SUAVE
        ).pack(pady=(12, 4))

        f_social = ctk.CTkFrame(scroll, fg_color="transparent")
        f_social.pack(pady=4)

        socials = [
            ("💬 DISCORD", "https://discord.gg/HJvgmCRpGm"),
            ("📂 GITHUB", "https://github.com/MVP-Savyn"),
            ("📺 YOUTUBE", "https://youtube.com/@T0xicArea")
        ]
        for texto, url in socials:
            ctk.CTkButton(
                f_social,
                text=texto,
                font=("Consolas", 12, "bold"),
                fg_color=AZUL_CARD,
                border_width=1,
                border_color=AZUL_ELECTRICO,
                width=135,
                height=34,
                cursor="hand2",
                command=lambda u=url: webbrowser.open_new_tab(u)
            ).pack(side="left", padx=6)

        # -------------------------------------------------------------
        # 🚀 BOTÓN "ENTRAR A HOLLOWDRIVE" (UBICADO POR ENCIMA DE LICENCIAS)
        # -------------------------------------------------------------
        self.btn_entrar = ctk.CTkButton(
            scroll,
            text=f"🚀 {t('modals.initial.enter_btn')}",
            font=("Segoe UI", 16, "bold"),
            fg_color=AZUL_ELECTRICO,
            hover_color="#0046c7",
            width=320,
            height=48,
            corner_radius=12,
            cursor="hand2",
            command=self._al_entrar_click
        )
        self.btn_entrar.pack(pady=(20, 16))

        # 4. Sección de Herramientas, Licencias y MediCat (DEBAJO del botón entrar)
        ctk.CTkLabel(
            scroll,
            text=t("modals.initial.resources"),
            font=("Consolas", 13, "bold"),
            text_color=AZUL_SUAVE
        ).pack(pady=(8, 4))

        credits_licencias = [
            ("VENTOY CORE (GNU GPLv3)", "https://github.com/ventoy/Ventoy"),
            ("7-ZIP ENGINE (GNU LGPL)", "https://www.7-zip.org"),
            ("CACHY OS (GNU GPLv3)", "https://cachyos.org"),
            ("BATOCERA LINUX (GPLv2)", "https://batocera.org")
        ]

        f_credits = ctk.CTkFrame(scroll, fg_color=AZUL_CARD, corner_radius=10, border_width=1, border_color=COLOR_BORDE)
        f_credits.pack(fill="x", padx=40, pady=6)

        for name, link in credits_licencias:
            row = ctk.CTkFrame(f_credits, fg_color="transparent")
            row.pack(fill="x", padx=15, pady=3)
            ctk.CTkLabel(row, text=f"• {name}", font=("Consolas", 11, "bold")).pack(side="left")
            ctk.CTkButton(
                row,
                text=t("modals.initial.code_web"),
                width=100,
                height=22,
                font=("Segoe UI", 10, "bold"),
                fg_color=AZUL_ELECTRICO,
                command=lambda l=link: webbrowser.open_new_tab(l)
            ).pack(side="right")

        lbl_legal = ctk.CTkLabel(
            f_credits,
            text=t("modals.initial.third_party_notice"),
            font=("Segoe UI", 10, "italic"),
            text_color="#888888",
            wraplength=580,
            justify="center"
        )
        lbl_legal.pack(padx=10, pady=(5, 6))

        f_medicat = ctk.CTkFrame(scroll, fg_color="#181824", border_width=1, border_color=AZUL_ELECTRICO, corner_radius=8)
        f_medicat.pack(fill="x", padx=40, pady=(8, 15))

        lbl_thanks = ctk.CTkLabel(
            f_medicat,
            text=t("modals.initial.thanks"),
            font=("Consolas", 11, "italic"),
            text_color="#dddddd",
            wraplength=500
        )
        lbl_thanks.pack(pady=8, padx=15)

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

    def mostrar(self):
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.lift()

    def ocultar(self):
        self.place_forget()

    def _al_entrar_click(self):
        self.ocultar()
        if self.on_enter_hub:
            self.on_enter_hub()
