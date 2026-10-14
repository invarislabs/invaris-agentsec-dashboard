/* Applies the theme chosen in the dashboard (stored as agentsec-theme) before the documentation page paints,
   so a reader who picked dark or light does not see a flash of the other one. Loaded in <head>. */
(function () {
  "use strict";
  try {
    var t = localStorage.getItem("agentsec-theme");
    if (t === "dark" || t === "light") document.documentElement.setAttribute("data-theme", t);
  } catch (e) { /* storage unavailable: follow the system setting */ }
})();
