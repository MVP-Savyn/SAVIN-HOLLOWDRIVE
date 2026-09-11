# SAVIN-HOLLOWDRIVE

> Suite automatizada de ingeniería de almacenamiento para el despliegue y mantenimiento de unidades de arranque múltiple (Multi-Boot) de alto rendimiento.

---

## 1. Descripción General

**SAVIN-HOLLOWDRIVE** es una aplicación de escritorio desarrollada para sistemas operativos Windows orientada a la creación, configuración y gestión integral de dispositivos de almacenamiento extraíbles multifuncionales.

El sistema automatiza el particionado, formateo, descarga e inyección modular de tres entornos de ejecución independientes en un único soporte físico:
1. **Núcleo Multi-Boot (Ventoy):** Permite el arranque directo de múltiples imágenes `.iso`, `.img`, `.vhd` y entornos de rescate sin necesidad de descompresión ni flasheo individual.
2. **Sistema de Emulación (Batocera.linux):** Entorno preconfigurado para retrogaming integrado de forma portable y modular.
3. **Distribución Linux Portátil (CachyOS):** Instalación optimizada basada en Arch Linux con soporte para particiones dedicadas (EFI/GRUB y raíz Ext4), diseñada para ofrecer una estación de trabajo portátil de alto rendimiento.

El software opera de forma no intrusiva respecto al equipo anfitrión: las unidades generadas se ejecutan de manera aislada en memoria o en las particiones del disco externo, garantizando la preservación íntegra del sistema operativo y los datos del ordenador en el que se conectan.

---

## 2. Arquitectura del Sistema

```text
SAVIN-HOLLOWDRIVE/
├── Savin_GUI.py              # Interfaz gráfica principal (CustomTkinter) y orquestador
├── config.json               # Configuración local y persistencia de preferencias
├── requirements.txt          # Dependencias de Python
├── engine/                   # Motor lógico subyacente
│   ├── disk_logic.py         # Control de particionado (PowerShell, Diskpart, Win32 I/O)
│   ├── download_manager.py   # Gestión de mirrors, resolución de tamaños y red
│   ├── i18n.py               # Motor de internacionalización (10 idiomas)
│   ├── mirrors.json          # Enlaces de distribución y metadatos de paquetes
│   ├── watchdog.py           # Proceso supervisor independiente post-mortem
│   ├── locales/              # Catálogos de traducción en formato JSON
│   └── resources/            # Binarios auxiliares empaquetados (7-Zip, Ventoy core)
├── media/                    # Recursos multimedia locales (iconos, banners, assets)
└── web/                      # Landing page y recursos de distribución web
    └── index.html            # Portal informativo y descarga de versiones
```

---

## 3. Características Técnicas

* **Volcado por Streaming a RAM (Zero Temp Files):**  
  Implementa una arquitectura productor-consumidor multihilo que canaliza paquetes comprimidos directamente a memoria RAM y los escribe en los sectores físicos de la unidad mediante llamadas nativas de bajo nivel de la API de Windows (`kernel32.CreateFileW` con flag `FILE_FLAG_NO_BUFFERING` y `WriteFile`). Esto evita el desgaste innecesario de ciclos de escritura en unidades SSD locales.

* **Extracción de Archivos al Vuelo:**  
  Canalización directa de flujos de datos HTTP entrantes hacia el descriptor estándar de entrada (`STDIN`) de `7z.exe` (`-si -ttar`), descomprimiendo colecciones de archivos masivos en tiempo real.

* **Seguridad y Prevención de Pérdida de Datos:**  
  * Detección y bloqueo automático de la unidad de sistema (`SystemDrive`, típicamente `C:`).
  * Exclusión por defecto de discos no extraíbles. La habilitación deliberada de discos internos requiere confirmación explícita mediante diálogo de seguridad tipográfico (`"BORRAR"`).

* **HollowTools (Mantenimiento No Destructivo):**  
  Módulo de gestión posterior que permite arrastrar y soltar (*Drag & Drop*) nuevas imágenes ISO, inyectar paquetes de emulación adicionales o redimensionar y reinstalar particiones de CachyOS sin necesidad de reformatear el disco completo.

* **Supervisión de Procesos (Watchdog):**  
  Módulo independiente (`watchdog.py`) ejecutado como proceso desacoplado que monitoriza el PID principal. En caso de terminación anormal o violación de acceso, analiza el registro de depuración y genera reportes técnicos de telemetría.

