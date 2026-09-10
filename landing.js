document.querySelectorAll('.video-thumb video').forEach((video) => {
  // Nothing is downloaded until the visitor explicitly chooses a clip.
  video.autoplay = false;
  video.removeAttribute('autoplay');
  video.preload = 'none';
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'video-play';
  button.textContent = '▶ Ver el vídeo';
  const title = video.closest('.video-card')?.querySelector('h3')?.textContent || 'entrenamiento';
  button.setAttribute('aria-label', `Reproducir: ${title}`);
  video.parentElement.append(button);
  button.addEventListener('click', async () => {
    document.querySelectorAll('video').forEach((other) => { if (other !== video) other.pause(); });
    if (!video.getAttribute('src')) {
      const source = video.dataset.src;
      if (!source) return;
      const base = document.body.dataset.mediaBaseUrl;
      video.src = base && !/^(https?:)?\/\//i.test(source) && !source.startsWith('/uploads/')
        ? `${base.replace(/\/$/, '')}/${source.replace(/^\//, '')}` : source;
    }
    video.controls = true;
    button.hidden = true;
    try { await video.play(); } catch { button.hidden = false; button.textContent = '▶ Reintentar'; }
  });
  video.addEventListener('error', () => { button.hidden = false; button.textContent = '▶ Reintentar'; });
});
document.addEventListener('visibilitychange', () => {
  if (document.hidden) document.querySelectorAll('video').forEach((video) => video.pause());
});

// Keep carousel navigation in sync with touch, trackpad and keyboard scrolling.
const videoTrack = document.querySelector('#video-carousel');
if (videoTrack) {
  const previous = document.querySelector('[data-video-prev]');
  const next = document.querySelector('[data-video-next]');
  const count = document.querySelector('.gallery-count');
  const cards = [...videoTrack.querySelectorAll('.video-card')];
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const step = () => cards.length > 1 ? cards[1].offsetLeft - cards[0].offsetLeft : videoTrack.clientWidth;
  const update = () => {
    previous.disabled = videoTrack.scrollLeft <= 2;
    next.disabled = videoTrack.scrollLeft >= videoTrack.scrollWidth - videoTrack.clientWidth - 2;
    const current = Math.min(cards.length, Math.round(videoTrack.scrollLeft / step()) + 1);
    count.textContent = cards.length ? `${String(current).padStart(2, '0')} / ${String(cards.length).padStart(2, '0')}` : '';
  };
  const move = (direction) => videoTrack.scrollBy({left:direction * step(),behavior:reducedMotion.matches ? 'instant' : 'smooth'});
  previous.hidden = next.hidden = cards.length < 2;
  previous.addEventListener('click', () => move(-1));
  next.addEventListener('click', () => move(1));
  videoTrack.addEventListener('keydown', (event) => {
    if (event.target !== videoTrack || !['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
    event.preventDefault();
    move(event.key === 'ArrowRight' ? 1 : -1);
  });
  videoTrack.addEventListener('scroll', update, {passive:true});
  new ResizeObserver(update).observe(videoTrack);
  update();
  // Pause a playing clip when it leaves the strip or the page viewport.
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(({target,isIntersecting}) => { if (!isIntersecting) target.pause(); });
  }, {threshold:0});
  videoTrack.querySelectorAll('video').forEach((video) => observer.observe(video));
}

const partners = document.querySelector('.partners');
if (partners) {
  const toggle = partners.querySelector('.sponsor-toggle');
  partners.querySelectorAll('.sponsor-loop[aria-hidden="true"]').forEach((copy) => {
    copy.inert = true;
    copy.querySelectorAll('a').forEach((link) => { link.tabIndex = -1; });
  });
  toggle.hidden = !partners.querySelector('.sponsor-track');
  toggle.addEventListener('click', () => {
    const paused = partners.classList.toggle('is-paused');
    toggle.setAttribute('aria-pressed', String(paused));
    toggle.textContent = paused ? 'Reanudar carrusel' : 'Pausar carrusel';
  });
}
