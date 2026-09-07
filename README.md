# SAVIN-HOLLOWDRIVE

> **Suite automatizada de ingeniería de almacenamiento para el despliegue y mantenimiento de unidades de arranque múltiple (Multi-Boot) de alto rendimiento.**

---

## 1. Descripción General

**SAVIN-HOLLOWDRIVE** es una aplicación de escritorio desarrollada para sistemas operativos Windows orientada a la creación, configuración y gestión integral de dispositivos de almacenamiento extraíbles multifuncionales.

El sistema automatiza el particionado, formateo, descarga e inyección modular de tres entornos de ejecución independientes en un único soporte físico:
1. **Núcleo Multi-Boot (Ventoy):** Permite el arranque directo de múltiples imágenes `.iso`, `.img`, `.vhd` y entornos de rescate sin necesidad de descompresión ni flasheo individual.
2. **Sistema de Emulación (Batocera.linux):** Entorno preconfigurado para retrogaming que se ejecuta de forma autónoma desde el dispositivo.
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