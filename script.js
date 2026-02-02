document.addEventListener("DOMContentLoaded", () => {
  const fallbackVideos = [
    '<div class="video-card tall stagger-item">',
    '  <div class="video-thumb">',
    '    <video src="FOTOS/dominadas.mp4" autoplay loop muted playsinline preload="metadata"></video>',
    "  </div>",
    '  <div class="video-meta">',
    '    <span class="tag glass-pill">Dominadas</span>',
    "    <h3>Disciplina en la barra</h3>",
    "    <p>Series limpias con enfoque técnico.</p>",
    "  </div>",
    "</div>",
    '<div class="video-card wide stagger-item">',
    '  <div class="video-thumb">',
    '    <video src="FOTOS/muscle-up.mp4" autoplay loop muted playsinline preload="metadata"></video>',
    "  </div>",
    '  <div class="video-meta">',
    '    <span class="tag glass-pill">Muscle up</span>',
    "    <h3>Transición precisa</h3>",
    "    <p>Explosivo y controlado.</p>",
    "  </div>",
    "</div>",
    '<div class="video-card stagger-item">',
    '  <div class="video-thumb">',
    '    <video src="FOTOS/pino-video.mp4" autoplay loop muted playsinline preload="metadata"></video>',
    "  </div>",
    '  <div class="video-meta">',
    '    <span class="tag glass-pill">Pino</span>',
    "    <h3>Línea en silencio</h3>",
    "    <p>Balance y respiración.</p>",
    "  </div>",
    "</div>",
    '<div class="video-card tall stagger-item">',
    '  <div class="video-thumb">',
    '    <video src="FOTOS/front-lever.mp4" autoplay loop muted playsinline preload="metadata"></video>',
    "  </div>",
    '  <div class="video-meta">',
    '    <span class="tag glass-pill">Front lever</span>',
    "    <h3>Horizonte quieto</h3>",
    "    <p>Control total en estáticos.</p>",
    "  </div>",
    "</div>",
    '<div class="video-card wide stagger-item">',
    '  <div class="video-thumb">',
    '    <video src="FOTOS/fondos.mp4" autoplay loop muted playsinline preload="metadata"></video>',
    "  </div>",
    '  <div class="video-meta">',
    '    <span class="tag glass-pill">Fondos</span>',
    "    <h3>Fondo profundo</h3>",
    "    <p>Ritmo de resistencia brutal.</p>",
    "  </div>",
    "</div>",
    '<div class="video-card stagger-item">',
    '  <div class="video-thumb">',
    '    <video src="FOTOS/back-lever.mp4" autoplay loop muted playsinline preload="metadata"></video>',
    "  </div>",
    '  <div class="video-meta">',
    '    <span class="tag glass-pill">Back lever</span>',
    "    <h3>Reversa total</h3>",
    "    <p>Control posterior con aura.</p>",
    "  </div>",
    "</div>",
  ].join("");

  const fallbackEvents = [
    '<article class="news-card glass-card stagger-item">',
    '  <span class="news-date">16-19 ABR 2026 - Colonia, Alemania</span>',
    "  <h3>Calisthenics Cup 2026</h3>",
    "  <p>FIBO Fitness Convention.</p>",
    '  <span class="news-tag">Europa</span>',
    "</article>",
    '<article class="news-card glass-card stagger-item">',
    '  <span class="news-date">MAR/ABR 2026 - Málaga, España</span>',
    "  <h3>Copa Málaga</h3>",
    "  <p>Fecha prevista entre marzo y abril.</p>",
    '  <span class="news-tag">Nacional</span>',
    "</article>",
    '<article class="news-card glass-card stagger-item">',
    '  <span class="news-date">14-15 MAR 2026 - O Porto, Portugal</span>',
    "  <h3>Endurance Battles</h3>",
    "  <p>Eagle Calisthenics.</p>",
    '  <span class="news-tag">Europa</span>',
    "</article>",
  ].join("");

  const fallbackAccess = [
    '<div class="access-grid" data-stagger>',
    '  <div class="portal-card glass-card stagger-item">',
    "    <h3>Acceso único</h3>",
    "    <p>Usa tus credenciales de alumno o admin.</p>",
    '    <form class="admin-form" action="/login" method="post">',
    '      <div class="form-field">',
    '        <label for="portal_user">Usuario</label>',
    '        <input id="portal_user" name="username" type="text" required>',
    "      </div>",
    '      <div class="form-field">',
    '        <label for="portal_pass">Contraseña</label>',
    '        <input id="portal_pass" name="password" type="password" required>',
    "      </div>",
    '      <button class="btn glass primary" type="submit">Entrar</button>',
    "    </form>",
    "  </div>",
    "</div>",
    '<p class="form-note">Si ves esta versión estática, inicia el servidor con python app.py.</p>',
  ].join("");

  const replaceIfToken = (selector, token, html) => {
    const el = document.querySelector(selector);
    if (!el || !el.textContent.includes(token)) {
      return false;
    }
    el.innerHTML = html;
    return true;
  };

  replaceIfToken(".video-arena", "{{VIDEOS}}", fallbackVideos);
  replaceIfToken(".news-grid", "{{EVENTS}}", fallbackEvents);

  const accessContainer = document.querySelector("#acceso .container");
  if (accessContainer && accessContainer.innerHTML.includes("{{ACCESS_CONTENT}}")) {
    accessContainer.innerHTML = accessContainer.innerHTML.replace(
      "{{ACCESS_CONTENT}}",
      fallbackAccess
    );
  }

  const formCard = document.querySelector(".form-card");
  if (formCard && formCard.innerHTML.includes("{{FORM_ALERT}}")) {
    formCard.innerHTML = formCard.innerHTML.replace("{{FORM_ALERT}}", "");
  }

  const lockMute = (video) => {
    const enforce = () => {
      if (!video.muted || video.volume > 0) {
        video.muted = true;
        video.volume = 0;
      }
    };
    video.muted = true;
    video.volume = 0;
    video.setAttribute("muted", "");
    video.addEventListener("volumechange", enforce);
    video.addEventListener("loadedmetadata", enforce);
  };

  document.querySelectorAll("video").forEach(lockMute);

  const staggerGroups = document.querySelectorAll("[data-stagger]");
  staggerGroups.forEach((group) => {
    const items = group.querySelectorAll(".stagger-item");
    items.forEach((item, index) => {
      item.style.setProperty("--stagger-delay", `${index * 0.12}s`);
    });
  });

  const reveals = document.querySelectorAll(".reveal");
  const observer = new IntersectionObserver(
    (entries, obs) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          obs.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.2 }
  );

  reveals.forEach((section) => observer.observe(section));
});