* **Soporte Multilingüe (i18n):**  
  Soporte dinámico con cambio en caliente para 10 idiomas (Alemán, Chino simplificado, Coreano, Español, Francés, Inglés, Italiano, Japonés, Portugués y Ruso) con resolución de fallbacks en cascada.

---

## 4. Estructura de Particionado del Disco Destino

Cuando la instalación completa está seleccionada, el dispositivo de almacenamiento adopta el siguiente esquema de particiones físicas:

| N.º | Etiqueta | Sistema de Archivos | Tamaño Estimado | Propósito |
| :-- | :--- | :--- | :--- | :--- |
| **1** | `HOLLOWDRIVE` | exFAT | Variable (según asignación) | Almacenamiento principal de Ventoy, ISOs, herramientas y Batocera |
| **2** | `VTOYEFI` | FAT16 | 32 MB | Partición de arranque EFI oculta creada por Ventoy |
| **3** | `GRUB` | FAT32 | 512 MB | Gestor de arranque dedicado para el entorno CachyOS |
| **4** | `CachyOS` | Ext4 | Variable ($\ge$ 20 GB) | Sistema operativo CachyOS (raíz del sistema y espacio de usuario) |
| **-** | *Sin asignar* | *Ninguno* | Restante (opcional) | Espacio preservado si se activa la opción correspondiente |

### ¿Y dónde está Batocera?

A diferencia de las instalaciones tradicionales que exigen particionar discos enteros o crear particiones Ext4 rígidas e invisibles para Windows que fragmentan y consumen el espacio de la unidad, **SAVIN-HOLLOWDRIVE implementa una solución optimizada**:

* **Imagen adaptada sin partición dedicada:** Se utiliza una versión modificada y comprimida de Batocera diseñada específicamente para arrancar directamente dentro del entorno Ventoy, evitando crear particiones adicionales que bloqueen espacio útil del dispositivo.
* **Gestión nativa en `exFAT`:** Todos los datos de usuario de Batocera residen en la carpeta `batocera/` ubicada en la raíz de la partición principal `HOLLOWDRIVE`. Desde cualquier ordenador con Windows, Linux o macOS se pueden copiar, mover o borrar ROMs, BIOS y decoraciones simplemente usando el explorador de archivos habitual.
* **Persistencia total:** Las partidas guardadas, los estados (*savestates*), las configuraciones de emuladores y las descargas de carátulas se conservan entre sesiones en dicha carpeta, tienes control total sobre el sistema, pudiendo agregar o borrar roms, emuladores, bios, etc.
* **Mismo rendimiento, cero desperdicio de espacio:** El sistema funciona con exactamente las mismas capacidades y rendimiento que una instalación convencional en disco físico, pero sin monopolizar almacenamiento en particiones cerradas.

Todo funciona como si batocera estuviera instalado en el pincho, pero... ¡No lo está!

---

## 5. Requisitos del Sistema y Recomendaciones de Hardware

### Requisitos Mínimos
* **Sistema Operativo:** Microsoft Windows 10 o Windows 11 (arquitectura de 64 bits).
* **Capacidad de Almacenamiento:** Unidad de almacenamiento extraíble (USB o disco externo) con capacidad mínima de **3 GB**. (Necesitas más si quieres instalar todo lo que HollowDrive ofrece, para una instalación completa necesitas al menos unos 70GB, pero puedo trabajar en packs un poquito más pequeños para que los usb de 64GB puedan tener todo)
* **Privilegios de Ejecución:** Permisos de Administrador en Windows (imprescindibles para el bloqueo de volúmenes, asignación de letras con `diskpart` y escritura de bajo nivel en sectores físicos).
* **Conectividad:** Conexión a Internet activa para la descarga de mirrors y paquetes seleccionados.

### Recomendación Técnica de Hardware
Se desaconseja el uso de memorias flash USB convencionales (pendrives USB de bajo coste) para instalaciones completas que incluyan sistemas operativos persistentes (CachyOS). Las memorias flash estándar carecen de controladores avanzados de nivelación de desgaste (*wear leveling*) y mecanismos eficientes de disipación térmica, degradándose rápidamente ante escrituras intensivas continuas.

