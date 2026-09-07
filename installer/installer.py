import os
import sys
import shutil
import zipfile
import threading
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk

# --- PALETA DE COLORES HOLLOWDRIVE ---
AZUL_FONDO = "#05080a"
AZUL_CARD = "#0d1117"
AZUL_CARD_INNER = "#090d12"
AZUL_CIAN = "#00d4ff"
AZUL_CELESTE = "#38bdf8"
AZUL_ELECTRICO = "#005eff"
AZUL_SUAVE = "#70a1ff"
COLOR_BORDE = "#1e293b"
VERDE_EXITO = "#2ecc71"

def resource_path(relative_path):
    """ Resuelve la ruta absoluta buscando en variables de Nuitka, PyInstaller o local """
    if "NUITKA_ONEFILE_DIRECTORY" in os.environ:
        base_path = os.environ["NUITKA_ONEFILE_DIRECTORY"]
    elif hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

if hasattr(sys, 'frozen') or '__compiled__' in globals():
    EXE_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
else:
    EXE_DIR = os.path.dirname(os.path.abspath(__file__))

def localizar_payload():
    """ Rastrea el archivo payload.zip en todas las ubicaciones posibles """
    rutas_candidatas = [
        resource_path("payload.zip"),
        os.path.join(EXE_DIR, "payload.zip"),
        os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "payload.zip"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "payload.zip"),
        "payload.zip"
    ]
    if "NUITKA_ONEFILE_DIRECTORY" in os.environ:
        rutas_candidatas.insert(0, os.path.join(os.environ["NUITKA_ONEFILE_DIRECTORY"], "payload.zip"))

    for ruta in rutas_candidatas:
        if os.path.exists(ruta):
            return os.path.abspath(ruta)
    return None

def crear_acceso_directo(ruta_exe, ruta_acceso, ruta_icono=None):
    """ Crea un acceso directo nativo de Windows mediante PowerShell sin dependencias externas """
    try:
        os.makedirs(os.path.dirname(ruta_acceso), exist_ok=True)
        ps_cmd = (
            f"$ws = New-Object -ComObject WScript.Shell; "
            f"$s = $ws.CreateShortcut('{ruta_acceso}'); "
            f"$s.TargetPath = '{ruta_exe}'; "
            f"$s.WorkingDirectory = '{os.path.dirname(ruta_exe)}'; "
        )
        if ruta_icono and os.path.exists(ruta_icono):
            ps_cmd += f"$s.IconLocation = '{ruta_icono}'; "
        ps_cmd += "$s.Save()"

        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], startupinfo=si, creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception as e:
        print(f"Aviso: Error creando acceso directo: {e}")

