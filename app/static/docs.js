/* AgentSec documentation: theme switch, mobile navigation, copy buttons, the "On this page" highlight and
 * instant search. The pages are complete without this script (search falls back to /docs/search); it only
 * adds convenience. Text is always inserted as text nodes, never parsed as HTML. */
(function () {
  "use strict";

  var root = document.documentElement;

  /* ---------------------------------------------------------------- theme (shared with the dashboard) */
  var themeBtn = document.getElementById("theme");
  if (themeBtn) {
    themeBtn.addEventListener("click", function () {
      var cur = root.getAttribute("data-theme") || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
      var next = cur === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("agentsec-theme", next); } catch (e) { /* storage unavailable */ }
    });
  }

  /* ---------------------------------------------------------------- mobile navigation */
  var menu = document.getElementById("dx-menu");
  var scrim = document.getElementById("dx-scrim");
  function setNav(open) {
    document.body.classList.toggle("dx-nav-open", open);
    if (menu) menu.setAttribute("aria-expanded", open ? "true" : "false");
    if (scrim) scrim.hidden = !open;
  }
  if (menu) menu.addEventListener("click", function () { setNav(!document.body.classList.contains("dx-nav-open")); });
  if (scrim) scrim.addEventListener("click", function () { setNav(false); });
  var active = document.querySelector(".dx-nav-group a.active");
  if (active && active.scrollIntoView) active.scrollIntoView({ block: "center" });

  /* ---------------------------------------------------------------- copy buttons */
  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) return navigator.clipboard.writeText(text);
    return new Promise(function (resolve) {
      var ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.className = "dx-offscreen";
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); } catch (e) { /* nothing more to try */ }
      document.body.removeChild(ta);
      resolve();
    });
  }
  Array.prototype.forEach.call(document.querySelectorAll(".dx-code"), function (fig) {
    var btn = fig.querySelector(".dx-copy");
    var code = fig.querySelector("pre code");
    if (!btn || !code) return;
    btn.hidden = false;
    btn.setAttribute("aria-label", "Copy code to clipboard");
    btn.addEventListener("click", function () {
      copyText(code.textContent.replace(/\n$/, "")).then(function () {
        btn.textContent = "Copied";
        setTimeout(function () { btn.textContent = "Copy"; }, 1400);
      });
    });
  });

  /* ---------------------------------------------------------------- screenshots: click to enlarge */
  // Without JavaScript the link simply opens the image. With it, the image opens in a dialog over the page
  // (Escape, the Close button or a click closes it), using whichever theme's picture is showing.
  var zoom = null;
  function openZoom(link) {
    var imgs = Array.prototype.slice.call(link.querySelectorAll("img"));
    var shown = imgs.filter(function (i) { return i.offsetParent !== null; })[0] || imgs[0];
    if (!shown) return false;
    if (!zoom) {
      zoom = document.createElement("dialog");
      zoom.className = "dx-lightbox";
      zoom.setAttribute("aria-label", "Enlarged screenshot");
      var close = document.createElement("button");
      close.type = "button";
      close.className = "btn small dx-lightbox-close";
      close.textContent = "Close";
      close.addEventListener("click", function () { zoom.close(); });
      var big = document.createElement("img");
      var cap = document.createElement("p");
      cap.className = "dx-lightbox-cap";
      zoom.appendChild(close);
      zoom.appendChild(big);
      zoom.appendChild(cap);
      zoom.addEventListener("click", function (e) { if (e.target === zoom || e.target === big) zoom.close(); });
      document.body.appendChild(zoom);
    }
    var img = zoom.querySelector("img");
    img.src = shown.currentSrc || shown.src;
    img.alt = shown.alt;
    var fc = link.parentNode.querySelector("figcaption");
    zoom.querySelector(".dx-lightbox-cap").textContent = fc ? fc.textContent : "";
    zoom.showModal();
    zoom.querySelector("button").focus();
    return true;
  }
  if (typeof HTMLDialogElement === "function") {
    Array.prototype.forEach.call(document.querySelectorAll("a.dx-zoom"), function (a) {
      a.addEventListener("click", function (e) {
        if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
        if (openZoom(a)) e.preventDefault();
      });
    });
  }

  /* ---------------------------------------------------------------- "On this page" highlight */
  var tocLinks = Array.prototype.slice.call(document.querySelectorAll(".dx-toc a"));
  if (tocLinks.length && "IntersectionObserver" in window) {
    var byId = {};
    tocLinks.forEach(function (a) { byId[decodeURIComponent(a.getAttribute("href").slice(1))] = a; });
    var headings = Object.keys(byId).map(function (id) { return document.getElementById(id); }).filter(Boolean);
    var visible = {};
    var mark = function () {
      var current = null;
      for (var i = 0; i < headings.length; i++) {
        if (visible[headings[i].id]) { current = headings[i]; break; }
      }
      if (!current) {
        // Between headings: the last one above the viewport.
        for (var j = headings.length - 1; j >= 0; j--) {
          if (headings[j].getBoundingClientRect().top < 120) { current = headings[j]; break; }
        }
      }
      tocLinks.forEach(function (a) { a.classList.remove("active"); });
      if (current && byId[current.id]) byId[current.id].classList.add("active");
    };
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { visible[e.target.id] = e.isIntersecting; });
      mark();
    }, { rootMargin: "-64px 0px -60% 0px" });
    headings.forEach(function (h) { io.observe(h); });
  }

  /* ---------------------------------------------------------------- search */
  var input = document.getElementById("dx-q");
  var panel = document.getElementById("dx-results");
  if (!input || !panel) return;
  var index = null, loading = null, selected = -1, results = [];

  function setPanel(open) {
    panel.hidden = !open;
    input.setAttribute("aria-expanded", open ? "true" : "false");
    if (!open) input.removeAttribute("aria-activedescendant");
  }

  function load() {
    if (index) return Promise.resolve(index);
    if (!loading) {
      loading = fetch("/docs/search-index.json", { credentials: "same-origin" })
        .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
        .then(function (d) {
          index = d.entries.map(function (e) {
            return { e: e, heading: (e.heading || "").toLowerCase(), page: e.page.toLowerCase(), text: e.text.toLowerCase() };
          });
          return index;
        })
        .catch(function (err) { loading = null; throw err; });
    }
    return loading;
  }

  // Keep STOP, terms() and the scoring below in step with app/docs/site.py (STOPWORDS, _terms, search), which
  // serves the same results without JavaScript; tests/test_docs.py checks the stop-word lists match.
  var STOP = ("a an and are as at be by can do does for from get how i if in is it me mean meaning my of on " +
    "or our the this to use using what when where which why with work you your").split(" ");

  function terms(q) {
    var out = [];
    q.toLowerCase().split(/[^a-z0-9_.\/-]+/).forEach(function (t) {
      if (!t || STOP.indexOf(t) >= 0) return;
      if (t.length > 3 && t.slice(-1) === "s" && t.slice(-2) !== "ss") t = t.slice(0, -1);
      if (out.indexOf(t) < 0) out.push(t);
    });
    return out;
  }

  function count(hay, needle) {
    var n = 0, i = hay.indexOf(needle);
    while (i >= 0 && n < 6) { n++; i = hay.indexOf(needle, i + needle.length); }
    return n;
  }

  // -> {matched: terms found, s: score}. A heading containing the whole query ranks first.
  function score(item, ts, phrase) {
    var total = 0, matched = 0;
    for (var i = 0; i < ts.length; i++) {
      var t = ts[i], hit = 0;
      if (item.heading.indexOf(t) >= 0) hit += 12 + (item.heading === t || item.heading.indexOf(t) === 0 ? 6 : 0);
      if (item.page.indexOf(t) >= 0) hit += 6;
      hit += count(item.text, t);
      if (hit) matched++;
      total += hit;
    }
    if (phrase.length > 3 && item.heading.indexOf(phrase) >= 0) total += 30;
    return { matched: matched, s: total };
  }

  function highlighted(text, ts) {
    var frag = document.createDocumentFragment();
    var low = text.toLowerCase(), pos = 0;
    while (pos < text.length) {
      var best = -1, len = 0;
      ts.forEach(function (t) {
        var i = low.indexOf(t, pos);
        if (i >= 0 && (best < 0 || i < best)) { best = i; len = t.length; }
      });
      if (best < 0) { frag.appendChild(document.createTextNode(text.slice(pos))); break; }
      if (best > pos) frag.appendChild(document.createTextNode(text.slice(pos, best)));
      var m = document.createElement("mark");
      m.textContent = text.slice(best, best + len);
      frag.appendChild(m);
      pos = best + len;
    }
    return frag;
  }

  function snippet(text, ts) {
    var low = text.toLowerCase(), pos = -1;
    ts.forEach(function (t) { var i = low.indexOf(t); if (i >= 0 && (pos < 0 || i < pos)) pos = i; });
    if (pos < 0) pos = 0;
    var start = Math.max(0, pos - 50);
    return (start ? "…" : "") + text.slice(start, start + 180) + (start + 180 < text.length ? "…" : "");
  }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  }

  function show() {
    var q = input.value.trim();
    while (panel.firstChild) panel.removeChild(panel.firstChild);
    selected = -1;
    if (!q) { setPanel(false); return; }
    load().then(function (idx) {
      if (input.value.trim() !== q) return;
      var ts = terms(q), phrase = q.toLowerCase().split(/\s+/).join(" ");
      var scored = ts.length ? idx.map(function (it) { var r = score(it, ts, phrase); r.it = it; return r; })
        .filter(function (x) { return x.matched > 0; }) : [];
      // Every term must match; when nothing matches them all, show what matches the most.
      if (scored.some(function (x) { return x.matched === ts.length; })) {
        scored = scored.filter(function (x) { return x.matched === ts.length; });
      }
      results = scored.sort(function (a, b) { return b.matched - a.matched || b.s - a.s; }).slice(0, 10);
      while (panel.firstChild) panel.removeChild(panel.firstChild);
      if (!results.length) {
        panel.appendChild(el("p", "dx-empty", "No results for “" + q + "”."));
      }
      results.forEach(function (r, i) {
        var e = r.it.e;
        var a = el("a");
        a.href = e.url;
        a.id = "dx-r-" + i;
        a.setAttribute("role", "option");
        var strong = el("strong");
        strong.appendChild(highlighted(e.heading || e.page, ts));
        a.appendChild(strong);
        a.appendChild(el("span", "dx-r-path", e.section + " · " + e.page));
        var p = el("p");
        p.appendChild(highlighted(snippet(e.text, ts), ts));
        a.appendChild(p);
        a.addEventListener("click", function () { setPanel(false); setNav(false); });
        panel.appendChild(a);
      });
      var hint = el("div", "dx-hint");
      hint.appendChild(el("span", null, "↑ ↓ to move"));
      hint.appendChild(el("span", null, "Enter to open"));
      hint.appendChild(el("span", null, "Esc to close"));
      panel.appendChild(hint);
      setPanel(true);
    }).catch(function () {
      // Index unavailable: the form still submits to the server-side results page.
      setPanel(false);
    });
  }

  function move(delta) {
    var links = panel.querySelectorAll("a[role=option]");
    if (!links.length) return;
    selected = (selected + delta + links.length) % links.length;
    Array.prototype.forEach.call(links, function (a, i) { a.setAttribute("aria-selected", i === selected ? "true" : "false"); });
    links[selected].scrollIntoView({ block: "nearest" });
    input.setAttribute("aria-activedescendant", links[selected].id);
  }

  var timer;
  input.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(show, 90); });
  input.addEventListener("focus", function () { load().catch(function () {}); if (input.value.trim()) show(); });
  input.addEventListener("keydown", function (e) {
    if (e.key === "ArrowDown") { e.preventDefault(); move(1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); move(-1); }
    else if (e.key === "Escape") { setPanel(false); input.blur(); }
    else if (e.key === "Enter" && selected >= 0) {
      e.preventDefault();
      var a = panel.querySelectorAll("a[role=option]")[selected];
      if (a) location.href = a.href;
    }
  });
  document.addEventListener("click", function (e) {
    if (!panel.contains(e.target) && e.target !== input) setPanel(false);
  });
  document.addEventListener("keydown", function (e) {
    var tag = (e.target.tagName || "").toLowerCase();
    var typing = tag === "input" || tag === "textarea" || tag === "select" || e.target.isContentEditable;
    if ((e.key === "/" && !typing) || (e.key.toLowerCase() === "k" && (e.metaKey || e.ctrlKey))) {
      e.preventDefault();
      input.focus();
      input.select();
    } else if (e.key === "Escape") {
      setNav(false);
    }
  });
})();
