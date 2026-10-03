/**
 * =====================================================================
 * ✨ HOLLOWDRIVE INTRO SPLASH & SHATTER ANIMATION CONTROLLER
 * =====================================================================
 * Secuencia cinemática inicial:
 * 1. Icono central de HollowDrive gira 360° sobre sí mismo con perspectiva 3D.
 * 2. El icono se desliza suavemente hacia la izquierda.
 * 3. Desde dentro/detrás del icono, emerge el título cursivo hacia la derecha.
 * 4. Sobrecarga de energía luminosa cian/esmeralda.
 * 5. ¡Rompimiento en cachitos! (Explosión de esquirlas/cristales y chispas).
 * 6. Desvanecimiento y revelación de la pantalla principal de información (overlayInfo).
 */

(function initSplashModule() {
  'use strict';

  let splashFinished = false;
  let animFrameId = null;
  let timeouts = [];

  function safeTimeout(fn, ms) {
    const id = setTimeout(fn, ms);
    timeouts.push(id);
    return id;
  }

  function clearAllTimeouts() {
    timeouts.forEach(clearTimeout);
    timeouts = [];
    if (animFrameId) {
      cancelAnimationFrame(animFrameId);
      animFrameId = null;
    }
  }

  function finishSplash(immediate = false) {
    if (splashFinished) return;
    splashFinished = true;
    clearAllTimeouts();

    const splash = document.getElementById('introSplash');
    const infoOverlay = document.getElementById('overlayInfo');

    if (!splash) return;

    // Desactivar de inmediato cualquier captura de ratón en el splash
    splash.style.pointerEvents = 'none';

    // Asegurarse de que overlayInfo se muestre adecuadamente de forma garantizada
    try {
      if (infoOverlay) {
        if (typeof window.openOverlayInfo === 'function') {
          window.openOverlayInfo();
        } else {
          infoOverlay.classList.remove('fade-out');
          infoOverlay.style.visibility = 'visible';
          infoOverlay.style.display = 'flex';
          infoOverlay.classList.add('open');
        }
      }
    } catch (e) {
      console.error("[SPLASH] Error asegurando apertura de overlayInfo:", e);
    }

    function releaseSplashMemory() {
      splash.style.display = 'none';
      cachedShards = null;
      cachedSparks = null;
      const canvas = document.getElementById('splashShatterCanvas');
      if (canvas) {
        canvas.width = 0;
        canvas.height = 0;
      }
    }

    if (immediate) {
      splash.style.transition = 'opacity 0.2s ease-out';
      splash.classList.add('fade-out');
      setTimeout(releaseSplashMemory, 210);
    } else {
      splash.classList.add('fade-out');
      setTimeout(releaseSplashMemory, 550);
    }
  }

  // Generador de esquirlas triangulares a partir de una cuadrícula con perturbación
  function createShardsFromRect(rect, img, rows, cols, epicenterX, epicenterY) {
    const shards = [];
    const cellW = rect.width / cols;
    const cellH = rect.height / rows;

    // Crear matriz de vértices perturbados
    const points = [];
    for (let r = 0; r <= rows; r++) {
      points[r] = [];
      for (let c = 0; c <= cols; c++) {
        let px = rect.left + c * cellW;
        let py = rect.top + r * cellH;

        // Vértices interiores perturbados aleatoriamente para crear fragmentos orgánicos
        if (r > 0 && r < rows && c > 0 && c < cols) {
          px += (Math.random() - 0.5) * cellW * 0.55;
          py += (Math.random() - 0.5) * cellH * 0.55;
        }
        points[r][c] = { x: px, y: py };
      }
    }

    // Convertir cada cuadrante en dos triángulos
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const p00 = points[r][c];
        const p10 = points[r][c + 1];
        const p11 = points[r + 1][c + 1];
        const p01 = points[r + 1][c];

        const tris = [
          [p00, p10, p11],
          [p00, p11, p01]
        ];

        tris.forEach(tri => {
          const cx = (tri[0].x + tri[1].x + tri[2].x) / 3;
          const cy = (tri[0].y + tri[1].y + tri[2].y) / 3;

          // Vértices relativos al baricentro para rotar sin deformación
          const v0 = { x: tri[0].x - cx, y: tri[0].y - cy };
          const v1 = { x: tri[1].x - cx, y: tri[1].y - cy };
          const v2 = { x: tri[2].x - cx, y: tri[2].y - cy };

          // Vector de explosión radial desde el epicentro
          const dx = cx - epicenterX;
          const dy = cy - epicenterY;
          const dist = Math.sqrt(dx * dx + dy * dy) + 1;
          const baseSpeed = 220 + Math.random() * 420;
          const angle = Math.atan2(dy, dx) + (Math.random() - 0.5) * 0.5;

          shards.push({
            img: img,
            rectLeft: rect.left,
            rectTop: rect.top,
            rectW: rect.width,
            rectH: rect.height,
            cx: cx,
            cy: cy,
            v0: v0,
            v1: v1,
            v2: v2,
            x: cx,
            y: cy,
            vx: Math.cos(angle) * baseSpeed,
            vy: Math.sin(angle) * baseSpeed - (40 + Math.random() * 90), // Impulso ascendente
            rot: 0,
            vRot: (Math.random() - 0.5) * 8.5,
            scale: 1,
            alpha: 1
          });
        });
      }
    }
    return shards;
  }

  let cachedShards = null;
  let cachedSparks = null;

  function precomputeShatter(iconImg, titleImg) {
    try {
      if (!iconImg || !titleImg) return;
      const iconRect = iconImg.getBoundingClientRect();
      const titleRect = titleImg.getBoundingClientRect();
      if (!iconRect.width || !titleRect.width) return;

      const iconEpicenterX = iconRect.left + iconRect.width * 0.5;
      const iconEpicenterY = iconRect.top + iconRect.height * 0.5;
      const titleEpicenterX = titleRect.left + titleRect.width * 0.35;
      const titleEpicenterY = titleRect.top + titleRect.height * 0.5;

      const iconShards = createShardsFromRect(iconRect, iconImg, 5, 5, iconEpicenterX, iconEpicenterY);
      const titleShards = createShardsFromRect(titleRect, titleImg, 4, 10, titleEpicenterX, titleEpicenterY);
      cachedShards = iconShards.concat(titleShards);

      const sparks = [];
      const sparkColors = ['#00f0ff', '#38bdf8', '#10b981', '#34d399', '#ffffff', '#e0f2fe'];
      const totalSparks = 75;

      for (let i = 0; i < totalSparks; i++) {
        const isIcon = (i % 2 === 0);
        const originX = isIcon ? iconEpicenterX + (Math.random() - 0.5) * iconRect.width : titleRect.left + Math.random() * titleRect.width;
        const originY = isIcon ? iconEpicenterY + (Math.random() - 0.5) * iconRect.height : titleEpicenterY + (Math.random() - 0.5) * titleRect.height;
        const spd = 260 + Math.random() * 620;
        const ang = Math.random() * Math.PI * 2;

        sparks.push({
          x: originX,
          y: originY,
          vx: Math.cos(ang) * spd,
          vy: Math.sin(ang) * spd - 60,
          radius: 1.2 + Math.random() * 2.8,
          color: sparkColors[Math.floor(Math.random() * sparkColors.length)],
          alpha: 1,
          life: 0,
          maxLife: 0.65 + Math.random() * 0.45
        });
      }
      cachedSparks = sparks;
    } catch (_) {}
  }

  // Animación del estallido en Canvas
  function runShatterCanvas(iconImg, titleImg) {
    try {
      const canvas = document.getElementById('splashShatterCanvas');
      if (!canvas) {
        finishSplash();
        return;
      }

      const ctx = canvas.getContext('2d');
      if (!ctx) {
        finishSplash();
        return;
      }

      const width = window.innerWidth;
      const height = window.innerHeight;
      canvas.width = width;
      canvas.height = height;

      if (!cachedShards || !cachedSparks) {
        precomputeShatter(iconImg, titleImg);
      }
      const allShards = cachedShards || [];
      const sparks = cachedSparks || [];

      let lastTime = performance.now();
      const durationSec = 0.85;
      let elapsed = 0;

      function renderFrame(now) {
        try {
          const dt = Math.min((now - lastTime) / 1000, 0.05);
          lastTime = now;
          elapsed += dt;

          ctx.clearRect(0, 0, width, height);

          const progress = Math.min(elapsed / durationSec, 1);
          const globalFade = Math.max(0, 1 - Math.pow(progress, 1.4));

          // 1. Dibujar y actualizar esquirlas
          allShards.forEach(s => {
            s.vx *= (1 - 0.95 * dt);
            s.vy += 220 * dt; // Gravedad suave
            s.x += s.vx * dt;
            s.y += s.vy * dt;
            s.rot += s.vRot * dt;
            s.alpha = globalFade;
            s.scale = Math.max(0.2, 1 - progress * 0.6);

            if (s.alpha > 0.01) {
              ctx.save();
              ctx.translate(s.x, s.y);
              ctx.rotate(s.rot);
              ctx.scale(s.scale, s.scale);
              ctx.globalAlpha = s.alpha;

              // Trazo triangular del fragmento
              ctx.beginPath();
              ctx.moveTo(s.v0.x, s.v0.y);
              ctx.lineTo(s.v1.x, s.v1.y);
              ctx.lineTo(s.v2.x, s.v2.y);
              ctx.closePath();

              // Recorte exacto y renderizado de la imagen
              ctx.clip();
              const imgRelX = s.rectLeft - s.cx;
              const imgRelY = s.rectTop - s.cy;
              if (s.img && s.img.complete && s.img.naturalWidth > 0) {
                ctx.drawImage(s.img, imgRelX, imgRelY, s.rectW, s.rectH);
              }

              // Borde brillante de cristal cian
              ctx.strokeStyle = `rgba(0, 240, 255, ${s.alpha * 0.75})`;
              ctx.lineWidth = 1.3;
              ctx.stroke();

              ctx.restore();
            }
          });

          // 2. Dibujar chispas de luz
          sparks.forEach(sp => {
            sp.life += dt;
            const spProg = sp.life / sp.maxLife;
            if (spProg < 1) {
              sp.vx *= (1 - 0.8 * dt);
              sp.vy += 80 * dt;
              sp.x += sp.vx * dt;
              sp.y += sp.vy * dt;
              const spAlpha = (1 - spProg) * globalFade;

              ctx.save();
              ctx.globalAlpha = spAlpha;
              ctx.fillStyle = sp.color;
              ctx.shadowColor = sp.color;
              ctx.shadowBlur = 8;
              ctx.beginPath();
              ctx.arc(sp.x, sp.y, sp.radius, 0, Math.PI * 2);
              ctx.fill();
              ctx.restore();
            }
          });

          if (progress < 1) {
            animFrameId = requestAnimationFrame(renderFrame);
          } else {
            ctx.clearRect(0, 0, width, height);
            finishSplash(false);
          }
        } catch (renderErr) {
          console.error("[SPLASH] Error en renderFrame:", renderErr);
          finishSplash(true);
        }
      }

      animFrameId = requestAnimationFrame(renderFrame);
    } catch (err) {
      console.error("[SPLASH] Error iniciando runShatterCanvas:", err);
      finishSplash(true);
    }
  }

  function startSequence() {
    const splash = document.getElementById('introSplash');
    const stage = document.getElementById('splashStage');
    const iconWrap = document.getElementById('splashIconWrap');
    const iconImg = document.getElementById('splashIconImg');
    const titleWrap = document.getElementById('splashTitleWrap');
    const titleImg = document.getElementById('splashTitleImg');
    const skipHint = document.getElementById('splashSkipHint');

    if (!splash || !iconWrap || !titleWrap || !iconImg || !titleImg) {
      finishSplash();
      return;
    }

    // WATCHDOG ABSOLUTO: Si por cualquier motivo el hardware o canvas tardara,
    // forzar finalización a los 4.2s para NUNCA congelar ni bloquear la interfaz
    safeTimeout(() => {
      if (!splashFinished) {
        finishSplash(false);
      }
    }, 4200);

    let splashMouseDownScreenX = 0;
    let splashMouseDownScreenY = 0;

    splash.addEventListener('mousedown', (e) => {
      splashMouseDownScreenX = e.screenX;
      splashMouseDownScreenY = e.screenY;
    });

    // Permitir saltar en cualquier momento pulsando cualquier tecla o haciendo clic
    const onUserSkip = (e) => {
      if (e.type === 'keydown') {
        if (['Control', 'Shift', 'Alt', 'Meta'].includes(e.key)) return;
      }
      if (e.type === 'click') {
        const dist = Math.hypot(e.screenX - splashMouseDownScreenX, e.screenY - splashMouseDownScreenY);
        if (dist >= 8) return; // Fue arrastre de ventana, no click de skip
      }
      cleanupListeners();
      finishSplash(true);
    };

    function cleanupListeners() {
      window.removeEventListener('keydown', onUserSkip);
      if (splash) splash.removeEventListener('click', onUserSkip);
    }

    window.addEventListener('keydown', onUserSkip);
    splash.addEventListener('click', onUserSkip);

    // Mostrar sugerencia de omitir tras 1.4s
    safeTimeout(() => {
      if (skipHint) skipHint.style.opacity = '1';
    }, 1400);

    // FASE 1: Icono gira 360° sobre sí mismo en el centro (0.0s - 1.2s)
    safeTimeout(() => {
      iconWrap.style.animation = 'splashIconSpinIn 1.2s cubic-bezier(0.18, 0.89, 0.32, 1.15) forwards';
    }, 100);

    // FASE 2: Icono se desliza suavemente hacia la izquierda (1.35s - 1.9s)
    safeTimeout(() => {
      iconWrap.style.opacity = '1';
      iconWrap.style.animation = 'splashIconSlideLeft 0.58s cubic-bezier(0.2, 0.9, 0.3, 1) forwards';
    }, 1350);

    // FASE 3: Desde dentro/detrás del icono, emerge el título cursivo hacia la derecha (1.65s - 2.45s)
    safeTimeout(() => {
      titleWrap.style.animation = 'splashTitleEmerge 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards';
      const iconHalo = document.querySelector('.splash-icon-halo');
      if (iconHalo) {
        iconHalo.style.animation = 'splashIconPulse 0.85s ease-out forwards';
      }
    }, 1650);

    // Precalcular esquirlas y chispas cuando el título ha terminado de emerger (2.48s)
    safeTimeout(() => {
      precomputeShatter(iconImg, titleImg);
    }, 2480);

    // FASE 4: Sobrecarga de resplandor luminiscente (2.55s - 2.85s)
    safeTimeout(() => {
      iconImg.style.animation = 'splashEnergySurge 0.35s ease-in-out forwards';
      titleImg.style.animation = 'splashEnergySurge 0.35s ease-in-out forwards';
    }, 2550);

    // FASE 5: ¡Se rompen en cachitos! (Explosión de fragmentos y chispas) (2.88s)
    safeTimeout(() => {
      // Ocultar elementos DOM del logo antes de comenzar la física de Canvas
      if (stage) stage.style.visibility = 'hidden';
      if (skipHint) skipHint.style.opacity = '0';
      runShatterCanvas(iconImg, titleImg);
    }, 2880);
  }

  // Iniciar cuando el DOM esté listo
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', startSequence);
  } else {
    startSequence();
  }

  // Exportar para depuración o invocación manual si fuese requerida
  window.triggerHollowDriveSplash = () => {
    splashFinished = false;
    clearAllTimeouts();
    const splash = document.getElementById('introSplash');
    const stage = document.getElementById('splashStage');
    const iconWrap = document.getElementById('splashIconWrap');
    const titleWrap = document.getElementById('splashTitleWrap');
    const iconImg = document.getElementById('splashIconImg');
    const titleImg = document.getElementById('splashTitleImg');
    const canvas = document.getElementById('splashShatterCanvas');
    if (canvas) {
      const ctx = canvas.getContext('2d');
      if (ctx) ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
    if (splash) {
      splash.style.display = 'flex';
      splash.classList.remove('fade-out');
      if (stage) stage.style.visibility = 'visible';
      if (iconWrap) {
        iconWrap.style.animation = 'none';
        iconWrap.style.opacity = '0';
      }
      if (titleWrap) {
        titleWrap.style.animation = 'none';
        titleWrap.style.opacity = '0';
        titleWrap.style.width = '';
      }
      if (iconImg) iconImg.style.animation = 'none';
      if (titleImg) titleImg.style.animation = 'none';
    }
    setTimeout(startSequence, 60);
  };
})();
