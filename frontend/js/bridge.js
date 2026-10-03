/**
 * =====================================================================
 * 🔌 PUENTE JAVASCRIPT <-> PYTHON (PYWEBVIEW BRIDGE)
 * =====================================================================
 */

(function () {
  const eventListeners = {};

  // Captura global de errores de frontend redirigidos a la consola y a Python
  window.addEventListener('error', (event) => {
    const errorDetails = `${event.message} at ${event.filename || 'app'}:${event.lineno || 0}:${event.colno || 0}`;
    console.error('[FRONTEND ERROR]', errorDetails);
    try {
      if (window.pywebview?.api?.log_frontend) {
        window.pywebview.api.log_frontend('error', errorDetails);
      }
    } catch (_) {}
  });

  window.addEventListener('unhandledrejection', (event) => {
    const reason = event.reason ? (event.reason.stack || event.reason.message || String(event.reason)) : 'Rechazo no especificado';
    console.error('[PROMISE REJECTION]', reason);
    try {
      if (window.pywebview?.api?.log_frontend) {
        window.pywebview.api.log_frontend('error', `[PROMISE] ${reason}`);
      }
    } catch (_) {}
  });

  const Bridge = {
    ready: false,
    hasRealApi: false,
    _readyCallbacks: [],

    onReady(callback) {
      if (this.ready) {
        callback();
      } else {
        this._readyCallbacks.push(callback);
      }
    },

    _markReady(hasRealApi = false) {
      this.ready = true;
      this.hasRealApi = hasRealApi;
      if (hasRealApi) {
        console.log("⚡ [BRIDGE] Pywebview API conectada con éxito.");
        window.dispatchEvent(new CustomEvent('hollowdrive:api-ready'));
      }
      const cbs = [...this._readyCallbacks];
      this._readyCallbacks = [];
      cbs.forEach(cb => {
        try { cb(); } catch (err) { console.error('[BRIDGE] Error en callback de arranque:', err); }
      });
    },

    // Registro de escuchadores de eventos emitidos desde Python
    on(event, handler) {
      if (!eventListeners[event]) {
        eventListeners[event] = [];
      }
      eventListeners[event].push(handler);
    },

    off(event, handler) {
      if (!eventListeners[event]) return;
      eventListeners[event] = eventListeners[event].filter(h => h !== handler);
    },

    handleEvent(event, data) {
      if (eventListeners[event]) {
        eventListeners[event].forEach(handler => {
          try {
            handler(data);
          } catch (err) {
            console.error(`[BRIDGE] Error en listener de '${event}':`, err);
          }
        });
      }
    },

    emit(event, data) {
      this.handleEvent(event, data);
    },

    // Ejecutor seguro con espera activa para evitar condiciones de carrera en el arranque de PyWebView
    async _call(method, ...args) {
      if (!window.pywebview?.api?.[method]) {
        for (let i = 0; i < 80; i++) {
          if (window.pywebview?.api?.[method]) break;
          await new Promise(r => setTimeout(r, 80));
        }
      }
      const fn = window.pywebview?.api?.[method];
      if (typeof fn === 'function') {
        try {
          return await fn(...args);
        } catch (err) {
          console.error(`[BRIDGE] Error ejecutando ${method}:`, err);
          return null;
        }
      }
      console.warn(`[BRIDGE] Método '${method}' no disponible en pywebview.api`);
      return null;
    },

    // Métodos asíncronos que invocan a Python
    async getDisks(includeInternal = false) {
      const res = await this._call('get_disks', includeInternal);
      return res || { success: false, disks: [] };
    },

    async getLanguages() {
      const res = await this._call('get_languages');
      return res || { current: 'ES', available: [] };
    },

    async setLanguage(langCode) {
      return await this._call('set_language', langCode);
    },

    async getTranslations() {
      const res = await this._call('get_translations');
      return res || { lang: 'ES', strings: {} };
    },

    async getToolsCatalog() {
      const res = await this._call('get_tools_catalog');
      return res || [];
    },

    async startInstallation(config) {
      const res = await this._call('start_installation', config);
      return res || { success: false, error: "API no disponible" };
    },

    async cancelInstallation() {
      const res = await this._call('cancel_installation');
      return res || { success: false };
    },

    async pickFileDialog(title, fileTypes) {
      return await this._call('pick_file_dialog', title, fileTypes);
    },

    async loadAddonsCatalog(source) {
      const res = await this._call('load_addons_catalog', source);
      return res || { success: false, error: "API no disponible" };
    },

    async injectAddons(packList, discoInfo) {
      const res = await this._call('inject_addons', packList, discoInfo);
      return res || { success: false, error: "API no disponible" };
    },

    async cancelAddons() {
      const res = await this._call('cancel_addons');
      return res || { success: false };
    },

    async openUrl(url) {
      if (!window.pywebview?.api?.open_external_url) {
        window.open(url, '_blank');
        return { success: true };
      }
      return await this._call('open_external_url', url);
    },

    async openFolder(path) {
      const res = await this._call('open_folder', path);
      return res || { success: false };
    },

    async checkInternet() {
      const res = await this._call('check_internet');
      return res || { connected: true };
    },

    // Métodos dedicados para HollowTools (Mantenimiento)
    async getHollowDisks() {
      const res = await this._call('get_hollow_disks');
      return res || { success: false, disks: [] };
    },

    async getDiskPartitionsInfo(diskIndex) {
      const res = await this._call('get_disk_partitions_info', diskIndex);
      return res || { success: false, partitions: [] };
    },

    async pickIsoFiles() {
      const res = await this._call('pick_iso_files');
      return res || [];
    },

    async copyIsos(diskIndex, filePaths) {
      const res = await this._call('copy_isos', diskIndex, filePaths);
      return res || { success: false, error: "API no disponible" };
    },

    async injectToolsPackages(diskIndex, installBato, installPack) {
      const res = await this._call('inject_tools_packages', diskIndex, installBato, installPack);
      return res || { success: false, error: "API no disponible" };
    },

    async cachyosToolsAction(diskIndex, actionType, flavor, sizeGb) {
      const res = await this._call('cachyos_tools_action', diskIndex, actionType, flavor, sizeGb);
      return res || { success: false, error: "API no disponible" };
    },

    async cancelToolsAction() {
      const res = await this._call('cancel_tools_action');
      return res || { success: false };
    },

    // Métodos de control de ventana (Frameless UI)
    async windowMinimize() {
      return await this._call('window_minimize');
    },

    async windowToggleMaximize() {
      return await this._call('window_toggle_maximize');
    },

    async windowMaximize() {
      if (window.pywebview?.api?.window_maximize) {
        return await this._call('window_maximize');
      }
      return await this._call('window_toggle_maximize');
    },

    async windowClose() {
      return await this._call('window_close');
    },

    async windowStartDrag() {
      return await this._call('window_start_drag');
    },

    async windowStartResize(edge = 'BOTTOM_RIGHT') {
      return await this._call('window_start_resize', edge);
    },

    async windowMove(x, y) {
      const res = await this._call('window_move', x, y);
      return res || { success: false };
    },

    async windowGetState() {
      const res = await this._call('window_get_state');
      return res || { is_maximized: false, width: 1060, height: 860 };
    },

    async windowUnmaximize(screenX, screenY) {
      const res = await this._call('window_unmaximize', screenX, screenY);
      return res || { success: false };
    },

    async windowResize(width, height, fixPoint = 'NORTH_WEST') {
      const res = await this._call('window_resize', width, height, fixPoint);
      return res || { success: false };
    }
  };

  function checkAndMarkReady() {
    if (window.pywebview?.api) {
      if (!Bridge.hasRealApi) {
        Bridge._markReady(true);
      }
      return true;
    }
    return false;
  }

  // 1. Detección inmediata
  checkAndMarkReady();

  // 2. Escuchar evento oficial pywebviewready
  window.addEventListener('pywebviewready', () => {
    checkAndMarkReady();
  });

  // 3. Polling activo por si pywebview se inyecta con leve retraso
  let pollAttempts = 0;
  const readyPoll = setInterval(() => {
    pollAttempts++;
    if (checkAndMarkReady()) {
      clearInterval(readyPoll);
    } else if (pollAttempts >= 120) { // 120 * 100ms = 12s
      clearInterval(readyPoll);
      if (!Bridge.ready) {
        console.warn("[BRIDGE] Pywebview API no detectada tras 12s. Inicializando en modo independiente.");
        Bridge._markReady(false);
      }
    }
  }, 100);

  window.hollowdrive = Bridge;
})();
