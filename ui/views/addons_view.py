import os
import threading
from tkinter import messagebox, filedialog
import customtkinter as ctk
from engine.addons_manager import AddonsManager
from engine.disk_logic import obtener_unidades_usb
from engine.download_manager import formatear_tamano
from ui.theme import (
    AZUL_CARD, AZUL_CARD_INNER, AZUL_CIAN, AZUL_ELECTRICO,
    AZUL_SUAVE, COLOR_BORDE, COLOR_MORADO_CYBER, COLOR_CACHY,
    CTkToolTip, hacer_combobox_clicable_total
)
from ui.components.progress_panel import ProgressPanel

try:
    import windnd
    HAS_WINDND = True
except ImportError:
    HAS_WINDND = False

class AddonsView(ctk.CTkFrame):
    """
    Pantalla del Módulo ADDONS: Catálogo dinámico de la comunidad vía archivos .json.
    Permite cargar catálogos desde el disco o URLs, seleccionar paquetes
    y descargarlos/inyectarlos en las particiones correspondientes del USB.
    """
    def __init__(self, master, recursos, on_return_hub, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.recursos = recursos
        self.on_return_hub = on_return_hub

        self.catalogo_actual = None
        self.packs_seleccionados = {}
        self.lista_discos = []
        self.abortar_proceso = False

        # -------------------------------------------------------------
        # 1. Cabecera y Barra de Carga de Catálogo
        # -------------------------------------------------------------
        f_top = ctk.CTkFrame(self, fg_color=AZUL_CARD, corner_radius=12, border_width=1, border_color="#1e293b")
        f_top.pack(fill="x", padx=15, pady=(4, 6))

        f_top_row = ctk.CTkFrame(f_top, fg_color="transparent")
        f_top_row.pack(fill="x", padx=15, pady=8)

        # Título
        f_title = ctk.CTkFrame(f_top_row, fg_color="transparent")
        f_title.pack(side="left")
        ctk.CTkLabel(f_title, text="🧩 CATÁLOGO DE ADDONS Y EXPANSIONES", font=("Impact", 20), text_color=COLOR_MORADO_CYBER).pack(anchor="w")
        self.lbl_cat_sub = ctk.CTkLabel(f_title, text="Carga un archivo .json oficial o de la comunidad", font=("Segoe UI", 10), text_color="#94a3b8")
        self.lbl_cat_sub.pack(anchor="w")

        # Botones de Carga y Selector de USB
        f_actions = ctk.CTkFrame(f_top_row, fg_color="transparent")
        f_actions.pack(side="right")

        self.combo_target_usb = ctk.CTkComboBox(
            f_actions,
            values=["Buscando USBs..."],
            width=260,
            font=("Segoe UI", 11)
        )
        self.combo_target_usb.pack(side="left", padx=(0, 8))
        hacer_combobox_clicable_total(self.combo_target_usb)

        btn_load_file = ctk.CTkButton(
            f_actions,
            text="📂 Cargar JSON",
            font=("Segoe UI", 11, "bold"),
            fg_color="#1e293b",
            hover_color="#334155",
            width=110,
            height=32,
            cursor="hand2",
            command=self._cargar_json_dialogo
        )
        btn_load_file.pack(side="left", padx=(0, 6))

        btn_load_url = ctk.CTkButton(
            f_actions,
            text="🌐 Cargar URL",
            font=("Segoe UI", 11, "bold"),
            fg_color="#1e293b",
            hover_color="#334155",
            width=100,
            height=32,
            cursor="hand2",
            command=self._cargar_url_dialogo
        )
        btn_load_url.pack(side="left")

        # -------------------------------------------------------------
        # 2. Zona de Drag & Drop y Contenedor de Catálogo
        # -------------------------------------------------------------
        self.f_drop_hint = ctk.CTkFrame(self, fg_color="#090d12", corner_radius=10, border_width=1, border_color="#1e293b")
        self.f_drop_hint.pack(fill="x", padx=15, pady=(0, 6))

        self.lbl_drop = ctk.CTkLabel(
            self.f_drop_hint,
            text="💡 Tip: Puedes arrastrar y soltar un archivo .json en cualquier parte de esta ventana para cargar el catálogo.",
            font=("Segoe UI", 11, "italic"),
            text_color=AZUL_SUAVE
        )
        self.lbl_drop.pack(pady=5)

        # Contenedor con Scroll para los paquetes
        self.scroll_packs = ctk.CTkScrollableFrame(self, fg_color="transparent", label_text="")
        self.scroll_packs.pack(fill="both", expand=True, padx=15, pady=2)

        # Panel de Progreso
        self.progress_panel = ProgressPanel(self, on_cancel=self._cancelar_descarga)

        # -------------------------------------------------------------
        # 3. Barra Inferior de Acciones
        # -------------------------------------------------------------
        f_bottom = ctk.CTkFrame(self, fg_color="transparent", height=45)
        f_bottom.pack(fill="x", padx=15, pady=(4, 8))

        self.btn_back_hub = ctk.CTkButton(
            f_bottom,
            text="⬅ Volver al Menú Principal",
            font=("Segoe UI", 12, "bold"),
            fg_color="#1e293b",
            hover_color="#334155",
            height=38,
            width=210,
            command=self.on_return_hub
        )
        self.btn_back_hub.pack(side="left")

        self.btn_inject = ctk.CTkButton(
            f_bottom,
            text="📥 DESCARGAR E INYECTAR EN USB",
            font=("Segoe UI", 13, "bold"),
            fg_color=COLOR_MORADO_CYBER,
            hover_color="#9333ea",
            height=38,
            width=280,
            cursor="hand2",
            command=self._iniciar_inyeccion_addons
        )
        self.btn_inject.pack(side="right")
        self.btn_inject.configure(state="disabled")

        self._mostrar_pantalla_vacia("No hay ningún catálogo cargado.\nHaz clic en 'Cargar JSON' o arrastra un archivo de catálogo aquí.")

        # Escaneo inicial de USBs
        self.refrescar_usbs()

        # Drag & Drop Hook
        if HAS_WINDND:
            self.after(500, self._enganchar_drag_drop)

    def _enganchar_drag_drop(self):
        try:
            windnd.hook_dropfiles(self, func=self._al_soltar_archivos)
        except Exception:
            pass

    def _al_soltar_archivos(self, archivos):
        if not archivos:
            return
        item = archivos[0]
        ruta = item.decode('utf-8', errors='ignore') if isinstance(item, bytes) else str(item)
        ruta = ruta.strip('{}').strip()

        if ruta.lower().endswith(".json") and os.path.isfile(ruta):
            self._procesar_catalogo(ruta)
        else:
            messagebox.showwarning("Formato no válido", "Por favor arrastra únicamente archivos de catálogo con extensión .json")

    def refrescar_usbs(self):
        def run():
            try:
                discos = obtener_unidades_usb(incluir_internos=False)
            except Exception:
                discos = []

            def fin():
                if not self.winfo_exists():
                    return
                self.lista_discos = discos
                if not discos:
                    self.combo_target_usb.configure(values=["⚠️ No se detectan USBs"])
                    self.combo_target_usb.set("⚠️ No se detectan USBs")
                else:
                    nombres = [d["display"] for d in discos]
                    self.combo_target_usb.configure(values=nombres)
                    # Priorizar HollowDrive si existe
                    hollow = next((d["display"] for d in discos if d.get("is_hollow")), nombres[0])
                    self.combo_target_usb.set(hollow)

            self.after(0, fin)

        threading.Thread(target=run, daemon=True).start()

    def _cargar_json_dialogo(self):
        f = filedialog.askopenfilename(
            title="Seleccionar Catálogo JSON",
            filetypes=[("Archivos JSON", "*.json")]
        )
        if f:
            self._procesar_catalogo(f)

    def _cargar_url_dialogo(self):
        dialog = ctk.CTkInputDialog(
            text="Introduce la URL del catálogo de addons (ej. https://.../catalogo.json):",
            title="Cargar Catálogo Remoto"
        )
        url = dialog.get_input()
        if url and url.startswith("http"):
            self._procesar_catalogo(url)

    def _procesar_catalogo(self, origen):
        exito, res = AddonsManager.cargar_catalogo(origen)
        if not exito:
            messagebox.showerror("Error de Catálogo", f"No se pudo cargar el catálogo:\n{res}")
            return

        self.catalogo_actual = res
        nombre = res.get("catalog_name", "Catálogo")
        ver = res.get("version", "1.0")
        self.lbl_cat_sub.configure(text=f"Catálogo: {nombre} (v{ver}) - {len(res.get('packs', []))} paquetes disponibles", text_color=COLOR_CACHY)
        self._renderizar_paquetes(res.get("packs", []))

    def _mostrar_pantalla_vacia(self, texto):
        for c in self.scroll_packs.winfo_children():
            c.destroy()
        lbl = ctk.CTkLabel(
            self.scroll_packs,
            text=texto,
            font=("Segoe UI", 13),
            text_color="#64748b",
            justify="center"
        )
        lbl.pack(pady=60)
        self.btn_inject.configure(state="disabled")

    def _renderizar_paquetes(self, packs):
        for c in self.scroll_packs.winfo_children():
            c.destroy()
        self.packs_seleccionados.clear()

        if not packs:
            self._mostrar_pantalla_vacia("Este catálogo no contiene ningún paquete.")
            return

        for p in packs:
            pid = p["id"]
            card = ctk.CTkFrame(self.scroll_packs, fg_color=AZUL_CARD, corner_radius=12, border_width=1, border_color="#1e293b")
            card.pack(fill="x", padx=6, pady=4)

            f_row = ctk.CTkFrame(card, fg_color="transparent")
            f_row.pack(fill="x", padx=12, pady=10)

            # Checkbox selección
            var_sel = ctk.BooleanVar(value=False)
            self.packs_seleccionados[pid] = (p, var_sel)

            ch = ctk.CTkCheckBox(
                f_row,
                text="",
                variable=var_sel,
                width=24,
                checkbox_height=20,
                checkbox_width=20,
                command=self._actualizar_contador_seleccion
            )
            ch.pack(side="left", padx=(0, 10))

            # Info del paquete
            f_info = ctk.CTkFrame(f_row, fg_color="transparent")
            f_info.pack(side="left", fill="both", expand=True)

            nombre = p.get("name", "Paquete")
            autor = p.get("author", "Comunidad")
            tam_str = formatear_tamano(p.get("size_bytes", 0))
            cat = p.get("category", "General").upper()
            t_part = p.get("target_partition", "HOLLOWDRIVE")
            t_path = p.get("target_path", "")

            # Fila 1: Título y Badge
            f_t_row = ctk.CTkFrame(f_info, fg_color="transparent")
            f_t_row.pack(fill="x")

            ctk.CTkLabel(f_t_row, text=nombre, font=("Segoe UI", 13, "bold"), text_color="#f8fafc").pack(side="left")
            ctk.CTkLabel(f_t_row, text=f" [{cat}] ", font=("Segoe UI", 10, "bold"), text_color=COLOR_MORADO_CYBER).pack(side="left", padx=6)
            ctk.CTkLabel(f_t_row, text=f"•  Peso: {tam_str}", font=("Segoe UI", 11), text_color="#38bdf8").pack(side="left", padx=4)
            ctk.CTkLabel(f_t_row, text=f"•  Autor: {autor}", font=("Segoe UI", 11, "italic"), text_color="#94a3b8").pack(side="left", padx=4)

            # Fila 2: Descripción
            desc = p.get("description", "")
            if desc:
                ctk.CTkLabel(f_info, text=desc, font=("Segoe UI", 11), text_color="#cbd5e1", wraplength=520, justify="left").pack(anchor="w", pady=(2, 2))

            # Fila 3: Destino
            f_dest_row = ctk.CTkFrame(f_info, fg_color="transparent")
            f_dest_row.pack(fill="x", pady=(2, 0))
            ctk.CTkLabel(f_dest_row, text=f"Destino: [{t_part}] ➜ {t_path}", font=("Consolas", 10), text_color=COLOR_CACHY).pack(side="left")

        self._actualizar_contador_seleccion()

    def _actualizar_contador_seleccion(self):
        seleccionados = sum(1 for p, var in self.packs_seleccionados.values() if var.get())
        if seleccionados > 0:
            self.btn_inject.configure(state="normal", text=f"📥 INYECTAR {seleccionados} PAQUETE(S)")
        else:
            self.btn_inject.configure(state="disabled", text="📥 DESCARGAR E INYECTAR EN USB")

    def _iniciar_inyeccion_addons(self):
        sel_usb = self.combo_target_usb.get()
        disco_elegido = next((d for d in self.lista_discos if d.get("display") == sel_usb), None)

        paquetes_a_inyectar = [p for p, var in self.packs_seleccionados.values() if var.get()]
        if not paquetes_a_inyectar:
            messagebox.showwarning("Sin selección", "No has seleccionado ningún paquete para instalar.")
            return

        if not messagebox.askyesno(
            "CONFIRMAR INYECCIÓN",
            f"Se descargarán e inyectarán {len(paquetes_a_inyectar)} paquete(s) en la unidad:\n'{sel_usb}'.\n\n¿Deseas continuar?"
        ):
            return

        self.abortar_proceso = False
        self.btn_inject.configure(state="disabled")
        self.btn_back_hub.configure(state="disabled")

        self.progress_panel.reset()
        self.progress_panel.pack(fill="x", padx=15, pady=(4, 6), before=self.btn_back_hub)

        id_t = "addons_batch"
        self.progress_panel.crear_tarea_dinamica(id_t, "Preparando inyección de addons...", color=COLOR_MORADO_CYBER)

        def run():
            total = len(paquetes_a_inyectar)
            exitosos = 0
            try:
                for idx, pack in enumerate(paquetes_a_inyectar, 1):
                    if self.abortar_proceso:
                        raise InterruptedError()

                    nom = pack.get("name", f"Paquete #{idx}")
                    self.progress_panel.set_status(f"Instalando ({idx}/{total}): {nom}...", "cian")

                    def cb_prog(b_read, t_size, pct, msg):
                        pct_g = (idx - 1 + pct) / total
                        self.progress_panel.set_task_progress(pct)
                        self.progress_panel.set_total_progress(pct_g)
                        self.progress_panel.actualizar_tarea_dinamica(id_t, pct_g, f"[{idx}/{total}] {msg}")

                    AddonsManager.instalar_pack_addon(
                        pack_dict=pack,
                        disco_info=disco_elegido,
                        method="ram",
                        progress_callback=cb_prog,
                        abort_check=lambda: self.abortar_proceso
                    )
                    exitosos += 1

                self.after(0, lambda: messagebox.showinfo("ÉXITO", f"¡{exitosos} paquete(s) inyectado(s) correctamente en el USB!"))
            except InterruptedError:
                self.after(0, lambda: messagebox.showinfo("CANCELADO", "Operación abortada por el usuario."))
            except Exception as e:
                self.after(0, lambda err=str(e): messagebox.showerror("ERROR EN ADDON", f"Fallo al inyectar paquetes:\n{err}"))
            finally:
                self.progress_panel.eliminar_tarea_dinamica(id_t)
                self.progress_panel.pack_forget()
                self.after(0, lambda: self.btn_inject.configure(state="normal"))
                self.after(0, lambda: self.btn_back_hub.configure(state="normal"))

        threading.Thread(target=run, daemon=True).start()

    def _cancelar_descarga(self):
        self.abortar_proceso = True