class HollowDriveInstaller(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Savin HollowDrive // Instalador")
        self.geometry("640x520")
        self.resizable(False, False)
        self.configure(fg_color=AZUL_FONDO)

        # Variables de estado
        self.ruta_instalacion = ctk.StringVar(value=os.path.join(EXE_DIR, "Savin-HollowDrive"))
        self.crear_acceso_escritorio = ctk.BooleanVar(value=True)
        self.crear_acceso_inicio = ctk.BooleanVar(value=True)
        self.instalando = False

        self.setup_ui()

    def setup_ui(self):
        # 1. CABECERA
        f_header = ctk.CTkFrame(self, fg_color="transparent")
        f_header.pack(fill="x", padx=25, pady=(20, 5))

        ctk.CTkLabel(f_header, text="⚡ SAVIN HOLLOWDRIVE", font=("Impact", 32), text_color=AZUL_CIAN).pack(anchor="w")
        ctk.CTkLabel(f_header, text="Asistente de instalación del creador multiherramientas", font=("Segoe UI", 13), text_color=AZUL_SUAVE).pack(anchor="w", pady=(2, 0))

        # 2. TARJETA DE RUTA DE DESTINO
        f_card = ctk.CTkFrame(self, fg_color=AZUL_CARD, corner_radius=12, border_width=1, border_color=COLOR_BORDE)
        f_card.pack(fill="x", padx=25, pady=12)

        ctk.CTkLabel(f_card, text="📁 Carpeta de destino:", font=("Segoe UI", 12, "bold"), text_color="#ffffff").pack(anchor="w", padx=15, pady=(12, 4))

        f_path_box = ctk.CTkFrame(f_card, fg_color=AZUL_CARD_INNER, corner_radius=8)
        f_path_box.pack(fill="x", padx=15, pady=(0, 10))

        self.lbl_path = ctk.CTkLabel(
            f_path_box, 
            textvariable=self.ruta_instalacion, 
            font=("Consolas", 11, "bold"), 
            text_color=AZUL_CELESTE, 
            anchor="w"
        )
        self.lbl_path.pack(side="left", fill="x", expand=True, padx=10, pady=8)

        self.btn_browse = ctk.CTkButton(
            f_card, 
            text="📂 Elegir ruta personalizada...", 
            font=("Segoe UI", 11, "bold"), 
            fg_color="#1e293b", 
            hover_color="#334155",
            border_width=1,
            border_color=AZUL_CIAN,
            text_color=AZUL_CIAN,
            height=32, 
            command=self.seleccionar_ruta
        )
        self.btn_browse.pack(anchor="e", padx=15, pady=(0, 12))

        # 3. ACCESOS DIRECTOS
        f_options = ctk.CTkFrame(self, fg_color="transparent")
        f_options.pack(fill="x", padx=25, pady=(0, 10))

        self.ch_desktop = ctk.CTkCheckBox(
            f_options, 
            text="Crear acceso directo en el Escritorio", 
            font=("Segoe UI", 12),
            variable=self.crear_acceso_escritorio,
            fg_color=AZUL_ELECTRICO,
            hover_color="#0046c7"
        )
        self.ch_desktop.pack(anchor="w", padx=5, pady=(0, 8))

        self.ch_start_menu = ctk.CTkCheckBox(
            f_options, 
            text="Añadir al Menú de Inicio de Windows", 
            font=("Segoe UI", 12),
            variable=self.crear_acceso_inicio,
            fg_color=AZUL_ELECTRICO,
            hover_color="#0046c7"
        )
        self.ch_start_menu.pack(anchor="w", padx=5, pady=(0, 5))

        # 4. ÁREA DE PROGRESO
        self.f_progreso = ctk.CTkFrame(self, fg_color="transparent")
        
        self.lbl_status = ctk.CTkLabel(self.f_progreso, text="Listo para comenzar.", font=("Consolas", 11, "bold"), text_color=AZUL_SUAVE)
        self.lbl_status.pack(anchor="w", pady=(0, 4))

        self.p_bar = ctk.CTkProgressBar(self.f_progreso, height=10, progress_color=AZUL_CIAN)
        self.p_bar.set(0)
        self.p_bar.pack(fill="x")

        # 5. BOTÓN INSTALAR
        self.btn_install = ctk.CTkButton(
            self, 
            text="🚀 INSTALAR", 
            font=("Segoe UI", 14, "bold"), 
            fg_color=AZUL_ELECTRICO, 
            hover_color="#0046c7", 
            height=46, 
            corner_radius=10,
            command=self.iniciar_instalacion
        )
        self.btn_install.pack(fill="x", padx=25, side="bottom", pady=20)

    def seleccionar_ruta(self):
        if self.instalando: return
        carpeta = filedialog.askdirectory(title="Selecciona la carpeta de instalación")
        if carpeta:
            self.ruta_instalacion.set(os.path.join(carpeta, "Savin-HollowDrive"))

    def restaurar_ui_error(self):
        """ Vuelve a activar los controles si ocurre un error sin cerrar la aplicación """
        self.instalando = False
        self.btn_browse.configure(state="normal")
        self.btn_install.configure(state="normal")
        self.ch_desktop.configure(state="normal")
        self.ch_start_menu.configure(state="normal")

    def iniciar_instalacion(self):
        if self.instalando: return
        self.instalando = True
        self.btn_browse.configure(state="disabled")
        self.btn_install.configure(state="disabled")
        self.ch_desktop.configure(state="disabled")
        self.ch_start_menu.configure(state="disabled")

        self.f_progreso.pack(fill="x", padx=25, pady=5, before=self.btn_install)
        threading.Thread(target=self._hilo_instalacion, daemon=True).start()

    def _hilo_instalacion(self):
        destino = self.ruta_instalacion.get()
        payload_zip = localizar_payload()

        try:
            if not payload_zip or not os.path.exists(payload_zip):
                raise FileNotFoundError(
                    f"No se pudo encontrar 'payload.zip'.\n\n"
                    f"Asegúrate de que 'payload.zip' esté en la misma carpeta que el instalador "
                    f"o empaquetado dentro del ejecutable."
                )

            self.after(0, lambda: self.lbl_status.configure(text="Extrayendo sistema HollowDrive...", text_color=AZUL_SUAVE))
            os.makedirs(destino, exist_ok=True)

            # Descompresión elemento a elemento para dar barra de progreso en vivo
            with zipfile.ZipFile(payload_zip, 'r') as zf:
                miembros = [m for m in zf.infolist() if not m.is_dir()]
                total = len(miembros)
                for i, miembro in enumerate(miembros, 1):
                    zf.extract(miembro, destino)
                    if i % 5 == 0 or i == total:
                        pct = i / total
                        nombre = os.path.basename(miembro.filename) or "archivos"
                        self.after(0, lambda p=pct, n=nombre: (
                            self.p_bar.set(p),
                            self.lbl_status.configure(text=f"Instalando: {n[:35]}")
                        ))

            # Rutas del programa recién instalado
            exe_hollow = os.path.join(destino, "HollowDrive.exe")
            ico_hollow = os.path.join(destino, "icon.ico")
            
            # 1. Acceso Directo Escritorio
            if self.crear_acceso_escritorio.get() and os.path.exists(exe_hollow):
                self.after(0, lambda: self.lbl_status.configure(text="Generando acceso en Escritorio..."))
                escritorio = os.path.join(os.path.expanduser("~"), "Desktop")
                crear_acceso_directo(exe_hollow, os.path.join(escritorio, "Savin HollowDrive.lnk"), ico_hollow)

            # 2. Acceso Directo Menú Inicio
            if self.crear_acceso_inicio.get() and os.path.exists(exe_hollow):
                self.after(0, lambda: self.lbl_status.configure(text="Generando acceso en Menú de Inicio..."))
                appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
                start_menu = os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs")
                crear_acceso_directo(exe_hollow, os.path.join(start_menu, "Savin HollowDrive.lnk"), ico_hollow)

            self.after(0, lambda: self.lbl_status.configure(text="✔ ¡Instalación completada con éxito!", text_color=VERDE_EXITO))
            self.after(0, lambda: self.p_bar.set(1.0))
            self.after(0, lambda: self.finalizar_exito(exe_hollow))

        except Exception as e:
            err_msg = str(e)
            # En caso de error NO cerramos la ventana; mostramos el mensaje para saber exactamente qué ocurrió
            self.after(0, lambda msg=err_msg: self.lbl_status.configure(text="Error en la instalación", text_color="#ff4d4d"))
            self.after(0, lambda msg=err_msg: messagebox.showerror("Error de Instalación", msg))
            self.after(0, self.restaurar_ui_error)

    def finalizar_exito(self, ruta_exe):
        if messagebox.askyesno("¡Instalación Lista!", "¡Savin HollowDrive se ha instalado correctamente!\n\n¿Deseas iniciar la aplicación ahora?"):
            if os.path.exists(ruta_exe):
                subprocess.Popen([ruta_exe], cwd=os.path.dirname(ruta_exe))
        self.destroy()

if __name__ == "__main__":
    app = HollowDriveInstaller()
    app.mainloop()