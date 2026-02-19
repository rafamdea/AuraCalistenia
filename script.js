document.addEventListener("DOMContentLoaded", () => {
  const lowPerfDevice = (() => {
    const cores = Number(navigator.hardwareConcurrency || 8);
    const memory = Number(navigator.deviceMemory || 8);
    return cores <= 4 || memory <= 4;
  })();
  if (lowPerfDevice) {
    document.documentElement.classList.add("perf-lite");
  }

  const fallbackVideos = [
    '<div class="video-card tall stagger-item">',
    '  <div class="video-thumb">',
    '    <video data-src="FOTOS/dominadas.mp4" autoplay loop muted playsinline preload="none"></video>',
    "  </div>",
    '  <div class="video-meta">',
    '    <span class="tag glass-pill">Dominadas</span>',
    "    <h3>Disciplina en la barra</h3>",
    "    <p>Series limpias con enfoque técnico.</p>",
    "  </div>",
    "</div>",
    '<div class="video-card wide stagger-item">',
    '  <div class="video-thumb">',
    '    <video data-src="FOTOS/muscle-up.mp4" autoplay loop muted playsinline preload="none"></video>',
    "  </div>",
    '  <div class="video-meta">',
    '    <span class="tag glass-pill">Muscle up</span>',
    "    <h3>Transición precisa</h3>",
    "    <p>Explosivo y controlado.</p>",
    "  </div>",
    "</div>",
    '<div class="video-card stagger-item">',
    '  <div class="video-thumb">',
    '    <video data-src="FOTOS/pino-video.mp4" autoplay loop muted playsinline preload="none"></video>',
    "  </div>",
    '  <div class="video-meta">',
    '    <span class="tag glass-pill">Pino</span>',
    "    <h3>Línea en silencio</h3>",
    "    <p>Balance y respiración.</p>",
    "  </div>",
    "</div>",
    '<div class="video-card tall stagger-item">',
    '  <div class="video-thumb">',
    '    <video data-src="FOTOS/front-lever.mp4" autoplay loop muted playsinline preload="none"></video>',
    "  </div>",
    '  <div class="video-meta">',
    '    <span class="tag glass-pill">Front lever</span>',
    "    <h3>Horizonte quieto</h3>",
    "    <p>Control total en estáticos.</p>",
    "  </div>",
    "</div>",
    '<div class="video-card wide stagger-item">',
    '  <div class="video-thumb">',
    '    <video data-src="FOTOS/fondos.mp4" autoplay loop muted playsinline preload="none"></video>',
    "  </div>",
    '  <div class="video-meta">',
    '    <span class="tag glass-pill">Fondos</span>',
    "    <h3>Fondo profundo</h3>",
    "    <p>Ritmo de resistencia brutal.</p>",
    "  </div>",
    "</div>",
    '<div class="video-card stagger-item">',
    '  <div class="video-thumb">',
    '    <video data-src="FOTOS/back-lever.mp4" autoplay loop muted playsinline preload="none"></video>',
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

  const prefersReducedMotion =
    window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const ensureVideoSource = (video) => {
    const src = video.getAttribute("src");
    if (src && src.trim()) {
      return true;
    }
    const lazySrc = (video.dataset && video.dataset.src) || video.getAttribute("data-src") || "";
    if (!lazySrc.trim()) {
      return false;
    }
    video.setAttribute("src", lazySrc.trim());
    video.load();
    return true;
  };

  const safePlayVideo = (video) => {
    if (prefersReducedMotion) {
      return;
    }
    if (!ensureVideoSource(video)) {
      return;
    }
    const playPromise = video.play();
    if (playPromise && playPromise.catch) {
      playPromise.catch(() => {});
    }
  };

  const pauseVideo = (video) => {
    if (!video.paused) {
      video.pause();
    }
    video.dataset.inViewport = "false";
    const wrapper =
      video.closest(".video-thumb") || video.closest(".progression-media");
    if (wrapper) {
      wrapper.classList.remove("is-looping");
    }
  };

  const setupLoopIndicator = (video) => {
    const wrapper =
      video.closest(".video-thumb") || video.closest(".progression-media");
    if (!wrapper) {
      return;
    }
    if (!wrapper.querySelector(".video-loop-indicator")) {
      const indicator = document.createElement("span");
      indicator.className = "video-loop-indicator";
      wrapper.appendChild(indicator);
    }
    const safePlay = () => {
      if (video.dataset.inViewport !== "true") {
        return;
      }
      safePlayVideo(video);
    };
    video.loop = false;
    video.removeAttribute("loop");
    video.addEventListener("ended", () => {
      wrapper.classList.add("is-looping");
      window.setTimeout(() => {
        video.currentTime = 0;
        safePlay();
      }, 200);
    });
    const clearIndicator = () => wrapper.classList.remove("is-looping");
    video.addEventListener("playing", clearIndicator);
    video.addEventListener("play", clearIndicator);
  };

  const allVideos = Array.from(document.querySelectorAll("video"));
  allVideos.forEach((video) => {
    video.preload = "none";
    lockMute(video);
    setupLoopIndicator(video);
    video.dataset.inViewport = "false";
    pauseVideo(video);
  });

  if (!prefersReducedMotion && allVideos.length) {
    const videoObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          const video = entry.target;
          const isVisible = entry.isIntersecting;
          if (isVisible) {
            video.dataset.inViewport = "true";
            safePlayVideo(video);
          } else if (video.dataset.inViewport === "true") {
            pauseVideo(video);
          }
        });
      },
      {
        threshold: 0.1,
        rootMargin: "200px 0px 200px 0px",
      }
    );
    allVideos.forEach((video) => videoObserver.observe(video));
  }

  const horizontalTracks = Array.from(
    document.querySelectorAll(".video-arena, .progression-grid, .day-grid, .portal-items-row")
  );
  horizontalTracks.forEach((track) => {
    track.addEventListener(
      "wheel",
      (event) => {
        if (event.ctrlKey) {
          return;
        }
        if (track.scrollWidth <= track.clientWidth + 2) {
          return;
        }
        const mostlyVertical = Math.abs(event.deltaY) > Math.abs(event.deltaX);
        if (!mostlyVertical || Math.abs(event.deltaY) < 1) {
          return;
        }
        event.preventDefault();
        track.scrollLeft += event.deltaY;
      },
      { passive: false }
    );
  });

  const dragTracks = Array.from(document.querySelectorAll(".video-arena, .progression-grid"));
  dragTracks.forEach((track) => {
    let pointerDown = false;
    let startX = 0;
    let startLeft = 0;
    let moved = false;

    track.addEventListener("pointerdown", (event) => {
      if (event.pointerType !== "mouse" || event.button !== 0) {
        return;
      }
      if (track.scrollWidth <= track.clientWidth + 2) {
        return;
      }
      pointerDown = true;
      moved = false;
      startX = event.clientX;
      startLeft = track.scrollLeft;
      track.style.scrollBehavior = "auto";
      track.setPointerCapture(event.pointerId);
    });

    track.addEventListener("pointermove", (event) => {
      if (!pointerDown) {
        return;
      }
      const delta = event.clientX - startX;
      if (Math.abs(delta) > 2) {
        moved = true;
      }
      track.scrollLeft = startLeft - delta;
    });

    const stopDrag = (event) => {
      if (!pointerDown) {
        return;
      }
      pointerDown = false;
      track.style.scrollBehavior = "";
      if (event && typeof event.pointerId === "number") {
        try {
          track.releasePointerCapture(event.pointerId);
        } catch (error) {
          // Ignore browsers that already released the pointer capture.
        }
      }
      setTimeout(() => {
        moved = false;
      }, 0);
    };

    track.addEventListener("pointerup", stopDrag);
    track.addEventListener("pointercancel", stopDrag);
    track.addEventListener("pointerleave", (event) => {
      if (event.pointerType === "mouse") {
        stopDrag(event);
      }
    });

    track.addEventListener(
      "click",
      (event) => {
        if (!moved) {
          return;
        }
        event.preventDefault();
        event.stopPropagation();
      },
      true
    );
  });

  const planEditor = document.querySelector(".plan-editor");
  if (planEditor) {
    const planDataEl = document.getElementById("plan-data");
    const progressDataEl = document.getElementById("plan-progress-data");
    const chatDataEl = document.getElementById("coach-chat-data");
    let planData = {};
    let progressData = {};
    let chatData = {};
    if (planDataEl) {
      try {
        planData = JSON.parse(planDataEl.textContent || "{}");
      } catch (error) {
        planData = {};
      }
    }
    if (progressDataEl) {
      try {
        progressData = JSON.parse(progressDataEl.textContent || "{}");
      } catch (error) {
        progressData = {};
      }
    }
    if (chatDataEl) {
      try {
        chatData = JSON.parse(chatDataEl.textContent || "{}");
      } catch (error) {
        chatData = {};
      }
    }

    const itemToLine = (item = {}) => {
      const parts = [
        String(item.exercise || "").trim(),
        String(item.sets || "").trim(),
        String(item.reps || "").trim(),
        String(item.weight || "").trim(),
        String(item.rest || "").trim(),
        String(item.notes || "").trim(),
      ];
      while (parts.length && !parts[parts.length - 1]) {
        parts.pop();
      }
      return parts.length ? parts.join(" | ") : "";
    };

    const itemsToText = (items) => {
      if (!Array.isArray(items)) {
        return "";
      }
      return items
        .map((item) => itemToLine(item))
        .filter((line) => line)
        .join("\n");
    };

    const parseDayItemsText = (text) => {
      return String(text || "")
        .split("\n")
        .map((line) => line.trim())
        .filter((line) => line)
        .map((line) => {
          const parts = line.split("|").map((chunk) => chunk.trim());
          while (parts.length < 6) {
            parts.push("");
          }
          const [exercise, sets, reps, weight, rest, notes] = parts;
          if (!exercise) {
            return null;
          }
          return {
            exercise,
            sets,
            reps,
            weight,
            rest,
            notes,
          };
        })
        .filter((item) => item);
    };

    const updateRestState = (dayCard) => {
      const restToggle = dayCard.querySelector('[data-field="day-rest"]');
      const isRest = restToggle ? restToggle.checked : false;
      dayCard.classList.toggle("is-rest", isRest);
      const dayEditor = dayCard.querySelector('[data-field="day-text"]');
      if (dayEditor) {
        dayEditor.disabled = isRest;
      }
    };

    const extractDayData = (dayCard) => {
      const titleInput = dayCard.querySelector('[data-field="day-title"]');
      const restToggle = dayCard.querySelector('[data-field="day-rest"]');
      const dayEditor = dayCard.querySelector('[data-field="day-text"]');
      const textValue = dayEditor ? dayEditor.value : "";
      return {
        title: titleInput ? titleInput.value.trim() : "",
        rest: restToggle ? restToggle.checked : false,
        items: parseDayItemsText(textValue),
      };
    };

    const applyDayData = (dayCard, data) => {
      const titleInput = dayCard.querySelector('[data-field="day-title"]');
      const restToggle = dayCard.querySelector('[data-field="day-rest"]');
      const dayEditor = dayCard.querySelector('[data-field="day-text"]');
      if (titleInput) {
        titleInput.value = data.title || "";
      }
      if (restToggle) {
        restToggle.checked = Boolean(data.rest);
      }
      if (dayEditor) {
        if (typeof data.text === "string" && data.text.trim()) {
          dayEditor.value = data.text;
        } else {
          dayEditor.value = itemsToText(data.items);
        }
      }
      updateRestState(dayCard);
    };

    const extractWeekData = (weekBlock) => {
      const titleInput = weekBlock.querySelector(".plan-week-title-field input");
      const days = Array.from(weekBlock.querySelectorAll(".plan-day-card")).map((day) =>
        extractDayData(day)
      );
      return {
        title: titleInput ? titleInput.value.trim() : "",
        days,
      };
    };

    const applyWeekData = (weekBlock, data) => {
      const titleInput = weekBlock.querySelector(".plan-week-title-field input");
      if (titleInput) {
        titleInput.value = data.title || "";
      }
      const dayCards = Array.from(weekBlock.querySelectorAll(".plan-day-card"));
      dayCards.forEach((dayCard, idx) => {
        applyDayData(dayCard, (data.days && data.days[idx]) || {});
      });
    };

    const emptyDayData = (dayNumber) => ({
      title: `Día ${dayNumber}`,
      rest: false,
      items: [],
    });

    const emptyWeekData = (weekNumber) => ({
      title: `Semana ${weekNumber}`,
      days: Array.from({ length: 7 }, (_, idx) => emptyDayData(idx + 1)),
    });

    const activateWeekTab = (weekNumber, scrollToWeek = false) => {
      const selected = Number(weekNumber || 1);
      planEditor.querySelectorAll(".plan-week-block").forEach((block) => {
        const current = Number(block.dataset.week || 0);
        block.classList.toggle("is-active", current === selected);
      });
      if (scrollToWeek) {
        const selectedBlock = planEditor.querySelector(
          `.plan-week-block[data-week="${selected}"]`
        );
        if (selectedBlock) {
          selectedBlock.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      }
    };

    const renderCoachProgress = (username, weekNumber) => {
      const weekSelect = document.getElementById("coach_progress_week");
      const donut = document.getElementById("coach_progress_donut");
      const pctEl = document.getElementById("coach_progress_pct");
      const doneEl = document.getElementById("coach_progress_done");
      const missedEl = document.getElementById("coach_progress_missed");
      const pendingEl = document.getElementById("coach_progress_pending");
      const userData = progressData[username];
      const weeks = userData && Array.isArray(userData.weeks) ? userData.weeks : [];
      const targetWeek = Number(weekNumber || (weekSelect ? weekSelect.value : 1) || 1);
      const row = weeks.find((item) => Number(item.week || 0) === targetWeek) || {
        done: 0,
        missed: 0,
        pending: 0,
        done_pct: 0,
        missed_pct: 0,
        pending_pct: 0,
      };
      if (weekSelect) {
        weekSelect.value = String(targetWeek);
      }
      if (donut) {
        donut.style.setProperty("--done", String(row.done_pct || 0));
        donut.style.setProperty("--missed", String(row.missed_pct || 0));
        donut.style.setProperty("--pending", String(row.pending_pct || 0));
      }
      if (pctEl) pctEl.textContent = `${row.done_pct || 0}%`;
      if (doneEl) doneEl.textContent = String(row.done || 0);
      if (missedEl) missedEl.textContent = String(row.missed || 0);
      if (pendingEl) pendingEl.textContent = String(row.pending || 0);
    };

    const renderCoachChat = (username) => {
      const title = document.getElementById("coach_chat_title");
      const list = document.getElementById("coach_chat_list");
      const hiddenUser = document.getElementById("coach_chat_username");
      if (title) {
        title.textContent = `Comentarios con ${username}`;
      }
      if (hiddenUser) {
        hiddenUser.value = username;
      }
      if (!list) {
        return;
      }
      const messages = Array.isArray(chatData[username]) ? chatData[username] : [];
      if (!messages.length) {
        list.innerHTML = '<li class="chat-empty">Sin mensajes todavía.</li>';
        return;
      }
      list.innerHTML = messages
        .slice(-200)
        .map((message) => {
          const isOwn = message.author === "coach" ? " is-own" : "";
          const author = message.author === "coach" ? "Profesor" : "Alumno";
          const text = String(message.text || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
          const created = message.created_at
            ? new Date(Number(message.created_at) * 1000).toLocaleString("es-ES", {
                day: "2-digit",
                month: "2-digit",
                hour: "2-digit",
                minute: "2-digit",
              })
            : "";
          return `
            <li class="chat-message${isOwn}">
              <span class="chat-author">${author}</span>
              <p>${text}</p>
              <span class="chat-time">${created}</span>
            </li>
          `;
        })
        .join("");
    };

    const setCurrentUser = (username) => {
      const currentLabel = planEditor.querySelector(".plan-current-user strong");
      if (currentLabel) {
        currentLabel.textContent = username;
      }
      const userSelect = document.getElementById("plan_user_select");
      if (userSelect) {
        userSelect.value = username;
      }
      planEditor.querySelectorAll('input[name="username"]').forEach((field) => {
        field.value = username;
      });
    };

    const loadUserPlan = (username) => {
      const userPlan = planData[username];
      if (!userPlan) {
        return;
      }
      const activeWeekNode = planEditor.querySelector(".plan-week-block.is-active");
      const activeWeek =
        Number(
          activeWeekNode && activeWeekNode.dataset ? activeWeekNode.dataset.week : 1
        ) || 1;
      const planTitle = planEditor.querySelector("#plan_title");
      if (planTitle) {
        planTitle.value = userPlan.title || "";
      }
      const weekBlocks = Array.from(
        planEditor.querySelectorAll(".plan-week-block")
      );
      weekBlocks.forEach((block, idx) => {
        applyWeekData(block, (userPlan.weeks && userPlan.weeks[idx]) || {});
      });
      setCurrentUser(username);
      activateWeekTab(activeWeek);
      const weekSelect = document.getElementById("coach_progress_week");
      renderCoachProgress(username, weekSelect ? Number(weekSelect.value || 1) : 1);
      renderCoachChat(username);
    };

    planEditor.querySelectorAll(".plan-day-card").forEach(updateRestState);
    activateWeekTab(1);
    const initialUser =
      (planEditor.querySelector('input[name="username"]') || {}).value || "";
    renderCoachProgress(initialUser, 1);
    renderCoachChat(initialUser);
    const progressWeekSelect = document.getElementById("coach_progress_week");
    if (progressWeekSelect) {
      progressWeekSelect.addEventListener("change", () => {
        const user = (planEditor.querySelector('input[name="username"]') || {}).value || "";
        renderCoachProgress(user, Number(progressWeekSelect.value || 1));
      });
    }

    planEditor.addEventListener("change", (event) => {
      if (event.target.matches('[data-field="day-rest"]')) {
        const dayCard = event.target.closest(".plan-day-card");
        if (dayCard) {
          updateRestState(dayCard);
        }
      }
    });

    planEditor.addEventListener("click", (event) => {
      const moveDayButton = event.target.closest(".plan-day-move");
      if (moveDayButton) {
        event.preventDefault();
        const dayCard = moveDayButton.closest(".plan-day-card");
        if (!dayCard) return;
        const weekBlock = dayCard.closest(".plan-week-block");
        if (!weekBlock) return;
        const direction = moveDayButton.dataset.action;
        const currentIndex = Number(dayCard.dataset.day || 0);
        const targetIndex = direction === "left" ? currentIndex - 1 : currentIndex + 1;
        const targetCard = weekBlock.querySelector(
          `.plan-day-card[data-day="${targetIndex}"]`
        );
        if (!targetCard) return;
        const currentData = extractDayData(dayCard);
        const targetData = extractDayData(targetCard);
        applyDayData(dayCard, targetData);
        applyDayData(targetCard, currentData);
        return;
      }

      const clearDayButton = event.target.closest(".plan-day-clear");
      if (clearDayButton) {
        event.preventDefault();
        const dayCard = clearDayButton.closest(".plan-day-card");
        if (!dayCard) return;
        const dayNumber = Number(dayCard.dataset.day || 1);
        applyDayData(dayCard, emptyDayData(dayNumber));
        return;
      }

      const moveWeekButton = event.target.closest(".plan-week-move");
      if (moveWeekButton) {
        event.preventDefault();
        const weekBlock = moveWeekButton.closest(".plan-week-block");
        if (!weekBlock) return;
        const direction = moveWeekButton.dataset.action;
        const currentIndex = Number(weekBlock.dataset.week || 0);
        const targetIndex = direction === "up" ? currentIndex - 1 : currentIndex + 1;
        const targetBlock = planEditor.querySelector(
          `.plan-week-block[data-week="${targetIndex}"]`
        );
        if (!targetBlock) return;
        const currentData = extractWeekData(weekBlock);
        const targetData = extractWeekData(targetBlock);
        applyWeekData(weekBlock, targetData);
        applyWeekData(targetBlock, currentData);
        return;
      }

      const weekActionButton = event.target.closest(".plan-week-action");
      if (weekActionButton) {
        event.preventDefault();
        const weekBlock = weekActionButton.closest(".plan-week-block");
        if (!weekBlock) return;
        const weekNumber = Number(weekBlock.dataset.week || 1);
        const action = weekActionButton.dataset.action;
        if (action === "clear") {
          applyWeekData(weekBlock, emptyWeekData(weekNumber));
        } else if (action === "duplicate") {
          const cloneData = extractWeekData(weekBlock);
          const targetIndex = weekNumber < 4 ? weekNumber + 1 : weekNumber - 1;
          const targetBlock = planEditor.querySelector(
            `.plan-week-block[data-week="${targetIndex}"]`
          );
          if (targetBlock) {
            applyWeekData(targetBlock, cloneData);
          }
        }
        return;
      }
    });

    const loadUserButton = document.getElementById("load_user_btn");
    if (loadUserButton) {
      loadUserButton.addEventListener("click", (event) => {
        event.preventDefault();
        const userSelect = document.getElementById("plan_user_select");
        const username = userSelect ? userSelect.value : "";
        if (!username) return;
        loadUserPlan(username);
      });
    }

    const copyButton = document.getElementById("copy_week_btn");
    if (copyButton) {
      copyButton.addEventListener("click", (event) => {
        event.preventDefault();
        const userSelect = document.getElementById("copy_plan_user");
        const weekSelect = document.getElementById("copy_plan_week");
        const targetUserSelect = document.getElementById("copy_target_user");
        const targetSelect = document.getElementById("copy_target_week");
        const sourceUser = userSelect ? userSelect.value : "";
        const sourceWeek = Number(weekSelect ? weekSelect.value : 0);
        const targetUser = targetUserSelect ? targetUserSelect.value : "";
        const targetWeek = Number(targetSelect ? targetSelect.value : 0);
        if (!sourceUser || !sourceWeek || !targetWeek || !targetUser) {
          return;
        }
        const sourcePlan = planData[sourceUser];
        if (!sourcePlan || !Array.isArray(sourcePlan.weeks)) {
          return;
        }
        const weekData = sourcePlan.weeks[sourceWeek - 1];
        if (!weekData) {
          return;
        }
        if (targetUser !== (planEditor.querySelector('input[name="username"]') || {}).value) {
          loadUserPlan(targetUser);
        }
        const targetBlock = planEditor.querySelector(
          `.plan-week-block[data-week="${targetWeek}"]`
        );
        if (targetBlock) {
          applyWeekData(targetBlock, weekData);
          activateWeekTab(targetWeek, true);
        }
      });
    }

    const copyDayButton = document.getElementById("copy_day_btn");
    if (copyDayButton) {
      copyDayButton.addEventListener("click", (event) => {
        event.preventDefault();
        const userSelect = document.getElementById("copy_day_user");
        const weekSelect = document.getElementById("copy_day_week");
        const daySelect = document.getElementById("copy_day_day");
        const targetUserSelect = document.getElementById("copy_day_target_user");
        const targetWeekSelect = document.getElementById("copy_day_target_week");
        const targetDaySelect = document.getElementById("copy_day_target_day");
        const sourceUser = userSelect ? userSelect.value : "";
        const sourceWeek = Number(weekSelect ? weekSelect.value : 0);
        const sourceDay = Number(daySelect ? daySelect.value : 0);
        const targetUser = targetUserSelect ? targetUserSelect.value : "";
        const targetWeek = Number(targetWeekSelect ? targetWeekSelect.value : 0);
        const targetDay = Number(targetDaySelect ? targetDaySelect.value : 0);
        if (
          !sourceUser ||
          !sourceWeek ||
          !sourceDay ||
          !targetUser ||
          !targetWeek ||
          !targetDay
        ) {
          return;
        }
        const sourcePlan = planData[sourceUser];
        if (!sourcePlan || !Array.isArray(sourcePlan.weeks)) {
          return;
        }
        const weekData = sourcePlan.weeks[sourceWeek - 1];
        if (!weekData || !Array.isArray(weekData.days)) {
          return;
        }
        const dayData = weekData.days[sourceDay - 1];
        if (!dayData) {
          return;
        }
        if (targetUser !== (planEditor.querySelector('input[name="username"]') || {}).value) {
          loadUserPlan(targetUser);
        }
        const targetBlock = planEditor.querySelector(
          `.plan-week-block[data-week="${targetWeek}"]`
        );
        if (!targetBlock) {
          return;
        }
        const targetDayCard = targetBlock.querySelector(
          `.plan-day-card[data-day="${targetDay}"]`
        );
        if (targetDayCard) {
          applyDayData(targetDayCard, dayData);
          activateWeekTab(targetWeek, true);
        }
      });
    }

    const moveDayButton = document.getElementById("move_day_btn");
    if (moveDayButton) {
      moveDayButton.addEventListener("click", (event) => {
        event.preventDefault();
        const sourceWeek = Number(
          (document.getElementById("move_day_week_from") || {}).value || 0
        );
        const sourceDay = Number((document.getElementById("move_day_from") || {}).value || 0);
        const targetWeek = Number(
          (document.getElementById("move_day_week_to") || {}).value || 0
        );
        const targetDay = Number((document.getElementById("move_day_to") || {}).value || 0);
        if (!sourceWeek || !sourceDay || !targetWeek || !targetDay) {
          return;
        }
        if (sourceWeek === targetWeek && sourceDay === targetDay) {
          return;
        }
        const sourceWeekBlock = planEditor.querySelector(
          `.plan-week-block[data-week="${sourceWeek}"]`
        );
        const targetWeekBlock = planEditor.querySelector(
          `.plan-week-block[data-week="${targetWeek}"]`
        );
        if (!sourceWeekBlock || !targetWeekBlock) {
          return;
        }
        const sourceCard = sourceWeekBlock.querySelector(
          `.plan-day-card[data-day="${sourceDay}"]`
        );
        const targetCard = targetWeekBlock.querySelector(
          `.plan-day-card[data-day="${targetDay}"]`
        );
        if (!sourceCard || !targetCard) {
          return;
        }
        const sourceData = extractDayData(sourceCard);
        applyDayData(targetCard, sourceData);
        applyDayData(sourceCard, emptyDayData(sourceDay));
        activateWeekTab(targetWeek, true);
      });
    }

    const clearDestinationButton = document.getElementById("clear_day_btn");
    if (clearDestinationButton) {
      clearDestinationButton.addEventListener("click", (event) => {
        event.preventDefault();
        const targetWeek = Number(
          (document.getElementById("move_day_week_to") || {}).value || 0
        );
        const targetDay = Number((document.getElementById("move_day_to") || {}).value || 0);
        if (!targetWeek || !targetDay) {
          return;
        }
        const targetWeekBlock = planEditor.querySelector(
          `.plan-week-block[data-week="${targetWeek}"]`
        );
        if (!targetWeekBlock) {
          return;
        }
        const targetCard = targetWeekBlock.querySelector(
          `.plan-day-card[data-day="${targetDay}"]`
        );
        if (targetCard) {
          applyDayData(targetCard, emptyDayData(targetDay));
          activateWeekTab(targetWeek, true);
        }
      });
    }
  }

  const studentSearch = document.getElementById("student_search");
  if (studentSearch) {
    const filterStudents = () => {
      const query = studentSearch.value.trim().toLowerCase();
      document.querySelectorAll(".student-item").forEach((item) => {
        const haystack = (item.dataset.search || "").toLowerCase();
        item.style.display = !query || haystack.includes(query) ? "" : "none";
      });
    };
    studentSearch.addEventListener("input", filterStudents);
  }

  const videoAdminSearch = document.getElementById("video_admin_search");
  if (videoAdminSearch) {
    const filterMedia = () => {
      const query = videoAdminSearch.value.trim().toLowerCase();
      document.querySelectorAll(".admin-media-item").forEach((item) => {
        const haystack = (item.dataset.search || "").toLowerCase();
        item.style.display = !query || haystack.includes(query) ? "" : "none";
      });
    };
    videoAdminSearch.addEventListener("input", filterMedia);
    filterMedia();
  }

  const adminTabs = document.getElementById("admin_section_tabs");
  if (adminTabs) {
    const tabButtons = Array.from(
      adminTabs.querySelectorAll("[data-admin-section]")
    );
    const tabPanels = Array.from(
      document.querySelectorAll("[data-admin-section-panel]")
    );
    const navSectionLinks = Array.from(
      document.querySelectorAll("[data-admin-section-link]")
    );
    const hasSection = (value) =>
      tabButtons.some((button) => button.dataset.adminSection === value);
    const currentUrl = new URL(window.location.href);
    let initialSection = "inicio";
    const fromQuery = currentUrl.searchParams.get("admin_section");
    if (fromQuery && hasSection(fromQuery)) {
      initialSection = fromQuery;
    } else if (
      currentUrl.hash === "#plan" ||
      currentUrl.searchParams.has("plan_user")
    ) {
      initialSection = "portal";
    }
    const activateSection = (section, syncUrl = true) => {
      if (!hasSection(section)) {
        return;
      }
      tabButtons.forEach((button) => {
        const isActive = button.dataset.adminSection === section;
        button.classList.toggle("is-active", isActive);
      });
      tabPanels.forEach((panel) => {
        panel.hidden = panel.dataset.adminSectionPanel !== section;
      });
      navSectionLinks.forEach((link) => {
        const isActive = link.dataset.adminSectionLink === section;
        link.classList.toggle("is-active", isActive);
      });
      if (syncUrl) {
        const nextUrl = new URL(window.location.href);
        nextUrl.searchParams.set("admin_section", section);
        window.history.replaceState({}, "", nextUrl.toString());
      }
    };
    tabButtons.forEach((button) => {
      button.addEventListener("click", () => {
        activateSection(button.dataset.adminSection || "inicio");
      });
    });
    navSectionLinks.forEach((link) => {
      link.addEventListener("click", (event) => {
        const section = link.dataset.adminSectionLink || "";
        if (!hasSection(section)) {
          return;
        }
        event.preventDefault();
        activateSection(section);
      });
    });
    activateSection(initialSection, false);
  }

  const portalWeekSelect = document.getElementById("portal_week_select");
  if (portalWeekSelect) {
    const currentWeek = (document.getElementById("portal_week_current") || {}).value || "all";
    portalWeekSelect.value = currentWeek;
    const applyWeekFilter = (weekValue) => {
      document.querySelectorAll(".training-week").forEach((weekCard) => {
        const cardWeek = weekCard.dataset.week || "";
        const visible = weekValue === "all" || cardWeek === weekValue;
        weekCard.style.display = visible ? "" : "none";
        if (visible && weekValue !== "all" && weekCard.tagName === "DETAILS") {
          weekCard.open = true;
        }
      });
    };
    applyWeekFilter(portalWeekSelect.value || "all");
    portalWeekSelect.addEventListener("change", () => {
      const selected = portalWeekSelect.value || "all";
      applyWeekFilter(selected);
      const url = new URL(window.location.href);
      if (selected === "all") {
        url.searchParams.delete("week");
      } else {
        url.searchParams.set("week", selected);
      }
      window.history.replaceState({}, "", url.toString());
    });
  }

  const trainingWeeks = Array.from(document.querySelectorAll(".training-week"));
  if (trainingWeeks.length) {
    const syncWeekToggleLabel = (weekCard) => {
      const toggle = weekCard.querySelector(".training-week-toggle");
      if (!toggle) {
        return;
      }
      const openLabel = toggle.dataset.openLabel || "Minimizar";
      const closedLabel = toggle.dataset.closedLabel || "Maximizar";
      toggle.textContent = weekCard.open ? openLabel : closedLabel;
    };
    trainingWeeks.forEach((weekCard) => {
      syncWeekToggleLabel(weekCard);
      weekCard.addEventListener("toggle", () => {
        syncWeekToggleLabel(weekCard);
      });
    });
  }

  const staggerGroups = document.querySelectorAll("[data-stagger]");
  staggerGroups.forEach((group) => {
    const items = group.querySelectorAll(".stagger-item");
    items.forEach((item, index) => {
      item.style.setProperty("--stagger-delay", `${index * 0.06}s`);
    });
  });

  const reveals = document.querySelectorAll(".reveal");
  if (prefersReducedMotion || lowPerfDevice) {
    reveals.forEach((section) => section.classList.add("is-visible"));
  } else {
    const observer = new IntersectionObserver(
      (entries, obs) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            obs.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.1, rootMargin: "80px 0px 80px 0px" }
    );
    reveals.forEach((section) => observer.observe(section));
  }
});
