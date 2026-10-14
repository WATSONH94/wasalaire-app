/* WaSalaire vitrine — motion & interactions (vanilla, léger, respecte prefers-reduced-motion) */
(() => {
  "use strict";
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* 1) Barre de progression de lecture */
  const bar = document.querySelector(".progress");
  const onScroll = () => {
    const h = document.documentElement;
    const p = h.scrollTop / (h.scrollHeight - h.clientHeight || 1);
    if (bar) bar.style.width = (p * 100).toFixed(2) + "%";
    const header = document.querySelector(".header");
    if (header) header.classList.toggle("scrolled", h.scrollTop > 12);
  };
  document.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  /* 2) Reveals au scroll (IntersectionObserver) */
  const reveal = document.querySelectorAll("[data-reveal]");
  if (reduce) {
    reveal.forEach(el => el.classList.add("in"));
  } else {
    const io = new IntersectionObserver((entries) => {
      entries.forEach(e => {
        if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });
    reveal.forEach(el => io.observe(el));
    // Filet de sécurité : tout ce qui est DÉJÀ visible au chargement se révèle aussitôt
    // (évite un hero vide si l'IntersectionObserver ne déclenche pas à temps).
    requestAnimationFrame(() => {
      const vh = window.innerHeight || document.documentElement.clientHeight;
      reveal.forEach(el => {
        const r = el.getBoundingClientRect();
        if (r.top < vh * 0.92 && r.bottom > 0) { el.classList.add("in"); io.unobserve(el); }
      });
    });
  }

  /* 3) Compteurs animés (count-up) */
  const nums = document.querySelectorAll("[data-count]");
  const fmt = (n) => n.toLocaleString("fr-FR");
  const run = (el) => {
    const target = parseFloat(el.dataset.count);
    const suffix = el.dataset.suffix || "";
    const dur = 1400; const t0 = performance.now();
    const tick = (t) => {
      const k = Math.min(1, (t - t0) / dur);
      const e = 1 - Math.pow(1 - k, 3);
      el.textContent = fmt(Math.round(target * e)) + suffix;
      if (k < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  };
  if (nums.length) {
    const io2 = new IntersectionObserver((entries) => {
      entries.forEach(e => { if (e.isIntersecting) { if (!reduce) run(e.target); else e.target.textContent = fmt(parseFloat(e.target.dataset.count)) + (e.target.dataset.suffix || ""); io2.unobserve(e.target); } });
    }, { threshold: 0.6 });
    nums.forEach(n => io2.observe(n));
  }

  /* 4) Parallaxe souris sur le mock device */
  const device = document.querySelector(".device");
  const phone = document.querySelector(".phone");
  if (device && phone && !reduce && window.matchMedia("(pointer:fine)").matches) {
    device.addEventListener("mousemove", (ev) => {
      const r = device.getBoundingClientRect();
      const x = (ev.clientX - r.left) / r.width - 0.5;
      const y = (ev.clientY - r.top) / r.height - 0.5;
      phone.style.transform = `rotateY(${-14 + x * 10}deg) rotateX(${6 - y * 10}deg) translateY(${y * -6}px)`;
    });
    device.addEventListener("mouseleave", () => { phone.style.transform = ""; });
  }

  /* 5) Spotlight sur les cartes (suivi curseur) */
  if (!reduce) document.querySelectorAll(".card").forEach(c => {
    c.addEventListener("mousemove", (e) => {
      const r = c.getBoundingClientRect();
      c.style.setProperty("--mx", (e.clientX - r.left) + "px");
      c.style.setProperty("--my", (e.clientY - r.top) + "px");
    });
  });

  /* 6) Toggle tarifs mensuel/annuel */
  const toggle = document.querySelector(".toggle");
  if (toggle) {
    toggle.addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      toggle.querySelectorAll("button").forEach(x => x.classList.remove("on"));
      b.classList.add("on");
      const annual = b.dataset.period === "annuel";
      document.querySelectorAll("[data-m]").forEach(el => {
        el.textContent = annual ? el.dataset.a : el.dataset.m;
      });
    });
  }

  /* 7) Nav mobile */
  const burger = document.querySelector(".burger");
  const nav = document.querySelector(".nav");
  if (burger && nav) burger.addEventListener("click", () => nav.classList.toggle("open"));
  nav && nav.querySelectorAll("a").forEach(a => a.addEventListener("click", () => nav.classList.remove("open")));

  /* 8) Marquee : duplique la piste pour une boucle continue */
  document.querySelectorAll(".marquee .track").forEach(tr => {
    tr.innerHTML += tr.innerHTML;
  });

  /* 9) Année courante dans le footer */
  document.querySelectorAll("[data-year]").forEach(el => el.textContent = new Date().getFullYear());

  /* 10) Faux envoi de formulaire (démo vitrine, pas de backend) */
  document.querySelectorAll("form[data-demo]").forEach(f => {
    f.addEventListener("submit", (e) => {
      e.preventDefault();
      const ok = f.querySelector(".form-ok");
      f.querySelectorAll("input,select,textarea,button").forEach(x => x.disabled = true);
      if (ok) ok.style.display = "block";
    });
  });

  /* 11) Séquence animée du hero (joue la paie en boucle) */
  const seq = document.querySelector(".seq");
  if (seq && !reduce) {
    const frames = [...seq.querySelectorAll(".frame")];
    const dots = [...document.querySelectorAll(".seqdots i")];
    let i = 0;
    const show = (n) => {
      frames.forEach((f, k) => f.classList.toggle("active", k === n));
      dots.forEach((d, k) => d.classList.toggle("on", k === n));
    };
    show(0);
    setInterval(() => { i = (i + 1) % frames.length; show(i); }, 2300);
  } else if (seq) {
    // reduced-motion : afficher la dernière frame (résultat payé)
    const frames = [...seq.querySelectorAll(".frame")];
    frames.forEach((f, k) => f.classList.toggle("active", k === frames.length - 1));
  }

  /* 12) Révélation par mot (titres taggés data-words, texte simple uniquement) */
  document.querySelectorAll("[data-words]").forEach(el => {
    const words = el.textContent.trim().split(/\s+/);
    el.textContent = "";
    words.forEach((w, k) => {
      const s = document.createElement("span");
      s.className = "word"; s.textContent = w;
      s.style.transitionDelay = (k * 0.045).toFixed(3) + "s";
      el.appendChild(s);
      el.appendChild(document.createTextNode(" "));
    });
    if (reduce) { el.querySelectorAll(".word").forEach(s => s.classList.add("in")); return; }
    const io3 = new IntersectionObserver((ents) => {
      ents.forEach(e => { if (e.isIntersecting) { el.querySelectorAll(".word").forEach(s => s.classList.add("in")); io3.unobserve(el); } });
    }, { threshold: 0.4 });
    io3.observe(el);
  });

  /* 13) Boutons magnétiques (desktop fin) */
  if (!reduce && window.matchMedia("(pointer:fine)").matches) {
    document.querySelectorAll(".btn-lg").forEach(b => {
      b.addEventListener("mousemove", (e) => {
        const r = b.getBoundingClientRect();
        b.style.transform = `translate(${((e.clientX - r.left) / r.width - .5) * 8}px,${((e.clientY - r.top) / r.height - .5) * 8}px)`;
      });
      b.addEventListener("mouseleave", () => { b.style.transform = ""; });
    });
  }
})();
