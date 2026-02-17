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
      const playPromise = video.play();
      if (playPromise && playPromise.catch) {
        playPromise.catch(() => {});
      }
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

  document.querySelectorAll("video").forEach((video) => {
    lockMute(video);
    setupLoopIndicator(video);
  });

  const planEditor = document.querySelector(".plan-editor");
  if (planEditor) {
    const planDataEl = document.getElementById("plan-data");
    let planData = {};
    if (planDataEl) {
      try {
        planData = JSON.parse(planDataEl.textContent || "{}");
      } catch (error) {
        planData = {};
      }
    }

    const buildRow = (week, day, rowIndex, values = {}) => {
      const row = document.createElement("div");
      row.className = "plan-item-row";
      row.dataset.row = rowIndex;
      row.innerHTML = `
        <input data-field="exercise" name="week${week}_day${day}_item${rowIndex}_exercise" list="exercise-options" placeholder="Ejercicio">
        <input data-field="sets" name="week${week}_day${day}_item${rowIndex}_sets" placeholder="Series">
        <input data-field="reps" name="week${week}_day${day}_item${rowIndex}_reps" placeholder="Reps">
        <input data-field="weight" name="week${week}_day${day}_item${rowIndex}_weight" placeholder="Peso">
        <input data-field="rest" name="week${week}_day${day}_item${rowIndex}_rest" placeholder="Descanso">
        <input data-field="notes" name="week${week}_day${day}_item${rowIndex}_notes" placeholder="Observaciones">
        <button class="plan-item-remove" type="button" aria-label="Quitar ejercicio" title="Quitar ejercicio">×</button>
      `;
      row.querySelector('[data-field="exercise"]').value = values.exercise || "";
      row.querySelector('[data-field="sets"]').value = values.sets || "";
      row.querySelector('[data-field="reps"]').value = values.reps || "";
      row.querySelector('[data-field="weight"]').value = values.weight || "";
      row.querySelector('[data-field="rest"]').value = values.rest || "";
      row.querySelector('[data-field="notes"]').value = values.notes || "";
      return row;
    };

    const updateRestState = (dayCard) => {
      const restToggle = dayCard.querySelector('[data-field="day-rest"]');
      const isRest = restToggle ? restToggle.checked : false;
      dayCard.classList.toggle("is-rest", isRest);
      dayCard.querySelectorAll(".plan-items input").forEach((input) => {
        input.disabled = isRest;
      });
      dayCard.querySelectorAll(".plan-item-remove").forEach((btn) => {
        btn.disabled = isRest;
      });
      const addButton = dayCard.querySelector(".plan-item-add");
      if (addButton) {
        addButton.disabled = isRest;
      }
    };

    const extractDayData = (dayCard) => {
      const titleInput = dayCard.querySelector('[data-field="day-title"]');
      const restToggle = dayCard.querySelector('[data-field="day-rest"]');
      const items = Array.from(dayCard.querySelectorAll(".plan-item-row")).map((row) => {
        const value = (field) =>
          (row.querySelector(`[data-field="${field}"]`) || {}).value || "";
        return {
          exercise: value("exercise").trim(),
          sets: value("sets").trim(),
          reps: value("reps").trim(),
          weight: value("weight").trim(),
          rest: value("rest").trim(),
          notes: value("notes").trim(),
        };
      });
      return {
        title: titleInput ? titleInput.value.trim() : "",
        rest: restToggle ? restToggle.checked : false,
        items: items.filter(
          (item) =>
            item.exercise || item.sets || item.reps || item.weight || item.rest || item.notes
        ),
      };
    };

    const applyDayData = (dayCard, data) => {
      const week = Number(dayCard.dataset.week || 0);
      const day = Number(dayCard.dataset.day || 0);
      const titleInput = dayCard.querySelector('[data-field="day-title"]');
      const restToggle = dayCard.querySelector('[data-field="day-rest"]');
      const itemsContainer = dayCard.querySelector(".plan-items");
      if (titleInput) {
        titleInput.value = data.title || "";
      }
      if (restToggle) {
        restToggle.checked = Boolean(data.rest);
      }
      if (itemsContainer) {
        itemsContainer.innerHTML = "";
        const items = Array.isArray(data.items) ? data.items : [];
        const rowsNeeded = Math.max(items.length + 1, 3);
        for (let i = 0; i < rowsNeeded; i += 1) {
          itemsContainer.appendChild(buildRow(week, day, i + 1, items[i] || {}));
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

    const setCurrentUser = (username) => {
      const currentLabel = planEditor.querySelector(".plan-current-user strong");
      if (currentLabel) {
        currentLabel.textContent = username;
      }
      const userSelect = document.getElementById("plan_user_select");
      if (userSelect) {
        userSelect.value = username;
      }
      const formUser = planEditor.querySelector('input[name="username"]');
      if (formUser) {
        formUser.value = username;
      }
    };

    const loadUserPlan = (username) => {
      const userPlan = planData[username];
      if (!userPlan) {
        return;
      }
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
    };

    planEditor.querySelectorAll(".plan-day-card").forEach(updateRestState);

    planEditor.addEventListener("change", (event) => {
      if (event.target.matches('[data-field="day-rest"]')) {
        const dayCard = event.target.closest(".plan-day-card");
        if (dayCard) {
          updateRestState(dayCard);
        }
      }
    });

    planEditor.addEventListener("click", (event) => {
      const addButton = event.target.closest(".plan-item-add");
      if (addButton) {
        event.preventDefault();
        const dayCard = addButton.closest(".plan-day-card");
        if (!dayCard) return;
        const week = Number(dayCard.dataset.week || 0);
        const day = Number(dayCard.dataset.day || 0);
        const itemsContainer = dayCard.querySelector(".plan-items");
        if (!itemsContainer) return;
        const rows = itemsContainer.querySelectorAll(".plan-item-row");
        const lastIndex = rows.length
          ? Number(rows[rows.length - 1].dataset.row || rows.length)
          : 0;
        itemsContainer.appendChild(buildRow(week, day, lastIndex + 1, {}));
        return;
      }

      const removeButton = event.target.closest(".plan-item-remove");
      if (removeButton) {
        event.preventDefault();
        const row = removeButton.closest(".plan-item-row");
        const container = removeButton.closest(".plan-items");
        if (row && container) {
          if (container.querySelectorAll(".plan-item-row").length > 1) {
            row.remove();
          }
        }
        return;
      }

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

  const portalWeekSelect = document.getElementById("portal_week_select");
  if (portalWeekSelect) {
    const currentWeek = (document.getElementById("portal_week_current") || {}).value || "all";
    portalWeekSelect.value = currentWeek;
    const applyWeekFilter = (weekValue) => {
      document.querySelectorAll(".training-week").forEach((weekCard) => {
        const cardWeek = weekCard.dataset.week || "";
        weekCard.style.display = weekValue === "all" || cardWeek === weekValue ? "" : "none";
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
