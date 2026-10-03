# SAVIN-HOLLOWDRIVE // Documentación Técnica
> **Módulo:** Arquitectura & Motor &nbsp;|&nbsp; **Sección:** Telemetría y Tiempo Restante &nbsp;|&nbsp; **Versión:** 2.0 (Beta)

Este documento forma parte de la suite de documentación técnica de **SAVIN-HOLLOWDRIVE**. Detalla la arquitectura, bases matemáticas y mecanismos de resiliencia del motor de estimación temporal predictivo implementado en el backend (`engine/time_estimator.py`) y en la interfaz (`frontend/js/app.js`).

---

## 📑 Índice de la Sección
- [1. El Desafío: ¿Por qué fallan los estimadores convencionales?](#1-el-desafío-por-qué-fallan-los-estimadores-convencionales)
- [2. Diagrama de Arquitectura del Sistema](#2-diagrama-de-arquitectura-del-sistema)
- [3. Las 7 Capas de Protección Activa](#3-las-7-capas-de-protección-activa)
  - [Capa 1: Micro-Sondeo Pre-Vuelo de Ancho de Banda Real](#capa-1-micro-sondeo-pre-vuelo-de-ancho-de-banda-real)
  - [Capa 2: Calibración Física Directa con fsync y Saturación SLC](#capa-2-calibración-física-directa-con-fsync-y-saturación-slc)
  - [Capa 3: Matriz Universal de Ratios Físicos por Tipo de I/O](#capa-3-matriz-universal-de-ratios-físicos-por-tipo-de-io)
  - [Capa 4: Detección Dinámica de Cuellos de Botella por Modo de Descarga](#capa-4-detección-dinámica-de-cuellos-de-botella-por-modo-de-descarga)
  - [Capa 5: Autocalibración de Hardware en Vivo (Paso 1: Ventoy)](#capa-5-autocalibración-de-hardware-en-vivo-paso-1-ventoy)
  - [Capa 6: Fusión Bayesiana en Vivo (Ticker Desacoplado a 1 Hz)](#capa-6-fusión-bayesiana-en-vivo-ticker-desacoplado-a-1-hz)
  - [Capa 7: Propagación Ambiental y Prevención de Congelamiento (Anti-Freeze)](#capa-7-propagación-ambiental-y-prevención-de-congelamiento-anti-freeze)
- [4. Matriz de Resiliencia ante Factores Adversos](#4-matriz-de-resiliencia-ante-factores-adversos)
- [5. Memoria de Aprendizaje Persistente (`usb_history.json`)](#5-memoria-de-aprendizaje-persistente-usb_historyjson)
- [6. Integración en la Interfaz de Usuario y Telemetría](#6-integración-en-la-interfaz-de-usuario-y-telemetría)

---

## 1. El Desafío: ¿Por qué fallan los estimadores convencionales?

La estimación de tiempo en instaladores de sistemas operativos y herramientas de flasheo suele ser uno de los puntos más débiles de la experiencia de usuario. Típicamente, los programas caen en uno de dos errores de diseño:

```
                               ┌────────────────────────────────────────────────────────┐
                               │             MODELO ESTÁTICO (CIEGO)                    │
                               │  "Instalar tomará 35 minutos" (predicción prefijada)   │
                               │  ❌ Falla con redes de 5 MB/s o puertos USB 2.0         │
                               └────────────────────────────────────────────────────────┘
                                                           VS
                               ┌────────────────────────────────────────────────────────┐
                               │           MODELO INSTANTÁNEO (WINDOWS / BROWSER)       │
                               │        Tiempo = Bytes Restantes / Velocidad Actual     │
                               │  ❌ Microcorte de red -> "Faltan 4 días"               │
                               │  ❌ Búfer saturado    -> "Faltan 10 segundos"          │
                               └────────────────────────────────────────────────────────┘
                                                           VS
                               ┌────────────────────────────────────────────────────────┐
                               │        SAVIN-HOLLOWDRIVE: BUCLE CERRADO EN 5 CAPAS     │
                               │  ✔ Micro-sondeo previo de red real al CDN              │
                               │  ✔ Calibración de USB 2.0 vs 3.0 en Paso 1             │
                               │  ✔ Ticker a 1 Hz desacoplado de la red                 │
                               │  ✔ Fusión Bayesiana progresiva                         │
                               │  ✔ Propagación amortiguada a fases futuras             │
                               └────────────────────────────────────────────────────────┘
```

---

## 2. Diagrama de Arquitectura del Sistema

El flujo de control y calibración se organiza en cuatro fases principales interconectadas en bucle cerrado:

![Diagrama de Arquitectura del Contador](diagrama_contador.svg)

---

## 3. Las 7 Capas de Protección Activa

### Capa 1: Micro-Sondeo Pre-Vuelo de Ancho de Banda Real
Antes de iniciar cualquier proceso destructivo o de particionado, el backend ejecuta una micro-prueba no intrusiva contra el CDN Cloudflare R2 donde se alojan los paquetes de HollowDrive (`engine/time_estimator.py` -> `probe_network_speed`):
- Petición HTTP en streaming acotada (`Range: bytes=0-2097151`, 1–3 MB).
- Tiempo de ejecución acotado a un máximo de **1.2 segundos**.
- Obtiene la velocidad real de transferencia $V_{\text{red}}$ (en MB/s) entre la máquina del usuario y el servidor exacto de descarga.
- **Resultado:** Si el usuario tiene fibra de 1 Gbps, el plan arranca calibrado para alta velocidad; si tiene conexión lenta de 4 MB/s, el plan maestro inicial ya refleja esa condición sin prometer tiempos irreales.

### Capa 2: Calibración Física Directa con fsync y Saturación SLC
Durante la ventana de preparación inicial previa a las descargas pesadas (`probe_usb_write_speed`), el motor realiza un sondeo físico exhaustivo directamente sobre la unidad destino:
- Escribe un bloque continuo de hasta **48 MB** con sincronización forzada al medio físico mediante `flush()` y `os.fsync(fileno)`.
- Esto supera y satura intencionadamente la pequeña memoria caché volátil (SLC Cache) del controlador USB, capturando la **velocidad sostenida real** ($K_{\text{usb}}$ en MB/s) de las celdas NAND crudas.
- Incluye un temporizador de seguridad de 10 segundos para no penalizar a unidades USB 2.0 lentas.

### Capa 3: Matriz Universal de Ratios Físicos por Tipo de I/O
El rendimiento de una memoria NAND varía drásticamente según la naturaleza de la operación de escritura. En lugar de asumir una velocidad lineal única, el motor aplica una **Matriz Universal de Ratios Físicos** calibrada analíticamente sobre el valor real $K_{\text{usb}}$:
- **Extracción de paquetes TAR multiparte ($V_{\text{tar}} = \max(2.5, K_{\text{usb}} \times 0.91)$):**
  Penalización del 9% debido al sobrecoste de crear miles de archivos pequeños, directorios y actualizar metadatos del sistema de archivos.
- **Volcado secuencial monolítico ($V_{\text{single}} = \max(3.0, K_{\text{usb}} \times 1.00)$):**
  Aprovecha el 100% de la tasa sostenida en la escritura continua de imágenes grandes (como `batocera.img`).
- **Flasheo de particiones reducidas ($V_{\text{flash\_small}} = \max(4.0, K_{\text{usb}} \times 1.45)$):**
  Un 45% más veloz en bloques pequeños (como el bootloader GRUB de ~512 MB) al beneficiarse íntegramente de la ráfaga inicial de la caché SLC.
- **Gran volcado sectorial continuo ($V_{\text{flash\_large}} = \max(2.5, K_{\text{usb}} \times 0.84)$):**
  Penalización térmica del 16% en volcados masivos (>9 GB como CachyOS) para reflejar con exactitud el estrangulamiento térmico (*thermal throttling*) de la memoria flash.

### Capa 4: Detección Dinámica de Cuellos de Botella por Modo de Descarga
El tiempo necesario varía sustancialmente según el método de instalación seleccionado:
- **Modo Streaming en RAM:** La descarga HTTP y la descompresión/escritura en el USB se ejecutan simultáneamente mediante un pipeline en memoria. El rendimiento efectivo está limitado por el recurso más lento:
  $$V_{\text{efectiva}} = \min(V_{\text{red}}, V_{\text{usb}})$$
  *Ejemplo:* Con una conexión de 100 MB/s pero un pendrive cuya memoria NAND escribe a 8.7 MB/s, el sistema predice sobre 8.7 MB/s, evitando falsas expectativas.
- **Modo Clásico (Descarga a Disco):** Operación en dos fases secuenciales (descarga a `%TEMP%` y posterior extracción al pendrive):
  $$T_{\text{total}} = \frac{\text{Tamaño}}{V_{\text{red}}} + \frac{\text{Tamaño}}{V_{\text{usb}}}$$

### Capa 5: Autocalibración de Hardware en Vivo (Paso 1: Ventoy)
El Paso 1 (instalación del núcleo Ventoy) es una operación puramente local: particionado MBR/GPT y formateo de bajo nivel sin intervención de red.
- Si el Paso 1 se completa en **18–21 segundos**, el sistema ratifica que el pendrive y el puerto son **USB 3.x / USB 3.2** con controlador veloz.
- Si el Paso 1 demora **45–55 segundos**, el sistema detecta de forma autónoma que el usuario conectó la unidad a un **puerto USB 2.0 legado** o que la controladora presenta alta latencia.
- El factor de desviación ambiental ($\alpha_{\text{env}}$) se calibra con esta medición empírica **antes** de comenzar la descarga de paquetes pesados.

### Capa 6: Fusión Bayesiana en Vivo (Ticker Desacoplado a 1 Hz)
La interfaz visual no recalcula el tiempo a partir de la velocidad bruta instantánea. Cuenta con un reloj propio (`TimeTickerEngine`) que actualiza la pantalla una vez por segundo (1 Hz) aplicando una **fusión Bayesiana adaptativa**:
1. **Fase de Calentamiento ($Progreso < 8\%$):** Durante los primeros instantes de una tarea (establecimiento de conexiones TCP, negociación TLS, inicialización de hilos), el modelo confía al 100% en la base analítica. Esto elimina cualquier fluctuación o salto caótico en el primer segundo.
2. **Fase de Régimen ($Progreso \ge 8\%$ y $T_{\text{transcurrido}} \ge 5\text{s}$):**
   Se calcula la proyección basada en el ritmo empírico observado:
   $$T_{\text{proyectado}} = \frac{T_{\text{transcurrido}}}{Progreso}$$
   $$T_{\text{restante\_observado}} = T_{\text{proyectado}} - T_{\text{transcurrido}}$$
3. **Ponderación Bayesiana Dinámica ($W$):**
   El peso de la observación empírica ($W$) crece suavemente desde 0.0 hasta un máximo de 0.85:
   $$W = \min\left(0.85, \max\left(0, (Progreso - 0.08) \cdot 1.5\right)\right)$$
   $$T_{\text{restante\_paso}} = (1 - W) \cdot T_{\text{analítico}} + W \cdot T_{\text{restante\_observado}}$$

### Capa 7: Propagación Ambiental y Prevención de Congelamiento (Anti-Freeze)
- **Propagación hacia fases futuras:**
  Si durante el volcado de un paquete el USB sufre calentamiento (*thermal throttling*) y reduce su tasa de escritura un 35%, o el proveedor de internet experimenta congestión temporal, el factor de desviación ambiental se actualiza suavemente:
  $$\alpha_{\text{env}} = 0.85 \cdot \alpha_{\text{anterior}} + 0.15 \cdot \alpha_{\text{paso}}$$
  Este factor se propaga con una amortiguación del 75% a todos los pasos pesados de red y disco que **aún no han comenzado**. Así, el tiempo global restante se adapta sin saltos abruptos.
- **Amortiguación Asintótica (Evita que el reloj se pare a 00:00):**
  Si una tarea excede el tiempo estimado (por ejemplo, si Windows Defender retiene temporalmente archivos para inspección o la controladora tarda en ejecutar `FlushFileBuffers`), el contador **nunca se congela en 00:00 ni muestra valores negativos**. Se aplica un decaimiento asintótico suave:
  $$T_{\text{restante}} = \max\left(4, \frac{T_{\text{estimado}}}{1 + \frac{T_{\text{excedido}}}{15}}\right)$$
  La interfaz añade la etiqueta aclaratoria `(Ajustando)` para mantener al usuario informado en todo momento.

---

## 4. Matriz de Resiliencia ante Factores Adversos

| Factor Imprevisto | Comportamiento en Sistemas Tradicionales | Comportamiento en SAVIN-HOLLOWDRIVE |
| :--- | :--- | :--- |
| **Microcorte de red de 2 segundos** | La velocidad cae a 0 KB/s; el tiempo restante salta a *"Faltan 5 días"*. | El reloj de 1 Hz no se inmuta. Sigue descontando segundo a segundo gracias a la inercia Bayesiana. |
| **USB 3.0 conectado a puerto USB 2.0** | El instalador estima 20 min pero tarda 1h 45m; la barra parece congelada. | El Paso 1 (Ventoy) tarda ~48s; el sistema detecta de inmediato el bus USB 2.0 y calibra los pasos futuros automáticamente. |
| **Estrangulamiento térmico (Thermal Throttling)** | La memoria NAND se calienta tras 3 minutos y baja de 40 a 12 MB/s; el tiempo nunca coincide. | La desviación se propaga en tiempo real con amortiguación ($\alpha_{\text{env}}$), ajustando progresivamente el tiempo total. |
| **Conexión lenta de 5 Mbps** | El programa predice tiempos estándar de alta velocidad que nunca se cumplen. | El micro-sondeo inicial mide ~0.6 MB/s antes de iniciar y genera el plan inicial adaptado a la velocidad real de la línea. |
| **Retención por Windows Defender / Flush** | El reloj llega a 00:00 y se congela, haciendo creer al usuario que el proceso crasheó. | Decaimiento asintótico: muestra `Est: ~15:46 (Ajustando)` y el reloj sigue vivo hasta que el sistema operativo libera el bloqueo. |

---

## 5. Memoria de Aprendizaje Persistente (`usb_history.json`)

Para evitar tener que calibrar desde cero en cada ejecución, el backend almacena un registro histórico local persistente:

```json
{
  "USB SanDisk 3.2Gen1 USB": {
    "tier": "usb3_standard",
    "samples": 3,
    "last_date": "2026-10-02 04:11:03",
    "ventoy_sec": 21.0,
    "settle_sec": 7.0,
    "grub_part_sec": 10.0,
    "cachy_part_sec": 26.0,
    "v_tar_mb_s": 8.73,
    "v_single_file_mb_s": 9.70,
    "v_flash_small_mb_s": 16.17,
    "v_flash_large_mb_s": 11.55
  }
}
```

Cada vez que se completa una instalación exitosa, los tiempos reales de cada fase se integran en la base de datos mediante un suavizado exponencial:
$$V_{\text{nuevo\_promedio}} = (1 - \alpha) \cdot V_{\text{anterior}} + \alpha \cdot V_{\text{medido}}$$
con factor de aprendizaje $\alpha = 0.4$, refinando progresivamente la precisión predictiva para ese dispositivo en particular.

---

## 6. Integración en la Interfaz de Usuario y Telemetría

La interfaz de usuario en `frontend/index.html` presenta las métricas del instalador sincronizadas en tiempo real:

### Vista Detallada (Telemetría de 5 Métricas)

```
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ FASE ACTUAL  │ │  VELOCIDAD   │ │TIEMPO PROCESO│ │TOTAL RESTANTE│ │    ESTADO    │
│   Paso 2/7   │ │  18.2 MB/S   │ │    00:15     │ │    36:36     │ │   [Knight]   │
│ Paso 2 de 7  │ │Transferencia │ │ Est: ~15:46  │ │ Transc: 00:36│ │ Linterna WebP│
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
```

1. **Fase Actual (`#metricStep`):** Identificador numérico y descripción del paso activo (`Paso 1 de 7`).
2. **Velocidad (`#metricSpeed`):** Tasa de transferencia en MB/s sostenidos calculada en ventana móvil.
3. **Tiempo Proceso (`#metricTaskTime`):** Minutos y segundos transcurridos en la tarea actual junto a la proyección analítica (`Est: ~MM:SS` o `Est: ~MM:SS (Ajustando)`).
4. **Total Restante (`#metricEta`):** Contador global regresivo en esmeralda neón (`text-glow-emerald`) desacoplado por el `TimeTickerEngine` a 1 Hz, acompañado del tiempo total transcurrido.
5. **Estado Visual Interactivo (`#metricStatusGif`):** Widget gráfico con el Caballero sosteniendo la linterna (`/media/hollow-linterna.webp`) con resplandor cyan y animación fluida que refleja que el motor está operando en tiempo real.

### Barras de Progreso Desacopladas

- **Progreso del Proceso Actual (`#taskProgressBar`):**
  La etiqueta del proceso (`#lblTaskProgress`) y el porcentaje numérico (`#taskProgressPct`) se muestran alineados en una sola fila compacta con tipografía color verde esmeralda neón idéntica a la barra de llenado, ofreciendo lectura clara y uniforme.
- **Progreso Global de la Instalación (`#totalProgressBar`):**
  Ubicada al pie con degradado continuo esmeralda-cian, reflejando el avance ponderado de todos los pasos del plan maestro.

### Vista Simple y Desglose Certificado Final

- **Vista Simple:** Para usuarios que prefieren minimalismo, muestra únicamente la tarea actual, el porcentaje y un reloj de cuenta atrás luminoso flotante (`#simpleTimerDigits`).
- **Desglose Final:** Al concluir la instalación, las barras dan paso automáticamente a una tarjeta translúcida de vidrio con el desglose exacto de segundos invertidos en cada módulo (Ventoy Core, Pack HollowDrive, Batocera OS, GRUB, CachyOS) y el tiempo total certificado.
