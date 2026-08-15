(() => {
  "use strict";

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  function isEnglish() {
    return document.documentElement.lang.toLowerCase().startsWith("en");
  }

  function syncEditorialCopy() {
    const key = isEnglish() ? "copyEn" : "copyZh";
    $$('[data-copy-zh]').forEach((element) => {
      const copy = element.dataset[key];
      if (copy) element.textContent = copy;
    });

    const input = $("#chat-input");
    if (input) {
      input.placeholder = isEnglish()
        ? "e.g. Saturday afternoon, two people, night views and photos"
        : "例如：周六下午，两个人，想看夜景和拍照";
    }
  }

  function initHeader() {
    const header = $("#site-header");
    const toggle = $("#menu-toggle");
    const nav = $("#header-nav");
    if (!header) return;

    const updateHeader = () => header.classList.toggle("is-scrolled", window.scrollY > 18);
    updateHeader();
    window.addEventListener("scroll", updateHeader, { passive: true });

    if (!toggle || !nav) return;
    const closeMenu = () => {
      toggle.setAttribute("aria-expanded", "false");
      nav.classList.remove("is-open");
    };

    toggle.addEventListener("click", () => {
      const open = toggle.getAttribute("aria-expanded") !== "true";
      toggle.setAttribute("aria-expanded", String(open));
      nav.classList.toggle("is-open", open);
    });
    nav.addEventListener("click", (event) => {
      if (event.target.closest("a")) closeMenu();
    });
    document.addEventListener("click", (event) => {
      if (!header.contains(event.target)) closeMenu();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeMenu();
    });
  }

  function initReveals() {
    const items = $$(".reveal");
    if (!items.length) return;
    if (reducedMotion.matches || !("IntersectionObserver" in window)) {
      items.forEach((item) => item.classList.add("is-visible"));
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        });
      },
      { rootMargin: "0px 0px -10%", threshold: 0.08 },
    );
    items.forEach((item) => observer.observe(item));
  }

  function initActiveNavigation() {
    if (!("IntersectionObserver" in window)) return;
    const links = $$('#header-nav a[href^="#"]');
    const sections = links
      .map((link) => $(link.getAttribute("href")))
      .filter(Boolean);
    if (!sections.length) return;

    const byId = new Map(links.map((link) => [link.getAttribute("href").slice(1), link]));
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (!visible) return;
        links.forEach((link) => link.removeAttribute("aria-current"));
        byId.get(visible.target.id)?.setAttribute("aria-current", "page");
      },
      { rootMargin: "-34% 0px -55%", threshold: [0.05, 0.25, 0.55] },
    );
    sections.forEach((section) => observer.observe(section));
  }

  function makeRandom(seed) {
    let state = seed >>> 0;
    return () => {
      state = (1664525 * state + 1013904223) >>> 0;
      return state / 4294967296;
    };
  }

  function initTowerGravity() {
    const canvas = $("#tower-gravity-canvas");
    if (!canvas) return;
    const context = canvas.getContext("2d", { alpha: true });
    if (!context) return;

    let width = 0;
    let height = 0;
    let particles = [];
    let frame = 0;
    let animationFrame = 0;
    let visible = true;
    const pointer = { x: 0, y: 0, active: false };
    const palette = ["114,169,179", "231,199,122", "247,243,232", "199,74,53"];

    const buildParticles = () => {
      const random = makeRandom(338);
      const count = Math.max(62, Math.min(148, Math.floor((width * height) / 11500)));
      particles = Array.from({ length: count }, (_, index) => ({
        x: random() * width,
        y: random() * height,
        vx: (random() - 0.5) * 0.34,
        vy: (random() - 0.5) * 0.28,
        radius: 0.45 + random() * 1.45,
        alpha: 0.14 + random() * 0.48,
        phase: random() * Math.PI * 2,
        color: palette[index % palette.length],
      }));
    };

    const resize = () => {
      const bounds = canvas.getBoundingClientRect();
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      width = Math.max(1, bounds.width);
      height = Math.max(1, bounds.height);
      canvas.width = Math.round(width * ratio);
      canvas.height = Math.round(height * ratio);
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      context.clearRect(0, 0, width, height);
      buildParticles();
    };

    const render = () => {
      if (!visible) return;
      context.fillStyle = reducedMotion.matches ? "rgba(7,11,17,1)" : "rgba(7,11,17,0.085)";
      context.fillRect(0, 0, width, height);

      const axisX = width * 0.608;
      const crownY = height * 0.17;
      context.beginPath();
      context.moveTo(axisX, crownY);
      context.lineTo(axisX, height * 0.88);
      context.strokeStyle = "rgba(231,199,122,0.13)";
      context.lineWidth = 0.8;
      context.stroke();

      particles.forEach((particle, index) => {
        const dx = axisX - particle.x;
        const dy = height * 0.46 - particle.y;
        const distance = Math.max(38, Math.hypot(dx, dy));
        const gravity = Math.min(0.028, 32 / (distance * distance));
        const orbit = 0.0045 * Math.sin(frame * 0.007 + particle.phase);
        const drift = Math.sin(particle.y * 0.012 + frame * 0.009 + particle.phase) * 0.006;

        particle.vx += dx * gravity + (-dy / distance) * orbit + drift;
        particle.vy += dy * gravity * 0.28 + (dx / distance) * orbit * 0.45;

        if (pointer.active) {
          const pdx = pointer.x - particle.x;
          const pdy = pointer.y - particle.y;
          const pointerDistance = Math.max(30, Math.hypot(pdx, pdy));
          if (pointerDistance < 190) {
            particle.vx += (pdx / pointerDistance) * 0.006;
            particle.vy += (pdy / pointerDistance) * 0.006;
          }
        }

        particle.vx *= 0.992;
        particle.vy *= 0.992;
        particle.x += particle.vx;
        particle.y += particle.vy;

        if (particle.x < -24 || particle.x > width + 24 || particle.y < -24 || particle.y > height + 24) {
          const random = makeRandom(338 + frame + index * 29);
          particle.x = random() > 0.5 ? -8 : width + 8;
          particle.y = random() * height;
          particle.vx = (random() - 0.5) * 0.25;
          particle.vy = (random() - 0.5) * 0.2;
        }

        const glow = Math.max(0.14, 1 - Math.abs(dx) / Math.max(width * 0.62, 1));
        context.beginPath();
        context.arc(particle.x, particle.y, particle.radius * (0.7 + glow * 0.55), 0, Math.PI * 2);
        context.fillStyle = `rgba(${particle.color},${particle.alpha * glow})`;
        context.fill();
      });

      frame += 1;
      if (!reducedMotion.matches) animationFrame = requestAnimationFrame(render);
    };

    const boundsToPointer = (event) => {
      const bounds = canvas.getBoundingClientRect();
      pointer.x = event.clientX - bounds.left;
      pointer.y = event.clientY - bounds.top;
      pointer.active = true;
    };

    canvas.addEventListener("pointermove", boundsToPointer, { passive: true });
    canvas.addEventListener("pointerleave", () => { pointer.active = false; });
    document.addEventListener("visibilitychange", () => {
      visible = !document.hidden;
      if (visible && !reducedMotion.matches) {
        cancelAnimationFrame(animationFrame);
        animationFrame = requestAnimationFrame(render);
      }
    });
    window.addEventListener("resize", resize, { passive: true });
    resize();
    render();
  }

  function initArtCallout() {
    const canvas = $("#art-callout-canvas");
    if (!canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;

    const draw = () => {
      const bounds = canvas.getBoundingClientRect();
      const ratio = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.round(bounds.width * ratio);
      canvas.height = Math.round(bounds.height * ratio);
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      context.fillStyle = "#091019";
      context.fillRect(0, 0, bounds.width, bounds.height);
      const random = makeRandom(338);
      const axis = bounds.width * 0.64;
      context.strokeStyle = "rgba(231,199,122,.34)";
      context.lineWidth = 1;
      context.beginPath();
      context.moveTo(axis, bounds.height * 0.11);
      context.lineTo(axis, bounds.height * 0.9);
      context.stroke();

      for (let index = 0; index < 52; index += 1) {
        const x = random() * bounds.width;
        const y = random() * bounds.height;
        const bend = (axis - x) * (0.15 + random() * 0.28);
        context.beginPath();
        context.moveTo(x, y);
        context.quadraticCurveTo(x + bend * 0.45, y - 18 + random() * 36, x + bend, y + (random() - 0.5) * 38);
        context.strokeStyle = index % 5 === 0 ? "rgba(199,74,53,.48)" : index % 3 === 0 ? "rgba(231,199,122,.38)" : "rgba(114,169,179,.3)";
        context.lineWidth = 0.4 + random() * 1.1;
        context.stroke();
      }
    };
    draw();
    window.addEventListener("resize", draw, { passive: true });
  }

  function initPlannerPreview() {
    const chat = $("#chat");
    const preview = $("#planner-preview");
    if (!chat || !preview || !("MutationObserver" in window)) return;

    const renderPreview = () => {
      const route = chat.querySelector(".route-card");
      const typing = chat.querySelector(".typing");
      chat.setAttribute("aria-busy", String(Boolean(typing)));
      const send = $("#chat-send");
      if (send) send.disabled = Boolean(typing);
      if (!route) return;

      const title = route.querySelector("h3, h4, .route-title")?.textContent?.trim();
      const stops = [...route.querySelectorAll("li")].slice(0, 4).map((item) => item.textContent.trim());
      const reason = route.querySelector(".route-reason, p")?.textContent?.trim();
      if (!title && !stops.length && !reason) return;

      const fragment = document.createDocumentFragment();
      const eyebrow = document.createElement("span");
      eyebrow.className = "planner-aside__status";
      eyebrow.textContent = isEnglish() ? "LIVE ROUTE" : "实时路线";
      fragment.append(eyebrow);

      if (title) {
        const heading = document.createElement("h3");
        heading.textContent = title;
        fragment.append(heading);
      }
      if (stops.length) {
        const list = document.createElement("ol");
        stops.forEach((stop) => {
          const item = document.createElement("li");
          item.textContent = stop;
          list.append(item);
        });
        fragment.append(list);
      }
      if (reason) {
        const paragraph = document.createElement("p");
        paragraph.textContent = reason;
        fragment.append(paragraph);
      }

      preview.replaceChildren(fragment);
      preview.closest(".planner-aside")?.classList.add("has-route");
    };

    new MutationObserver(renderPreview).observe(chat, { childList: true, subtree: true });
    renderPreview();
  }

  function initModalFocus() {
    const modal = $("#modal-memento");
    if (!modal || !("MutationObserver" in window)) return;
    const dialog = modal.querySelector('[role="dialog"], .modal-card, .modal__panel');
    let previousFocus = null;

    const focusable = () => $$('a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])', modal)
      .filter((element) => !element.hidden && element.offsetParent !== null);

    const sync = () => {
      const open = !modal.hidden;
      document.body.classList.toggle("modal-open", open);
      if (open) {
        previousFocus = document.activeElement;
        requestAnimationFrame(() => (dialog || focusable()[0])?.focus());
      } else if (previousFocus instanceof HTMLElement) {
        previousFocus.focus({ preventScroll: true });
      }
    };

    new MutationObserver(sync).observe(modal, { attributes: true, attributeFilter: ["hidden"] });
    document.addEventListener("keydown", (event) => {
      if (modal.hidden) return;
      if (event.key === "Escape") {
        modal.querySelector("[data-close-modal]")?.click();
        return;
      }
      if (event.key !== "Tab") return;
      const items = focusable();
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    });
  }

  function init() {
    syncEditorialCopy();
    initHeader();
    initReveals();
    initActiveNavigation();
    initTowerGravity();
    initArtCallout();
    initPlannerPreview();
    initModalFocus();

    $("#lang-toggle")?.addEventListener("click", () => requestAnimationFrame(syncEditorialCopy));
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();

