/**
 * =====================================================================
 * 🚀 HOLLOWDRIVE MASTER CONTROLLER (SPA FRONTEND)
 * =====================================================================
 */

function initApp() {
  // Diccionario exhaustivo de traducciones cargado desde translations.js (10 idiomas completos)
  const TRANSLATIONS = window.HOLLOWDRIVE_TRANSLATIONS || {};

  // Fallback seguro a español o inglés para cualquier idioma
  function getLangDict(code) {
    return TRANSLATIONS[code] || TRANSLATIONS['es'] || {};
  }

  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  // Estado reactivo central
  const State = {
    screen: 'hub',
    wizardStep: 1,
    disks: [],
    selectedDisk: null,
    showInternal: false,
    lockConfirmed: false,
    currentStepTitle: '',
    
    // Opciones del Asistente
    installKit: true,
    installBatocera: true,
    batoceraArch: 'x86_64',
    portableOs: 'cachyos', // 'none' | 'cachyos'
    installCachy: true,
    cachyFlavor: 'hyprland',
    downloadMode: 'ram', // 'ram' (Asíncrona) | 'disco' (Clásica)
    preserveSpace: false,
    
    // Particionado Real (Hollowdrive, Sistema, Libre)
    totalDiskGb: 64.0,
    valHollowGb: 24.0,
    valCachyGb: 20.0,
    valLibreGb: 20.0,
    
    // HollowTools State
    toolsDisks: [],
    toolsSelectedDisk: null,
    toolsDiskInfo: null,
    toolsCachyMode: 'actualizar',
    toolsCachyFlavor: 'hyprland',
    toolsCachySize: 20.0,
    toolsIsOperating: false,
    toolsIsoQueue: [],
    toolsActiveTasks: {},
    
    // Idioma
    currentLang: 'es',
    translations: {},
    
    // Progreso
    isInstalling: false,
    installViewMode: (function() {
      try {
        return localStorage.getItem('hollowdrive_install_view_mode') || 'simple';
      } catch (_) {
        return 'simple';
      }
    })()
  };

  // Referencias DOM
  const DOM = {
    screens: document.querySelectorAll('.screen'),
    stepperWrap: document.getElementById('stepperWrap'),
    stepPanes: document.querySelectorAll('.wizard-step-pane'),
    stepItems: document.querySelectorAll('.step-item'),
    
    btnPrev: document.getElementById('btnPrev'),
    btnNext: document.getElementById('btnNext'),
    
    // Header & Info
    headerLogo: document.getElementById('headerLogo'),
    btnHeaderInfo: document.getElementById('btnHeaderInfo'),
    overlayInfo: document.getElementById('overlayInfo'),
    btnEnterApp: document.getElementById('btnEnterApp'),
    btnEnterAppText: document.getElementById('btnEnterAppText'),
    videoTutorialTrigger: document.getElementById('videoTutorialTrigger'),
    
    // Selectores de Idioma (Header e Info Overlay)
    langBtn: document.getElementById('langBtn'),
    langDropdown: document.getElementById('langDropdown'),
    langCurrentText: document.getElementById('langCurrentText'),
    langBtnInfo: document.getElementById('langBtnInfo'),
    langDropdownInfo: document.getElementById('langDropdownInfo'),
    langCurrentTextInfo: document.getElementById('langCurrentTextInfo'),
    
    // Textos Hub
    hubHeroTitle: document.getElementById('hubHeroTitle'),
    hubHeroHighlight: document.getElementById('hubHeroHighlight'),
    hubHeroSub: document.getElementById('hubHeroSub'),
    hubTagHollow: document.getElementById('hubTagHollow'),
    hubBtnHollow: document.getElementById('hubBtnHollow'),
    hubTagTools: document.getElementById('hubTagTools'),
    hubBtnTools: document.getElementById('hubBtnTools'),
    hubTagAddons: document.getElementById('hubTagAddons'),
    hubBtnAddons: document.getElementById('hubBtnAddons'),
    hintDragMoveText: document.getElementById('hintDragMoveText'),
    hintDragResizeText: document.getElementById('hintDragResizeText'),
    
    // Stepper Labels
    stepLabel1: document.getElementById('stepLabel1'),
    stepLabel2: document.getElementById('stepLabel2'),
    stepLabel3: document.getElementById('stepLabel3'),
    stepLabel4: document.getElementById('stepLabel4'),
    stepLabel5: document.getElementById('stepLabel5'),
    stepLabel6: document.getElementById('stepLabel6'),
    
    // Step 5: Modo de Descarga
    cardModeAsync: document.getElementById('cardModeAsync'),
    cardModeClassic: document.getElementById('cardModeClassic'),
    downloadModeTitle: document.getElementById('downloadModeTitle'),
    downloadModeSub: document.getElementById('downloadModeSub'),
    titleDlAsync: document.getElementById('titleDlAsync'),
    descDlAsync: document.getElementById('descDlAsync'),
    titleDlClassic: document.getElementById('titleDlClassic'),
    descDlClassic: document.getElementById('descDlClassic'),
    badgeDlAsync: document.getElementById('badgeDlAsync'),
    radioLblAsync: document.getElementById('radioLblAsync'),
    radioLblClassic: document.getElementById('radioLblClassic'),
    featAsync1: document.getElementById('featAsync1'),
    featAsync2: document.getElementById('featAsync2'),
    featAsync3: document.getElementById('featAsync3'),
    featClassic1: document.getElementById('featClassic1'),
    featClassic2: document.getElementById('featClassic2'),
    featClassic3: document.getElementById('featClassic3'),
    
    // Step 1: USB
    usbStepTitle: document.getElementById('usbStepTitle'),
    usbSelect: document.getElementById('usbSelect'),
    btnRefreshUsb: document.getElementById('btnRefreshUsb'),
    chkShowInternal: document.getElementById('chkShowInternal'),
    lblShowInternal: document.getElementById('lblShowInternal'),
    usbWarningTitle: document.getElementById('usbWarningTitle'),
    usbWarningText: document.getElementById('usbWarningText'),
    usbLockCheckbox: document.getElementById('usbLockCheckbox'),
    usbLockLabel: document.getElementById('usbLockLabel'),
    
    // Step 2: Kit
    paneTitleKit: document.getElementById('paneTitleKit'),
    switchKit: document.getElementById('switchKit'),
    btnKitInfo: document.getElementById('btnKitInfo'),
    videoKit: document.getElementById('videoKit'),
    modalKitTools: document.getElementById('modalKitTools'),
    
    // Step 3: Batocera
    paneTitleBatocera: document.getElementById('paneTitleBatocera'),
    switchBatocera: document.getElementById('switchBatocera'),
    btnBato64: document.getElementById('btnBato64'),
    btnBato32: document.getElementById('btnBato32'),
    btnBatoInfo: document.getElementById('btnBatoInfo'),
    videoBatocera: document.getElementById('videoBatocera'),
    modalBatocera: document.getElementById('modalBatocera'),
    
    // Step 4: Sistema Portable
    paneTitleSystem: document.getElementById('paneTitleSystem'),
    selectPortableOs: document.getElementById('selectPortableOs'),
    optOsCachy: document.getElementById('optOsCachy'),
    optOsNone: document.getElementById('optOsNone'),
    optOsZorin: document.getElementById('optOsZorin'),
    optOsDeepin: document.getElementById('optOsDeepin'),
    optOsUbuntu: document.getElementById('optOsUbuntu'),
    optOsDebian: document.getElementById('optOsDebian'),
    cachyFlavorWrap: document.getElementById('cachyFlavorWrap'),
    btnCachyHypr: document.getElementById('btnCachyHypr'),
    btnCachyKde: document.getElementById('btnCachyKde'),
    btnCachyInfo: document.getElementById('btnCachyInfo'),
    videoCachy: document.getElementById('videoCachy'),
    modalCachy: document.getElementById('modalCachy'),
    
    // Step 5: Particionado Real
    partitionHeading: document.getElementById('partitionHeading'),
    partitionSetupCard: document.getElementById('partitionSetupCard'),
    diskTotalLabel: document.getElementById('diskTotalLabel'),
    partitionBar: document.getElementById('partitionBar'),
    legendHollow: document.getElementById('legendHollow'),
    legendCachyItem: document.getElementById('legendCachyItem'),
    legendCachy: document.getElementById('legendCachy'),
    legendLibreItem: document.getElementById('legendLibreItem'),
    legendLibre: document.getElementById('legendLibre'),
    partitionSlidersGrid: document.getElementById('partitionSlidersGrid'),
    sliderHollowLabel: document.getElementById('sliderHollowLabel'),
    hollowSlider: document.getElementById('hollowSlider'),
        cachySliderGroup: document.getElementById('cachySliderGroup'),
    sliderSystemLabel: document.getElementById('sliderSystemLabel'),
    cachySlider: document.getElementById('cachySlider'),
        switchPreserveSpace: document.getElementById('switchPreserveSpace'),
    lblPreserveSpace: document.getElementById('lblPreserveSpace'),
    btnInstalarRow: document.getElementById('btnInstalarRow'),
    btnStartInstallImg: document.getElementById('btnStartInstallImg'),
    taskProgressBarWrap: document.getElementById('taskProgressBarWrap'),
    totalProgressBarWrap: document.getElementById('totalProgressBarWrap'),
    completionSummaryCard: document.getElementById('completionSummaryCard'),
    completionTimesGrid: document.getElementById('completionTimesGrid'),
    btnNewInstall: document.getElementById('btnNewInstall'),
    lblInstallSuccessTitle: document.getElementById('lblInstallSuccessTitle'),
    lblNewInstallBtn: document.getElementById('lblNewInstallBtn'),

    // Controles de Ventana Frameless (Barra Superior y Botones Neón)
    windowTopBar: document.getElementById('windowTopBar'),
    windowTopBarDragSpacer: document.getElementById('windowTopBarDragSpacer'),
    windowTopEdgeTrigger: document.getElementById('windowTopBar'),
    windowControlsSlider: document.getElementById('windowControlsSlider'),
    winBtnMinimize: document.getElementById('winBtnMinimize'),
    winBtnMaximize: document.getElementById('winBtnMaximize'),
    winBtnClose: document.getElementById('winBtnClose'),
    
    // Modales y Textos
    infoWelcomeText: document.getElementById('infoWelcomeText'),
    infoVideoPrompt: document.getElementById('infoVideoPrompt'),
    infoLicensesPrompt: document.getElementById('infoLicensesPrompt'),
    infoLegalNotice: document.getElementById('infoLegalNotice'),
    infoThanksText: document.getElementById('infoThanksText'),
    modalKitHeader: document.getElementById('modalKitHeader'),
    toolCatAntivirus: document.getElementById('toolCatAntivirus'),
    toolCatBackups: document.getElementById('toolCatBackups'),
    toolCatLiveOs: document.getElementById('toolCatLiveOs'),
    toolCatIsos: document.getElementById('toolCatIsos'),
    toolCatVentoyDesc: document.getElementById('toolCatVentoyDesc'),
    toolCatPartitions: document.getElementById('toolCatPartitions'),
    toolCatRescue: document.getElementById('toolCatRescue'),
    modalBatoceraTitle: document.getElementById('modalBatoceraTitle'),
    modalBatoceraBody: document.getElementById('modalBatoceraBody'),
    modalSystemTitle: document.getElementById('modalSystemTitle'),
    modalSystemBody: document.getElementById('modalSystemBody'),
    modalSystemNote: document.getElementById('modalSystemNote'),

    // Donaciones y Caballero
    knightClickWrapper: document.getElementById('knightClickWrapper'),
        modalDonate: document.getElementById('modalDonate'),
        donateModalText: document.getElementById('donateModalText'),
        donateKofiMain: document.getElementById('donateKofiMain'),
    donateKofiSub: document.getElementById('donateKofiSub'),
    donatePaypalText: document.getElementById('donatePaypalText'),
    
    // Modales de Confirmación y Peligro
    modalInternalDanger: document.getElementById('modalInternalDanger'),
    modalInternalDangerTitle: document.getElementById('modalInternalDangerTitle'),
    modalInternalDangerBody: document.getElementById('modalInternalDangerBody'),
    btnConfirmInternalModal: document.getElementById('btnConfirmInternalModal'),
    btnCancelInternalModal: document.getElementById('btnCancelInternalModal'),
    btnCancelInternalModalX: document.getElementById('btnCancelInternalModalX'),
    
    modalConfirmInstall: document.getElementById('modalConfirmInstall'),
    modalConfirmInstallTitle: document.getElementById('modalConfirmInstallTitle'),
    confirmInstallMsg: document.getElementById('confirmInstallMsg'),
    btnCancelInstallModal: document.getElementById('btnCancelInstallModal'),
    btnCancelInstallModalX: document.getElementById('btnCancelInstallModalX'),
    btnExecuteInstallConfirmed: document.getElementById('btnExecuteInstallConfirmed'),
    
    // Modal Cancelar Instalación
    modalConfirmCancel: document.getElementById('modalConfirmCancel'),
    btnCancelAbortModalX: document.getElementById('btnCancelAbortModalX'),
    btnStayInInstall: document.getElementById('btnStayInInstall'),
    btnExecuteAbortConfirmed: document.getElementById('btnExecuteAbortConfirmed'),
    
    // Lock dialog interno ('BORRAR')
    lockDialogOverlay: document.getElementById('lockDialogOverlay'),
    modalLockTitle: document.getElementById('modalLockTitle'),
    modalLockBody: document.getElementById('modalLockBody'),
    lockInputText: document.getElementById('lockInputText'),
    btnCancelLock: document.getElementById('btnCancelLock'),
    btnConfirmLock: document.getElementById('btnConfirmLock'),
    
    // Modal Aviso Sin Conexión
    modalNoInternet: document.getElementById('modalNoInternet'),
    modalNoInternetTitle: document.getElementById('modalNoInternetTitle'),
    modalNoInternetBody: document.getElementById('modalNoInternetBody'),
    
    // HollowTools
    toolsTitle: document.getElementById('toolsTitle'),
    toolsUsbSelect: document.getElementById('toolsUsbSelect'),
    btnRefreshToolsUsb: document.getElementById('btnRefreshToolsUsb'),
    btnBackFromTools: document.getElementById('btnBackFromTools'),
    
    // HollowTools - Tarjeta 1: ISOs & Cola
    toolsCardIsoTitle: document.getElementById('toolsCardIsoTitle'),
    btnInfoToolsIso: document.getElementById('btnInfoToolsIso'),
    toolsDropZone: document.getElementById('toolsDropZone'),
    toolsDropMsg: document.getElementById('toolsDropMsg'),
    btnPlusIso: document.getElementById('btnPlusIso'),
    fileInputIsos: document.getElementById('fileInputIsos'),
    toolsIsoQueueBlock: document.getElementById('toolsIsoQueueBlock'),
    toolsQueueCount: document.getElementById('toolsQueueCount'),
    btnPlusMoreIso: document.getElementById('btnPlusMoreIso'),
    btnClearIsoQueue: document.getElementById('btnClearIsoQueue'),
    toolsIsoList: document.getElementById('toolsIsoList'),
    btnInjectIsos: document.getElementById('btnInjectIsos'),
    
    // HollowTools - Tarjeta 2: Paquetes
    toolsCardPacksTitle: document.getElementById('toolsCardPacksTitle'),
    btnInfoToolsPacks: document.getElementById('btnInfoToolsPacks'),
    chkToolsBato: document.getElementById('chkToolsBato'),
    chkToolsPack: document.getElementById('chkToolsPack'),
    btnInjectPacks: document.getElementById('btnInjectPacks'),
    
    // HollowTools - Tarjeta 3: Sistema Portable
        toolsCardPortableTitle: document.getElementById('toolsCardPortableTitle'),
    toolsPortableStatusBox: document.getElementById('toolsPortableStatusBox'),
    toolsPortableBadge: document.getElementById('toolsPortableBadge'),
    toolsPortableStatusText: document.getElementById('toolsPortableStatusText'),
    btnOpenPortableOptions: document.getElementById('btnOpenPortableOptions'),
    toolsGearLabel: document.getElementById('toolsGearLabel'),
    btnInfoToolsCachy: document.getElementById('btnInfoToolsCachy'),
    btnApplyCachy: document.getElementById('btnApplyCachy'),
    toolsBtnApplyText: document.getElementById('toolsBtnApplyText'),
    
    // HollowTools - Modal Opciones Portable
    modalPortableOptions: document.getElementById('modalPortableOptions'),
    modalPortableOptionsTitle: document.getElementById('modalPortableOptionsTitle'),
    btnToolsCachyUpdate: document.getElementById('btnToolsCachyUpdate'),
    btnToolsCachyInstall: document.getElementById('btnToolsCachyInstall'),
    toolsFlavorRadios: document.querySelectorAll('input[name="toolsFlavor"]'),
    toolsCachySliderWrap: document.getElementById('toolsCachySliderWrap'),
    toolsCachySpaceText: document.getElementById('toolsCachySpaceText'),
    toolsSliderCachy: document.getElementById('toolsSliderCachy'),
    btnModalClosePortable: document.getElementById('btnModalClosePortable'),
    
    // HollowTools - Comparativa Visual (Mini-Gráfica en Modal)
        toolsBarActualInfo: document.getElementById('toolsBarActualInfo'),
    toolsBarActual: document.getElementById('toolsBarActual'),
    toolsBarFuturoInfo: document.getElementById('toolsBarFuturoInfo'),
    toolsBarFuturo: document.getElementById('toolsBarFuturo'),
    
    // HollowTools - Monitor de Operaciones Multitarea
    toolsMonitorCard: document.getElementById('toolsMonitorCard'),
    toolsTasksCount: document.getElementById('toolsTasksCount'),
    toolsTasksList: document.getElementById('toolsTasksList'),
    btnCancelToolsOp: document.getElementById('btnCancelToolsOp'),
    
    // HollowTools - Modales Info
    modalToolsIso: document.getElementById('modalToolsIso'),
    modalToolsPacks: document.getElementById('modalToolsPacks'),
    modalToolsCachy: document.getElementById('modalToolsCachy'),
    
    // Modal de Confirmación Dinámico (Cyberpunk UI)
    modalConfirmToolsAction: document.getElementById('modalConfirmToolsAction'),
    modalConfirmToolsTitle: document.getElementById('modalConfirmToolsTitle'),
    modalConfirmToolsBody: document.getElementById('modalConfirmToolsBody'),
    btnConfirmToolsOk: document.getElementById('btnConfirmToolsOk'),
    btnConfirmToolsCancel: document.getElementById('btnConfirmToolsCancel'),
    btnConfirmToolsClose: document.getElementById('btnConfirmToolsClose'),
    
    // Monitor de Instalación
    installMonitorCard: document.getElementById('installMonitorCard'),
    btnCancelInstallProcess: document.getElementById('btnCancelInstallProcess'),
    metricTitleStep: document.getElementById('metricTitleStep'),
    metricStep: document.getElementById('metricStep'),
    metricStepSub: document.getElementById('metricStepSub'),
    metricTitleSpeed: document.getElementById('metricTitleSpeed'),
    metricSpeed: document.getElementById('metricSpeed'),
    metricSpeedSub: document.getElementById('metricSpeedSub'),
    metricTitleTaskTime: document.getElementById('metricTitleTaskTime'),
    metricTaskTime: document.getElementById('metricTaskTime'),
    metricTaskTimeEst: document.getElementById('metricTaskTimeEst'),
    metricTitleEta: document.getElementById('metricTitleEta'),
    metricEta: document.getElementById('metricEta'),
    metricTotalElapsed: document.getElementById('metricTotalElapsed'),
    metricTitleStatus: document.getElementById('metricTitleStatus'),
            lblTaskProgress: document.getElementById('lblTaskProgress'),
    taskProgressBar: document.getElementById('taskProgressBar'),
    taskProgressPct: document.getElementById('taskProgressPct'),
    totalProgressBar: document.getElementById('totalProgressBar'),
    totalProgressPct: document.getElementById('totalProgressPct'),
    terminalToggleRow: document.getElementById('terminalToggleRow'),
    btnToggleTerminal: document.getElementById('btnToggleTerminal'),
    terminalToggleIcon: document.getElementById('terminalToggleIcon'),
    terminalToggleText: document.getElementById('terminalToggleText'),
    terminalConsole: document.getElementById('terminalConsole'),
        
    // Selector de Modo de Vista (Simple / Detallado)
    installModeToggle: document.getElementById('installModeToggle'),
    btnModeSimple: document.getElementById('btnModeSimple'),
    btnModeDetailed: document.getElementById('btnModeDetailed'),
    lblModeSimple: document.getElementById('lblModeSimple'),
    lblModeDetailed: document.getElementById('lblModeDetailed'),

    // Vista Simple de Instalación
    installViewSimple: document.getElementById('installViewSimple'),
    simpleMonitorCard: document.getElementById('simpleMonitorCard'),
    simpleRingWrap: document.getElementById('simpleRingWrap'),
    simpleRingFillOuter: document.getElementById('simpleRingFillOuter'),
    simpleRingFillInner: document.getElementById('simpleRingFillInner'),
    simpleRingFill: document.getElementById('simpleRingFillOuter'),
    simpleCenterAvatar: document.getElementById('simpleCenterAvatar'),
    simpleCenterPctWrap: document.getElementById('simpleCenterPctWrap'),
    simpleCenterPct: document.getElementById('simpleCenterPct'),
        simpleBottomTimerCard: document.getElementById('simpleBottomTimerCard'),
    simpleTimerDigits: document.getElementById('simpleTimerDigits'),
    simpleTimerSub: document.getElementById('simpleTimerSub'),
    simpleHollowBottomWrap: document.getElementById('simpleHollowBottomWrap'),
    simpleHollowGif: document.getElementById('simpleHollowGif'),
    simpleSuccessTick: document.getElementById('simpleSuccessTick'),
    simpleStatusInfo: document.getElementById('simpleStatusInfo'),
    simplePhaseTitle: document.getElementById('simplePhaseTitle'),
    simplePhasePct: document.getElementById('simplePhasePct'),
    simplePctText: document.getElementById('simpleCenterPct'),
    simpleCompletionZone: document.getElementById('simpleCompletionZone'),
    simpleProcessTimesList: document.getElementById('simpleProcessTimesList'),
    lblSimpleBreakdownTitle: document.getElementById('lblSimpleBreakdownTitle'),
    lblSimpleTotalTimeTitle: document.getElementById('lblSimpleTotalTimeTitle'),
    simpleTotalTimeValue: document.getElementById('simpleTotalTimeValue'),
    btnSimpleNext: document.getElementById('btnSimpleNext'),
    lblSimpleNext: document.getElementById('lblSimpleNext'),
    simpleGratitudeCard: document.getElementById('simpleGratitudeCard'),
    lblGratitudeTitle: document.getElementById('lblGratitudeTitle'),
    lblGratitudeSub: document.getElementById('lblGratitudeSub'),
    btnGratitudeBackMenu: document.getElementById('btnGratitudeBackMenu'),
    lblGratitudeBackMenu: document.getElementById('lblGratitudeBackMenu'),

    // Vista Detallada de Instalación
    installViewDetailed: document.getElementById('installViewDetailed'),
    statusGifContainer: document.getElementById('statusGifContainer'),
    metricStatusGif: document.getElementById('metricStatusGif')
  };

  // =========================================================================
  // 🌐 IDIOMAS E INTERNACIONALIZACIÓN REACTIVA
  // =========================================================================
  function getT(key, fallback = '') {
    const langDict = getLangDict(State.currentLang);
    if (langDict && key in langDict) return langDict[key];
    const esDict = TRANSLATIONS['es'];
    if (esDict && key in esDict) return esDict[key];
    return fallback;
  }

  function applyTranslations() {
    const L = (key, def) => getT(key, def);

    // 1. Hub
    if (DOM.hubHeroTitle && DOM.hubHeroHighlight) {
      DOM.hubHeroTitle.childNodes[0].textContent = L('hub_hero_title', 'El Kit Más Potente del Mundo') + " ";
      DOM.hubHeroHighlight.textContent = L('hub_hero_highlight', 'en tu Bolsillo');
    }
    if (DOM.hubHeroSub) DOM.hubHeroSub.textContent = L('hub_hero_sub', 'Sistemas portátiles y herramientas autónomas sin tocar el ordenador al que se conecta.');
    if (DOM.hubTagHollow) DOM.hubTagHollow.textContent = L('hub_tag_hollow', 'CREAR USB');
    if (DOM.hubBtnHollow) DOM.hubBtnHollow.textContent = L('hub_btn_hollow', 'Comenzar Asistente ➜');
    if (DOM.hubTagTools) DOM.hubTagTools.textContent = L('hub_tag_tools', 'MANTENIMIENTO');
    if (DOM.hubBtnTools) DOM.hubBtnTools.textContent = L('hub_btn_tools', 'Herramientas ➜');
    if (DOM.hubTagAddons) DOM.hubTagAddons.textContent = L('hub_tag_addons', 'CATÁLOGO DINÁMICO');
    if (DOM.hubBtnAddons) DOM.hubBtnAddons.textContent = L('hub_btn_addons', 'Próximamente');
    if (DOM.hintDragMoveText) DOM.hintDragMoveText.textContent = L('hint_drag_move', 'Mover ventana al arrastrar');
    if (DOM.hintDragResizeText) DOM.hintDragResizeText.textContent = L('hint_drag_resize', 'Redimensionar al arrastrar');

    // 2. Stepper
    if (DOM.stepLabel1) DOM.stepLabel1.textContent = L('step1', 'Unidad USB');
    if (DOM.stepLabel2) DOM.stepLabel2.textContent = L('step2', 'Kit de Herramientas');
    if (DOM.stepLabel3) DOM.stepLabel3.textContent = L('step3', 'Batocera');
    if (DOM.stepLabel4) DOM.stepLabel4.textContent = L('step4', 'Sistema Portable');
    if (DOM.stepLabel5) DOM.stepLabel5.textContent = L('step5', 'Método de Descarga');
    if (DOM.stepLabel6) DOM.stepLabel6.textContent = L('step6', 'Particionado');

    // 3. Step 1: USB
    if (DOM.usbStepTitle) DOM.usbStepTitle.textContent = L('usb_title', 'Selecciona una unidad');
    if (DOM.lblShowInternal) DOM.lblShowInternal.textContent = L('usb_show_internal', 'Mostrar discos internos');
    if (DOM.usbWarningTitle) DOM.usbWarningTitle.textContent = L('usb_warn_title', 'ADVERTENCIA:');
    if (DOM.usbWarningText) DOM.usbWarningText.textContent = L('usb_warn_text', 'Esta acción formateará por completo la unidad seleccionada. Asegúrate de respaldar cualquier archivo antes de continuar.');
    if (DOM.usbLockLabel) DOM.usbLockLabel.textContent = L('usb_lock_accept', 'Entiendo los riesgos y confirmo el formateo del dispositivo');

    // 4. Step 2: Kit
    if (DOM.paneTitleKit) DOM.paneTitleKit.textContent = L('kit_title', 'Pack de Herramientas (8.7 GB)');
    document.querySelectorAll('.switch-text-install').forEach(el => {
      el.textContent = L('switch_install', '¿Instalar?');
    });

    // 5. Step 3: Batocera
    if (DOM.paneTitleBatocera) DOM.paneTitleBatocera.textContent = L('bato_title', '¿Instalar Batocera?');
    if (DOM.btnBato64) DOM.btnBato64.textContent = L('bato_arch64', 'Batocera 64bits (4.6 GB)');
    if (DOM.btnBato32) DOM.btnBato32.textContent = L('bato_arch32', 'Batocera 32bits (Próximamente)');

    // 6. Step 4: Sistema Portable
    if (DOM.paneTitleSystem) DOM.paneTitleSystem.textContent = L('sys_title', '¿Instalar Sistema Portable?');
    if (DOM.optOsCachy) DOM.optOsCachy.textContent = L('sys_opt_cachy', 'CachyOS (Arch Linux Optimizado)');
    if (DOM.optOsNone) DOM.optOsNone.textContent = L('sys_opt_none', 'Ninguno (No instalar sistema)');
    if (DOM.optOsZorin) DOM.optOsZorin.textContent = L('sys_opt_soon', '{name} (Próximamente)').replace('{name}', 'Zorin OS');
    if (DOM.optOsDeepin) DOM.optOsDeepin.textContent = L('sys_opt_soon', '{name} (Próximamente)').replace('{name}', 'Deepin OS');
    if (DOM.optOsUbuntu) DOM.optOsUbuntu.textContent = L('sys_opt_soon', '{name} (Próximamente)').replace('{name}', 'Ubuntu');
    if (DOM.optOsDebian) DOM.optOsDebian.textContent = L('sys_opt_soon', '{name} (Próximamente)').replace('{name}', 'Debian');
    if (DOM.btnCachyKde) DOM.btnCachyKde.textContent = L('sys_plasma_soon', 'KDE Plasma (Próximamente)');

    // 7. Step 5: Método de Descarga
    if (DOM.downloadModeTitle) DOM.downloadModeTitle.textContent = L('dl_title', '¿Cómo deseas descargar los paquetes?');
    if (DOM.downloadModeSub) DOM.downloadModeSub.textContent = L('dl_sub', 'Selecciona la estrategia de transferencia óptima para tu equipo y conexión.');
    if (DOM.titleDlAsync) DOM.titleDlAsync.textContent = L('dl_async_title', 'Descarga Asíncrona');
    if (DOM.descDlAsync) DOM.descDlAsync.textContent = L('dl_async_desc', 'Descarga y descomprime los paquetes al vuelo directamente en memoria RAM hacia el USB.');
    if (DOM.titleDlClassic) DOM.titleDlClassic.textContent = L('dl_classic_title', 'Descarga Clásica');
    if (DOM.descDlClassic) DOM.descDlClassic.textContent = L('dl_classic_desc', 'Descarga primero las partes completas en una carpeta temporal y luego las extrae al USB.');
    if (DOM.badgeDlAsync) DOM.badgeDlAsync.textContent = L('dl_recommended', 'Recomendado');
    if (DOM.featAsync1) DOM.featAsync1.textContent = L('dl_feat_async_1', 'Sin archivos temporales gigantes en disco');
    if (DOM.featAsync2) DOM.featAsync2.textContent = L('dl_feat_async_2', 'Cero desgaste para tu disco SSD');
    if (DOM.featAsync3) DOM.featAsync3.textContent = L('dl_feat_async_3', 'Velocidad máxima de instalación');
    if (DOM.featClassic1) DOM.featClassic1.textContent = L('dl_feat_classic_1', 'Reanudación resiliente por partes');
    if (DOM.featClassic2) DOM.featClassic2.textContent = L('dl_feat_classic_2', 'Mínimo consumo de memoria RAM');
    if (DOM.featClassic3) DOM.featClassic3.textContent = L('dl_feat_classic_3', 'Requiere espacio libre temporal en disco');
    if (DOM.radioLblAsync) DOM.radioLblAsync.textContent = State.downloadMode === 'ram' ? L('dl_selected', 'Seleccionado') : L('dl_select', 'Seleccionar');
    if (DOM.radioLblClassic) DOM.radioLblClassic.textContent = State.downloadMode === 'disco' ? L('dl_selected', 'Seleccionado') : L('dl_select', 'Seleccionar');

    // 8. Step 6: Particionado
    if (DOM.partitionHeading) DOM.partitionHeading.textContent = L('part_heading', 'Distribución del Espacio en el Disco');
    if (DOM.sliderHollowLabel) DOM.sliderHollowLabel.textContent = L('part_slider_hollow', 'Tamaño Hollowdrive (Ventoy + ISOs):');
    if (DOM.sliderSystemLabel) DOM.sliderSystemLabel.textContent = L('part_slider_system', 'Tamaño Sistema (Ext4):');
    if (DOM.lblPreserveSpace) DOM.lblPreserveSpace.textContent = L('part_preserve', 'Preservar espacio libre en USB');

    // 8. Info Screen
    if (DOM.infoWelcomeText) DOM.infoWelcomeText.textContent = L('info_welcome', '');
    if (DOM.infoVideoPrompt) DOM.infoVideoPrompt.textContent = L('info_video_prompt', '¡MIRA ESTE VÍDEO PARA SABER CÓMO FUNCIONA!');
    if (DOM.btnEnterAppText) DOM.btnEnterAppText.textContent = L('btn_next_fixed', 'Siguiente ➡');
    if (DOM.infoLicensesPrompt) DOM.infoLicensesPrompt.textContent = L('info_licenses', 'HERRAMIENTAS CORE Y LICENCIAS');
    if (DOM.infoLegalNotice) DOM.infoLegalNotice.textContent = L('info_legal', '');
    if (DOM.infoThanksText) DOM.infoThanksText.textContent = L('info_thanks', '');
    document.querySelectorAll('.btn-credit-link').forEach(btn => {
      btn.textContent = L('info_code_web', 'Código / Web');
    });

    // 9. Modales
    document.querySelectorAll('.btn-modal-understood').forEach(btn => {
      btn.textContent = L('modal_understood', 'ENTENDIDO');
    });
    if (DOM.modalKitHeader) DOM.modalKitHeader.textContent = L('modal_kit_header', 'PACK DE HERRAMIENTAS HOLLOWDRIVE');
    if (DOM.toolCatAntivirus) DOM.toolCatAntivirus.textContent = L('cat_antivirus', 'ANTIVIRUS');
    if (DOM.toolCatBackups) DOM.toolCatBackups.textContent = L('cat_backups', 'BACKUPS Y CLONACIÓN DE DISCOS/SISTEMAS');
    if (DOM.toolCatLiveOs) DOM.toolCatLiveOs.textContent = L('cat_liveos', 'SISTEMA LIVE LLENO DE HERRAMIENTAS');
    if (DOM.toolCatIsos) DOM.toolCatIsos.textContent = L('cat_isos', 'CARPETA PARA DEJAR TUS PROPIAS ISOS');
    if (DOM.toolCatVentoyDesc) DOM.toolCatVentoyDesc.textContent = L('cat_ventoy_desc', 'Directorio nativo Ventoy (Copia y pega cualquier ISO)');
    if (DOM.toolCatPartitions) DOM.toolCatPartitions.textContent = L('cat_partitions', 'HERRAMIENTAS DE PARTICIONES');
    if (DOM.toolCatRescue) DOM.toolCatRescue.textContent = L('cat_rescue', 'RESCATE DE ARRANQUE');

    if (DOM.modalBatoceraTitle) DOM.modalBatoceraTitle.textContent = L('bato_modal_title', 'SOBRE BATOCERA');
    if (DOM.modalBatoceraBody) {
      DOM.modalBatoceraBody.innerHTML = `
        <p style="margin-bottom: 10px;">
          Batocera es un sistema de emulación que puede convertir cualquier ordenador en una consola de videojuegos retro y moderna.
        </p>
        <div class="badge-green-pill-wrap">
          <span class="badge-green-pill">Seguridad de datos</span>
        </div>
        <p style="margin-bottom: 12px; color: #cbd5e1;">
          Aunque inicies Batocera desde el USB, <strong>NUNCA perderás ni modificarás</strong> los datos del disco duro del ordenador anfitrión.
        </p>
        <div style="font-size: 0.88rem; color: var(--text-muted); display:flex; flex-direction:column; gap:4px;">
          <span>• No requiere instalación en el ordenador</span>
          <span>• Incluye drivers para mandos Bluetooth y USB</span>
          <span>• Guarda tus partidas directamente en el almacenamiento de HollowDrive</span>
        </div>
      `;
    }
    if (DOM.modalSystemTitle) DOM.modalSystemTitle.textContent = L('sys_modal_title', 'SISTEMA PORTABLE OPTIMIZADO');
    if (DOM.modalSystemBody) DOM.modalSystemBody.textContent = L('sys_modal_body', '');
    if (DOM.modalSystemNote) DOM.modalSystemNote.textContent = L('sys_modal_note', '');

    if (DOM.lblInstallSuccessTitle) DOM.lblInstallSuccessTitle.textContent = L('install_success_title', '¡Instalación Finalizada con Éxito!');
    if (DOM.lblNewInstallBtn) DOM.lblNewInstallBtn.textContent = L('btn_new_install', 'Nueva Instalación');
    if (DOM.lblSimpleBreakdownTitle) DOM.lblSimpleBreakdownTitle.textContent = L('simple_breakdown_title', 'DESGLOSE POR PROCESOS');
    
    // Donaciones y Caballero
            if (DOM.donateModalText) DOM.donateModalText.innerHTML = L('donate_desc', '');
    if (DOM.donateKofiMain) DOM.donateKofiMain.textContent = L('donate_kofi_main', 'Invítame a un café');
    if (DOM.donateKofiSub) DOM.donateKofiSub.textContent = L('donate_kofi_sub', '(Ko-fi)');
        if (DOM.donatePaypalText) DOM.donatePaypalText.textContent = L('donate_paypal', 'Donar con PayPal');

    if (DOM.modalInternalDangerTitle) DOM.modalInternalDangerTitle.textContent = L('danger_modal_title', 'AVISO: DISCOS INTERNOS');
    if (DOM.modalInternalDangerBody) DOM.modalInternalDangerBody.innerHTML = L('danger_modal_body', '').replace(/\n\n/g, '<br/><br/>');
    if (DOM.btnConfirmInternalModal) DOM.btnConfirmInternalModal.textContent = L('danger_modal_confirm', 'Activar de todos modos');
    if (DOM.btnCancelInternalModal) DOM.btnCancelInternalModal.textContent = L('danger_modal_cancel', 'Cancelar');

    if (DOM.modalConfirmInstallTitle) DOM.modalConfirmInstallTitle.textContent = L('confirm_modal_title', 'CONFIRMACIÓN DE INSTALACIÓN');
    if (DOM.btnExecuteInstallConfirmed) DOM.btnExecuteInstallConfirmed.textContent = L('confirm_modal_start', '¡Comenzar Instalación!');
    if (DOM.btnCancelInstallModal) DOM.btnCancelInstallModal.textContent = L('confirm_modal_cancel', 'Cancelar');

    if (DOM.modalLockTitle) DOM.modalLockTitle.textContent = L('lock_modal_title', 'ATENCIÓN: DISCO INTERNO SELECCIONADO');
    if (DOM.modalLockBody) DOM.modalLockBody.innerHTML = L('lock_modal_body', '').replace(/\n\n/g, '<br/><br/>');
    if (DOM.btnConfirmLock) DOM.btnConfirmLock.textContent = L('lock_modal_confirm', 'Confirmar');
    if (DOM.modalNoInternetTitle) DOM.modalNoInternetTitle.textContent = L('no_internet_title', 'AVISO: SIN CONEXIÓN A INTERNET');
    if (DOM.modalNoInternetBody) DOM.modalNoInternetBody.innerHTML = L('no_internet_body', '');

    // 10. HollowTools
    if (DOM.toolsCardPortableTitle) DOM.toolsCardPortableTitle.textContent = L('tools_card_portable_title', 'SISTEMA PORTABLE');
    if (DOM.toolsGearLabel) DOM.toolsGearLabel.textContent = L('tools_gear_options', 'Opciones');
    if (DOM.toolsBtnApplyText) DOM.toolsBtnApplyText.textContent = L('tools_btn_apply', 'Aplicar');
    if (DOM.modalPortableOptionsTitle) DOM.modalPortableOptionsTitle.textContent = L('tools_modal_options_title', 'OPCIONES DEL SISTEMA PORTABLE');
    if (DOM.btnToolsCachyUpdate) DOM.btnToolsCachyUpdate.textContent = L('tools_opt_mode_update', 'Actualizar CachyOS');
    if (DOM.btnToolsCachyInstall) DOM.btnToolsCachyInstall.textContent = L('tools_opt_mode_install', 'Instalar CachyOS');
    if (DOM.btnModalClosePortable) DOM.btnModalClosePortable.textContent = L('tools_modal_close', 'Cerrar');
    if (DOM.btnBackFromTools) DOM.btnBackFromTools.textContent = L('tools_back', '⬅ Atrás');

    // 11. Métricas del monitor de instalación
    if (DOM.metricTitleStep) DOM.metricTitleStep.textContent = L('metric_step', 'Fase Actual');
    if (DOM.metricTitleSpeed) DOM.metricTitleSpeed.textContent = L('metric_speed', 'Velocidad');
    if (DOM.metricTitleTaskTime) DOM.metricTitleTaskTime.textContent = L('metric_task_time', 'Tiempo Proceso');
    if (DOM.metricTitleEta) DOM.metricTitleEta.textContent = L('metric_eta', 'Total Restante');
    if (DOM.metricTitleStatus) DOM.metricTitleStatus.textContent = L('metric_status', 'Estado');

    // 12. Textos de Vista Simple y Selector de Modo
    if (DOM.lblModeSimple) DOM.lblModeSimple.textContent = L('mode_simple', 'Modo Simple');
    if (DOM.lblModeDetailed) DOM.lblModeDetailed.textContent = L('mode_detailed', 'Modo Detallado');
    if (DOM.lblSimpleTotalTimeTitle) DOM.lblSimpleTotalTimeTitle.textContent = L('simple_total_time_title', 'TIEMPO TOTAL DEL PROCESO');
    if (DOM.lblSimpleNext) DOM.lblSimpleNext.textContent = L('nav_next', 'Siguiente ➜');
    if (DOM.lblGratitudeTitle) DOM.lblGratitudeTitle.textContent = L('gratitude_title', '¡Tu HollowDrive está listo para la aventura!');
    if (DOM.lblGratitudeSub) DOM.lblGratitudeSub.textContent = L('gratitude_sub', 'Ya puedes retirar de forma segura la memoria USB e iniciarla en cualquier ordenador.');
    if (DOM.lblGratitudeBackMenu) DOM.lblGratitudeBackMenu.textContent = L('nav_back_menu', '⬅ Volver al Menú');

    updateWizardUI();
    updatePartitionVisuals();
  }

  const DEFAULT_LANGUAGES = [
    { code: 'es', name: 'Español', display: '🌐 Español' },
    { code: 'en', name: 'English', display: '🌐 English' },
    { code: 'zh', name: '简体中文', display: '🌐 简体中文' },
    { code: 'ja', name: '日本語', display: '🌐 日本語' },
    { code: 'ru', name: 'Русский', display: '🌐 Русский' },
    { code: 'pt', name: 'Português', display: '🌐 Português' },
    { code: 'de', name: 'Deutsch', display: '🌐 Deutsch' },
    { code: 'fr', name: 'Français', display: '🌐 Français' },
    { code: 'it', name: 'Italiano', display: '🌐 Italiano' },
    { code: 'ko', name: '한국어', display: '🌐 한국어' }
  ];

  function renderLanguageOptions(languages) {
    [DOM.langDropdown, DOM.langDropdownInfo].forEach(dropdown => {
      if (!dropdown) return;
      dropdown.innerHTML = '';
      languages.forEach(lang => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'lang-option';
        btn.dataset.lang = lang.code;
        btn.innerHTML = `${lang.display || ('🌐 ' + lang.name)}`;
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          switchLanguage(lang.code, lang.name);
        });
        dropdown.appendChild(btn);
      });
    });
  }

  // Poblado síncrono inicial garantizado para que el menú nunca abra vacío
  renderLanguageOptions(DEFAULT_LANGUAGES);

  async function initLanguages() {
    try {
      const res = await window.hollowdrive.getLanguages();
      if (res && res.available && res.available.length > 0) {
        renderLanguageOptions(res.available);

        const cur = res.current || 'es';
        const curObj = res.available.find(l => l.code === cur);
        const curName = curObj?.name || 'Español';
        if (DOM.langCurrentText) DOM.langCurrentText.textContent = `🌐 ${curName}`;
        if (DOM.langCurrentTextInfo) DOM.langCurrentTextInfo.textContent = `🌐 ${curName}`;
        State.currentLang = cur;
      }

      applyTranslations();
    } catch (e) {
      console.error("Error cargando idiomas:", e);
      applyTranslations();
    }
  }

  async function switchLanguage(code, name) {
    try {
      if (DOM.langCurrentText) DOM.langCurrentText.textContent = `🌐 ${name}`;
      if (DOM.langCurrentTextInfo) DOM.langCurrentTextInfo.textContent = `🌐 ${name}`;
      if (DOM.langDropdown) DOM.langDropdown.classList.remove('open');
      if (DOM.langDropdownInfo) DOM.langDropdownInfo.classList.remove('open');
      State.currentLang = code;
      await window.hollowdrive.setLanguage(code);
      applyTranslations();
    } catch (e) {
      console.error("Error cambiando idioma:", e);
    }
  }

  // Desplegable de idiomas del header
  if (DOM.langBtn) {
    DOM.langBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      DOM.langDropdown.classList.toggle('open');
    });
  }

  // Desplegable de idiomas en la pantalla de info
  if (DOM.langBtnInfo) {
    DOM.langBtnInfo.addEventListener('click', (e) => {
      e.stopPropagation();
      DOM.langDropdownInfo.classList.toggle('open');
    });
  }

  document.addEventListener('click', () => {
    if (DOM.langDropdown) DOM.langDropdown.classList.remove('open');
    if (DOM.langDropdownInfo) DOM.langDropdownInfo.classList.remove('open');
  });

  // =========================================================================
  // ℹ️ GESTIÓN DE MODALES INDEPENDIENTES Y SECUENCIALES
  // =========================================================================
  async function handleCloseOverlayInfo() {
    const overlay = DOM.overlayInfo || document.getElementById('overlayInfo');
    if (!overlay) return;

    try {
      overlay.classList.remove('open');
      overlay.classList.add('fade-out');

      // 1. Esperar a que overlayInfo desaparezca por completo (~500ms)
      await new Promise(r => setTimeout(r, 500));

      overlay.classList.remove('fade-out');
      overlay.style.visibility = 'hidden';
      overlay.style.display = 'none';

      // 2. Entrar a la pantalla principal de forma limpia e inmediata
      await setScreen(State.screen || 'hub', true);
    } catch (err) {
      console.error("[OVERLAY-INFO] Error cerrando pantalla de info:", err);
    } finally {
      isScreenTransitioning = false;
      document.body.classList.remove('nav-transitioning');
    }
  }

  function openModal(modalEl) {
    if (!modalEl) return;
    if (modalEl.id === 'overlayInfo') {
      modalEl.classList.remove('fade-out');
      modalEl.style.display = 'flex';
      modalEl.style.visibility = 'visible';
      modalEl.classList.add('open');
      return;
    }
    const overlay = document.getElementById('overlayInfo');
    if (overlay && overlay.classList.contains('open')) {
      closeModal(overlay);
    }
    modalEl.style.display = 'flex';
    modalEl.style.visibility = 'visible';
    modalEl.classList.add('open');
  }

  function closeModal(modalEl) {
    if (!modalEl) return;
    if (modalEl === DOM.overlayInfo || modalEl.id === 'overlayInfo') {
      handleCloseOverlayInfo();
      return;
    }
    modalEl.classList.remove('open');
    const onEnd = () => {
      modalEl.removeEventListener('transitionend', onEnd);
      if (!modalEl.classList.contains('open')) {
        modalEl.style.visibility = 'hidden';
        modalEl.style.display = 'none';
      }
    };
    modalEl.addEventListener('transitionend', onEnd, { once: true });
    setTimeout(() => {
      if (!modalEl.classList.contains('open')) {
        modalEl.style.visibility = 'hidden';
        modalEl.style.display = 'none';
      }
    }, 400);
  }

  function showCustomConfirm({ title, message, okText = "Confirmar", cancelText = "Cancelar", isDanger = false }) {
    return new Promise((resolve) => {
      const modal = DOM.modalConfirmToolsAction || document.getElementById('modalConfirmToolsAction');
      const titleEl = DOM.modalConfirmToolsTitle || document.getElementById('modalConfirmToolsTitle');
      const bodyEl = DOM.modalConfirmToolsBody || document.getElementById('modalConfirmToolsBody');
      const okBtn = DOM.btnConfirmToolsOk || document.getElementById('btnConfirmToolsOk');
      const cancelBtn = DOM.btnConfirmToolsCancel || document.getElementById('btnConfirmToolsCancel');
      const closeBtn = DOM.btnConfirmToolsClose || document.getElementById('btnConfirmToolsClose');

      if (!modal) {
        resolve(true);
        return;
      }

      if (titleEl) titleEl.textContent = title || "CONFIRMAR ACCIÓN";
      if (bodyEl) bodyEl.innerHTML = message;
      if (okBtn) {
        okBtn.textContent = okText;
        if (isDanger) {
          okBtn.style.background = 'linear-gradient(135deg, #ef4444, #dc2626)';
          okBtn.style.borderColor = '#f87171';
          okBtn.style.boxShadow = '0 0 15px rgba(239, 68, 68, 0.4)';
        } else {
          okBtn.style.background = '';
          okBtn.style.borderColor = '';
          okBtn.style.boxShadow = '';
        }
      }
      if (cancelBtn) {
        cancelBtn.style.display = cancelText ? 'inline-flex' : 'none';
        if (cancelText) cancelBtn.textContent = cancelText;
      }

      const cleanup = (result) => {
        closeModal(modal);
        if (okBtn) okBtn.onclick = null;
        if (cancelBtn) cancelBtn.onclick = null;
        if (closeBtn) closeBtn.onclick = null;
        resolve(result);
      };

      if (okBtn) okBtn.onclick = () => cleanup(true);
      if (cancelBtn) cancelBtn.onclick = () => cleanup(false);
      if (closeBtn) closeBtn.onclick = () => cleanup(false);

      openModal(modal);
    });
  }

  function showCustomAlert(title, message) {
    return showCustomConfirm({
      title: title || "AVISO",
      message: message,
      okText: "Entendido",
      cancelText: null
    });
  }

  // Cerrar cualquier modal al hacer clic en sus botones de cierre [data-modal-close]
  document.querySelectorAll('[data-modal-close]').forEach(btn => {
    btn.addEventListener('click', () => {
      const modalId = btn.getAttribute('data-modal-close');
      const target = document.getElementById(modalId);
      if (target) closeModal(target);
    });
  });

  // Cerrar al hacer clic en el backdrop exterior del modal
  document.querySelectorAll('.custom-modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        closeModal(overlay);
      }
    });
  });

  // Controles de Ventana Frameless (Minimizar, Maximizar, Cerrar)
  if (DOM.winBtnMinimize) {
    DOM.winBtnMinimize.addEventListener('click', (e) => {
      e.stopPropagation();
      window.hollowdrive.windowMinimize();
    });
  }
  if (DOM.winBtnMaximize) {
    DOM.winBtnMaximize.addEventListener('click', (e) => {
      e.stopPropagation();
      if (window.hollowdrive?.windowToggleMaximize) {
        window.hollowdrive.windowToggleMaximize().then(res => {
          if (res && typeof res.is_maximized === 'boolean') {
            setMaximizedState(res.is_maximized);
          } else {
            setMaximizedState(!isWindowMaximized);
          }
        }).catch(() => {
          setMaximizedState(!isWindowMaximized);
        });
      } else {
        setMaximizedState(!isWindowMaximized);
      }
    });
  }
  if (DOM.winBtnClose) {
    DOM.winBtnClose.addEventListener('click', (e) => {
      e.stopPropagation();
      window.hollowdrive.windowClose();
    });
  }

  // Deslizamiento suave de la barra superior al acercar el puntero al borde superior
  let topBarTimer = null;
  const topBarEl = DOM.windowTopBar || document.getElementById('windowTopBar');
  const sliderEl = DOM.windowControlsSlider || document.getElementById('windowControlsSlider');

  function showTopBar() {
    if (topBarTimer) {
      clearTimeout(topBarTimer);
      topBarTimer = null;
    }
    if (topBarEl) topBarEl.classList.add('active-slide');
    if (sliderEl) sliderEl.classList.add('active-slide');
  }

  function hideTopBar(delay = 500) {
    // Si ya hay un temporizador de cierre activo, permitir que expire exactamente en 500ms sin posponerlo
    if (topBarTimer) return;
    topBarTimer = setTimeout(() => {
      if (topBarEl) topBarEl.classList.remove('active-slide');
      if (sliderEl) sliderEl.classList.remove('active-slide');
      topBarTimer = null;
    }, delay);
  }

  if (sliderEl) {
    sliderEl.addEventListener('mouseenter', () => showTopBar());
    sliderEl.addEventListener('mouseleave', () => hideTopBar(500));
  }
  if (topBarEl) {
    topBarEl.addEventListener('mouseenter', () => showTopBar());
    topBarEl.addEventListener('mouseleave', () => hideTopBar(500));
  }

  window.addEventListener('mousemove', (e) => {
    // Zona de activación: borde superior (Y <= 36) o cursor sobre los controles de ventana
    const isTopEdge = e.clientY <= 36;
    const isOverControls = Boolean(e.target && e.target.closest && e.target.closest('#windowControlsSlider'));

    if (isTopEdge || isOverControls) {
      showTopBar();
    } else if (e.clientY > 44) {
      hideTopBar(500);
    }
  }, { passive: true });

  window.addEventListener('mouseleave', () => {
    hideTopBar(500);
  });

  // Doble clic en la barra superior para alternar maximizado
  if (topBarEl) {
    topBarEl.addEventListener('dblclick', (e) => {
      const targetEl = e.target instanceof Element ? e.target : e.target.parentElement;
      if (!targetEl || targetEl.closest('.neon-win-btn, .win-btn, button, a')) return;
      if (DOM.winBtnMaximize) DOM.winBtnMaximize.click();
    });
  }

  // =========================================================================
  // 🪟 GESTOR INTELIGENTE DE ARRASTRE DE VENTANA (FRAMELESS DRAG & UNMAXIMIZE)
  // =========================================================================
  let isWindowDragging = false;
  let dragStartScreenX = 0;
  let dragStartScreenY = 0;
  let dragInitialClientX = 0;
  let dragInitialClientY = 0;
  let isWindowMaximized = false;

  const DRAG_MOVE_THRESHOLD = 8; // Requiere 8px de movimiento intencional para no interferir con clics
  const UNMAXIMIZE_PULL_THRESHOLD = 20; // Si está maximizada y arrastra hacia abajo >= 20px, se desmaximiza
  const SNAP_TOP_THRESHOLD = 14; // Píxeles al borde superior de pantalla para activar Aero Snap

  function updateResponsiveState() {
    const isWide = window.innerWidth >= 1340 || (window.screen && window.innerWidth >= (window.screen.availWidth - 24));
    document.body.classList.toggle('is-large-screen', isWide);
    if (isWindowMaximized) {
      document.body.classList.add('is-maximized');
    } else {
      document.body.classList.remove('is-maximized');
    }
  }

  function setMaximizedState(isMax) {
    isWindowMaximized = Boolean(isMax);
    updateResponsiveState();
  }

  // Sincronizar estado inicial de maximizado
  if (window.hollowdrive?.windowGetState) {
    window.hollowdrive.windowGetState().then(st => {
      if (st && typeof st.is_maximized === 'boolean') {
        setMaximizedState(st.is_maximized);
      }
    }).catch(() => {});
  }
  updateResponsiveState();

  // Sincronizar estado al cambiar el tamaño de ventana
  window.addEventListener('resize', () => {
    updateResponsiveState();
    if (window.hollowdrive?.windowGetState) {
      window.hollowdrive.windowGetState().then(st => {
        if (st && typeof st.is_maximized === 'boolean') {
          setMaximizedState(st.is_maximized);
        }
      }).catch(() => {});
    }
  });

  // Doble clic en la barra superior para alternar maximizado (gesto estándar)
  const appHeaderEl = document.querySelector('.app-header');
  if (appHeaderEl) {
    appHeaderEl.addEventListener('dblclick', (e) => {
      const targetEl = e.target instanceof Element ? e.target : e.target.parentElement;
      if (!targetEl || targetEl.closest('button, a, input, select, .win-btn, .lang-select-wrap, .github-pill')) return;
      if (DOM.winBtnMaximize) DOM.winBtnMaximize.click();
    });
  }

  // Cola single-flight de baja latencia sin retrasos artificiales de RAF
  let isMoveInFlight = false;
  let pendingMoveCoord = null;

  async function scheduleWindowMove(targetX, targetY) {
    pendingMoveCoord = { x: targetX, y: targetY };
    if (isMoveInFlight) return;
    isMoveInFlight = true;

    while (pendingMoveCoord) {
      const next = pendingMoveCoord;
      pendingMoveCoord = null;
      try {
        if (window.hollowdrive?.windowMove) {
          await window.hollowdrive.windowMove(next.x, next.y);
        }
      } catch (err) {
        console.error("[DRAG] Error moviendo ventana:", err);
      }
    }
    isMoveInFlight = false;
  }

  function cancelPendingWindowMove() {
    pendingMoveCoord = null;
    isMoveInFlight = false;
  }

  window.addEventListener('mousedown', (e) => {
    // Solo clic primario izquierdo
    if (e.button !== 0) return;

    // Si el clic no ocurre sobre un elemento válido, salir
    const targetEl = e.target instanceof Element ? e.target : e.target.parentElement;
    if (!targetEl) return;

    // Permitir arrastre de ventana desde cualquier región no interactiva (barra de título, fondos, espacio vacío)
    const isInteractive = Boolean(
      targetEl.closest(
        'button, a, input, select, textarea, video, option, label, ' +
        '[role="button"], .win-btn, .neon-win-btn, .btn, .switch-control, .toggle-switch, ' +
        '.lang-select-wrap, .lang-dropdown, .github-pill, .btn-info-header, ' +
        '.hub-card, .tools-module-card, .tool-item, .custom-modal-card, ' +
        '.terminal-console, .segmented-selector, .partition-bar, .partition-sliders-grid, ' +
        '.tools-disk-select, .tools-drop-zone, .knight-wrapper, .hub-knight-widget, .hub-knight-widget *, ' +
        '.video-scrubber-track, .video-progress-container, .video-timeline-wrap, ' +
        '.disk-card, .disk-option, .dl-card'
      )
    );
    if (isInteractive) return;

    // Inicializar coordenadas para evaluar intención de arrastre
    isWindowDragging = false;
    dragStartScreenX = e.screenX;
    dragStartScreenY = e.screenY;
    dragInitialClientX = e.clientX;
    dragInitialClientY = e.clientY;

    let lastScreenX = e.screenX;
    let lastScreenY = e.screenY;
    let lastTargetY = 0;
    let isNearTopSnap = false;

    function onMouseMoveWindow(moveEvent) {
      lastScreenX = moveEvent.screenX;
      lastScreenY = moveEvent.screenY;

      const deltaX = moveEvent.screenX - dragStartScreenX;
      const deltaY = moveEvent.screenY - dragStartScreenY;
      const dist = Math.hypot(deltaX, deltaY);

      // Si aún no se supera el umbral, comprobar si el movimiento es intencional
      if (!isWindowDragging) {
        if (dist < DRAG_MOVE_THRESHOLD) {
          return; // Aún en zona de clic estático, no mover ventana
        }
        isWindowDragging = true;
        document.body.classList.add('dragging-window');
      }

      // Si la ventana está maximizada y el usuario arrastra con fuerza hacia abajo:
      if (isWindowMaximized) {
        if (deltaY >= 16 || dist >= UNMAXIMIZE_PULL_THRESHOLD) {
          setMaximizedState(false);
          // Desmaximizar colocando la ventana centrada bajo el cursor
          if (window.hollowdrive?.windowUnmaximize) {
            window.hollowdrive.windowUnmaximize(moveEvent.screenX, moveEvent.screenY).then(res => {
              if (res && res.width) {
                dragInitialClientX = Math.round(res.width / 2);
                dragInitialClientY = 20;
              }
            }).catch(() => {});
          }
        }
        return; // No mover rígidamente mientras siga maximizada
      }

      // Mover la ventana de forma fluida y no bloqueante
      const targetX = Math.round(moveEvent.screenX - dragInitialClientX);
      const targetY = Math.round(moveEvent.screenY - dragInitialClientY);
      lastTargetY = targetY;

      // 🪟 Detección de borde superior para Aero Snap (Maximizar al arrastrar arriba)
      const topEdge = (window.screen && typeof window.screen.availTop === 'number') ? window.screen.availTop : 0;
      isNearTopSnap = ((moveEvent.screenY - topEdge) <= SNAP_TOP_THRESHOLD) || (targetY <= 0 && (moveEvent.screenY - topEdge) <= 24);

      if (isNearTopSnap) {
        document.body.classList.add('snap-top-hint');
      } else {
        document.body.classList.remove('snap-top-hint');
      }

      scheduleWindowMove(targetX, targetY);
    }

    function onMouseUpWindow(upEvent) {
      window.removeEventListener('mousemove', onMouseMoveWindow);
      window.removeEventListener('mouseup', onMouseUpWindow);
      cancelPendingWindowMove();
      document.body.classList.remove('snap-top-hint', 'dragging-window');

      // Si se soltó en el borde superior de la pantalla estando en modo arrastre -> MAXIMIZAR
      const finalScreenY = (upEvent && typeof upEvent.screenY === 'number') ? upEvent.screenY : lastScreenY;
      const topEdge = (window.screen && typeof window.screen.availTop === 'number') ? window.screen.availTop : 0;
      const shouldSnapMaximize = isWindowDragging && !isWindowMaximized && (
        isNearTopSnap ||
        ((finalScreenY - topEdge) <= SNAP_TOP_THRESHOLD) ||
        (lastTargetY <= 0 && (finalScreenY - topEdge) <= 26)
      );

      isWindowDragging = false;
      isNearTopSnap = false;

      if (shouldSnapMaximize) {
        setMaximizedState(true);
        if (window.hollowdrive?.windowMaximize) {
          window.hollowdrive.windowMaximize();
        } else if (window.hollowdrive?.windowToggleMaximize) {
          window.hollowdrive.windowToggleMaximize();
        }
      }
    }

    window.addEventListener('mousemove', onMouseMoveWindow, { passive: true });
    window.addEventListener('mouseup', onMouseUpWindow, { once: true });
  });

  // Limpieza de seguridad garantizada si la ventana pierde el foco durante un arrastre o redimensionamiento
  window.addEventListener('blur', () => {
    if (isWindowDragging) {
      cancelPendingWindowMove();
      isWindowDragging = false;
      document.body.classList.remove('snap-top-hint', 'dragging-window');
    }
    if (isRightResizing) {
      cancelPendingWindowResize();
      isRightResizing = false;
      document.body.classList.remove('resizing-window', 'resizing-nwse', 'resizing-nesw');
    }
  });

  // =========================================================================
  // ↔️ REDIMENSIONAMIENTO CON CLIC DERECHO (RIGHT-CLICK DRAG RESIZE)
  // =========================================================================
  let isRightResizing = false;
  let resizeStartScreenX = 0;
  let resizeStartScreenY = 0;
  let resizeStartWidth = 0;
  let resizeStartHeight = 0;
  let resizeFixPoint = 'NORTH_WEST';

  // Cola single-flight de baja latencia sin retrasos artificiales de RAF para redimensionamiento
  let isResizeInFlight = false;
  let pendingResizeParams = null;

  async function scheduleWindowResize(w, h, fixPoint) {
    pendingResizeParams = { w, h, fixPoint };
    if (isResizeInFlight) return;
    isResizeInFlight = true;

    while (pendingResizeParams) {
      const next = pendingResizeParams;
      pendingResizeParams = null;
      try {
        if (window.hollowdrive?.windowResize) {
          await window.hollowdrive.windowResize(next.w, next.h, next.fixPoint);
        }
      } catch (err) {
        console.error("[RESIZE] Error redimensionando ventana:", err);
      }
    }
    isResizeInFlight = false;
  }

  function cancelPendingWindowResize() {
    pendingResizeParams = null;
    isResizeInFlight = false;
  }

  // Prevenir menú contextual del navegador para permitir el gesto libre de clic derecho
  window.addEventListener('contextmenu', (e) => {
    if (!e.target.closest('.terminal-console')) {
      e.preventDefault();
    }
  });

  window.addEventListener('mousedown', (e) => {
    // Clic secundario derecho
    if (e.button !== 2) return;

    const targetEl = e.target instanceof Element ? e.target : e.target.parentElement;
    if (!targetEl || targetEl.closest('.win-btn, .btn-mini-info, .lang-dropdown, input, select, textarea, .window-controls-slider')) return;

    e.preventDefault();

    resizeStartScreenX = e.screenX;
    resizeStartScreenY = e.screenY;
    resizeStartWidth = window.innerWidth;
    resizeStartHeight = window.innerHeight;
    isRightResizing = false;

    // Determinar cuadrante según la posición del cursor en la ventana
    const midX = window.innerWidth / 2;
    const midY = window.innerHeight / 2;
    const isLeft = e.clientX < midX;
    const isTop = e.clientY < midY;

    if (isLeft && isTop) {
      resizeFixPoint = 'SOUTH_EAST';
      document.body.classList.add('resizing-window', 'resizing-nwse');
    } else if (isLeft && !isTop) {
      resizeFixPoint = 'NORTH_EAST';
      document.body.classList.add('resizing-window', 'resizing-nesw');
    } else if (!isLeft && isTop) {
      resizeFixPoint = 'SOUTH_WEST';
      document.body.classList.add('resizing-window', 'resizing-nesw');
    } else {
      resizeFixPoint = 'NORTH_WEST';
      document.body.classList.add('resizing-window', 'resizing-nwse');
    }

    function onMouseMoveResize(moveEvent) {
      const deltaX = moveEvent.screenX - resizeStartScreenX;
      const deltaY = moveEvent.screenY - resizeStartScreenY;
      const dist = Math.hypot(deltaX, deltaY);

      if (!isRightResizing) {
        if (dist < 6) return; // Umbral de 6px
        isRightResizing = true;

        if (isWindowMaximized) {
          setMaximizedState(false);
          if (window.hollowdrive?.windowUnmaximize) {
            window.hollowdrive.windowUnmaximize(moveEvent.screenX, moveEvent.screenY);
          }
        }
      }

      let targetW = resizeStartWidth;
      let targetH = resizeStartHeight;

      if (resizeFixPoint === 'NORTH_WEST') {
        targetW = resizeStartWidth + deltaX;
        targetH = resizeStartHeight + deltaY;
      } else if (resizeFixPoint === 'NORTH_EAST') {
        targetW = resizeStartWidth - deltaX;
        targetH = resizeStartHeight + deltaY;
      } else if (resizeFixPoint === 'SOUTH_WEST') {
        targetW = resizeStartWidth + deltaX;
        targetH = resizeStartHeight - deltaY;
      } else if (resizeFixPoint === 'SOUTH_EAST') {
        targetW = resizeStartWidth - deltaX;
        targetH = resizeStartHeight - deltaY;
      }

      const clampedW = Math.max(940, Math.round(targetW));
      const clampedH = Math.max(680, Math.round(targetH));

      scheduleWindowResize(clampedW, clampedH, resizeFixPoint);
    }

    function onMouseUpResize(upEvent) {
      if (upEvent.button === 2) {
        window.removeEventListener('mousemove', onMouseMoveResize);
        window.removeEventListener('mouseup', onMouseUpResize);
        document.body.classList.remove('resizing-window', 'resizing-nwse', 'resizing-nesw');
        cancelPendingWindowResize();
        isRightResizing = false;
      }
    }

    window.addEventListener('mousemove', onMouseMoveResize, { passive: true });
    window.addEventListener('mouseup', onMouseUpResize);
  });

  // Header Info -> Pantalla Principal de Información
  DOM.btnHeaderInfo.addEventListener('click', () => {
    openModal(DOM.overlayInfo);
  });

  DOM.btnEnterApp.addEventListener('click', () => {
    closeModal(DOM.overlayInfo);
  });

  if (DOM.videoTutorialTrigger) {
    DOM.videoTutorialTrigger.addEventListener('click', () => {
      window.hollowdrive.openUrl('https://youtu.be/oHg5SJYRHA0?si=7nL_H5sIWuiLM4dp');
    });
  }

  // Paso 2: Kit Tools Catalog Modal
  if (DOM.btnKitInfo) {
    DOM.btnKitInfo.addEventListener('click', () => {
      openModal(DOM.modalKitTools);
    });
  }

  // Paso 3: Batocera Info Modal
  if (DOM.btnBatoInfo) {
    DOM.btnBatoInfo.addEventListener('click', () => {
      openModal(DOM.modalBatocera);
    });
  }

  // Paso 4: Sistema Portable Info Modal
  if (DOM.btnCachyInfo) {
    DOM.btnCachyInfo.addEventListener('click', () => {
      openModal(DOM.modalCachy);
    });
  }

  // Widget Caballero y Bocadillo (Donaciones)
  const hubKnightWidget = document.getElementById('hubKnightWidget');
  if (hubKnightWidget) {
    hubKnightWidget.addEventListener('click', (e) => {
      e.stopPropagation();
      openModal(DOM.modalDonate || document.getElementById('modalDonate'));
    });
  }
  if (DOM.knightClickWrapper) {
    DOM.knightClickWrapper.addEventListener('click', (e) => {
      e.stopPropagation();
      openModal(DOM.modalDonate || document.getElementById('modalDonate'));
    });
    DOM.knightClickWrapper.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        e.stopPropagation();
        openModal(DOM.modalDonate || document.getElementById('modalDonate'));
      }
    });
  }

  if (DOM.headerLogo) {
    DOM.headerLogo.addEventListener('click', () => {
      setScreen('hub');
    });
  }

  // =========================================================================
  // 🧭 CONTROL DE PANTALLAS Y WIZARD (TRANSICIONES ESTRICTAMENTE SECUENCIALES)
  // =========================================================================
  let isScreenTransitioning = false;
  let isWizardStepTransitioning = false;

  async function setScreen(screenName, immediate = false) {
    if (State.screen === 'tools' && State.toolsIsOperating && screenName !== 'tools') {
      console.warn("[HOLLOWTOOLS] Intento de salida bloqueado durante una operación activa");
      showCustomAlert("OPERACIÓN EN CURSO", "No puedes salir de HollowTools mientras haya una operación de copia, inyección o particionado en progreso. Cancélala primero si deseas salir.");
      return;
    }

    const currentScreen = document.querySelector('.screen.active');
    const targetScreen = document.getElementById(`screen-${screenName}`);

    // Solo omitir si la pantalla destino ya está activa y visible en el DOM
    if (currentScreen === targetScreen && State.screen === screenName && !immediate) return;

    if (isScreenTransitioning && !immediate) {
      return;
    }

    if (immediate || !currentScreen || currentScreen === targetScreen) {
      const screens = document.querySelectorAll('.screen');
      screens.forEach(s => {
        s.classList.remove('fade-out', 'instant');
        const isActive = (s.id === `screen-${screenName}`);
        s.classList.toggle('active', isActive);
        if (isActive && immediate) {
          s.classList.add('instant');
        }
      });
      State.screen = screenName;
      if (screenName === 'wizard') {
        updateWizardUIControls();
        manageStepVideos(State.wizardStep);
      } else {
        manageStepVideos(0);
      }
      if (screenName === 'tools') {
        loadHollowToolsDisks();
      }
      return;
    }

    // --- SECUENCIA ESTRICTA: 1º DESVANECER PANTALLA ACTUAL, 2º CARGAR SIGUIENTE PANTALLA ---
    isScreenTransitioning = true;
    document.body.classList.add('nav-transitioning');

    try {
      // 1. Desvanecer la pantalla saliente (fade-out suave)
      currentScreen.classList.remove('instant');
      currentScreen.classList.add('fade-out');

      // Esperar a que la pantalla saliente se desvanezca suavemente (~450ms)
      await new Promise(r => setTimeout(r, 450));

      // 2. Ocultar totalmente la pantalla saliente
      currentScreen.classList.remove('active', 'fade-out');

      // Con el escenario despejado, actualizar el estado
      State.screen = screenName;
      if (screenName === 'wizard') {
        updateWizardUIControls();
        manageStepVideos(State.wizardStep);
      } else {
        manageStepVideos(0);
      }
      if (screenName === 'tools') {
        loadHollowToolsDisks();
      }

      // Pequeño respiro limpio (~30ms)
      await new Promise(r => setTimeout(r, 30));

      // 3. La siguiente pantalla empieza a aparecer (fade-in)
      if (targetScreen) {
        targetScreen.classList.remove('fade-out', 'instant');
        targetScreen.classList.add('active');
      }

      // Esperar a que la nueva pantalla complete su animación suave (~500ms)
      await new Promise(r => setTimeout(r, 500));
    } catch (err) {
      console.error("[NAV] Error en transición de pantalla:", err);
    } finally {
      isScreenTransitioning = false;
      document.body.classList.remove('nav-transitioning');
    }
  }

  // Manejo inteligente de reproducción de vídeos según el paso activo
  function manageStepVideos(activeStep) {
    const vKit = DOM.videoKit || document.getElementById('videoKit');
    const vBato = DOM.videoBatocera || document.getElementById('videoBatocera');
    const vCachy = DOM.videoCachy || document.getElementById('videoCachy');

    const isWizard = (State.screen === 'wizard');

    if (vKit) {
      if (isWizard && activeStep === 2) {
        vKit.currentTime = 0;
        vKit.play().catch(() => {});
      } else {
        vKit.pause();
      }
    }
    if (vBato) {
      if (isWizard && activeStep === 3) {
        vBato.currentTime = 0;
        vBato.play().catch(() => {});
      } else {
        vBato.pause();
      }
    }
    if (vCachy) {
      if (isWizard && activeStep === 4) {
        vCachy.currentTime = 0;
        vCachy.play().catch(() => {});
      } else {
        vCachy.pause();
      }
    }
  }

  async function setWizardStep(step, immediate = false) {
    if (step < 1) {
      await setScreen('hub');
      return;
    }
    if (step > 6) return;
    if (step === State.wizardStep && !immediate) return;

    if (isWizardStepTransitioning && !immediate) {
      return;
    }

    // Bloqueo estricto: no permitir avanzar más allá del paso 1 sin unidad USB válida y confirmada
    if (step > 1 && State.wizardStep === 1) {
      const isDiskValid = State.selectedDisk && State.selectedDisk.device !== undefined && State.selectedDisk.device !== null && State.totalDiskGb >= MIN_DRIVE_GB;
      if (!isDiskValid) {
        showCustomAlert("SELECCIONA UNA UNIDAD", "Debes seleccionar una unidad USB válida de al menos 8 GB antes de continuar.");
        return;
      }
      if (!State.lockConfirmed) {
        showCustomAlert("CONFIRMA EL FORMATEO", "Debes marcar la casilla confirmando que entiendes los riesgos y autorizas el formateo antes de continuar.");
        return;
      }
    }

    const currentPane = document.querySelector('.wizard-step-pane.active');
    const targetPane = document.querySelector(`.wizard-step-pane[data-step="${step}"]`);

    const isBackward = (step < State.wizardStep);
    const outClass = isBackward ? 'pane-slide-out-right' : 'pane-slide-out-left';
    const inClass = isBackward ? 'pane-slide-in-left' : 'pane-slide-in-right';

    if (immediate || !currentPane || currentPane === targetPane) {
      const panes = document.querySelectorAll('.wizard-step-pane');
      panes.forEach(pane => {
        pane.classList.remove('pane-slide-out-left', 'pane-slide-out-right', 'pane-slide-in-left', 'pane-slide-in-right', 'instant', 'fade-out', 'slide-left-out', 'slide-right-out', 'from-left', 'from-right');
        const isActive = (pane.dataset.step == step);
        pane.classList.toggle('active', isActive);
        if (isActive && immediate) {
          pane.classList.add('instant');
        }
      });
      State.wizardStep = step;
      manageStepVideos(step);
      updateWizardUIControls();
      if (step === 1) refreshDisks();
      return;
    }

    // --- TRANSICIÓN SIMULTÁNEA EN CARRUSEL (MIENTRAS SALE UNA ENTRA LA SIGUIENTE) ---
    isWizardStepTransitioning = true;
    document.body.classList.add('nav-transitioning');

    // 1. Limpiar estados residuales en cualquier otra pestaña inactiva
    const allPanes = document.querySelectorAll('.wizard-step-pane');
    allPanes.forEach(pane => {
      if (pane !== currentPane && pane !== targetPane) {
        pane.classList.remove('active', 'pane-slide-out-left', 'pane-slide-out-right', 'pane-slide-in-left', 'pane-slide-in-right', 'instant');
      }
    });

    currentPane.classList.remove('instant', 'pane-slide-out-left', 'pane-slide-out-right', 'pane-slide-in-left', 'pane-slide-in-right');
    targetPane.classList.remove('instant', 'pane-slide-out-left', 'pane-slide-out-right', 'pane-slide-in-left', 'pane-slide-in-right');

    // 2. Disparar AMBAS animaciones al mismo tiempo:
    // Saliente hacia la izquierda/derecha MIENTRAS entrante entra desde la derecha/izquierda
    currentPane.classList.add(outClass);
    targetPane.classList.add('active', inClass);

    // 3. Actualizar número de paso en el stepper y botones de navegación de inmediato
    // Los botones y el stepper NO se mueven, solo actualizan su estado/texto
    State.wizardStep = step;
    updateWizardUIControls();
    manageStepVideos(step);

    // 4. Esperar exactamente a que termine la animación simultánea (750ms)
    await new Promise(r => setTimeout(r, 750));

    // 5. Limpieza final: dejar únicamente la nueva pestaña como activa y visible
    currentPane.classList.remove('active', outClass, 'pane-slide-out-left', 'pane-slide-out-right');
    targetPane.classList.remove(inClass, 'pane-slide-in-left', 'pane-slide-in-right');

    if (step === 1) {
      refreshDisks();
    }

    isWizardStepTransitioning = false;
    document.body.classList.remove('nav-transitioning');
  }

  function updateWizardUIControls() {
    DOM.stepItems.forEach(item => {
      const step = parseInt(item.dataset.step);
      item.classList.toggle('active', step === State.wizardStep);
      item.classList.toggle('completed', step < State.wizardStep);
    });

    if (State.wizardStep === 1) {
      DOM.btnPrev.textContent = getT('nav_back_menu', '⬅ Volver al Menú');
    } else {
      DOM.btnPrev.textContent = getT('nav_back', '⬅ Anterior');
    }

    // EN EL PASO 6: SE OCULTA COMPLETAMENTE EL BOTÓN SIGUIENTE DEL FOOTER
    // (El usuario explícitamente pidió: "Quita el botón de comenzar la instalación del final")
    if (State.wizardStep === 6) {
      DOM.btnNext.style.display = 'none';
      updatePartitionVisuals();
    } else {
      DOM.btnNext.style.display = 'flex';
      DOM.btnNext.innerHTML = getT('nav_next', 'Siguiente ➡');
      if (State.wizardStep === 1) {
        const isDiskValid = State.selectedDisk && State.totalDiskGb >= MIN_DRIVE_GB;
        DOM.btnNext.disabled = (!isDiskValid || !State.lockConfirmed);
      } else {
        DOM.btnNext.disabled = false;
      }
    }
  }

  function updateWizardUI() {
    const panes = document.querySelectorAll('.wizard-step-pane');
    panes.forEach(pane => {
      const isActive = (pane.dataset.step == State.wizardStep);
      pane.classList.remove('fade-out', 'pane-slide-out-left', 'pane-slide-out-right', 'pane-slide-in-left', 'pane-slide-in-right');
      pane.classList.toggle('active', isActive);
    });
    updateWizardUIControls();
  }

  window.selectDownloadMode = function(mode) {
    State.downloadMode = mode;
    if (DOM.cardModeAsync && DOM.cardModeClassic) {
      if (mode === 'ram') {
        DOM.cardModeAsync.classList.add('active');
        DOM.cardModeClassic.classList.remove('active');
        if (DOM.radioLblAsync) DOM.radioLblAsync.textContent = getT('dl_selected', 'Seleccionado');
        if (DOM.radioLblClassic) DOM.radioLblClassic.textContent = getT('dl_select', 'Seleccionar');
      } else {
        DOM.cardModeClassic.classList.add('active');
        DOM.cardModeAsync.classList.remove('active');
        if (DOM.radioLblClassic) DOM.radioLblClassic.textContent = getT('dl_selected', 'Seleccionado');
        if (DOM.radioLblAsync) DOM.radioLblAsync.textContent = getT('dl_select', 'Seleccionar');
      }
    }
  };

  // =========================================================================
  // 💾 DETECCIÓN DE DISCOS (USB E INTERNOS CON AVISO MODAL)
  // =========================================================================
  const MIN_DRIVE_GB = 7.0; // Mínimo de 8 GB comerciales

  let isRefreshingDisks = false;
  async function refreshDisks() {
    if (isRefreshingDisks) return;
    isRefreshingDisks = true;
    if (DOM.btnRefreshUsb) DOM.btnRefreshUsb.classList.add('spinning');
    // Solo mostrar texto de búsqueda si el desplegable está vacío
    if (DOM.usbSelect && (!State.disks || State.disks.length === 0)) {
      DOM.usbSelect.innerHTML = '<option value="">Buscando unidades disponibles...</option>';
    }
    try {
      const res = await window.hollowdrive.getDisks(State.showInternal);
      if (res && res.success && Array.isArray(res.disks)) {
        State.disks = res.disks;
        renderDiskOptions();
      } else {
        if (DOM.usbSelect && (!State.disks || State.disks.length === 0)) {
          DOM.usbSelect.innerHTML = '<option value="">No se encontraron unidades</option>';
        }
        onDiskSelected(null);
        updateWizardUI();
      }
    } catch (e) {
      console.error("Error obteniendo discos:", e);
      if (DOM.usbSelect && (!State.disks || State.disks.length === 0)) {
        DOM.usbSelect.innerHTML = '<option value="">Error al buscar unidades</option>';
      }
      onDiskSelected(null);
      updateWizardUI();
    } finally {
      isRefreshingDisks = false;
      if (DOM.btnRefreshUsb) {
        setTimeout(() => DOM.btnRefreshUsb.classList.remove('spinning'), 350);
      }
    }
  }

  function renderDiskOptions() {
    if (!DOM.usbSelect) return;
    DOM.usbSelect.innerHTML = '';

    if (!State.disks || State.disks.length === 0) {
      const opt = document.createElement('option');
      opt.value = '';
      opt.textContent = getT('usb_no_units', 'No se detectaron unidades disponibles');
      DOM.usbSelect.appendChild(opt);
      onDiskSelected(null);
      updateWizardUI();
      return;
    }

    const defaultOpt = document.createElement('option');
    defaultOpt.value = '';
    defaultOpt.textContent = getT('usb_select_prompt', '-- Selecciona una unidad USB --');
    DOM.usbSelect.appendChild(defaultOpt);

    State.disks.forEach(disk => {
      const opt = document.createElement('option');
      opt.value = String(disk.device);
      opt.textContent = disk.display || `[Disco ${disk.device}] ${disk.label} (${disk.size} GB)`;
      DOM.usbSelect.appendChild(opt);
    });

    // Mantener la selección previa si sigue existiendo y es válida, o auto-seleccionar si sólo hay un USB
    const existing = State.selectedDisk ? State.disks.find(d => String(d.device) === String(State.selectedDisk.device)) : null;
    if (existing) {
      DOM.usbSelect.value = String(existing.device);
      onDiskSelected(existing);
    } else if (State.disks.length === 1) {
      DOM.usbSelect.value = String(State.disks[0].device);
      onDiskSelected(State.disks[0]);
    } else {
      DOM.usbSelect.value = '';
      onDiskSelected(null);
    }

    updateWizardUI();
  }

  function onDiskSelected(disk) {
    State.selectedDisk = disk;
    if (disk && disk.size) {
      State.totalDiskGb = parseFloat(disk.size);

      // Aviso visual si el disco no alcanza el tamaño mínimo requerido
      if (DOM.usbWarningText) {
        if (State.totalDiskGb < MIN_DRIVE_GB) {
          DOM.usbWarningText.innerHTML = `⚠️ <strong style="color:var(--danger, #ff4444);">Capacidad insuficiente (${State.totalDiskGb} GB):</strong> HollowDrive requiere una unidad de al menos 8 GB para continuar.`;
          DOM.usbWarningText.style.color = 'var(--danger, #ff4444)';
        } else {
          DOM.usbWarningText.textContent = getT('usb_warning_desc', 'Todos los datos de la unidad seleccionada se eliminarán permanentemente.');
          DOM.usbWarningText.style.color = '';
        }
      }

      // Restricción dinámica de CachyOS si la unidad es menor a 28 GB (20 GB sistema + GRUB + Hollowdrive)
      if (DOM.optOsCachy) {
        if (State.totalDiskGb < 28.0) {
          DOM.optOsCachy.disabled = true;
          DOM.optOsCachy.textContent = "CachyOS (Requiere unidad ≥ 32 GB)";
          if (State.portableOs === 'cachyos') {
            State.portableOs = 'none';
            State.installCachy = false;
            if (DOM.selectPortableOs) DOM.selectPortableOs.value = 'none';
            if (DOM.cachyFlavorWrap) DOM.cachyFlavorWrap.style.display = 'none';
            if (DOM.cachySliderGroup) DOM.cachySliderGroup.style.display = 'none';
            if (DOM.legendCachyItem) DOM.legendCachyItem.style.display = 'none';
          }
        } else {
          DOM.optOsCachy.disabled = false;
          DOM.optOsCachy.textContent = getT('sys_opt_cachy', 'CachyOS (Arch Linux Optimizado)');
        }
      }

      rebalancePartitionsInitial();
    } else {
      State.totalDiskGb = 0;
      // Respetar la confirmación del usuario si ya la había marcado
      if (DOM.usbLockCheckbox) {
        State.lockConfirmed = DOM.usbLockCheckbox.checked;
      }
      if (DOM.usbWarningText) {
        DOM.usbWarningText.textContent = getT('usb_warning_desc', 'Todos los datos de la unidad seleccionada se eliminarán permanentemente.');
        DOM.usbWarningText.style.color = '';
      }
    }
    updateWizardUI();
  }

  DOM.usbSelect.addEventListener('change', (e) => {
    const rawVal = e.target.value;
    if (!rawVal) {
      onDiskSelected(null);
      return;
    }
    const val = parseInt(rawVal);
    const disk = State.disks.find(d => d.device === val) || null;
    onDiskSelected(disk);
  });

  DOM.usbLockCheckbox.addEventListener('change', (e) => {
    State.lockConfirmed = e.target.checked;
    updateWizardUI();
  });

  DOM.btnRefreshUsb.addEventListener('click', refreshDisks);

  // Toggle Discos Internos con Modal Cyberpunk (Sin browser confirm())
  DOM.chkShowInternal.addEventListener('click', (e) => {
    if (!State.showInternal) {
      e.preventDefault();
      openModal(DOM.modalInternalDanger);
    } else {
      State.showInternal = false;
      DOM.chkShowInternal.checked = false;
      refreshDisks();
    }
  });

  DOM.btnConfirmInternalModal.addEventListener('click', () => {
    closeModal(DOM.modalInternalDanger);
    State.showInternal = true;
    DOM.chkShowInternal.checked = true;
    refreshDisks();
  });

  function cancelInternalDangerModal() {
    closeModal(DOM.modalInternalDanger);
    State.showInternal = false;
    DOM.chkShowInternal.checked = false;
  }

  DOM.btnCancelInternalModal.addEventListener('click', cancelInternalDangerModal);
  DOM.btnCancelInternalModalX.addEventListener('click', cancelInternalDangerModal);

  // =========================================================================
  // 🎛️ OPCIONES DEL ASISTENTE
  // =========================================================================

  // Paso 2: Kit de Herramientas
  DOM.switchKit.addEventListener('click', () => {
    State.installKit = !State.installKit;
    DOM.switchKit.classList.toggle('active', State.installKit);
    rebalancePartitionsInitial();
  });

  // Paso 3: Batocera
  DOM.switchBatocera.addEventListener('click', () => {
    State.installBatocera = !State.installBatocera;
    DOM.switchBatocera.classList.toggle('active', State.installBatocera);
    rebalancePartitionsInitial();
  });

  DOM.btnBato64.addEventListener('click', () => {
    State.batoceraArch = 'x86_64';
    DOM.btnBato64.classList.add('active');
  });

  // Paso 4: Sistema Portable (Dropdown con Sistema Portable, Ninguno, y distros bloqueadas)
  DOM.selectPortableOs.addEventListener('change', (e) => {
    const val = e.target.value;
    State.portableOs = val;
    State.installCachy = (val === 'cachyos');

    if (DOM.cachyFlavorWrap) {
      DOM.cachyFlavorWrap.style.display = State.installCachy ? 'flex' : 'none';
    }
    if (DOM.cachySliderGroup) {
      DOM.cachySliderGroup.style.display = State.installCachy ? 'flex' : 'none';
    }
    if (DOM.legendCachyItem) {
      DOM.legendCachyItem.style.display = State.installCachy ? 'flex' : 'none';
    }

    rebalancePartitionsInitial();
  });

  DOM.btnCachyHypr.addEventListener('click', () => {
    State.cachyFlavor = 'hyprland';
    DOM.btnCachyHypr.classList.add('active');
    DOM.btnCachyKde.classList.remove('active');
  });

  // =========================================================================
  // 🎚️ LÓGICA DE PARTISIONADO REAL (HOLLOWDRIVE, SISTEMA, LIBRE)
  // =========================================================================
  function rebalancePartitionsInitial() {
    const total = State.totalDiskGb || 64.0;
    
    // Hollowdrive base: 10GB con el pack, 3GB sin el pack (+ 4.6GB si Batocera está activo)
    const minHollow = State.installKit ? 10.0 : 3.0;
    const batoGb = State.installBatocera ? 4.6 : 0.0;
    const reqHollow = minHollow + batoGb;
    
    const minSystem = State.installCachy ? 20.0 : 0.0;
    
    if (State.preserveSpace) {
      if (State.installCachy) {
        State.valCachyGb = Math.max(20.0, Math.min(32.0, total * 0.35));
        State.valHollowGb = Math.max(reqHollow, Math.min(total - State.valCachyGb - 5.0, total * 0.45));
        State.valLibreGb = Math.max(0.0, total - State.valHollowGb - State.valCachyGb);
      } else {
        State.valCachyGb = 0.0;
        const margenLibre = Math.max(5.0, total * 0.15);
        State.valLibreGb = margenLibre;
        State.valHollowGb = Math.max(reqHollow, total - State.valLibreGb);
      }
    } else {
      // Sin preservar espacio: Sistema (o Hollowdrive si no hay sistema) ocupa el 100% restante
      State.valLibreGb = 0.0;
      if (State.installCachy) {
        State.valHollowGb = Math.max(reqHollow, Math.min(total - minSystem, total * 0.45));
        State.valCachyGb = Math.max(minSystem, total - State.valHollowGb);
      } else {
        State.valCachyGb = 0.0;
        State.valHollowGb = total;
      }
    }

    // Ajustar límites de los sliders
    if (DOM.hollowSlider) {
      if (!State.installCachy && !State.preserveSpace) {
        DOM.hollowSlider.disabled = true;
        DOM.hollowSlider.min = total;
        DOM.hollowSlider.max = total;
        DOM.hollowSlider.value = total;
        DOM.hollowSlider.style.cursor = 'default';
        DOM.hollowSlider.title = 'HollowDrive ocupa el 100% de la unidad';
      } else {
        DOM.hollowSlider.disabled = false;
        DOM.hollowSlider.min = reqHollow;
        DOM.hollowSlider.max = Math.max(reqHollow + 2, total - minSystem);
        DOM.hollowSlider.value = State.valHollowGb;
        DOM.hollowSlider.style.cursor = 'pointer';
        DOM.hollowSlider.title = '';
      }
    }

    if (DOM.cachySlider) {
      DOM.cachySlider.min = 20.0;
      DOM.cachySlider.max = Math.max(20.0, total - reqHollow);
      DOM.cachySlider.value = State.valCachyGb;
    }

    updatePartitionVisuals();
  }

  // Switch Preservar Espacio Libre en USB
  DOM.switchPreserveSpace.addEventListener('click', () => {
    State.preserveSpace = !State.preserveSpace;
    DOM.switchPreserveSpace.classList.toggle('active', State.preserveSpace);
    rebalancePartitionsInitial();
  });

  if (DOM.hollowSlider) {
    DOM.hollowSlider.addEventListener('input', (e) => {
      if (!State.installCachy && !State.preserveSpace) {
        State.valHollowGb = State.totalDiskGb;
        DOM.hollowSlider.value = State.totalDiskGb;
        updatePartitionVisuals();
        return;
      }
      const total = State.totalDiskGb;
      let newH = parseFloat(e.target.value);
      
      if (!State.preserveSpace) {
        if (State.installCachy) {
          State.valHollowGb = newH;
          State.valCachyGb = Math.max(20.0, total - newH);
          State.valLibreGb = 0.0;
          if (DOM.cachySlider) {
            DOM.cachySlider.value = State.valCachyGb;
          }
        }
      } else {
        if (State.installCachy) {
          if (newH + State.valCachyGb > total) {
            State.valCachyGb = Math.max(20.0, total - newH);
            if (DOM.cachySlider) {
              DOM.cachySlider.value = State.valCachyGb;
            }
          }
        }
        State.valHollowGb = newH;
        State.valLibreGb = Math.max(0.0, total - State.valHollowGb - (State.installCachy ? State.valCachyGb : 0.0));
      }

      updatePartitionVisuals();
    });
  }

  if (DOM.cachySlider) {
    DOM.cachySlider.addEventListener('input', (e) => {
      const total = State.totalDiskGb;
      let newC = parseFloat(e.target.value);
      const minHollow = (State.installKit ? 10.0 : 3.0) + (State.installBatocera ? 4.6 : 0.0);

      if (!State.preserveSpace) {
        State.valCachyGb = newC;
        State.valHollowGb = Math.max(minHollow, total - newC);
        State.valLibreGb = 0.0;
        if (DOM.hollowSlider) {
          DOM.hollowSlider.value = State.valHollowGb;
        }
      } else {
        if (State.valHollowGb + newC > total) {
          State.valHollowGb = Math.max(minHollow, total - newC);
          if (DOM.hollowSlider) {
            DOM.hollowSlider.value = State.valHollowGb;
          }
        }
        State.valCachyGb = newC;
        State.valLibreGb = Math.max(0.0, total - State.valHollowGb - State.valCachyGb);
      }

      updatePartitionVisuals();
    });
  }

  function updatePartitionVisuals() {
    if (DOM.partitionSlidersGrid) {
      DOM.partitionSlidersGrid.classList.toggle('single-slider', !State.installCachy);
    }
    if (DOM.cachySliderGroup) {
      DOM.cachySliderGroup.style.display = State.installCachy ? 'flex' : 'none';
    }
    if (DOM.legendCachyItem) {
      DOM.legendCachyItem.style.display = State.installCachy ? 'flex' : 'none';
    }

    if (!DOM.partitionBar || !State.selectedDisk) return;

    const total = State.totalDiskGb || 64.0;
    const txtTotal = getT('part_total', 'Total:');
    const nameHollow = getT('part_hollow', 'Hollowdrive:').replace(':', '').trim();
    const nameSystem = getT('part_system', 'Sistema:').replace(':', '').trim();
    const nameLibre = getT('part_libre', 'Libre:').replace(':', '').trim();

    if (DOM.diskTotalLabel) {
      DOM.diskTotalLabel.textContent = `${txtTotal} ${total.toFixed(1)} GB`;
    }

    const showLibre = Boolean(State.preserveSpace && State.valLibreGb > 0.05);

    let pHollow = 0;
    let pCachy = 0;
    let pLibre = 0;

    if (!showLibre) {
      // Sin preservar espacio: Hollowdrive y Sistema ocupan exactamente el 100% de la barra
      pLibre = 0;
      if (State.installCachy) {
        pHollow = Math.max(5, (State.valHollowGb / total) * 100);
        pCachy = Math.max(5, 100 - pHollow);
      } else {
        pHollow = 100;
        pCachy = 0;
      }
    } else {
      pHollow = Math.max(5, (State.valHollowGb / total) * 100);
      pCachy = State.installCachy ? Math.max(5, (State.valCachyGb / total) * 100) : 0;
      pLibre = Math.max(0, 100 - (pHollow + pCachy));
    }

    // Los sectores dentro de la barra SOLO muestran el color, SIN letras ni texto
    DOM.partitionBar.innerHTML = `
      <div class="partition-slice slice-hollow" style="width: ${pHollow}%;"></div>
      ${State.installCachy && pCachy > 0 ? `<div class="partition-slice slice-cachy" style="width: ${pCachy}%;"></div>` : ''}
      ${showLibre && pLibre > 0 ? `<div class="partition-slice slice-free" style="width: ${pLibre}%;"></div>` : ''}
    `;

    // Los valores en GB SOLO se muestran en la leyenda
    if (DOM.legendHollow) {
      DOM.legendHollow.textContent = `${nameHollow}: ${State.valHollowGb.toFixed(1)} GB`;
    }
    if (DOM.legendCachy) {
      DOM.legendCachy.textContent = `${nameSystem}: ${State.valCachyGb.toFixed(1)} GB`;
    }
    if (DOM.legendLibre) {
      DOM.legendLibre.textContent = `${nameLibre}: ${State.valLibreGb.toFixed(1)} GB`;
    }
    if (DOM.legendLibreItem) {
      DOM.legendLibreItem.style.display = showLibre ? 'flex' : 'none';
    }
  }

  // =========================================================================
  // ⚡ EJECUCIÓN DEL ASISTENTE Y PROCESO DE INSTALACIÓN
  // =========================================================================
  async function handleWizardNext(e) {
    if (e && e.preventDefault) e.preventDefault();
    if (e && e.stopPropagation) e.stopPropagation();
    if (isWizardStepTransitioning || isScreenTransitioning) return;
    if (State.wizardStep === 1) {
      const isDiskValid = State.selectedDisk && State.selectedDisk.device !== undefined && State.selectedDisk.device !== null && State.totalDiskGb >= MIN_DRIVE_GB;
      if (!isDiskValid) {
        showCustomAlert("SELECCIONA UNA UNIDAD", "Por favor, selecciona una unidad USB válida de al menos 8 GB para continuar.");
        return;
      }
      if (!State.lockConfirmed) {
        showCustomAlert("CONFIRMACIÓN REQUERIDA", "Por favor, marca la casilla de confirmación para autorizar el formateo del dispositivo antes de continuar.");
        return;
      }
    }
    if (State.wizardStep < 6) {
      await setWizardStep(State.wizardStep + 1);
    }
  }

  if (DOM.btnNext) {
    DOM.btnNext.addEventListener('click', handleWizardNext);
  }

  // Permitir navegar directamente pulsando en los pasos del stepper si ya se seleccionó unidad
  if (DOM.stepItems) {
    DOM.stepItems.forEach(item => {
      item.addEventListener('click', async () => {
        if (State.isInstalling) return;
        const targetStep = parseInt(item.dataset.step);
        if (isNaN(targetStep) || targetStep === State.wizardStep) return;
        if (targetStep > 1 && State.wizardStep === 1) {
          const isDiskValid = State.selectedDisk && State.selectedDisk.device !== undefined && State.selectedDisk.device !== null && State.totalDiskGb >= MIN_DRIVE_GB;
          if (!isDiskValid || !State.lockConfirmed) return;
        }
        await setWizardStep(targetStep);
      });
    });
  }

  async function handleWizardPrev(e) {
    if (e && e.preventDefault) e.preventDefault();
    if (e && e.stopPropagation) e.stopPropagation();
    if (isWizardStepTransitioning || isScreenTransitioning) return;
    const isCompleted = !State.isInstalling && ((DOM.completionSummaryCard && DOM.completionSummaryCard.style.display !== 'none') || (DOM.simpleGratitudeCard && DOM.simpleGratitudeCard.style.display !== 'none'));
    if (State.wizardStep <= 1 || isCompleted) {
      await setScreen('hub');
      return;
    }
    await setWizardStep(State.wizardStep - 1);
  }

  if (DOM.btnPrev) {
    DOM.btnPrev.addEventListener('click', handleWizardPrev);
  }

  // Botón gráfico instalar.png y fila completa (activador en el paso 5)
  if (DOM.btnStartInstallImg) {
    DOM.btnStartInstallImg.addEventListener('click', handleStartInstallClick);
  }
  if (DOM.btnInstalarRow) {
    DOM.btnInstalarRow.addEventListener('click', handleStartInstallClick);
  }

  async function handleStartInstallClick() {
    if (State.isInstalling) return;
    if (!State.selectedDisk) {
      await showCustomAlert("UNIDAD NO SELECCIONADA", "Por favor, selecciona una unidad USB en el Paso 1 antes de comenzar la instalación.");
      setWizardStep(1);
      return;
    }

    const isInternal = State.selectedDisk.display?.includes('[INT]');
    if (isInternal) {
      openModal(DOM.lockDialogOverlay);
      DOM.lockInputText.value = '';
      DOM.lockInputText.focus();
    } else {
      if (DOM.confirmInstallMsg) {
        DOM.confirmInstallMsg.innerHTML = `
          <div class="confirm-install-prompt">
            ¿Deseas iniciar la instalación real de HollowDrive en la siguiente unidad?
          </div>
          <div class="confirm-target-box">
            <span class="confirm-target-label">Unidad de Destino Seleccionada</span>
            <div class="confirm-target-name">${State.selectedDisk.display || 'Unidad seleccionada'}</div>
          </div>
          <div class="confirm-warning-box">
            <span class="confirm-warning-title">ATENCIÓN:</span>
            <span class="confirm-warning-desc">Todos los datos de la unidad elegida serán eliminados por completo y de forma irreversible.</span>
          </div>
        `;
      }
      openModal(DOM.modalConfirmInstall);
    }
  }

  function cancelInstallModal() {
    closeModal(DOM.modalConfirmInstall);
  }

  DOM.btnCancelInstallModal.addEventListener('click', cancelInstallModal);
  DOM.btnCancelInstallModalX.addEventListener('click', cancelInstallModal);

  DOM.btnExecuteInstallConfirmed.addEventListener('click', () => {
    closeModal(DOM.modalConfirmInstall);
    startFullInstallation();
  });

  DOM.btnCancelLock.addEventListener('click', () => {
    closeModal(DOM.lockDialogOverlay);
  });

  DOM.btnConfirmLock.addEventListener('click', async () => {
    if (DOM.lockInputText.value.trim().toUpperCase() === 'BORRAR') {
      closeModal(DOM.lockDialogOverlay);
      startFullInstallation();
    } else {
      await showCustomAlert("TEXTO INCORRECTO", "Texto incorrecto. Debes escribir 'BORRAR' en mayúsculas.");
    }
  });

  // Modal Cancelar Instalación en Curso
  if (DOM.btnCancelInstallProcess) {
    DOM.btnCancelInstallProcess.addEventListener('click', () => {
      openModal(DOM.modalConfirmCancel);
    });
  }

  function dismissAbortModal() {
    closeModal(DOM.modalConfirmCancel);
  }

  if (DOM.btnStayInInstall) {
    DOM.btnStayInInstall.addEventListener('click', dismissAbortModal);
  }
  if (DOM.btnCancelAbortModalX) {
    DOM.btnCancelAbortModalX.addEventListener('click', dismissAbortModal);
  }

  if (DOM.btnExecuteAbortConfirmed) {
    DOM.btnExecuteAbortConfirmed.addEventListener('click', async () => {
      closeModal(DOM.modalConfirmCancel);
      logTerminal("Cancelando instalación por petición del usuario...", "warn");
      try {
        await window.hollowdrive.cancelInstallation();
      } catch (e) {
        console.error("Error al cancelar instalación:", e);
      }
      resetInstallProcessUI();
    });
  }

  // Toggle Plegable de la Consola Terminal (por defecto visible)
  let isTerminalVisible = true;
  if (DOM.btnToggleTerminal) {
    DOM.btnToggleTerminal.addEventListener('click', () => {
      isTerminalVisible = !isTerminalVisible;
      if (DOM.terminalConsole) {
        DOM.terminalConsole.style.display = isTerminalVisible ? 'block' : 'none';
      }
      if (DOM.terminalToggleIcon) {
        DOM.terminalToggleIcon.textContent = isTerminalVisible ? '▼' : '▲';
      }
      if (DOM.terminalToggleText) {
        DOM.terminalToggleText.textContent = isTerminalVisible ? 'Ocultar registro' : 'Mostrar registro';
      }
    });
  }

  // =========================================================================
  // ⏱️ MOTOR PREDICTIVO DE ESTIMACIÓN DE TIEMPO Y CRONÓMETRO REACTIVO (1 Hz)
  // =========================================================================
  function formatClockTime(sec) {
    if (sec === null || sec === undefined || isNaN(sec) || sec < 0) return "--:--";
    sec = Math.round(sec);
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    if (h > 0) {
      return `${h}:${m < 10 ? '0' : ''}${m}:${s < 10 ? '0' : ''}${s}`;
    }
    return `${m < 10 ? '0' : ''}${m}:${s < 10 ? '0' : ''}${s}`;
  }

  const TimeTickerEngine = {
    plan: null,
    intervalId: null,
    stepIdx: 0,
    taskElapsed: 0,
    totalElapsed: 0,
    taskProgress: 0,
    currentStepEst: 28,
    totalRemaining: 0,

    envDeviation: 1.0,

    buildClientPlan() {
      const isCachy = !!State.installCachy;
      const isPack = !!State.installKit;
      const isBato = !!State.installBatocera;
      const mode = State.downloadMode || 'ram';

      const diskLabel = (State.selectedDisk && State.selectedDisk.label) ? State.selectedDisk.label.toUpperCase() : '';
      const isFast = /3\.2|3\.1|BAR PLUS|EXTREME|PRO|SSD|NVME/.test(diskLabel);
      const isUsb2 = State.totalDiskGb <= 16 && !/3\./.test(diskLabel);

      let ventoyEst = isFast ? 18 : (isUsb2 ? 48 : 28);
      let packEst = isFast ? 380 : (isUsb2 ? 1250 : 946);
      let batoEst = isFast ? 140 : (isUsb2 ? 550 : 487);
      let grubPartEst = isFast ? 6 : (isUsb2 ? 14 : 10);
      let grubFlashEst = isFast ? 14 : (isUsb2 ? 50 : 32);
      let cachyPartEst = isFast ? 16 : (isUsb2 ? 32 : 26);
      let cachyFlashEst = isFast ? 320 : (isUsb2 ? 1200 : 809);

      if (mode === 'disco') {
        packEst = Math.round(packEst * 1.3);
        batoEst = Math.round(batoEst * 1.25);
        grubFlashEst = Math.round(grubFlashEst * 1.2);
        cachyFlashEst = Math.round(cachyFlashEst * 1.25);
      }

      const steps = [];
      let num = 1;
      steps.push({ step_num: num++, id: 'ventoy', title: 'Estructura Core (Ventoy)', est_sec: ventoyEst, type: 'disk_format' });
      if (isPack) {
        steps.push({ step_num: num++, id: 'pack_hollow', title: 'Pack Utils HollowDrive', est_sec: packEst, type: 'download_extract' });
      } else {
        steps.push({ step_num: num++, id: 'ventoy_base', title: 'Configuración Base Ventoy', est_sec: 4, type: 'local_extract' });
      }
      if (isBato) {
        steps.push({ step_num: num++, id: 'batocera_img', title: 'Sistema Batocera OS', est_sec: batoEst, type: 'download_file' });
      }
      if (isCachy) {
        steps.push({ step_num: num++, id: 'grub_part', title: 'Creación Bootloader GRUB', est_sec: grubPartEst, type: 'diskpart' });
        steps.push({ step_num: num++, id: 'grub_extract', title: 'Inyección Bootloader GRUB', est_sec: grubFlashEst, type: 'raw_flash' });
        steps.push({ step_num: num++, id: 'cachy_part', title: 'Creación Partición CachyOS', est_sec: cachyPartEst, type: 'diskpart' });
        steps.push({ step_num: num++, id: 'cachy_extract', title: 'Volcado Sistema CachyOS', est_sec: cachyFlashEst, type: 'raw_flash' });
      }

      const totalSec = steps.reduce((acc, s) => acc + s.est_sec, 0);
      return {
        total_steps: steps.length,
        total_est_sec: totalSec,
        steps: steps
      };
    },

    start(serverPlan = null) {
      this.stop();
      this.plan = serverPlan || this.buildClientPlan();
      this.stepIdx = 0;
      this.taskElapsed = 0;
      this.totalElapsed = 0;
      this.taskProgress = 0;
      this.envDeviation = 1.0;
      this.isCalibrated = false;
      this.currentStepEst = (this.plan.steps[0] && this.plan.steps[0].est_sec) || 28;
      this.totalRemaining = this.plan.total_est_sec;

      this.render();

      this.intervalId = setInterval(() => {
        this.tick();
      }, 1000);
    },

    syncPlan(serverPlan) {
      if (!serverPlan || !serverPlan.steps) return;
      this.plan = serverPlan;
      if (serverPlan.profile_source === 'micro_probed_physical') {
        this.isCalibrated = true;
      }
      if (this.plan.steps[this.stepIdx]) {
        this.currentStepEst = this.plan.steps[this.stepIdx].est_sec;
      }
      this.recalcTotalRemaining();
      this.render();
    },

    setStep(cur, tot, title, est_sec) {
      const nextIdx = Math.max(0, cur - 1);
      // Calibración adaptativa entre transiciones de fase:
      if (nextIdx > this.stepIdx && this.taskElapsed > 5 && this.currentStepEst > 0) {
        const stepRatio = Math.max(0.4, Math.min(2.5, this.taskElapsed / this.currentStepEst));
        this.envDeviation = (this.envDeviation * 0.6) + (stepRatio * 0.4);
      }

      this.stepIdx = nextIdx;
      this.taskElapsed = 0;
      this.taskProgress = 0;
      if (est_sec && est_sec > 0) {
        this.currentStepEst = est_sec;
      } else if (this.plan && this.plan.steps[this.stepIdx]) {
        this.currentStepEst = this.plan.steps[this.stepIdx].est_sec;
      }
      this.recalcTotalRemaining();
      this.render();
    },

    setProgress(p) {
      this.taskProgress = Math.max(0, Math.min(1.0, p || 0));
      this.recalcTotalRemaining();
    },

    recalcTotalRemaining() {
      if (!this.plan || !this.plan.steps) return;

      // 1. Estimación analítica base para el paso actual
      let remAnalytical = 0;
      if (this.taskProgress > 0) {
        remAnalytical = Math.max(0, Math.round(this.currentStepEst * (1 - this.taskProgress)));
      } else {
        remAnalytical = Math.max(0, this.currentStepEst - this.taskElapsed);
      }

      let remCurrent = remAnalytical;

      // 2. Fusión Bayesiana con observación empírica de velocidad real:
      // Cuando la tarea ya tiene cierto rodaje (>8% y >5 seg), evaluamos el ritmo real observado
      if (this.taskProgress >= 0.08 && this.taskElapsed >= 5) {
        const projectedTotal = this.taskElapsed / this.taskProgress;
        const remObserved = Math.max(2, Math.round(projectedTotal - this.taskElapsed));
        const liveStepRatio = Math.max(0.4, Math.min(2.2, projectedTotal / this.currentStepEst));
        
        // Suavizado exponencial del factor ambiental (red + USB)
        this.envDeviation = (this.envDeviation * 0.85) + (liveStepRatio * 0.15);

        // Peso bayesiano: aumenta suavemente de 0 a 0.85 a medida que avanza la tarea
        const weight = Math.min(0.85, Math.max(0, (this.taskProgress - 0.08) * 1.5));
        remCurrent = Math.round((1 - weight) * remAnalytical + weight * remObserved);
      }

      // 3. Amortiguación asintótica si la tarea excede el tiempo estimado (evita congelar a 00:00 o negativos)
      if (this.taskElapsed >= this.currentStepEst) {
        const overtime = this.taskElapsed - this.currentStepEst;
        remCurrent = Math.max(4, Math.round(this.currentStepEst / (1 + (overtime / 15))));
      }

      // 4. Proyección adaptativa a los pasos futuros:
      let remFuture = 0;
      const deviationFactor = 1 + (this.envDeviation - 1) * 0.75; // 75% de propagación amortiguada

      for (let i = this.stepIdx + 1; i < this.plan.steps.length; i++) {
        const step = this.plan.steps[i];
        const baseEst = step.est_sec || 0;
        const isIoHeavy = step.type === 'download_extract' || step.type === 'download_file' || step.type === 'raw_flash';
        
        if (isIoHeavy) {
          remFuture += Math.round(baseEst * deviationFactor);
        } else {
          remFuture += baseEst;
        }
      }

      this.totalRemaining = remCurrent + remFuture;
    },

    tick() {
      this.taskElapsed++;
      this.totalElapsed++;
      this.recalcTotalRemaining();
      this.render();
    },

    render() {
      if (DOM.metricTaskTime) {
        DOM.metricTaskTime.textContent = formatClockTime(this.taskElapsed);
      }
      if (DOM.metricTaskTimeEst) {
        const estStr = formatClockTime(this.currentStepEst);
        DOM.metricTaskTimeEst.textContent = (this.taskElapsed > this.currentStepEst) 
          ? `Est: ~${estStr} (Ajustando)`
          : `Est: ~${estStr}`;
      }

      const isPreparationWindow = (this.totalElapsed < 32 && !this.isCalibrated);
      if (DOM.metricEta) {
        DOM.metricEta.textContent = isPreparationWindow ? "Calculando..." : formatClockTime(this.totalRemaining);
      }
      if (DOM.metricTotalElapsed) {
        DOM.metricTotalElapsed.textContent = `Transcurrido: ${formatClockTime(this.totalElapsed)}`;
      }

      if (DOM.metricStepSub && this.plan) {
        const tot = this.plan.total_steps || this.plan.steps.length;
        DOM.metricStepSub.textContent = `Paso ${this.stepIdx + 1} de ${tot}`;
      }

      // Timer central en Vista Simple con dígitos transparentes y glow:
      // Durante la ventana de preparación inicial, muestra "--:--" y "Calculando..." con puntos animados.
      // Una vez calibrado el hardware, muestra el tiempo restante con dígitos luminosos y "TIEMPO RESTANTE".
      if (DOM.simpleTimerDigits && DOM.simpleTimerSub) {
        if (!isPreparationWindow && this.totalRemaining > 0) {
          DOM.simpleTimerDigits.textContent = formatClockTime(this.totalRemaining);
          DOM.simpleTimerSub.textContent = getT('simple_time_remaining', 'TIEMPO RESTANTE');
        } else {
          DOM.simpleTimerDigits.textContent = '--:--';
          DOM.simpleTimerSub.innerHTML = 'Calculando<span class="dots-animation"></span>';
        }
      }
    },

    stop() {
      if (this.intervalId) {
        clearInterval(this.intervalId);
        this.intervalId = null;
      }
    }
  };

  // =========================================================================
  // ⚡ GESTIÓN DE VISTA SIMPLE VS DETALLADA DE LA INSTALACIÓN
  // =========================================================================
  const RING_OUTER_CIRCUMFERENCE = 691.15; // r = 110 (2 * pi * 110)
  const RING_INNER_CIRCUMFERENCE = 578.05; // r = 92  (2 * pi * 92)
  const RING_CIRCUMFERENCE = 691.15;

  function updateSimpleProgress(pct) {
    const cleanPct = Math.max(0, Math.min(100, Math.round(pct || 0)));
    const ringSvg = DOM.simpleRingWrap ? DOM.simpleRingWrap.querySelector('.simple-progress-ring') : null;

    if (cleanPct < 1 && State.isInstalling) {
      // Mientras esté en 0% durante la instalación, el aro rota dinámicamente con arco elástico
      if (ringSvg && !ringSvg.classList.contains('ring-spinner-active')) {
        ringSvg.classList.add('ring-spinner-active');
      }
    } else {
      // En cuanto alcanza al menos 1% o finaliza: transición suave de animado a estático
      if (ringSvg && ringSvg.classList.contains('ring-spinner-active')) {
        ringSvg.classList.remove('ring-spinner-active');
      }
      if (DOM.simpleRingFillOuter) {
        const offset = RING_OUTER_CIRCUMFERENCE - (cleanPct / 100) * RING_OUTER_CIRCUMFERENCE;
        DOM.simpleRingFillOuter.style.strokeDasharray = `${RING_OUTER_CIRCUMFERENCE} ${RING_OUTER_CIRCUMFERENCE}`;
        DOM.simpleRingFillOuter.style.strokeDashoffset = offset.toFixed(2);
      }
    }

    if (DOM.simpleCenterPct) {
      DOM.simpleCenterPct.textContent = `${cleanPct}%`;
    }
  }

  function updateSimpleTaskProgress(taskProg) {
    const p = Math.max(0, Math.min(1, taskProg || 0));
    if (DOM.simpleRingFillInner) {
      const offset = RING_INNER_CIRCUMFERENCE - p * RING_INNER_CIRCUMFERENCE;
      DOM.simpleRingFillInner.style.strokeDasharray = `${RING_INNER_CIRCUMFERENCE} ${RING_INNER_CIRCUMFERENCE}`;
      DOM.simpleRingFillInner.style.strokeDashoffset = offset.toFixed(2);
    }
  }

  function setInstallViewMode(mode) {
    State.installViewMode = mode;
    try {
      localStorage.setItem('hollowdrive_install_view_mode', mode);
    } catch (_) {}

    if (DOM.btnModeSimple) DOM.btnModeSimple.classList.toggle('active', mode === 'simple');
    if (DOM.btnModeDetailed) DOM.btnModeDetailed.classList.toggle('active', mode === 'detailed');

    if (DOM.installViewSimple && DOM.installViewDetailed) {
      if (mode === 'simple') {
        DOM.installViewSimple.style.display = 'flex';
        DOM.installViewDetailed.style.display = 'none';
      } else {
        DOM.installViewSimple.style.display = 'none';
        DOM.installViewDetailed.style.display = 'block';
      }
    }
  }

  if (DOM.btnModeSimple) {
    DOM.btnModeSimple.addEventListener('click', () => setInstallViewMode('simple'));
  }
  if (DOM.btnModeDetailed) {
    DOM.btnModeDetailed.addEventListener('click', () => setInstallViewMode('detailed'));
  }

  function resetInstallProcessUI() {
    State.isInstalling = false;
    document.body.classList.remove('is-installing-active');
    TimeTickerEngine.stop();

    if (DOM.installModeToggle) DOM.installModeToggle.style.display = 'none';
    if (DOM.simpleGratitudeCard) {
      DOM.simpleGratitudeCard.style.display = 'none';
      DOM.simpleGratitudeCard.classList.remove('fade-out', 'fade-in');
    }
    if (DOM.simpleMonitorCard) {
      DOM.simpleMonitorCard.style.display = 'none';
      DOM.simpleMonitorCard.classList.remove('fade-out', 'fade-in');
    }
    if (DOM.installMonitorCard) {
      DOM.installMonitorCard.style.display = 'none';
      DOM.installMonitorCard.classList.remove('fade-out', 'fade-in');
    }
    if (DOM.simpleRingWrap) DOM.simpleRingWrap.style.display = 'none';
    if (DOM.simpleStatusInfo) DOM.simpleStatusInfo.style.display = 'none';
    if (DOM.simpleSuccessTick) DOM.simpleSuccessTick.style.display = 'none';
    if (DOM.simpleCompletionZone) DOM.simpleCompletionZone.style.display = 'none';
    if (DOM.simpleCenterPctWrap) DOM.simpleCenterPctWrap.style.display = 'none';
    if (DOM.simpleCenterPct) DOM.simpleCenterPct.textContent = '0%';
    if (DOM.simpleBottomTimerCard) DOM.simpleBottomTimerCard.style.display = 'none';
    if (DOM.simpleTimerDigits) DOM.simpleTimerDigits.textContent = '--:--';
    if (DOM.simpleTimerSub) DOM.simpleTimerSub.innerHTML = 'Calculando<span class="dots-animation"></span>';
    if (DOM.simpleHollowBottomWrap) DOM.simpleHollowBottomWrap.style.display = 'none';
    if (DOM.simpleHollowGif) {
      DOM.simpleHollowGif.style.display = 'none';
      DOM.simpleHollowGif.className = 'simple-hollow-gif mirror-mode';
    }
    if (DOM.simpleRingWrap) {
      const ringSvg = DOM.simpleRingWrap.querySelector('.simple-progress-ring');
      if (ringSvg) ringSvg.classList.remove('ring-spinner-active', 'ring-windows-spin', 'ring-intro-spin');
    }
    updateSimpleProgress(0);
    updateSimpleTaskProgress(0);

    if (DOM.taskProgressBarWrap) DOM.taskProgressBarWrap.style.display = 'flex';
    if (DOM.totalProgressBarWrap) DOM.totalProgressBarWrap.style.display = 'flex';
    if (DOM.completionSummaryCard) DOM.completionSummaryCard.style.display = 'none';

    // Restaurar pantalla de particionado limpia y funcional
    if (DOM.partitionSetupCard) {
      DOM.partitionSetupCard.style.display = 'flex';
      DOM.partitionSetupCard.classList.remove('fade-out');
    }
    if (DOM.btnInstalarRow) {
      DOM.btnInstalarRow.style.display = 'flex';
    }
    if (DOM.btnCancelInstallProcess) DOM.btnCancelInstallProcess.style.display = 'none';
    if (DOM.btnPrev) {
      DOM.btnPrev.style.display = 'inline-flex';
      DOM.btnPrev.textContent = getT('nav_back', '⬅ Anterior');
      DOM.btnPrev.disabled = false;
    }
    if (DOM.btnNext) {
      DOM.btnNext.style.display = 'none';
    }
    DOM.stepperWrap.style.pointerEvents = 'auto';

    if (DOM.taskProgressBar) DOM.taskProgressBar.style.width = '0%';
    if (DOM.taskProgressPct) DOM.taskProgressPct.textContent = '0%';
    if (DOM.simplePhasePct) DOM.simplePhasePct.textContent = '0%';
    if (DOM.totalProgressBar) DOM.totalProgressBar.style.width = '0%';
    if (DOM.totalProgressPct) DOM.totalProgressPct.textContent = '0%';
    if (DOM.metricStep) DOM.metricStep.textContent = 'Iniciando...';
    if (DOM.metricStepSub) DOM.metricStepSub.textContent = 'Paso 1 de 1';
    if (DOM.metricSpeed) DOM.metricSpeed.textContent = '-- MB/s';
    if (DOM.metricSpeedSub) DOM.metricSpeedSub.textContent = 'Transferencia';
    if (DOM.metricTaskTime) DOM.metricTaskTime.textContent = '00:00';
    if (DOM.metricTaskTimeEst) DOM.metricTaskTimeEst.textContent = 'Est: --:--';
    if (DOM.metricEta) DOM.metricEta.textContent = '--:--';

    updatePartitionVisuals();
  }

  // Botón "Siguiente ➜" en Vista Simple: desvanece el monitor y presenta la tarjeta del caballero con la moneda (~2s)
  if (DOM.btnSimpleNext) {
    DOM.btnSimpleNext.addEventListener('click', () => {
      if (DOM.installModeToggle) DOM.installModeToggle.style.display = 'none';
      if (DOM.btnPrev) DOM.btnPrev.style.display = 'none';
      if (DOM.simpleMonitorCard) {
        DOM.simpleMonitorCard.classList.remove('fade-in');
        DOM.simpleMonitorCard.classList.add('fade-out');
        setTimeout(() => {
          DOM.simpleMonitorCard.style.display = 'none';
          if (DOM.simpleGratitudeCard) {
            DOM.simpleGratitudeCard.style.display = 'flex';
            DOM.simpleGratitudeCard.classList.remove('fade-out');
            DOM.simpleGratitudeCard.classList.add('fade-in');
          }
        }, 950);
      }
    });
  }

  // Botón "Volver al Menú" desde la tarjeta de agradecimiento
  if (DOM.btnGratitudeBackMenu) {
    DOM.btnGratitudeBackMenu.addEventListener('click', () => {
      resetInstallProcessUI();
      setScreen('hub');
    });
  }

  async function startFullInstallation() {
    State.isInstalling = true;
    document.body.classList.add('is-installing-active');

    // 1. Ocultar el botón brillante de INSTALAR durante la instalación
    if (DOM.btnInstalarRow) DOM.btnInstalarRow.style.display = 'none';

    // 2. Reemplazar "Anterior" por "Cancelar instalación"
    if (DOM.btnPrev) DOM.btnPrev.style.display = 'none';
    if (DOM.btnNext) DOM.btnNext.style.display = 'none';
    if (DOM.btnCancelInstallProcess) DOM.btnCancelInstallProcess.style.display = 'inline-flex';

    DOM.stepperWrap.style.pointerEvents = 'none';

    // 3. Transición cinematográfica lenta (~2s): fade-out suave de la tarjeta de configuración
    if (DOM.partitionSetupCard) {
      DOM.partitionSetupCard.classList.add('fade-out');
    }

    setTimeout(() => {
      if (DOM.partitionSetupCard) {
        DOM.partitionSetupCard.style.display = 'none';
        DOM.partitionSetupCard.classList.remove('fade-out');
      }
      DOM.installMonitorCard.style.display = 'flex';
      DOM.installMonitorCard.classList.remove('fade-out');
      DOM.installMonitorCard.classList.add('fade-in');

      // 4. Activar y preparar vista según la preferencia (por defecto simple)
      if (DOM.installModeToggle) DOM.installModeToggle.style.display = 'flex';
      setInstallViewMode(State.installViewMode || 'simple');

      if (DOM.simpleMonitorCard) {
        DOM.simpleMonitorCard.style.display = 'flex';
        DOM.simpleMonitorCard.classList.remove('fade-out');
        DOM.simpleMonitorCard.classList.add('fade-in');
      }
      if (DOM.simpleGratitudeCard) DOM.simpleGratitudeCard.style.display = 'none';
      if (DOM.simpleCompletionZone) DOM.simpleCompletionZone.style.display = 'none';
      if (DOM.simpleSuccessTick) DOM.simpleSuccessTick.style.display = 'none';
      if (DOM.simpleRingWrap) DOM.simpleRingWrap.style.display = 'flex';
      if (DOM.simpleStatusInfo) DOM.simpleStatusInfo.style.display = 'flex';
      if (DOM.simpleCenterPctWrap) DOM.simpleCenterPctWrap.style.display = 'flex';
      if (DOM.simpleCenterPct) DOM.simpleCenterPct.textContent = '0%';
      if (DOM.simpleBottomTimerCard) DOM.simpleBottomTimerCard.style.display = 'inline-flex';
      if (DOM.simpleTimerDigits) DOM.simpleTimerDigits.textContent = '--:--';
      if (DOM.simpleTimerSub) DOM.simpleTimerSub.innerHTML = 'Calculando<span class="dots-animation"></span>';
      if (DOM.simpleHollowBottomWrap) DOM.simpleHollowBottomWrap.style.display = 'flex';

      // PASO A: Hollow linterna aparece debajo del aro con animación de zoom elástica (modo espejo)
      if (DOM.simpleHollowGif) {
        DOM.simpleHollowGif.style.display = 'block';
        DOM.simpleHollowGif.className = 'simple-hollow-gif mirror-mode hollow-intro-zoom';
      }

      if (DOM.simplePhaseTitle) {
        DOM.simplePhaseTitle.textContent = getT('install_starting', 'Iniciando preparación...');
      }

      // PASO B: El aro orbital arranca de inmediato con la animación continua de carga mientras esté en 0%
      updateSimpleProgress(0);
    }, 900);

    // Reset de métricas y tareas en curso
    if (DOM.metricStep) DOM.metricStep.textContent = "Paso 1/1";
    if (DOM.metricSpeed) DOM.metricSpeed.textContent = "-- MB/s";
    if (DOM.metricEta) DOM.metricEta.textContent = "Calculando...";
    if (DOM.lblTaskProgress) DOM.lblTaskProgress.textContent = "Iniciando particionamiento...";

    // Iniciar ticker reactivo a 1Hz con cálculo predictivo desacoplado
    TimeTickerEngine.start();

    DOM.terminalConsole.innerHTML = '';
    DOM.terminalConsole.style.display = 'block';
    isTerminalVisible = true;
    if (DOM.terminalToggleIcon) DOM.terminalToggleIcon.textContent = '▼';
    if (DOM.terminalToggleText) DOM.terminalToggleText.textContent = 'Ocultar registro';
    updateTerminalStatusGif(true); // Paso 1 es Ventoy (Particionado) -> breakdance.gif

    logTerminal("Iniciando preparación del sistema HollowDrive...", "info");

    const payload = {
      disk_index: State.selectedDisk.device,
      usb_model: (State.selectedDisk && State.selectedDisk.label) ? State.selectedDisk.label : "",
      cachy_gb: State.installCachy ? State.valCachyGb : 0.0,
      hollow_gb: State.valHollowGb,
      gb_totales: State.totalDiskGb,
      preservar_espacio: State.preserveSpace,
      instalar_cachy: State.installCachy,
      descargar_pack_hollow: State.installKit,
      instalar_bato: State.installBatocera,
      cachy_flavor: State.cachyFlavor,
      metodo_descarga: State.downloadMode || "ram"
    };

    const res = await window.hollowdrive.startInstallation(payload);
    if (!res.success) {
      logTerminal(`Error arrancando instalación: ${res.error}`, "error");
      State.isInstalling = false;
      TimeTickerEngine.stop();
      if (DOM.btnCancelInstallProcess) DOM.btnCancelInstallProcess.style.display = 'none';
      if (DOM.btnPrev) {
        DOM.btnPrev.style.display = 'inline-flex';
        DOM.btnPrev.disabled = false;
      }
      if (DOM.btnInstalarRow) DOM.btnInstalarRow.style.display = 'flex';
      DOM.stepperWrap.style.pointerEvents = 'auto';
    }
  }

  function logTerminal(msg, type = "info") {
    if (!DOM.terminalConsole) return;
    const line = document.createElement('div');
    line.className = `terminal-line ${type}`;
    const timestamp = new Date().toLocaleTimeString();
    line.textContent = `[${timestamp}] ${msg}`;
    DOM.terminalConsole.appendChild(line);
    DOM.terminalConsole.scrollTop = DOM.terminalConsole.scrollHeight;
  }

  // =========================================================================
  // 📡 PARSER DE MENSAJES Y EVENTOS EN TIEMPO REAL DESDE EL MOTOR PYTHON
  // =========================================================================
  function updateTerminalStatusGif(isPartitioning) {
    const targetFile = isPartitioning ? 'breakdance.gif' : 'hollow-linterna.webp';

    // GIF dinámico en el bloque de Estado de la vista detallada (agrandado a 50px)
    if (DOM.metricStatusGif) {
      if (!DOM.metricStatusGif.src || !DOM.metricStatusGif.src.includes(targetFile)) {
        DOM.metricStatusGif.src = `/media/${targetFile}`;
      }
      if (isPartitioning) {
        DOM.metricStatusGif.classList.remove('mirror-mode');
      } else {
        DOM.metricStatusGif.classList.add('mirror-mode');
      }
    }
  }

  function getMacroStatus(actionText, stepTitle = '') {
    const combined = `${actionText || ''} ${stepTitle || ''}`.toLowerCase();
    if (combined.includes('particion') || combined.includes('ventoy') || combined.includes('formateando') || combined.includes('diskpart')) {
      return 'Particionando';
    }
    if (combined.includes('descargando') || combined.includes('download')) {
      return 'Descargando';
    }
    if (combined.includes('volcado') || combined.includes('flasheando') || combined.includes('inyectando') || combined.includes('escribiendo') || combined.includes('copiando')) {
      return 'Escribiendo';
    }
    if (combined.includes('extrayendo') || combined.includes('descomprimiendo')) {
      return 'Extrayendo';
    }
    if (combined.includes('asentando') || combined.includes('sincronizando')) {
      return 'Asentando';
    }
    if (combined.includes('configuracion') || combined.includes('configuración') || combined.includes('configurando')) {
      return 'Configurando';
    }
    if (combined.includes('verificando') || combined.includes('comprobando')) {
      return 'Verificando';
    }
    if (combined.includes('instalando') || combined.includes('instalar')) {
      return 'Instalando';
    }
    return 'En progreso';
  }

  function formatTaskProgressLabel(actionText) {
    if (!actionText) return "Iniciando preparación...";
    let text = actionText.trim().replace(/\s*\d+%.*$/, '').replace(/\.{3,}$/, '').trim();
    const lower = text.toLowerCase();

    // 1. Acciones de particionado, sistema o almacenamiento que NO deben decir "Instalando":
    if (lower.startsWith("asentando")) {
      return text; // ej: "Asentando almacenamiento..."
    }
    if (lower.includes("ejecutando particionamiento") || lower.includes("particionamiento ventoy") || lower.includes("estructura ventoy")) {
      return "Particionando unidad (Ventoy)...";
    }
    if (lower.includes("creando partición") || lower.includes("creando particion")) {
      return text; // ej: "Creando partición GRUB...", "Creando partición CachyOS..."
    }
    if (lower.includes("volcado sectorial") || lower.includes("escribiendo sectores")) {
      return text; // ej: "Volcado sectorial CachyOS..."
    }
    if (lower.includes("localizando configuración") || lower.includes("localizando configuracion")) {
      return "Localizando configuración base...";
    }
    if (lower.includes("inyectando base")) {
      return "Inyectando configuración base...";
    }
    if (lower.startsWith("formateando") || lower.startsWith("limpiando") || lower.startsWith("preparando") || lower.startsWith("verificando")) {
      return text;
    }

    // 2. Si ya viene con "Instalando":
    if (/^instalando/i.test(text)) {
      return text;
    }

    // 3. Instalación de elementos / paquetes específicos:
    if (lower.includes("pack hollowdrive") || lower.includes("pack de hollowdrive") || lower.includes("hollowdrivepack") || lower.includes("pack utils hollowdrive")) {
      return "Instalando Pack de Hollowdrive";
    }
    if (lower.includes("batocera")) {
      return "Instalando Batocera OS";
    }
    if (lower.includes("cachyos") || lower.includes("cachy")) {
      return "Instalando CachyOS";
    }
    if (lower.includes("ventoy")) {
      return "Instalando Ventoy";
    }
    if (lower.includes("grub")) {
      return "Instalando Bootloader GRUB";
    }
    if (lower.includes("addon") || lower.includes("pack:")) {
      return `Instalando ${text.replace(/^.*pack:?\s*/i, 'Pack: ')}`;
    }

    // 4. Si el texto contiene una acción descriptiva como "Descargando X", "Extrayendo Y", etc. de paquetes:
    const actionMatch = text.match(/^(?:descargando|extrayendo(?:\s+al\s+vuelo)?|copiando|flasheando)\s+(.*)/i);
    if (actionMatch && actionMatch[1]) {
      const target = actionMatch[1].replace(/\.{3,}$/, '').trim();
      return `Instalando ${target}`;
    }

    // 5. Por defecto: mantener el texto limpio sin añadirle arbitrariamente "Instalando":
    const cleanTarget = text.replace(/\|.*$/, '').replace(/\.{3,}$/, '').trim();
    return cleanTarget || text;
  }

  function parseStatusMessage(rawMsg) {
    if (!rawMsg || typeof rawMsg !== 'string') return;
    let msg = rawMsg.trim();

    // 1. Extraer Fase / Paso (ej: "Paso 2/7: ...")
    const stepMatch = msg.match(/^Paso\s+(\d+\/\d+)\s*[:\-]?\s*(.*)$/i);
    if (stepMatch) {
      if (DOM.metricStep) DOM.metricStep.textContent = `Paso ${stepMatch[1]}`;
      msg = stepMatch[2].trim();
    }

    // 2. Extraer Velocidad (ej: "18.2 MB/s" o "950 KB/s")
    const speedMatch = msg.match(/(\d+(?:\.\d+)?\s*(?:MB|KB|GB|B)\/s)/i);
    if (speedMatch) {
      if (DOM.metricSpeed) DOM.metricSpeed.textContent = speedMatch[1].toUpperCase();
      msg = msg.replace(speedMatch[0], '').trim();
    }

    // 3. Extraer Tiempo Restante / ETA (ej: "Faltan: 01:23" o "ETA: 02:40")
    const etaMatch = msg.match(/(?:Faltan|ETA|Restante)[:\s]+([0-9:]+|\S+)/i);
    if (etaMatch) {
      // El tiempo total restante se gestiona exclusivamente por TimeTickerEngine para evitar saltos
      msg = msg.replace(etaMatch[0], '').trim();
    }

    // 4. Limpiar separadores residuales como "|" o ":" o "-"
    let cleanAction = msg
      .replace(/^\|\s*/, '')
      .replace(/\s*\|\s*$/, '')
      .replace(/^[:\-\s]+/, '')
      .replace(/[:\-\s]+$/, '')
      .trim();

    if (cleanAction) {
      // 1. Limpiar porcentajes residuales al final para la etiqueta de la barra de progreso
      const cleanProgressAction = cleanAction.replace(/\s*\d+%.*$/, '').replace(/\.{3,}$/, '').trim();
      const taskLabel = formatTaskProgressLabel(cleanProgressAction);
      if (DOM.lblTaskProgress) DOM.lblTaskProgress.textContent = taskLabel;
      if (DOM.simplePhaseTitle) DOM.simplePhaseTitle.textContent = taskLabel;

      // 2. En el BLOQUE DE ESTADO (Métrica 5): NUNCA volcar el texto de la terminal ni porcentajes.
      // Se muestra exclusivamente el macro-estado conciso y limpio de la operación
      const macroStatus = getMacroStatus(cleanAction, State.currentStepTitle || '');

      // 3. Si la acción actual corresponde a particionado, mostrar breakdance.gif, si no hollow-linterna.gif
      const isPartitioning = (macroStatus === 'Particionando');
      updateTerminalStatusGif(isPartitioning);
    }
  }

  window.hollowdrive.on('status', (data) => {
    logTerminal(data.message, data.level || "info");
    parseStatusMessage(data.message);
  });

  window.hollowdrive.on('task_progress', (data) => {
    const pct = Math.round((data.progress || 0) * 100);
    if (DOM.taskProgressBar) DOM.taskProgressBar.style.width = `${pct}%`;
    if (DOM.taskProgressPct) DOM.taskProgressPct.textContent = `${pct}%`;
    if (DOM.simplePhasePct) DOM.simplePhasePct.textContent = `${pct}%`;
    updateSimpleTaskProgress(data.progress);
    TimeTickerEngine.setProgress(data.progress);
  });

  window.hollowdrive.on('total_progress', (data) => {
    const pct = Math.round((data.progress || 0) * 100);
    if (DOM.totalProgressBar) DOM.totalProgressBar.style.width = `${pct}%`;
    if (DOM.totalProgressPct) DOM.totalProgressPct.textContent = `${pct}%`;
    updateSimpleProgress(pct);
  });

  window.hollowdrive.on('time_plan', (data) => {
    TimeTickerEngine.syncPlan(data);
  });

  window.hollowdrive.on('step', (data) => {
    updateSimpleTaskProgress(0); // Reiniciar anillo de proceso por separado
    State.currentStepTitle = data.title || '';
    if (DOM.metricStep) {
      DOM.metricStep.textContent = `Paso ${data.current}/${data.total}`;
    }
    if (data.title) {
      const taskLabel = formatTaskProgressLabel(data.title);
      const macroStatus = getMacroStatus(data.title, data.title);
      if (DOM.lblTaskProgress) DOM.lblTaskProgress.textContent = taskLabel;
      if (DOM.simplePhaseTitle) DOM.simplePhaseTitle.textContent = taskLabel;

      const isPartitioning = (macroStatus === 'Particionando');
      updateTerminalStatusGif(isPartitioning);
    }
    TimeTickerEngine.setStep(data.current, data.total, data.title, data.est_sec);
    logTerminal(`===> Paso [${data.current}/${data.total}]: ${data.title}`, "warn");
  });

  function formatDuration(sec) {
    if (!sec || isNaN(sec)) return "0s";
    sec = Math.round(sec);
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
  }

  window.hollowdrive.on('success', (data) => {
    State.isInstalling = false;
    TimeTickerEngine.stop();
    if (DOM.metricEta) DOM.metricEta.textContent = "00:00";
    if (DOM.metricTaskTimeEst) DOM.metricTaskTimeEst.textContent = "Finalizado";
    logTerminal(`¡INSTALACIÓN COMPLETADA CON ÉXITO en ${Math.round(data.time)} segundos!`, "success");
    if (DOM.lblTaskProgress) DOM.lblTaskProgress.textContent = "¡Instalación finalizada con éxito!";
    if (DOM.btnCancelInstallProcess) DOM.btnCancelInstallProcess.style.display = 'none';
    if (DOM.btnPrev) {
      DOM.btnPrev.style.display = 'inline-flex';
      DOM.btnPrev.disabled = false;
      DOM.btnPrev.textContent = getT('nav_back_menu', '⬅ Volver al Menú');
    }
    DOM.stepperWrap.style.pointerEvents = 'auto';

    // 1. Quitar las barras de progreso al terminar para tener más espacio según pedido
    if (DOM.taskProgressBarWrap) DOM.taskProgressBarWrap.style.display = 'none';
    if (DOM.totalProgressBarWrap) DOM.totalProgressBarWrap.style.display = 'none';

    // 2. Renderizar marcas de tiempo de cada proceso
    const records = data.records || {};
    const recordLabels = {
      'Estructura Core (Ventoy)': 'Ventoy Core',
      'Pack Utils HollowDrive': 'Pack HollowDrive',
      'Configuración Base Ventoy': 'Configuración Base',
      'Sistema Batocera OS': 'Batocera OS',
      'Creación Bootloader GRUB': 'Bootloader GRUB',
      'Inyección Bootloader GRUB': 'Inyección GRUB',
      'Creación Partición CachyOS': 'Partición Portable',
      'Volcado Sistema CachyOS': 'Sistema Portable',
      'ventoy': 'Ventoy Core',
      'hollow_pack': 'Pack HollowDrive',
      'batocera': 'Batocera OS',
      'cachyos': 'Sistema Portable',
      'grub': 'GRUB EFI'
    };

    if (DOM.completionTimesGrid) {
      DOM.completionTimesGrid.innerHTML = '';

      for (const [key, dur] of Object.entries(records)) {
        if (dur !== undefined && dur !== null && dur > 0) {
          const label = recordLabels[key] || key;
          const box = document.createElement('div');
          box.className = 'time-metric-box';
          box.innerHTML = `
            <span class="time-metric-name">${label}</span>
            <span class="time-metric-val">${formatDuration(dur)}</span>
          `;
          DOM.completionTimesGrid.appendChild(box);
        }
      }

      // Añadir métrica destacada de Tiempo Total
      const totalBox = document.createElement('div');
      totalBox.className = 'time-metric-box total-time-box';
      totalBox.innerHTML = `
        <span class="time-metric-name">Tiempo Total</span>
        <span class="time-metric-val">${formatDuration(data.time)}</span>
      `;
      DOM.completionTimesGrid.appendChild(totalBox);
    }

    // 3. Mostrar el bloque resumen y el botón de nueva instalación en vista detallada
    if (DOM.completionSummaryCard) {
      DOM.completionSummaryCard.style.display = 'flex';
      DOM.completionSummaryCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    // 4. SECUENCIA ANIMADA DE LA VISTA SIMPLE:
    updateSimpleProgress(100);
    updateSimpleTaskProgress(1);
    if (DOM.simplePhaseTitle) DOM.simplePhaseTitle.textContent = getT('install_success_title', '¡Instalación Finalizada con Éxito!');

    // Llenar desglose de marcas de tiempo por proceso para el bloque final (columna izquierda)
    if (DOM.simpleProcessTimesList) {
      DOM.simpleProcessTimesList.innerHTML = '';
      const records = data.records || {};
      let rowCount = 0;
      for (const [key, dur] of Object.entries(records)) {
        if (dur !== undefined && dur !== null && dur > 0) {
          const label = recordLabels[key] || key;
          const row = document.createElement('div');
          row.className = 'process-time-row';
          row.style.animationDelay = `${rowCount * 0.08}s`;
          row.innerHTML = `
            <div class="process-time-info">
              <span class="process-time-dot"></span>
              <span class="process-time-name">${label}</span>
            </div>
            <span class="process-time-val">${formatDuration(dur)}</span>
          `;
          DOM.simpleProcessTimesList.appendChild(row);
          rowCount++;
        }
      }
      if (rowCount === 0) {
        DOM.simpleProcessTimesList.innerHTML = `
          <div class="process-time-row">
            <div class="process-time-info">
              <span class="process-time-dot"></span>
              <span class="process-time-name">Instalación Global</span>
            </div>
            <span class="process-time-val">${formatDuration(data.time)}</span>
          </div>
        `;
      }
    }

    if (DOM.simpleTotalTimeValue) {
      DOM.simpleTotalTimeValue.textContent = formatDuration(data.time);
    }

    if (DOM.simpleHollowGif) {
      // a) El GIF de linterna da una vuelta completa de 360° celebrando
      DOM.simpleHollowGif.classList.add('celebrate-spin');

      // b) Al completarse el giro (750ms), el GIF desaparece y emerge el tick de confirmación en el centro del aro
      setTimeout(() => {
        DOM.simpleHollowGif.style.display = 'none';
        if (DOM.simpleHollowBottomWrap) DOM.simpleHollowBottomWrap.style.display = 'none';
        if (DOM.simpleBottomTimerCard) DOM.simpleBottomTimerCard.style.display = 'none';
        if (DOM.simpleCenterPctWrap) DOM.simpleCenterPctWrap.style.display = 'none';
        if (DOM.simpleSuccessTick) {
          DOM.simpleSuccessTick.style.display = 'flex';
        }

        // c) Tras animarse el tick (~600ms), transiciona suavemente al bloque de la fase final
        //    (con transparencia para ver las lumélulas a través, marcas de tiempo a la izquierda y total a la derecha)
        setTimeout(() => {
          if (DOM.simpleRingWrap) DOM.simpleRingWrap.style.display = 'none';
          if (DOM.simpleStatusInfo) DOM.simpleStatusInfo.style.display = 'none';
          if (DOM.simpleCompletionZone) {
            DOM.simpleCompletionZone.style.display = 'flex';
          }
        }, 600);
      }, 750);
    } else {
      if (DOM.simpleCenterPctWrap) DOM.simpleCenterPctWrap.style.display = 'none';
      if (DOM.simpleBottomTimerCard) DOM.simpleBottomTimerCard.style.display = 'none';
      if (DOM.simpleRingWrap) DOM.simpleRingWrap.style.display = 'none';
      if (DOM.simpleStatusInfo) DOM.simpleStatusInfo.style.display = 'none';
      if (DOM.simpleCompletionZone) DOM.simpleCompletionZone.style.display = 'flex';
    }
  });

  // Botón "Nueva Instalación" tras terminar
  if (DOM.btnNewInstall) {
    DOM.btnNewInstall.addEventListener('click', () => {
      resetInstallProcessUI();

      // Navegar al Paso 1 y refrescar discos
      State.downloadMode = 'ram';
      if (window.selectDownloadMode) window.selectDownloadMode('ram');
      setWizardStep(1);
      refreshDisks();
    });
  }

  window.hollowdrive.on('error', (data) => {
    State.isInstalling = false;
    TimeTickerEngine.stop();
    logTerminal(`FALLO EN LA INSTALACIÓN [${data.type}]: ${data.message}`, "error");
    if (DOM.lblTaskProgress) DOM.lblTaskProgress.textContent = "Fallo en la instalación";
    if (DOM.btnCancelInstallProcess) DOM.btnCancelInstallProcess.style.display = 'none';
    if (DOM.btnPrev) {
      DOM.btnPrev.style.display = 'inline-flex';
      DOM.btnPrev.disabled = false;
      DOM.btnPrev.textContent = getT('nav_back_menu', '⬅ Volver al Menú');
    }
    if (DOM.btnInstalarRow) DOM.btnInstalarRow.style.display = 'flex';
    DOM.stepperWrap.style.pointerEvents = 'auto';
  });

  window.hollowdrive.on('cancel', () => {
    logTerminal("Instalación cancelada por el usuario.", "warn");
    resetInstallProcessUI();
  });

  // Detector de Hotplug USB (Eventos automáticos al conectar/desconectar unidades)
  window.hollowdrive.on('usb_hotplug', () => {
    if (!State.isInstalling && State.wizardStep === 1) {
      console.log("[HOTPLUG] Evento de cambio USB recibido, recargando discos...");
      refreshDisks();
    }
    if (State.screen === 'tools' && !State.toolsIsOperating) {
      console.log("[HOTPLUG] Evento de cambio USB en HollowTools, recargando...");
      loadHollowToolsDisks();
    }
  });

  // =========================================================================
  // 🛠️ CONTROLADOR HOLLOWTOOLS (MANTENIMIENTO, ISOs, PAQUETES, CACHYOS)
  // =========================================================================
  function updateToolsTask(taskKey = 'copy_isos', msg = 'Procesando...', progress = 0) {
    if (!State.toolsActiveTasks) State.toolsActiveTasks = {};
    const pct = Math.min(100, Math.max(0, Math.round(progress * 100)));
    
    State.toolsActiveTasks[taskKey] = {
      message: msg,
      progress: pct
    };
    State.toolsIsOperating = true;

    // Bloquear controles globales mientras haya alguna operación activa
    if (DOM.btnBackFromTools) {
      DOM.btnBackFromTools.disabled = true;
      DOM.btnBackFromTools.classList.add('disabled');
      DOM.btnBackFromTools.setAttribute('title', 'Operación en curso: no se puede salir de HollowTools');
    }
    if (DOM.toolsUsbSelect) DOM.toolsUsbSelect.disabled = true;
    if (DOM.btnRefreshToolsUsb) DOM.btnRefreshToolsUsb.disabled = true;

    // Desactivar selectivamente el botón de la tarea en ejecución (las demás siguen habilitadas)
    if (taskKey === 'copy_isos') {
      if (DOM.btnInjectIsos) {
        DOM.btnInjectIsos.disabled = true;
        DOM.btnInjectIsos.textContent = 'Copiando ISOs...';
      }
    } else if (taskKey === 'inject_packages') {
      if (DOM.btnInjectPacks) {
        DOM.btnInjectPacks.disabled = true;
        DOM.btnInjectPacks.textContent = 'Inyectando Paquetes...';
      }
    } else if (taskKey === 'cachyos') {
      if (DOM.btnApplyCachy) {
        DOM.btnApplyCachy.disabled = true;
        DOM.btnApplyCachy.textContent = 'Procesando CachyOS...';
      }
    }

    if (DOM.toolsMonitorCard) {
      DOM.toolsMonitorCard.style.display = 'flex';
      renderToolsTasksMonitor();
    }
  }

  function finishToolsTask(taskKey = null) {
    if (!State.toolsActiveTasks) State.toolsActiveTasks = {};
    if (taskKey) {
      delete State.toolsActiveTasks[taskKey];
    } else {
      State.toolsActiveTasks = {};
    }

    // Restaurar selectivamente botones terminados
    if (!State.toolsActiveTasks['copy_isos']) {
      if (DOM.btnInjectIsos) {
        DOM.btnInjectIsos.disabled = false;
        const qCount = State.toolsIsoQueue ? State.toolsIsoQueue.length : 0;
        DOM.btnInjectIsos.textContent = qCount === 1 ? 'Inyectar 1 ISO' : `Inyectar ${qCount} ISOs`;
      }
    }
    if (!State.toolsActiveTasks['inject_packages']) {
      if (DOM.btnInjectPacks) {
        DOM.btnInjectPacks.disabled = false;
        DOM.btnInjectPacks.textContent = 'Inyectar Seleccionados';
      }
    }
    if (!State.toolsActiveTasks['cachyos']) {
      if (DOM.btnApplyCachy) {
        DOM.btnApplyCachy.disabled = false;
        const txt = DOM.toolsBtnApplyText ? DOM.toolsBtnApplyText.textContent : 'Aplicar';
        DOM.btnApplyCachy.textContent = txt || 'Aplicar';
      }
    }

    const remainingKeys = Object.keys(State.toolsActiveTasks);
    if (remainingKeys.length === 0) {
      State.toolsIsOperating = false;
      if (DOM.btnBackFromTools) {
        DOM.btnBackFromTools.disabled = false;
        DOM.btnBackFromTools.classList.remove('disabled');
        DOM.btnBackFromTools.removeAttribute('title');
      }
      if (DOM.toolsUsbSelect) DOM.toolsUsbSelect.disabled = false;
      if (DOM.btnRefreshToolsUsb) DOM.btnRefreshToolsUsb.disabled = false;
      if (DOM.toolsMonitorCard) {
        DOM.toolsMonitorCard.style.display = 'none';
      }
    } else {
      renderToolsTasksMonitor();
    }
  }

  function renderToolsTasksMonitor() {
    if (!DOM.toolsTasksList) return;
    const taskKeys = Object.keys(State.toolsActiveTasks || {});
    if (DOM.toolsTasksCount) {
      DOM.toolsTasksCount.textContent = `${taskKeys.length} ${taskKeys.length === 1 ? 'activa' : 'activas'}`;
    }

    const taskLabels = {
      copy_isos: 'ISOs',
      inject_packages: 'Paquetes',
      cachyos: 'CachyOS'
    };

    DOM.toolsTasksList.innerHTML = taskKeys.map(k => {
      const t = State.toolsActiveTasks[k];
      const badgeText = taskLabels[k] || k.toUpperCase();
      return `
        <div class="tools-task-item" id="taskRow_${k}">
          <div class="tools-task-head">
            <div class="tools-task-title-group">
              <span class="tools-task-badge badge-${k}">${badgeText}</span>
              <span class="tools-task-msg" title="${escapeHtml(t.message)}">${escapeHtml(t.message)}</span>
            </div>
            <div class="tools-task-meta">
              <span class="tools-task-pct">${t.progress}%</span>
              <button type="button" class="btn-cancel-task" data-task="${k}" title="Cancelar esta tarea">✕ Cancelar</button>
            </div>
          </div>
          <div class="tools-progress-track">
            <div class="tools-progress-fill fill-${k}" style="width: ${t.progress}%;"></div>
          </div>
        </div>
      `;
    }).join('');

    DOM.toolsTasksList.querySelectorAll('.btn-cancel-task').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const tKey = btn.getAttribute('data-task');
        const confirmed = await showCustomConfirm({
          title: "CANCELAR OPERACIÓN",
          message: `¿Deseas cancelar la operación en curso de <strong>${taskLabels[tKey] || tKey}</strong>?`,
          okText: "Sí, cancelar",
          isDanger: true
        });
        if (confirmed) {
          await window.hollowdrive.cancelToolsAction(tKey);
        }
      });
    });
  }

  function showToolsMonitor(msg, progress = 0, taskKey = 'copy_isos') {
    updateToolsTask(taskKey, msg, progress);
  }

  function hideToolsMonitor(taskKey = null) {
    finishToolsTask(taskKey);
  }

  async function loadHollowToolsDisks() {
    if (!DOM.toolsUsbSelect) return;
    DOM.toolsUsbSelect.innerHTML = '<option value="">Buscando unidades HOLLOWDRIVE...</option>';
    if (DOM.btnRefreshToolsUsb) {
      DOM.btnRefreshToolsUsb.disabled = true;
      DOM.btnRefreshToolsUsb.classList.add('spinning');
    }

    try {
      let res = await window.hollowdrive.getHollowDisks();
      if (!res || !res.success || !res.disks || res.disks.length === 0) {
        DOM.toolsUsbSelect.innerHTML = '<option value="">No se detectan unidades HOLLOWDRIVE</option>';
        State.toolsDisks = [];
        State.toolsSelectedDisk = null;
        State.toolsDiskInfo = null;
        if (DOM.toolsPortableBadge) {
          DOM.toolsPortableBadge.textContent = "Sin Disco";
          DOM.toolsPortableBadge.className = "portable-system-badge";
        }
        if (DOM.toolsPortableStatusText) {
          DOM.toolsPortableStatusText.textContent = "No se detectan unidades HOLLOWDRIVE";
        }
        renderToolsBars();
        return;
      }

      State.toolsDisks = res.disks;
      DOM.toolsUsbSelect.innerHTML = '<option value="">-- Selecciona una unidad HOLLOWDRIVE --</option>';
      res.disks.forEach(d => {
        const opt = document.createElement('option');
        opt.value = d.device;
        opt.textContent = d.display || `Disco ${d.device} (${d.size} GB)`;
        DOM.toolsUsbSelect.appendChild(opt);
      });

      // Si sólo hay un disco o teníamos uno previamente seleccionado
      const existing = res.disks.find(d => d.device === State.toolsSelectedDisk);
      if (existing) {
        DOM.toolsUsbSelect.value = existing.device;
        await onToolsDiskSelected(existing.device);
      } else if (res.disks.length === 1) {
        DOM.toolsUsbSelect.value = res.disks[0].device;
        await onToolsDiskSelected(res.disks[0].device);
      } else {
        State.toolsSelectedDisk = null;
        State.toolsDiskInfo = null;
        if (DOM.toolsPortableBadge) {
          DOM.toolsPortableBadge.textContent = "Sin Selección";
          DOM.toolsPortableBadge.className = "portable-system-badge";
        }
        if (DOM.toolsPortableStatusText) {
          DOM.toolsPortableStatusText.textContent = "Selecciona una unidad arriba para ver opciones";
        }
        renderToolsBars();
      }
    } catch (err) {
      console.error("[HOLLOWTOOLS] Error cargando discos:", err);
      DOM.toolsUsbSelect.innerHTML = '<option value="">Error al buscar unidades</option>';
    } finally {
      if (DOM.btnRefreshToolsUsb) {
        DOM.btnRefreshToolsUsb.disabled = false;
        setTimeout(() => DOM.btnRefreshToolsUsb.classList.remove('spinning'), 500);
      }
    }
  }

  async function onToolsDiskSelected(diskDevice) {
    if (!diskDevice) {
      State.toolsSelectedDisk = null;
      State.toolsDiskInfo = null;
      if (DOM.toolsPortableBadge) {
        DOM.toolsPortableBadge.textContent = "Sin Selección";
        DOM.toolsPortableBadge.className = "portable-system-badge";
      }
      if (DOM.toolsPortableStatusText) {
        DOM.toolsPortableStatusText.textContent = "Selecciona una unidad arriba para ver opciones";
      }
      renderToolsBars();
      return;
    }

    State.toolsSelectedDisk = diskDevice;
    if (DOM.toolsCachySpaceText) DOM.toolsCachySpaceText.textContent = "Consultando particiones...";
    if (DOM.toolsPortableStatusText) DOM.toolsPortableStatusText.textContent = "Consultando estado...";

    try {
      const res = await window.hollowdrive.getDiskPartitionsInfo(diskDevice);
      if (res && res.success) {
        State.toolsDiskInfo = res;
        const espacioDerecha = res.espacio_derecha || 0;

        if (res.tiene_cachy) {
          setToolsCachyMode('actualizar');
          if (DOM.toolsPortableBadge) {
            DOM.toolsPortableBadge.textContent = "CachyOS Instalado";
            DOM.toolsPortableBadge.className = "portable-system-badge installed";
          }
          if (DOM.toolsPortableStatusText) {
            const sizeCachy = res.size_cachy || 20.0;
            DOM.toolsPortableStatusText.textContent = `CachyOS detectado (${sizeCachy.toFixed(1)} GB) | Listo para actualizar`;
          }
        } else if (espacioDerecha >= 20.0) {
          setToolsCachyMode('instalar');
          if (DOM.toolsPortableBadge) {
            DOM.toolsPortableBadge.textContent = "Espacio Disponible";
            DOM.toolsPortableBadge.className = "portable-system-badge available";
          }
          if (DOM.toolsPortableStatusText) {
            DOM.toolsPortableStatusText.textContent = `Listo para instalar (${espacioDerecha.toFixed(1)} GB libres)`;
          }
        } else {
          setToolsCachyMode('actualizar');
          if (DOM.toolsPortableBadge) {
            DOM.toolsPortableBadge.textContent = "Espacio Insuficiente";
            DOM.toolsPortableBadge.className = "portable-system-badge insufficient";
          }
          if (DOM.toolsPortableStatusText) {
            DOM.toolsPortableStatusText.textContent = `Espacio libre insuficiente (${espacioDerecha.toFixed(1)} GB, mín. 20 GB)`;
          }
        }

        if (espacioDerecha >= 20.0) {
          if (DOM.toolsSliderCachy) {
            DOM.toolsSliderCachy.disabled = false;
            DOM.toolsSliderCachy.min = "20.0";
            DOM.toolsSliderCachy.max = String(espacioDerecha);
            if (State.toolsCachySize < 20.0 || State.toolsCachySize > espacioDerecha) {
              State.toolsCachySize = espacioDerecha;
            }
            DOM.toolsSliderCachy.value = String(State.toolsCachySize);
          }
          if (DOM.toolsCachySpaceText) {
            DOM.toolsCachySpaceText.textContent = `Disponible a la derecha: ${espacioDerecha.toFixed(2)} GB`;
          }
        } else {
          if (DOM.toolsSliderCachy) {
            DOM.toolsSliderCachy.disabled = true;
          }
          if (DOM.toolsCachySpaceText) {
            DOM.toolsCachySpaceText.textContent = `Insuficiente: ${espacioDerecha.toFixed(2)} GB (mín. 20GB)`;
          }
        }

        renderToolsBars();
      }
    } catch (err) {
      console.error("[HOLLOWTOOLS] Error obteniendo particiones:", err);
    }
  }

  function setToolsCachyMode(mode) {
    State.toolsCachyMode = mode;
    if (DOM.btnToolsCachyUpdate) DOM.btnToolsCachyUpdate.classList.toggle('active', mode === 'actualizar');
    if (DOM.btnToolsCachyInstall) DOM.btnToolsCachyInstall.classList.toggle('active', mode === 'instalar');
    if (DOM.toolsCachySliderWrap) {
      DOM.toolsCachySliderWrap.style.display = (mode === 'instalar') ? 'flex' : 'none';
    }
    renderToolsBars();
  }

  function renderToolsBars() {
    if (!DOM.toolsBarActual || !DOM.toolsBarFuturo) return;

    if (!State.toolsDiskInfo || !State.toolsDiskInfo.partitions || State.toolsDiskInfo.partitions.length === 0) {
      DOM.toolsBarActual.innerHTML = '<div class="tools-slice slice-libre" style="width: 100%;">Sin disco seleccionado</div>';
      DOM.toolsBarFuturo.innerHTML = '<div class="tools-slice slice-libre" style="width: 100%;">Sin disco seleccionado</div>';
      if (DOM.toolsBarActualInfo) DOM.toolsBarActualInfo.textContent = 'Libre: 0.0GB';
      if (DOM.toolsBarFuturoInfo) DOM.toolsBarFuturoInfo.textContent = 'Libre: 0.0GB';
      return;
    }

    const totalGb = State.toolsDiskInfo.total_disk_gb || 64.0;
    const partitions = State.toolsDiskInfo.partitions || [];
    const modoActualizar = (State.toolsCachyMode === 'actualizar');

    // 1. Barra ANTES (Actual)
    DOM.toolsBarActual.innerHTML = '';
    let sizeCachyAct = 0;
    let sumPartSizes = 0;

    partitions.forEach(p => {
      const pSize = parseFloat(p.Size) || 0;
      sumPartSizes += pSize;
      const pct = (pSize / totalGb) * 100;
      const lbl = (p.Label || '').toUpperCase();
      const num = p.Number;

      const slice = document.createElement('div');
      slice.className = 'tools-slice';
      slice.style.width = `${pct}%`;

      if (num === 1 || lbl.includes('HOLLOW') || lbl.includes('VENTOY')) {
        slice.classList.add('slice-hollow');
        if (pct >= 8) slice.textContent = `Hollow: ${pSize.toFixed(1)}GB`;
      } else if (lbl.includes('GRUB') || (pSize >= 0.2 && pSize <= 1.5 && num !== 1)) {
        slice.classList.add('slice-grub');
        if (pct >= 6) slice.textContent = 'GRUB';
      } else if (lbl.includes('CACHY') || (pSize >= 5.0 && num !== 1)) {
        slice.classList.add('slice-cachy');
        sizeCachyAct = pSize;
        if (pct >= 8) slice.textContent = `CachyOS: ${pSize.toFixed(1)}GB`;
      } else {
        slice.classList.add('slice-hollow');
        if (pct >= 8) slice.textContent = `${pSize.toFixed(1)}GB`;
      }
      DOM.toolsBarActual.appendChild(slice);
    });

    const libreAct = Math.max(0, totalGb - sumPartSizes);
    if (libreAct > 0.05) {
      const pctLibre = (libreAct / totalGb) * 100;
      const sliceLibre = document.createElement('div');
      sliceLibre.className = 'tools-slice slice-libre';
      sliceLibre.style.width = `${pctLibre}%`;
      DOM.toolsBarActual.appendChild(sliceLibre);
    }

    const infoActItems = [];
    if (sizeCachyAct > 0) infoActItems.push(`CachyOS: ${sizeCachyAct.toFixed(1)}GB`);
    infoActItems.push(`Libre: ${libreAct.toFixed(1)}GB`);
    if (DOM.toolsBarActualInfo) DOM.toolsBarActualInfo.textContent = infoActItems.join(' | ');

    // 2. Barra DESPUÉS (Futuro)
    DOM.toolsBarFuturo.innerHTML = '';
    if (modoActualizar) {
      partitions.forEach(p => {
        const pSize = parseFloat(p.Size) || 0;
        const pct = (pSize / totalGb) * 100;
        const lbl = (p.Label || '').toUpperCase();
        const num = p.Number;

        const slice = document.createElement('div');
        slice.className = 'tools-slice';
        slice.style.width = `${pct}%`;

        if (num === 1 || lbl.includes('HOLLOW') || lbl.includes('VENTOY')) {
          slice.classList.add('slice-hollow');
          if (pct >= 8) slice.textContent = `Hollow: ${pSize.toFixed(1)}GB`;
        } else if (lbl.includes('GRUB') || (pSize >= 0.2 && pSize <= 1.5 && num !== 1)) {
          slice.classList.add('slice-grub');
          slice.textContent = (pct >= 6) ? 'GRUB ✔' : '✔';
        } else if (lbl.includes('CACHY') || (pSize >= 5.0 && num !== 1)) {
          slice.classList.add('slice-cachy');
          slice.textContent = (pct >= 8) ? `CachyOS: ${pSize.toFixed(1)}GB ✔` : '✔';
        } else {
          slice.classList.add('slice-hollow');
          if (pct >= 8) slice.textContent = `${pSize.toFixed(1)}GB`;
        }
        DOM.toolsBarFuturo.appendChild(slice);
      });

      if (libreAct > 0.05) {
        const pctLibre = (libreAct / totalGb) * 100;
        const sliceLibre = document.createElement('div');
        sliceLibre.className = 'tools-slice slice-libre';
        sliceLibre.style.width = `${pctLibre}%`;
        DOM.toolsBarFuturo.appendChild(sliceLibre);
      }

      if (DOM.toolsBarFuturoInfo) DOM.toolsBarFuturoInfo.textContent = infoActItems.join(' | ');
    } else {
      // Modo INSTALAR
      const sizeH = State.toolsDiskInfo.size_hollow || 0;
      let sizeG = 0.512;
      for (const p of partitions) {
        const lbl = (p.Label || '').toUpperCase();
        const pSize = parseFloat(p.Size) || 0;
        if (lbl.includes('GRUB') || (pSize >= 0.2 && pSize <= 1.5 && p.Number !== 1)) {
          sizeG = pSize;
          break;
        }
      }
      const totalAlloc = State.toolsCachySize || 20.0;
      const sizeC = Math.max(1.0, totalAlloc - sizeG);

      // Slice Hollow
      const pctH = (sizeH / totalGb) * 100;
      const sliceH = document.createElement('div');
      sliceH.className = 'tools-slice slice-hollow';
      sliceH.style.width = `${pctH}%`;
      if (pctH >= 8) sliceH.textContent = `Hollow: ${sizeH.toFixed(1)}GB`;
      DOM.toolsBarFuturo.appendChild(sliceH);

      // Slice GRUB
      const pctG = (sizeG / totalGb) * 100;
      const sliceG = document.createElement('div');
      sliceG.className = 'tools-slice slice-grub';
      sliceG.style.width = `${pctG}%`;
      sliceG.textContent = (pctG >= 6) ? 'GRUB ✔' : '✔';
      DOM.toolsBarFuturo.appendChild(sliceG);

      // Slice CachyOS
      const pctC = (sizeC / totalGb) * 100;
      const sliceC = document.createElement('div');
      sliceC.className = 'tools-slice slice-cachy';
      sliceC.style.width = `${pctC}%`;
      if (pctC >= 8) sliceC.textContent = `CachyOS: ${sizeC.toFixed(1)}GB ✔`;
      DOM.toolsBarFuturo.appendChild(sliceC);

      // Slice Libre
      const libreFut = Math.max(0, totalGb - sizeH - sizeG - sizeC);
      if (libreFut > 0.05) {
        const pctL = (libreFut / totalGb) * 100;
        const sliceL = document.createElement('div');
        sliceL.className = 'tools-slice slice-libre';
        sliceL.style.width = `${pctL}%`;
        DOM.toolsBarFuturo.appendChild(sliceL);
      }

      const infoFutItems = [`CachyOS: ${sizeC.toFixed(1)}GB`, `Libre: ${libreFut.toFixed(1)}GB`];
      if (DOM.toolsBarFuturoInfo) DOM.toolsBarFuturoInfo.textContent = infoFutItems.join(' | ');
    }
  }

  // --- LISTENERS DE HOLLOWTOOLS ---
  if (DOM.toolsUsbSelect) {
    DOM.toolsUsbSelect.addEventListener('change', (e) => {
      onToolsDiskSelected(e.target.value);
    });
  }

  if (DOM.btnRefreshToolsUsb) {
    DOM.btnRefreshToolsUsb.addEventListener('click', () => {
      loadHollowToolsDisks();
    });
  }

  // Modales Diamond
  if (DOM.btnInfoToolsIso) {
    DOM.btnInfoToolsIso.addEventListener('click', () => openModal(DOM.modalToolsIso));
  }
  if (DOM.btnInfoToolsPacks) {
    DOM.btnInfoToolsPacks.addEventListener('click', () => openModal(DOM.modalToolsPacks));
  }
  if (DOM.btnInfoToolsCachy) {
    DOM.btnInfoToolsCachy.addEventListener('click', () => openModal(DOM.modalToolsCachy));
  }

  // =========================================================================
  // 📦 GESTIÓN DE COLA DE ISOs (ACUMULATIVA)
  // =========================================================================
  async function addIsosToQueue(paths) {
    if (!paths || paths.length === 0) return;
    if (!State.toolsIsoQueue) State.toolsIsoQueue = [];

    // Evitar añadir exactamente los mismos archivos duplicados
    const existingPaths = new Set(State.toolsIsoQueue.map(item => item.path.toLowerCase()));
    const newPaths = paths.filter(p => !existingPaths.has(p.toLowerCase()));

    if (newPaths.length === 0) {
      await showCustomAlert("ISOs YA EN COLA", "Los archivos ISO seleccionados ya están incluidos en la lista para inyectar.");
      return;
    }

    try {
      const filesInfo = await window.hollowdrive.getFilesInfo(newPaths);
      if (filesInfo && filesInfo.length > 0) {
        filesInfo.forEach(info => {
          State.toolsIsoQueue.push({
            path: info.path,
            name: info.name || (info.path.split(/[/\\]/).pop()),
            size_str: info.size_str || ''
          });
        });
      } else {
        newPaths.forEach(p => {
          State.toolsIsoQueue.push({
            path: p,
            name: p.split(/[/\\]/).pop(),
            size_str: ''
          });
        });
      }
    } catch (err) {
      newPaths.forEach(p => {
        State.toolsIsoQueue.push({
          path: p,
          name: p.split(/[/\\]/).pop(),
          size_str: ''
        });
      });
    }

    renderIsoQueue();
  }

  function removeIsoFromQueue(index) {
    if (!State.toolsIsoQueue) return;
    State.toolsIsoQueue.splice(index, 1);
    renderIsoQueue();
  }

  function clearIsoQueue() {
    State.toolsIsoQueue = [];
    renderIsoQueue();
  }

  function renderIsoQueue() {
    const queue = State.toolsIsoQueue || [];
    const count = queue.length;

    if (count === 0) {
      if (DOM.toolsIsoQueueBlock) DOM.toolsIsoQueueBlock.style.display = 'none';
      if (DOM.toolsDropZone) DOM.toolsDropZone.style.display = 'flex';
      return;
    }

    if (DOM.toolsDropZone) DOM.toolsDropZone.style.display = 'none';
    if (DOM.toolsIsoQueueBlock) DOM.toolsIsoQueueBlock.style.display = 'flex';

    if (DOM.toolsQueueCount) {
      DOM.toolsQueueCount.textContent = `${count} ${count === 1 ? 'ISO seleccionada' : 'ISOs seleccionadas'}`;
    }

    if (DOM.btnInjectIsos) {
      const isCopying = State.toolsActiveTasks && State.toolsActiveTasks['copy_isos'];
      if (!isCopying) {
        DOM.btnInjectIsos.disabled = false;
        DOM.btnInjectIsos.textContent = count === 1 ? 'Inyectar 1 ISO' : `Inyectar ${count} ISOs`;
      }
    }

    if (DOM.toolsIsoList) {
      DOM.toolsIsoList.innerHTML = queue.map((item, idx) => `
        <div class="tools-iso-item">
          <div class="iso-item-left">
            <svg class="iso-file-icon" viewBox="0 0 24 24"><path d="M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/></svg>
            <span class="iso-item-name" title="${escapeHtml(item.path)}">${escapeHtml(item.name)}</span>
          </div>
          <div class="iso-item-right">
            ${item.size_str ? `<span class="iso-item-size">${escapeHtml(item.size_str)}</span>` : ''}
            <button type="button" class="btn-remove-iso" data-index="${idx}" title="Eliminar de la lista">✕</button>
          </div>
        </div>
      `).join('');

      DOM.toolsIsoList.querySelectorAll('.btn-remove-iso').forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          const idx = parseInt(btn.getAttribute('data-index'), 10);
          removeIsoFromQueue(idx);
        });
      });
    }
  }

  // --- LISTENERS TARJETA 1: GESTOR DE ISOs ---
  const triggerPickIso = async () => {
    try {
      const picked = await window.hollowdrive.pickIsoFiles();
      if (picked && picked.length > 0) {
        await addIsosToQueue(picked);
      } else if (DOM.fileInputIsos) {
        DOM.fileInputIsos.click();
      }
    } catch (err) {
      console.error("Error seleccionando ISOs:", err);
      if (DOM.fileInputIsos) DOM.fileInputIsos.click();
    }
  };

  if (DOM.btnPlusIso) {
    DOM.btnPlusIso.addEventListener('click', async (e) => {
      e.stopPropagation();
      await triggerPickIso();
    });
  }

  if (DOM.btnPlusMoreIso) {
    DOM.btnPlusMoreIso.addEventListener('click', async (e) => {
      e.stopPropagation();
      await triggerPickIso();
    });
  }

  if (DOM.btnClearIsoQueue) {
    DOM.btnClearIsoQueue.addEventListener('click', (e) => {
      e.stopPropagation();
      clearIsoQueue();
    });
  }

  if (DOM.fileInputIsos) {
    DOM.fileInputIsos.addEventListener('change', async (e) => {
      const files = Array.from(e.target.files || []);
      if (files.length === 0) return;
      const paths = files.map(f => f.path || f.name);
      await addIsosToQueue(paths);
      e.target.value = '';
    });
  }

  // Arrastrar y soltar archivos ISO en la tarjeta
  const cardGestorIso = document.querySelector('.card-gestor-iso');
  if (cardGestorIso) {
    cardGestorIso.addEventListener('dragover', (e) => {
      e.preventDefault();
      if (DOM.toolsDropZone) DOM.toolsDropZone.classList.add('drag-over');
      if (DOM.toolsIsoQueueBlock) DOM.toolsIsoQueueBlock.classList.add('drag-over');
    });
    cardGestorIso.addEventListener('dragleave', (e) => {
      e.preventDefault();
      if (DOM.toolsDropZone) DOM.toolsDropZone.classList.remove('drag-over');
      if (DOM.toolsIsoQueueBlock) DOM.toolsIsoQueueBlock.classList.remove('drag-over');
    });
    cardGestorIso.addEventListener('drop', async (e) => {
      e.preventDefault();
      if (DOM.toolsDropZone) DOM.toolsDropZone.classList.remove('drag-over');
      if (DOM.toolsIsoQueueBlock) DOM.toolsIsoQueueBlock.classList.remove('drag-over');
      if (e.dataTransfer && e.dataTransfer.files) {
        const files = Array.from(e.dataTransfer.files).filter(f => f.name.toLowerCase().endsWith('.iso'));
        if (files.length === 0) {
          await showCustomAlert("FORMATO NO VÁLIDO", "Sólo se admiten archivos con extensión <strong>.iso</strong>");
          return;
        }
        const paths = files.map(f => f.path || f.name);
        await addIsosToQueue(paths);
      }
    });
  }

  // Inyectar la cola acumulada de ISOs
  if (DOM.btnInjectIsos) {
    DOM.btnInjectIsos.addEventListener('click', async () => {
      if (!State.toolsSelectedDisk) {
        await showCustomAlert("UNIDAD NO SELECCIONADA", "Por favor, selecciona primero una unidad HOLLOWDRIVE.");
        return;
      }
      const queue = State.toolsIsoQueue || [];
      if (queue.length === 0) {
        await showCustomAlert("COLA VACÍA", "No hay imágenes ISO en la lista para inyectar.");
        return;
      }
      const count = queue.length;
      const ok = await showCustomConfirm({
        title: "INYECCIÓN DE ISOs",
        message: `¿Deseas inyectar <strong>${count}</strong> archivo(s) ISO a la partición <strong>HOLLOWDRIVE\\OSimages</strong>?`,
        okText: count === 1 ? "Inyectar ISO" : "Inyectar ISOs"
      });
      if (!ok) return;

      const pathsToCopy = queue.map(item => item.path);
      updateToolsTask('copy_isos', 'Iniciando copia de archivos ISO...', 0.02);
      const res = await window.hollowdrive.copyIsos(State.toolsSelectedDisk, pathsToCopy);
      if (!res.success) {
        finishToolsTask('copy_isos');
        await showCustomAlert("ERROR AL COPIAR", "Error al iniciar la copia de ISOs: " + (res.error || "Desconocido"));
      }
    });
  }

  // Tarjeta 2: Paquetes
  if (DOM.btnInjectPacks) {
    DOM.btnInjectPacks.addEventListener('click', async () => {
      if (!State.toolsSelectedDisk) {
        await showCustomAlert("UNIDAD NO SELECCIONADA", "Por favor, selecciona primero una unidad HOLLOWDRIVE.");
        return;
      }
      const installBato = DOM.chkToolsBato ? DOM.chkToolsBato.checked : false;
      const installPack = DOM.chkToolsPack ? DOM.chkToolsPack.checked : false;

      if (!installBato && !installPack) {
        await showCustomAlert("PAQUETES NO SELECCIONADOS", "Por favor, marca al menos un paquete para inyectar.");
        return;
      }

      const ok = await showCustomConfirm({
        title: "INYECCIÓN DE PAQUETES",
        message: "¿Deseas inyectar los paquetes seleccionados en la unidad HOLLOWDRIVE?",
        okText: "Inyectar"
      });
      if (!ok) return;

      updateToolsTask('inject_packages', 'Iniciando inyección de paquetes...', 0.05);
      const res = await window.hollowdrive.injectToolsPackages(State.toolsSelectedDisk, installBato, installPack);
      if (!res.success) {
        finishToolsTask('inject_packages');
        await showCustomAlert("ERROR EN INYECCIÓN", "Error al iniciar la inyección: " + (res.error || "Desconocido"));
      }
    });
  }

  // Tarjeta 3: Sistema Portable & Modal de Opciones
  if (DOM.btnOpenPortableOptions) {
    DOM.btnOpenPortableOptions.addEventListener('click', async (e) => {
      e.stopPropagation();
      if (!State.toolsSelectedDisk) {
        await showCustomAlert("UNIDAD NO SELECCIONADA", "Por favor, selecciona primero una unidad HOLLOWDRIVE.");
        return;
      }
      openModal(DOM.modalPortableOptions);
    });
  }

  if (DOM.btnToolsCachyUpdate) {
    DOM.btnToolsCachyUpdate.addEventListener('click', () => setToolsCachyMode('actualizar'));
  }
  if (DOM.btnToolsCachyInstall) {
    DOM.btnToolsCachyInstall.addEventListener('click', () => setToolsCachyMode('instalar'));
  }

  if (DOM.toolsFlavorRadios) {
    DOM.toolsFlavorRadios.forEach(radio => {
      radio.addEventListener('change', (e) => {
        State.toolsCachyFlavor = e.target.value;
      });
    });
  }

  if (DOM.toolsSliderCachy) {
    DOM.toolsSliderCachy.addEventListener('input', (e) => {
      State.toolsCachySize = parseFloat(e.target.value) || 20.0;
      const maxDispo = State.toolsDiskInfo ? (State.toolsDiskInfo.espacio_derecha || 0) : 0;
      if (DOM.toolsCachySpaceText) {
        DOM.toolsCachySpaceText.textContent = `Tamaño seleccionado: ${State.toolsCachySize.toFixed(1)} GB (Disponible: ${maxDispo.toFixed(2)} GB)`;
      }
      renderToolsBars();
    });
  }

  if (DOM.btnApplyCachy) {
    DOM.btnApplyCachy.addEventListener('click', async () => {
      if (!State.toolsSelectedDisk) {
        await showCustomAlert("UNIDAD NO SELECCIONADA", "Por favor, selecciona primero una unidad HOLLOWDRIVE.");
        return;
      }

      const modo = State.toolsCachyMode;
      if (modo === 'actualizar') {
        const confirmed = await showCustomConfirm({
          title: "CONFIRMAR ACTUALIZACIÓN",
          message: "Se descargarán y flashearán los datos más recientes en las particiones de <strong>GRUB</strong> y <strong>CachyOS</strong> del disco seleccionado.<br/><br/>¿Deseas continuar?",
          okText: "Actualizar CachyOS"
        });
        if (!confirmed) return;

        updateToolsTask('cachyos', 'Preparando actualización de CachyOS...', 0.05);
        const res = await window.hollowdrive.cachyosToolsAction(State.toolsSelectedDisk, 'actualizar', State.toolsCachyFlavor, 0);
        if (!res.success) {
          finishToolsTask('cachyos');
          await showCustomAlert("ERROR EN ACTUALIZACIÓN", "Error iniciando actualización: " + (res.error || "Desconocido"));
        }
      } else {
        const confirmed = await showCustomConfirm({
          title: "CONFIRMAR INSTALACIÓN",
          message: `<div style="color:#ef4444; font-weight:800; margin-bottom:8px;">ATENCIÓN:</div>Se reestructurará el espacio libre a la derecha de HOLLOWDRIVE y se creará una nueva partición CachyOS de <strong>${State.toolsCachySize.toFixed(1)} GB</strong>.<br/><br/>¿Proceder con la operación?`,
          okText: "Instalar CachyOS",
          isDanger: true
        });
        if (!confirmed) return;

        updateToolsTask('cachyos', 'Preparando instalación de CachyOS...', 0.05);
        const res = await window.hollowdrive.cachyosToolsAction(State.toolsSelectedDisk, 'instalar', State.toolsCachyFlavor, State.toolsCachySize);
        if (!res.success) {
          finishToolsTask('cachyos');
          await showCustomAlert("ERROR EN INSTALACIÓN", "Error iniciando instalación: " + (res.error || "Desconocido"));
        }
      }
    });
  }

  // Cancelar operación en vivo de HollowTools
  if (DOM.btnCancelToolsOp) {
    DOM.btnCancelToolsOp.addEventListener('click', async () => {
      const ok = await showCustomConfirm({
        title: "CANCELAR TODAS LAS OPERACIONES",
        message: "¿Estás seguro de que deseas cancelar todas las operaciones en curso de HollowTools?",
        okText: "Sí, cancelar todas",
        isDanger: true
      });
      if (ok) {
        await window.hollowdrive.cancelToolsAction(null);
      }
    });
  }

  // Escuchadores de eventos emitidos desde Python para HollowTools
  window.hollowdrive.on('tools_progress', (data) => {
    const taskKey = (data && data.task) ? data.task : 'copy_isos';
    updateToolsTask(taskKey, data.message || 'Procesando...', data.progress || 0);
  });

  window.hollowdrive.on('tools_success', async (data) => {
    const taskKey = (data && data.task) ? data.task : 'copy_isos';
    finishToolsTask(taskKey);
    if (taskKey === 'copy_isos') {
      clearIsoQueue();
    }
    await showCustomAlert("OPERACIÓN COMPLETADA", data.message || "¡Operación completada con éxito!");
    if (State.toolsSelectedDisk) {
      onToolsDiskSelected(State.toolsSelectedDisk);
    }
  });

  window.hollowdrive.on('tools_error', async (data) => {
    const taskKey = (data && data.task) ? data.task : 'copy_isos';
    finishToolsTask(taskKey);
    await showCustomAlert("ERROR EN OPERACIÓN", "Error en la operación: " + (data.error || "Error desconocido"));
  });

  window.hollowdrive.on('tools_cancel', async (data) => {
    const taskKey = (data && data.task) ? data.task : null;
    finishToolsTask(taskKey);
    await showCustomAlert("OPERACIÓN CANCELADA", "Operación cancelada por el usuario.");
  });

  // =========================================================================
  // 🏠 NAVEGACIÓN DESDE EL HUB
  // =========================================================================
  const enterHollowdrive = async () => {
    if (isScreenTransitioning || isWizardStepTransitioning) return;
    setWizardStep(1, true);
    await setScreen('wizard');
  };
  const cardHollow = document.getElementById('hubCardHollow');
  if (cardHollow) cardHollow.addEventListener('click', enterHollowdrive);
  const btnHollow = document.getElementById('hubBtnHollow');
  if (btnHollow) btnHollow.addEventListener('click', (e) => { e.stopPropagation(); enterHollowdrive(); });

  const enterTools = async () => {
    if (isScreenTransitioning || isWizardStepTransitioning) return;
    await setScreen('tools');
  };
  const cardTools = document.getElementById('hubCardTools');
  if (cardTools) cardTools.addEventListener('click', enterTools);
  const btnTools = document.getElementById('hubBtnTools');
  if (btnTools) btnTools.addEventListener('click', (e) => { e.stopPropagation(); enterTools(); });

  const btnBackTools = document.getElementById('btnBackFromTools');
  if (btnBackTools) {
    btnBackTools.addEventListener('click', async (e) => {
      if (e) { e.preventDefault(); e.stopPropagation(); }
      if (State.toolsIsOperating) {
        showCustomAlert("OPERACIÓN EN CURSO", "No puedes salir de HollowTools mientras haya una operación de copia, inyección o particionado en progreso. Cancélala primero si deseas salir.");
        return;
      }
      await setScreen('hub');
    });
  }

  // Conexión con los métodos globales en window para garantizar reactividad total
  window.State = State;
  window._setScreenReal = setScreen;
  window._setWizardStepReal = setWizardStep;
  window._enterHollowdriveReal = enterHollowdrive;
  window._enterToolsReal = enterTools;
  window._handleStartInstallClickReal = handleStartInstallClick;
  window._wizardPrevReal = handleWizardPrev;
  window.startFullInstallation = startFullInstallation;
  window.parseStatusMessage = parseStatusMessage;
  window.setInstallViewMode = setInstallViewMode;
  window.updateSimpleProgress = updateSimpleProgress;
  window.resetInstallProcessUI = resetInstallProcessUI;
  window._closeOverlayInfoReal = handleCloseOverlayInfo;

  window.setScreen = setScreen;
  window.setWizardStep = setWizardStep;
  window.enterHollowdrive = (e) => { if (e && e.stopPropagation) e.stopPropagation(); enterHollowdrive(); };
  window.enterTools = (e) => { if (e && e.stopPropagation) e.stopPropagation(); enterTools(); };
  window.openModal = openModal;
  window.closeModal = closeModal;
  window.closeOverlayInfo = handleCloseOverlayInfo;
  window.openOverlayInfo = () => openModal(DOM.overlayInfo || document.getElementById('overlayInfo'));
  window.openModalDonate = (e) => { if (e && e.stopPropagation) e.stopPropagation(); openModal(DOM.modalDonate || document.getElementById('modalDonate')); };
  window.startInstallClick = (e) => { if (e && e.stopPropagation) e.stopPropagation(); handleStartInstallClick(); };
  window.wizardNext = (e) => { handleWizardNext(e); };
  window.wizardPrev = (e) => { if (e && e.stopPropagation) e.stopPropagation(); handleWizardPrev(); };

  // =========================================================================
  // 🎬 CONTROL Y BARRA DE PROGRESO INTERACTIVA DE VÍDEOS
  // =========================================================================
  function formatVideoTime(seconds) {
    if (isNaN(seconds) || seconds < 0) return "0:00";
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  }

  function initVideoScrubbers() {
    const boxes = document.querySelectorAll('.video-preview-box');
    boxes.forEach(box => {
      const video = box.querySelector('video');
      const hoverBar = box.querySelector('.video-hover-bar');
      const playBtn = box.querySelector('.video-play-btn');
      const track = box.querySelector('.video-scrub-track');
      const fill = box.querySelector('.video-scrub-fill');
      const thumb = box.querySelector('.video-scrub-thumb');
      const timeChip = box.querySelector('.video-time-chip');

      if (!video || !hoverBar || !track || !fill) return;

      const updateProgress = () => {
        if (!video.duration || isNaN(video.duration)) {
          fill.style.width = '0%';
          if (thumb) thumb.style.left = '0%';
          if (timeChip) timeChip.textContent = '0:00 / 0:00';
          return;
        }
        const pct = Math.min(100, Math.max(0, (video.currentTime / video.duration) * 100));
        fill.style.width = `${pct}%`;
        if (thumb) thumb.style.left = `${pct}%`;
        if (timeChip) {
          timeChip.textContent = `${formatVideoTime(video.currentTime)} / ${formatVideoTime(video.duration)}`;
        }
      };

      video.addEventListener('timeupdate', updateProgress);
      video.addEventListener('loadedmetadata', updateProgress);
      video.addEventListener('durationchange', updateProgress);

      video.addEventListener('play', () => {
        if (playBtn) playBtn.classList.remove('paused');
      });
      video.addEventListener('pause', () => {
        if (playBtn) playBtn.classList.add('paused');
      });

      if (playBtn) {
        playBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          if (video.paused) {
            video.play().catch(() => {});
          } else {
            video.pause();
          }
        });
      }

      // Clic en el propio vídeo para alternar pausa/reproducción
      video.addEventListener('click', (e) => {
        e.stopPropagation();
        if (video.paused) {
          video.play().catch(() => {});
        } else {
          video.pause();
        }
      });

      // Clic y arrastre (scrubbing) interactivo en la barra
      let isScrubbing = false;
      const seek = (e) => {
        const rect = track.getBoundingClientRect();
        if (rect.width <= 0) return;
        const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
        const pct = x / rect.width;
        if (video.duration && !isNaN(video.duration)) {
          video.currentTime = pct * video.duration;
          updateProgress();
        }
      };

      track.addEventListener('mousedown', (e) => {
        e.stopPropagation();
        isScrubbing = true;
        hoverBar.classList.add('is-scrubbing');
        seek(e);

        const onMouseMove = (moveEvent) => {
          if (isScrubbing) {
            seek(moveEvent);
          }
        };

        const onMouseUp = () => {
          if (isScrubbing) {
            isScrubbing = false;
            hoverBar.classList.remove('is-scrubbing');
            window.removeEventListener('mousemove', onMouseMove);
            window.removeEventListener('mouseup', onMouseUp);
          }
        };

        window.addEventListener('mousemove', onMouseMove);
        window.addEventListener('mouseup', onMouseUp);
      });
    });
  }

  // =========================================================================
  // 🚀 INICIALIZACIÓN
  // =========================================================================
  async function checkInternetConnection() {
    try {
      const res = await window.hollowdrive.checkInternet();
      if (res && res.connected === false) {
        openModal(DOM.modalNoInternet);
      }
    } catch (err) {
      console.warn('[INTERNET] Error verificando conexión:', err);
    }
  }

  let isInitialized = false;
  function startApp() {
    if (isInitialized) return;
    isInitialized = true;
    try { initLanguages(); } catch (e) { console.error("[STARTUP] Error initLanguages:", e); }
    try { setInstallViewMode(State.installViewMode || 'simple'); } catch (e) { console.error("[STARTUP] Error setInstallViewMode:", e); }
    try { refreshDisks(); } catch (e) { console.error("[STARTUP] Error refreshDisks:", e); }
    try { checkInternetConnection(); } catch (e) { console.error("[STARTUP] Error checkInternetConnection:", e); }
    try { initVideoScrubbers(); } catch (e) { console.error("[STARTUP] Error initVideoScrubbers:", e); }
    try { manageStepVideos(State.wizardStep); } catch (e) { console.error("[STARTUP] Error manageStepVideos:", e); }

    // Activar siempre de forma garantizada e inmediata la pantalla principal del Hub
    try { setScreen('hub', true); } catch (e) { console.error("[STARTUP] Error setScreen hub:", e); }
  }

  window.hollowdrive.onReady(() => {
    startApp();
  });

  if (window.hollowdrive.ready) {
    startApp();
  }

  window.addEventListener('pywebviewready', () => {
    if (!isInitialized) {
      startApp();
    } else {
      initLanguages();
      refreshDisks();
    }
  });

  window.addEventListener('hollowdrive:api-ready', () => {
    if (!isInitialized) {
      startApp();
    } else {
      initLanguages();
      refreshDisks();
    }
  });
}

// =====================================================================
// Escala del caballerito independiente del escalado de Windows (100%, 125%, 150%...)
// Se contrarresta el devicePixelRatio para que mantenga siempre el mismo tamaño físico.
// =====================================================================
(function initKnightDprScale() {
  let mq = null;
  const apply = () => {
    const dpr = window.devicePixelRatio || 1;
    const factor = Math.max(0.5, Math.min(1.25, 1 / dpr));
    document.documentElement.style.setProperty('--knight-dpr-scale', factor.toFixed(3));
    // Re-suscribir al nuevo DPR (p. ej. al arrastrar la ventana a otro monitor)
    if (mq) mq.removeEventListener('change', apply);
    mq = window.matchMedia(`(resolution: ${dpr}dppx)`);
    mq.addEventListener('change', apply);
  };
  apply();
})();

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initApp);
} else {
  initApp();
}
