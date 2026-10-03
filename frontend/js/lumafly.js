/**
 * =====================================================================
 * 🪰 LUMÉLULAS (LUMAFLYS) DE HOLLOW KNIGHT
 * Criaturas de luz muy simples que flotan por el fondo y juguetean
 * alrededor del puntero con un aleteo orgánico y suave resplandor.
 * =====================================================================
 */
(function() {
  'use strict';

  let canvas = null;
  let ctx = null;
  let width = 0;
  let height = 0;
  let dpr = 1;
  let animationFrameId = null;

  const NUM_LUMAFLIES = 20;
  const lumaflies = [];

  const mouse = {
    x: -999,
    y: -999,
    active: false,
    lastMove: 0
  };

  function init() {
    canvas = document.getElementById('lumaflyCanvas');
    if (!canvas) {
      canvas = document.createElement('canvas');
      canvas.id = 'lumaflyCanvas';
      canvas.className = 'lumafly-canvas';
      document.body.prepend(canvas);
    }

    ctx = canvas.getContext('2d');
    if (!ctx) return;

    resize();
    window.addEventListener('resize', resize, { passive: true });

    window.addEventListener('mousemove', function(e) {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
      mouse.active = true;
      mouse.lastMove = performance.now();
    }, { passive: true });

    window.addEventListener('mouseleave', function() {
      mouse.active = false;
    }, { passive: true });

    // Crear lumélulas
    for (let i = 0; i < NUM_LUMAFLIES; i++) {
      const size = 2.2 + Math.random() * 2.2;
      lumaflies.push({
        x: Math.random() * (width || window.innerWidth || 800),
        y: Math.random() * (height || window.innerHeight || 600),
        vx: (Math.random() - 0.5) * 0.7,
        vy: (Math.random() - 0.5) * 0.7,
        size: size,
        glowRadius: size * 4.2 + Math.random() * 4,
        wanderAngle: Math.random() * Math.PI * 2,
        flutterSpeed: 0.18 + Math.random() * 0.12,
        flutterPhase: Math.random() * Math.PI * 2,
        pulseSpeed: 0.025 + Math.random() * 0.03,
        pulsePhase: Math.random() * Math.PI * 2,
        baseAlpha: 0.65 + Math.random() * 0.35,
        orbitOffset: Math.random() * Math.PI * 2,
        orbitRadius: 35 + Math.random() * 75
      });
    }

    document.addEventListener('visibilitychange', function() {
      if (document.hidden) {
        if (animationFrameId) cancelAnimationFrame(animationFrameId);
      } else {
        lastTime = performance.now();
        requestAnimationFrame(animate);
      }
    });

    lastTime = performance.now();
    requestAnimationFrame(animate);
  }

  function resize() {
    if (!canvas || !ctx) return;
    dpr = window.devicePixelRatio || 1;
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    canvas.style.width = width + 'px';
    canvas.style.height = height + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  let lastTime = 0;
  let lastModalCheckTime = 0;
  let cachedModalOpen = false;

  function animate(time) {
    animationFrameId = requestAnimationFrame(animate);

    const dt = Math.min((time - lastTime) / 1000, 0.1);
    lastTime = time;

    ctx.clearRect(0, 0, width, height);

    // Comprobar modales abiertos cada 250ms en vez de en cada fotograma para eliminar sobrecoste DOM
    if (time - lastModalCheckTime > 250) {
      lastModalCheckTime = time;
      cachedModalOpen = Boolean(
        document.querySelector('#overlayInfo.open, #modalDonate.open, .custom-modal-overlay.open, .modal.open')
      );
    }
    const isMouseActive = mouse.active && !cachedModalOpen && (time - mouse.lastMove < 4000);

    for (let i = 0; i < lumaflies.length; i++) {
      const l = lumaflies[i];

      l.flutterPhase += l.flutterSpeed * 60 * dt;
      l.pulsePhase += l.pulseSpeed * 60 * dt;
      const currentAlpha = l.baseAlpha * (0.8 + 0.2 * Math.sin(l.pulsePhase));

      // Movimiento orgánico y flotación natural
      l.wanderAngle += (Math.random() - 0.5) * 0.35;
      let targetVx = Math.cos(l.wanderAngle) * 0.65;
      let targetVy = Math.sin(l.wanderAngle) * 0.65 - 0.12; // sutil flotación hacia arriba

      // Reacción curiosa hacia el puntero
      if (isMouseActive) {
        const dx = mouse.x - l.x;
        const dy = mouse.y - l.y;
        const dist = Math.hypot(dx, dy);

        if (dist < 260) {
          const orbitAngle = time * 0.0016 + l.orbitOffset;
          const targetX = mouse.x + Math.cos(orbitAngle) * l.orbitRadius;
          const targetY = mouse.y + Math.sin(orbitAngle) * (l.orbitRadius * 0.7);
          const tx = targetX - l.x;
          const ty = targetY - l.y;
          const tdist = Math.hypot(tx, ty);

          if (tdist > 6) {
            targetVx = (tx / tdist) * 1.7;
            targetVy = (ty / tdist) * 1.7;
          }
        }
      }

      // Suavizado inercial de la velocidad
      l.vx += (targetVx - l.vx) * 0.04;
      l.vy += (targetVy - l.vy) * 0.04;

      l.x += l.vx;
      l.y += l.vy;

      // Límites con margen para entrar y salir suavemente
      const margin = 35;
      if (l.x < -margin) l.x = width + margin;
      if (l.x > width + margin) l.x = -margin;
      if (l.y < -margin) l.y = height + margin;
      if (l.y > height + margin) l.y = -margin;

      // Dibujo de la lumélula
      ctx.save();
      ctx.translate(l.x, l.y);

      const angle = Math.atan2(l.vy, l.vx) + Math.PI / 2;
      ctx.rotate(angle);

      // 1. Halo suave de luz dorada/blanca
      const glow = ctx.createRadialGradient(0, 0, 1, 0, 0, l.glowRadius);
      glow.addColorStop(0, 'rgba(255, 255, 235, ' + (0.95 * currentAlpha) + ')');
      glow.addColorStop(0.28, 'rgba(251, 216, 120, ' + (0.55 * currentAlpha) + ')');
      glow.addColorStop(0.65, 'rgba(245, 158, 11, ' + (0.16 * currentAlpha) + ')');
      glow.addColorStop(1, 'rgba(245, 158, 11, 0)');
      ctx.fillStyle = glow;
      ctx.beginPath();
      ctx.arc(0, 0, l.glowRadius, 0, Math.PI * 2);
      ctx.fill();

      // 2. Alitas translúcidas batiendo
      const wingSpan = l.size * 1.8 * Math.abs(Math.sin(l.flutterPhase));
      ctx.fillStyle = 'rgba(255, 255, 255, ' + (0.48 * currentAlpha) + ')';
      ctx.strokeStyle = 'rgba(255, 255, 240, ' + (0.75 * currentAlpha) + ')';
      ctx.lineWidth = 0.6;

      // Ala izquierda
      ctx.beginPath();
      ctx.ellipse(-l.size * 0.5, -wingSpan * 0.4, l.size * 0.6, Math.max(1, wingSpan), -0.4, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();

      // Ala derecha
      ctx.beginPath();
      ctx.ellipse(l.size * 0.5, -wingSpan * 0.4, l.size * 0.6, Math.max(1, wingSpan), 0.4, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();

      // 3. Cuerpo brillante y simple (semilla de luz)
      ctx.fillStyle = 'rgba(255, 255, 255, ' + currentAlpha + ')';
      ctx.beginPath();
      ctx.ellipse(0, 0, l.size * 0.7, l.size * 1.1, 0, 0, Math.PI * 2);
      ctx.fill();

      ctx.restore();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
