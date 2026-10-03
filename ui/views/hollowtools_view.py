import os
import threading
import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
from engine.disk_logic import obtener_unidades_usb, obtener_estructura_disco_ps
from engine.installer_backend import (
    encontrar_letra_por_etiqueta_ps,
    obtener_o_asignar_letras_cachyos_grub,
    eliminar_particiones_cachy_diskpart,
    crear_particion_adicional,
    stream_flash_image_direct,
    stream_download_file_direct,
    stream_extract_tar,
    copiar_iso_ultrarrapido,
    GB_GRUB
)
from engine.i18n import t
from ui.theme import (
    AZUL_CARD, AZUL_CARD_INNER, AZUL_CIAN, AZUL_ELECTRICO,
    AZUL_SUAVE, COLOR_CACHY, COLOR_BORDE, COLOR_HOLLOW,
    COLOR_LIMINE, COLOR_LIBRE, CTkToolTip, hacer_combobox_clicable_total,
    color_canvas_actual
)
from ui.components.progress_panel import ProgressPanel

class HollowToolsView(ctk.CTkFrame):
    """
    Pantalla de Mantenimiento HollowTools:
    - Selector de unidades con etiqueta HollowDrive
    - Tarjeta 1: Gestor de ISOs (Drag & Drop + botón)
    - Tarjeta 2: Inyección de Paquetes
    - Tarjeta 3: Gestión y Actualización de CachyOS
    - Barra comparativa Antes / Después
    - Botón [ ⬅ Volver al Menú ]
    """
    def __init__(self, master, recursos, on_return_hub, on_open_modal, mirrors_data=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.recursos = recursos
        self.on_return_hub = on_return_hub
        self.on_open_modal = on_open_modal
        self.mirrors_data = mirrors_data or {}

        self.lista_discos_hollow = []
        self._refrescando_ht = False
        self.abortar_proceso = False
        self.en_proceso = False

        # -------------------------------------------------------------
        # 1. Cabecera y Selector HollowDrive
        # -------------------------------------------------------------
        f_top = ctk.CTkFrame(self, fg_color=AZUL_CARD, corner_radius=12, border_width=1, border_color="#1e293b")
        f_top.pack(fill="x", padx=15, pady=(4, 6))

        f_top_inner = ctk.CTkFrame(f_top, fg_color="transparent")
        f_top_inner.pack(fill="x", padx=15, pady=8)

        ctk.CTkLabel(
            f_top_inner,
            text="🛠️ HOLLOWTOOLS: MANTENIMIENTO Y GESTIÓN",
            font=("Impact", 20),
            text_color=AZUL_CIAN
        ).pack(side="left")

        # Selector de disco
        f_combo = ctk.CTkFrame(f_top_inner, fg_color="transparent")
        f_combo.pack(side="right")

        self.combo_ht_disk = ctk.CTkComboBox(
            f_combo,
            values=["Buscando HOLLOWDRIVES..."],
            width=380,
            font=("Segoe UI", 11),
            command=self._al_seleccionar_disco
        )
        self.combo_ht_disk.pack(side="left", padx=(0, 6))
        hacer_combobox_clicable_total(self.combo_ht_disk)

        img_reload = recursos.get("img_reload")
        self.btn_refresh = ctk.CTkButton(
            f_combo,
            image=img_reload,
            text="" if img_reload else "🔄",
            width=36,
            height=32,
            fg_color="#1e293b",
            hover_color="#334155",
            cursor="hand2",
            command=self.refrescar_discos
        )
        self.btn_refresh.pack(side="left")
        CTkToolTip(self.btn_refresh, "Buscar unidades HollowDrive", delay_ms=400)

        # -------------------------------------------------------------
        # 2. Rejilla de 3 Tarjetas de Acción
        # -------------------------------------------------------------
        self.f_grid = ctk.CTkFrame(self, fg_color="transparent")
        self.f_grid.pack(fill="both", expand=True, padx=15, pady=4)
        self.f_grid.grid_columnconfigure((0, 1, 2), weight=1, uniform="col_ht")

        # TARJETA 1: GESTOR DE ISOs
        self.card_iso = ctk.CTkFrame(self.f_grid, fg_color=AZUL_CARD, corner_radius=14, border_width=1, border_color="#1e293b")
        self.card_iso.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

        f_h_iso = ctk.CTkFrame(self.card_iso, fg_color="transparent")
        f_h_iso.pack(fill="x", padx=10, pady=(10, 4))
        ctk.CTkLabel(f_h_iso, text="💿 GESTOR DE ISOs", font=("Segoe UI", 14, "bold"), text_color=AZUL_CIAN).pack(side="left")

        img_triangulo = recursos.get("img_triangulo")
        ctk.CTkButton(
            f_h_iso, image=img_triangulo, text="" if img_triangulo else "ℹ", width=26, height=26,
            fg_color="transparent", hover_color="#1e293b", command=lambda: self.on_open_modal("ht_isos")
        ).pack(side="right")

        f_drop = ctk.CTkFrame(self.card_iso, fg_color="#090d12", corner_radius=10, border_width=1, border_color="#1e293b")
        f_drop.pack(fill="both", expand=True, padx=10, pady=8)

        ctk.CTkLabel(f_drop, text="Arrastra archivos .iso aquí\no haz clic abajo", font=("Segoe UI", 11), text_color=AZUL_SUAVE).pack(pady=(12, 6))

        ctk.CTkButton(
            f_drop,
            text="➕ AÑADIR ARCHIVOS .ISO",
            font=("Segoe UI", 12, "bold"),
            fg_color=AZUL_ELECTRICO,
            hover_color="#0046c7",
            height=38,
            cursor="hand2",
            command=self._agregar_isos
        ).pack(pady=(4, 14), padx=15, fill="x")

        # TARJETA 2: PAQUETES
        self.card_packs = ctk.CTkFrame(self.f_grid, fg_color=AZUL_CARD, corner_radius=14, border_width=1, border_color="#1e293b")
        self.card_packs.grid(row=0, column=1, sticky="nsew", padx=4, pady=4)

        f_h_p = ctk.CTkFrame(self.card_packs, fg_color="transparent")
        f_h_p.pack(fill="x", padx=10, pady=(10, 4))
        ctk.CTkLabel(f_h_p, text="📦 PAQUETES", font=("Segoe UI", 14, "bold"), text_color=AZUL_CIAN).pack(side="left")
        ctk.CTkButton(
            f_h_p, image=img_triangulo, text="" if img_triangulo else "ℹ", width=26, height=26,
            fg_color="transparent", hover_color="#1e293b", command=lambda: self.on_open_modal("ht_packs")
        ).pack(side="right")

        f_ch_box = ctk.CTkFrame(self.card_packs, fg_color="#090d12", corner_radius=10, border_width=1, border_color="#1e293b")
        f_ch_box.pack(fill="both", expand=True, padx=10, pady=8)

        self.var_tool_bato = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(f_ch_box, text="Batocera OS (.img)", font=("Segoe UI", 11), variable=self.var_tool_bato).pack(anchor="w", pady=(10, 6), padx=12)

        self.var_tool_pack = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(f_ch_box, text="Pack HollowDrive (8.7 GB)", font=("Segoe UI", 11), variable=self.var_tool_pack).pack(anchor="w", pady=(0, 10), padx=12)

        ctk.CTkButton(
            f_ch_box,
            text="📥 INYECTAR SELECCIONADOS",
            font=("Segoe UI", 11, "bold"),
            fg_color=AZUL_ELECTRICO,
            hover_color="#0046c7",
            height=36,
            cursor="hand2",
            command=self._inyectar_paquetes
        ).pack(side="bottom", pady=10, padx=12, fill="x")

        # TARJETA 3: CACHYOS
        self.card_cachy = ctk.CTkFrame(self.f_grid, fg_color=AZUL_CARD, corner_radius=14, border_width=1, border_color="#1e293b")
        self.card_cachy.grid(row=0, column=2, sticky="nsew", padx=4, pady=4)

        f_h_c = ctk.CTkFrame(self.card_cachy, fg_color="transparent")
        f_h_c.pack(fill="x", padx=10, pady=(10, 4))
        ctk.CTkLabel(f_h_c, text="🚀 CACHYOS OS", font=("Segoe UI", 14, "bold"), text_color=COLOR_CACHY).pack(side="left")
        ctk.CTkButton(
            f_h_c, image=img_triangulo, text="" if img_triangulo else "ℹ", width=26, height=26,
            fg_color="transparent", hover_color="#1e293b", command=lambda: self.on_open_modal("ht_cachy")
        ).pack(side="right")

        f_b_cachy = ctk.CTkFrame(self.card_cachy, fg_color="transparent")
        f_b_cachy.pack(fill="both", expand=True, padx=10, pady=6)

        self.seg_modo_cachy = ctk.CTkSegmentedButton(
            f_b_cachy,
            values=["🔄 Actualizar", "➕ Instalar"],
            font=("Segoe UI", 11, "bold"),
            selected_color=AZUL_ELECTRICO,
            command=self._al_cambiar_modo_cachy
        )
        self.seg_modo_cachy.set("🔄 Actualizar")
        self.seg_modo_cachy.pack(fill="x", pady=(0, 6))

        self.slider_cachy = ctk.CTkSlider(f_b_cachy, from_=20, to=100, progress_color=COLOR_CACHY, command=lambda v: self._actualizar_preview_barras())
        self.lbl_slider_info = ctk.CTkLabel(f_b_cachy, text="Disponible: 0.0 GB", font=("Segoe UI", 10), text_color="#94a3b8")

        self.btn_ejecutar_cachy = ctk.CTkButton(
            f_b_cachy,
            text="⚡ APLICAR EN CACHYOS",
            font=("Segoe UI", 11, "bold"),
            fg_color=AZUL_ELECTRICO,
            hover_color="#0046c7",
            height=36,
            command=self._ejecutar_accion_cachy
        )
        self.btn_ejecutar_cachy.pack(side="bottom", fill="x", pady=(6, 4))

        # -------------------------------------------------------------
        # 3. Comparativa Visual Antes / Después
        # -------------------------------------------------------------
        self.f_preview = ctk.CTkFrame(self, fg_color=AZUL_CARD, corner_radius=12, border_width=1, border_color="#1e293b")
        self.f_preview.pack(fill="x", padx=15, pady=(4, 6))

        f_p1 = ctk.CTkFrame(self.f_preview, fg_color="transparent")
        f_p1.pack(fill="x", padx=12, pady=(4, 2))
        ctk.CTkLabel(f_p1, text="ESTRUCTURA ACTUAL", font=("Segoe UI", 10, "bold"), text_color=AZUL_SUAVE).pack(side="left")
        self.lbl_bar_actual = ctk.CTkLabel(f_p1, text="", font=("Segoe UI", 10), text_color="#ffffff")
        self.lbl_bar_actual.pack(side="right")
        self.canvas_actual = tk.Canvas(self.f_preview, height=18, bg=color_canvas_actual(), highlightthickness=0, borderwidth=0)
        self.canvas_actual.pack(fill="x", padx=12, pady=(0, 2))

        f_p2 = ctk.CTkFrame(self.f_preview, fg_color="transparent")
        f_p2.pack(fill="x", padx=12, pady=(2, 2))
        ctk.CTkLabel(f_p2, text="ESTRUCTURA TRAS OPERACIÓN", font=("Segoe UI", 10, "bold"), text_color=COLOR_CACHY).pack(side="left")
        self.lbl_bar_futuro = ctk.CTkLabel(f_p2, text="", font=("Segoe UI", 10), text_color="#ffffff")
        self.lbl_bar_futuro.pack(side="right")
        self.canvas_futuro = tk.Canvas(self.f_preview, height=18, bg=color_canvas_actual(), highlightthickness=0, borderwidth=0)
        self.canvas_futuro.pack(fill="x", padx=12, pady=(0, 6))

        # Panel de Tareas Dinámicas
        self.progress_panel = ProgressPanel(self, on_cancel=self._cancelar_proceso)

        # -------------------------------------------------------------
        # 4. Barra Inferior de Retorno al Menú
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
            width=220,
            command=self.on_return_hub
        )
        self.btn_back_hub.pack(side="left")

        # Escaneo inicial
        self.refrescar_discos()

    def refrescar_discos(self):
        if self._refrescando_ht:
            return
        self._refrescando_ht = True
        self.btn_refresh.configure(state="disabled")
        self.combo_ht_disk.configure(values=[t("hollowtools.searching")])
        self.combo_ht_disk.set(t("hollowtools.searching"))

        def run():
            try:
                unidades = obtener_unidades_usb(incluir_internos=False)
                filtradas = [u for u in unidades if u.get("is_hollow")]
            except Exception:
                filtradas = []

            def fin():
                if not self.winfo_exists():
                    return
                self._refrescando_ht = False
                self.btn_refresh.configure(state="normal")
                self.lista_discos_hollow = filtradas
                if not filtradas:
                    self.combo_ht_disk.configure(values=[t("hollowtools.no_units")])
                    self.combo_ht_disk.set(t("hollowtools.no_units"))
                else:
                    nombres = [d["display"] for d in filtradas]
                    self.combo_ht_disk.configure(values=nombres)
                    self.combo_ht_disk.set(nombres[0])
                    self._al_seleccionar_disco(nombres[0])

            self.after(0, fin)

        threading.Thread(target=run, daemon=True).start()

    def _al_seleccionar_disco(self, seleccion):
        disco = next((d for d in self.lista_discos_hollow if d.get("display") == seleccion), None)
        if not disco:
            return

        def run():
            particiones = obtener_estructura_disco_ps(disco["device"])
            total_disk_gb = disco.get("size", 0.0)

            size_hollow = 0.0
            for p in particiones:
                lbl = (p.get("Label") or "").upper()
                if p.get("Number") == 1 or lbl in ["HOLLOWDRIVE", "VENTOY"]:
                    size_hollow = p.get("Size", 0.0)
                    break

            espacio_derecha = max(0.0, total_disk_gb - size_hollow)

            def update():
                if not self.winfo_exists():
                    return
                self.ht_particiones = particiones
                self.ht_total_gb = total_disk_gb
                self.ht_size_hollow = size_hollow
                self.ht_espacio_derecha = espacio_derecha

                if espacio_derecha >= 20.0:
                    self.slider_cachy.configure(state="normal", from_=20.0, to=espacio_derecha)
                    self.slider_cachy.set(espacio_derecha)
                    self.lbl_slider_info.configure(text=f"Disponible a la derecha: {espacio_derecha:.1f} GB")
                else:
                    self.slider_cachy.configure(state="disabled")
                    self.lbl_slider_info.configure(text=f"Espacio insuficiente: {espacio_derecha:.1f} GB (mín. 20 GB)")

                self._actualizar_preview_barras()

            self.after(0, update)

        threading.Thread(target=run, daemon=True).start()

    def _al_cambiar_modo_cachy(self, value):
        if "Actualizar" in value:
            self.slider_cachy.pack_forget()
            self.lbl_slider_info.pack_forget()
        else:
            self.lbl_slider_info.pack(pady=(2, 0), before=self.btn_ejecutar_cachy)
            self.slider_cachy.pack(fill="x", pady=(2, 6), padx=10, before=self.btn_ejecutar_cachy)
        self._actualizar_preview_barras()

    def _actualizar_preview_barras(self):
        if not hasattr(self, 'ht_particiones'):
            return
        total_gb = getattr(self, 'ht_total_gb', 0.0)
        if total_gb <= 0:
            return

        w_act = self.canvas_actual.winfo_width()
        w_fut = self.canvas_futuro.winfo_width()
        if w_act <= 1 or w_fut <= 1:
            return

        self.canvas_actual.delete("all")
        x = 0
        size_cachy_act = 0.0

        for p in self.ht_particiones:
            p_size = p.get("Size", 0.0)
            pix = int((p_size / total_gb) * w_act)
            lbl = (p.get("Label") or "").upper()
            num = p.get("Number")

            if "HOLLOW" in lbl or "VENTOY" in lbl or num == 1:
                col = COLOR_HOLLOW
            elif "GRUB" in lbl or (0.2 <= p_size <= 1.5 and num != 1):
                col = COLOR_LIMINE
            elif "CACHY" in lbl or (p_size >= 5.0 and num != 1):
                col = COLOR_CACHY
                size_cachy_act = p_size
            else:
                col = COLOR_HOLLOW

            self.canvas_actual.create_rectangle(x, 0, x + pix, 18, fill=col, outline="#05080a")
            x += pix

        if x < w_act:
            self.canvas_actual.create_rectangle(x, 0, w_act, 18, fill=COLOR_LIBRE, outline="")

        info_act = []
        if size_cachy_act > 0:
            info_act.append(f"CachyOS: {size_cachy_act:.1f} GB")
        info_act.append(f"Libre: {max(0.0, total_gb - sum(p.get('Size', 0.0) for p in self.ht_particiones)):.1f} GB")
        self.lbl_bar_actual.configure(text=" | ".join(info_act))

        # Barra Futuro
        self.canvas_futuro.delete("all")
        self.canvas_futuro.create_rectangle(0, 0, w_fut, 18, fill=COLOR_HOLLOW, outline="")

    def _agregar_isos(self):
        letra = encontrar_letra_por_etiqueta_ps("HOLLOWDRIVE") or encontrar_letra_por_etiqueta_ps("Ventoy")
        if not letra:
            messagebox.showerror("Error", "No se encontró montada la partición HOLLOWDRIVE.")
            return

        archivos = filedialog.askopenfilenames(
            title="Selecciona archivos ISO",
            filetypes=[("Archivos ISO", "*.iso")]
        )
        if not archivos:
            return

        self._procesar_e_inyectar_isos(archivos, letra)

    def _procesar_e_inyectar_isos(self, lista_isos, letra_hollow):
        destino = os.path.join(letra_hollow.rstrip("\\/"), "HOLLOWDRIVE", "OSimages")
        os.makedirs(destino, exist_ok=True)

        id_t = "copia_isos"
        self.progress_panel.pack(fill="x", padx=15, pady=(4, 6), before=self.btn_back_hub)
        self.progress_panel.crear_tarea_dinamica(id_t, "Copiando ISOs...", color=AZUL_CIAN)

        def run():
            total = len(lista_isos)
            try:
                for idx, iso in enumerate(lista_isos, 1):
                    if self.abortar_proceso:
                        raise InterruptedError()
                    nombre = os.path.basename(iso)
                    dest_path = os.path.join(destino, nombre)

                    def cb_prog(b_read, t_size):
                        pct = b_read / t_size if t_size else 0.0
                        pct_g = (idx - 1 + pct) / total
                        self.progress_panel.actualizar_tarea_dinamica(id_t, pct_g, f"ISO ({idx}/{total}): {nombre} [{pct*100:.1f}%]")

                    copiar_iso_ultrarrapido(iso, dest_path, callback_progreso=cb_prog, abort_check=lambda: self.abortar_proceso)

                self.after(0, lambda: messagebox.showinfo("ÉXITO", f"¡{total} archivo(s) ISO copiados en:\n{destino}!"))
            except InterruptedError:
                self.after(0, lambda: messagebox.showinfo("CANCELADO", "Operación abortada."))
            except Exception as e:
                self.after(0, lambda err=str(e): messagebox.showerror("ERROR", err))
            finally:
                self.progress_panel.eliminar_tarea_dinamica(id_t)
                self.progress_panel.pack_forget()

        threading.Thread(target=run, daemon=True).start()

    def _inyectar_paquetes(self):
        bato = self.var_tool_bato.get()
        pack = self.var_tool_pack.get()
        if not (bato or pack):
            messagebox.showwarning("Selección Vacía", "Por favor marca al menos un paquete para inyectar.")
            return

        letra = encontrar_letra_por_etiqueta_ps("HOLLOWDRIVE") or encontrar_letra_por_etiqueta_ps("Ventoy")
        if not letra:
            messagebox.showerror("Error", "No se encontró montada la partición HOLLOWDRIVE.")
            return

        id_t = "inyectar_packs"
        self.progress_panel.pack(fill="x", padx=15, pady=(4, 6), before=self.btn_back_hub)
        self.progress_panel.crear_tarea_dinamica(id_t, "Inyectando paquetes...", color=AZUL_CIAN)

        def run():
            try:
                if bato and not self.abortar_proceso:
                    ruta_bato = os.path.join(letra, "HOLLOWDRIVE", "BATOCERUMEN")
                    os.makedirs(ruta_bato, exist_ok=True)
                    dest = os.path.join(ruta_bato, "batocera.img")
                    url = self.mirrors_data.get("batocera_base", {}).get("mirrors", [{}])[0].get("url", "https://pub-988eebcee5e94631a55af8a89d12129d.r2.dev/batocerumen.img")

                    def cb_b(b, t, m):
                        p = b / t if t else 0.5
                        self.progress_panel.actualizar_tarea_dinamica(id_t, p, f"Batocera OS: {m}")

                    stream_download_file_direct(url, dest, progress_callback=cb_b, abort_check=lambda: self.abortar_proceso)

                if pack and not self.abortar_proceso:
                    url = self.mirrors_data.get("hollowdrive_pack", {}).get("mirrors", [{}])[0].get("url", "https://pub-b872cd561e404a9599c943c6705afe9e.r2.dev/HollowdrivePackV1.tar")

                    def cb_p(b, t, m):
                        p = b / t if t else 0.5
                        self.progress_panel.actualizar_tarea_dinamica(id_t, p, f"Pack Hollow: {m}")

                    stream_extract_tar(url, letra, progress_callback=cb_p, abort_check=lambda: self.abortar_proceso)

                self.after(0, lambda: messagebox.showinfo("ÉXITO", "¡Paquetes inyectados con éxito!"))
            except Exception as e:
                self.after(0, lambda err=str(e): messagebox.showerror("ERROR", err))
            finally:
                self.progress_panel.eliminar_tarea_dinamica(id_t)
                self.progress_panel.pack_forget()

        threading.Thread(target=run, daemon=True).start()

    def _ejecutar_accion_cachy(self):
        disco = next((d for d in self.lista_discos_hollow if d.get("display") == self.combo_ht_disk.get()), None)
        if not disco:
            return

        modo = self.seg_modo_cachy.get()
        letra_grub, letra_cachy = obtener_o_asignar_letras_cachyos_grub(disco["device"])

        if "Actualizar" in modo:
            if not (letra_grub and letra_cachy):
                messagebox.showerror("Error", "No se detectaron las letras de GRUB y CachyOS.")
                return
            if messagebox.askyesno("CONFIRMAR", f"¿Actualizar CachyOS en:\n• GRUB ({letra_grub})\n• CachyOS ({letra_cachy})?"):
                self._flashear_cachy_async(letra_grub, letra_cachy)
        else:
            tam_gb = self.slider_cachy.get()
            if messagebox.askyesno("CONFIRMAR", f"¿Crear partición CachyOS de {tam_gb:.1f} GB?"):
                self._instalar_cachy_async(disco["device"], tam_gb)

    def _flashear_cachy_async(self, letra_grub, letra_cachy):
        id_t = "cachy_flash"
        self.progress_panel.pack(fill="x", padx=15, pady=(4, 6), before=self.btn_back_hub)
        self.progress_panel.crear_tarea_dinamica(id_t, "Flasheando CachyOS...", color=COLOR_CACHY)

        def run():
            try:
                url_g = self.mirrors_data.get("cachyos_images", {}).get("efi_grub_hyprland", {}).get("mirrors", [{}])[0].get("url")
                url_c = self.mirrors_data.get("cachyos_images", {}).get("hyprland", {}).get("mirrors", [{}])[0].get("url")

                def cb_g(b, t, m):
                    p = b / t if t else 0.5
                    self.progress_panel.actualizar_tarea_dinamica(id_t, p * 0.3, f"GRUB: {m}")

                stream_flash_image_direct(url_g, letra_grub, progress_callback=cb_g, abort_check=lambda: self.abortar_proceso)

                def cb_c(b, t, m):
                    p = b / t if t else 0.5
                    self.progress_panel.actualizar_tarea_dinamica(id_t, 0.3 + (p * 0.7), f"CachyOS: {m}")

                stream_flash_image_direct(url_c, letra_cachy, progress_callback=cb_c, abort_check=lambda: self.abortar_proceso)
                self.after(0, lambda: messagebox.showinfo("ÉXITO", "¡CachyOS actualizado correctamente!"))
            except Exception as e:
                self.after(0, lambda err=str(e): messagebox.showerror("ERROR", err))
            finally:
                self.progress_panel.eliminar_tarea_dinamica(id_t)
                self.progress_panel.pack_forget()

        threading.Thread(target=run, daemon=True).start()

    def _instalar_cachy_async(self, disk_idx, tam_gb):
        id_t = "cachy_install"
        self.progress_panel.pack(fill="x", padx=15, pady=(4, 6), before=self.btn_back_hub)
        self.progress_panel.crear_tarea_dinamica(id_t, "Preparando particiones CachyOS...", color=COLOR_CACHY)

        def run():
            try:
                eliminar_particiones_cachy_diskpart(disk_idx)
                crear_particion_adicional(disk_index=disk_idx, size_gb=GB_GRUB, label="GRUB", fs="fat32")
                tam_c = max(1.0, tam_gb - GB_GRUB - 0.15)
                crear_particion_adicional(disk_index=disk_idx, size_gb=tam_c, label="CachyOS", fs="ntfs")
                lg, lc = obtener_o_asignar_letras_cachyos_grub(disk_idx)
                if not (lg and lc):
                    raise RuntimeError("No se pudieron asignar letras a GRUB y CachyOS.")
                self._flashear_cachy_async(lg, lc)
            except Exception as e:
                self.after(0, lambda err=str(e): messagebox.showerror("ERROR", err))
                self.progress_panel.eliminar_tarea_dinamica(id_t)
                self.progress_panel.pack_forget()

        threading.Thread(target=run, daemon=True).start()

    def _cancelar_proceso(self):
        self.abortar_proceso = True