**Configuración recomendada:**
* Utilizar una unidad de estado sólido (SSD) o disco duro mecánico (HDD) de formato 2.5 pulgadas conectada mediante una controladora/carcasa externa USB 3.0 o superior (las unidades de 64 GB o 128 GB de bajo coste resultan idóneas).
* Este tipo de dispositivos dispone de memorias con mayor tolerancia a ciclos P/E (*Program/Erase*) y controladores preparados para soportar cargas de lectura/escritura concurrentes sin estrangulamiento térmico (*thermal throttling*).

---

## 6. Dependencias y Compilación

### Instalación en Entorno de Desarrollo
Para ejecutar el software desde el código fuente se requiere **Python 3.10** o superior:

```bash
# Clonar el repositorio
git clone https://github.com/MVP-Savyn/SAVIN-HOLLOWDRIVE.git
cd SAVIN-HOLLOWDRIVE

# Crear y activar entorno virtual
python -m venv .venv
.venv\Scripts\activate

# Instalar dependencias requeridas
pip install -r requirements.txt

# Ejecutar con privilegios de administrador
python Savin_GUI.py
```

### Compilación a Ejecutable Binario
El proyecto está optimizado para su empaquetado como binario único (`--onefile`) mediante **Nuitka**:

```cmd
python -m nuitka --standalone --onefile ^
  --windows-uac-admin ^
  --enable-plugin=tk-inter ^
  --windows-icon-from-ico=icon.ico ^
  --include-data-dir=engine=engine ^
  --include-data-dir=media=media ^
  --output-dir=Savin_GUI.dist ^
  Savin_GUI.py
```

---

## 7. Licencias y Créditos de Componentes de Terceros

SAVIN-HOLLOWDRIVE integra, enlaza o interactúa con proyectos de código abierto bajo el principio legal de **mera agregación** (*mere aggregation*). Cada componente conserva su respectiva licencia independiente y los derechos pertenecen a sus autores originales:

| Componente | Rol / Función | Licencia | Repositorio / Web Oficial |
| :--- | :--- | :--- | :--- |
| **Ventoy Core** | Motor base de arranque múltiple | [GNU General Public License v3.0 (GPL)](https://www.gnu.org/licenses/gpl-3.0.html) | [github.com/ventoy/Ventoy](https://github.com/ventoy/Ventoy) |
| **7-Zip (7z.exe)** | Motor de descompresión por consola | [GNU Lesser General Public License (LGPL)](https://www.7-zip.org/license.txt) | [7-zip.org](https://www.7-zip.org/) |
| **CachyOS** | Distribución Linux portátil optimizada | [GNU General Public License v3.0 (GPL)](https://www.gnu.org/licenses/gpl-3.0.html) | [cachyos.org](https://cachyos.org/) |
| **Batocera.linux** | Sistema operativo de emulación retro | [GNU General Public License v2.0 (GPL)](https://github.com/batocera-linux/batocera.linux/blob/master/LICENSE) | [batocera.org](https://batocera.org/) |
| **CustomTkinter** | Biblioteca de interfaz gráfica moderna | [MIT License](https://github.com/TomSchimansky/CustomTkinter/blob/master/LICENSE) | [github.com/TomSchimansky/CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) |
| **Pillow (PIL)** | Procesamiento y escalado de imágenes | [HPND License / Historical Permission](https://github.com/python-pillow/Pillow/blob/main/LICENSE) | [python-pillow.org](https://python-pillow.org/) |
| **Requests** | Cliente HTTP para descargas y API | [Apache License 2.0](https://github.com/psf/requests/blob/main/LICENSE) | [requests.readthedocs.io](https://requests.readthedocs.io/) |
| **urllib3** | Cliente HTTP y gestión de conexiones | [MIT License](https://github.com/urllib3/urllib3/blob/main/LICENSE.txt) | [urllib3.readthedocs.io](https://urllib3.readthedocs.io/) |
| **windnd** | Módulo nativo Win32 Drag and Drop | [MIT License](https://github.com/AuspexLabs/windnd) | [github.com/AuspexLabs/windnd](https://github.com/AuspexLabs/windnd) |

### Reconocimiento de Inspiración Técnica
El diseño de la partición de utilidades y la estructura de herramientas de diagnóstico de este software reconoce como referente conceptual al proyecto comunitario **MediCat USB**.