// The served page, loaded and running, in one place.
//
// Two harnesses need this and there is one copy of it: render-check.js proves the
// page loads and every card and terminal DRAWS, ref-check.js reads what a painter
// actually produced. Both were going to grow their own element stub and their own
// window, which is how four terminal painters drifted apart in the first place.
// (v3.76 patch11)
const fs = require("fs"), vm = require("vm");

function el() {
  return { innerHTML: "", textContent: "", value: "", title: "",
    style: { setProperty() {}, removeProperty() {}, getPropertyValue: () => "" },
    dataset: {}, children: [], scrollTop: 0, clientHeight: 0, scrollHeight: 0,
    offsetWidth: 0, offsetParent: null,
    classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
    appendChild() {}, removeChild() {}, insertBefore() {}, remove() {},
    replaceWith() {}, isConnected: false,
    setAttribute() {}, removeAttribute() {}, getAttribute: () => null,
    addEventListener() {}, removeEventListener() {}, focus() {}, blur() {},
    querySelector: () => null, querySelectorAll: () => [], closest: () => null,
    scrollIntoView() {},
    getBoundingClientRect: () => ({ top: 0, left: 0, width: 0, height: 0 }) };
}

function sandbox() {
  const ctx = {
    console,
    document: { body: el(), documentElement: el(), head: el(), cookie: "",
      activeElement: { tagName: "BODY" }, getElementById: () => el(),
      querySelector: () => el(), querySelectorAll: () => [],
      createElement: () => el(), addEventListener() {} },
    navigator: { clipboard: {}, userAgent: "node" },
    location: { href: "http://x/", search: "", hash: "", reload() {} },
    localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
    sessionStorage: { getItem: () => null, setItem() {}, removeItem() {} },
    setTimeout: () => 0, setInterval: () => 0, clearTimeout() {}, clearInterval() {},
    requestAnimationFrame: () => 0, cancelAnimationFrame() {},
    fetch: () => new Promise(() => {}),
    EventSource: function () { this.addEventListener = () => {}; this.close = () => {}; },
    Audio: function () { this.play = () => {}; this.pause = () => {}; },
    FileReader: function () {}, Image: function () {},
    MutationObserver: function () { this.observe = () => {}; this.disconnect = () => {}; },
    ResizeObserver: function () { this.observe = () => {}; this.disconnect = () => {}; },
    IntersectionObserver: function () { this.observe = () => {}; this.disconnect = () => {}; },
    matchMedia: () => ({ matches: false, addEventListener() {}, addListener() {} }),
    getComputedStyle: () => ({ getPropertyValue: () => "" }),
    performance: { now: () => 0 },
    // the two values the panel injects into the page before serving it
    __TSKINDS__: [], __MOODS__: {},
    addEventListener() {}, removeEventListener() {}, dispatchEvent() {},
  };
  ctx.window = ctx; ctx.globalThis = ctx; ctx.self = ctx; ctx.top = ctx;
  vm.createContext(ctx);
  return ctx;
}

// Run the page and hand back a probe over the names a harness asked for. The probe
// is appended to the page source rather than reached into, because the page script
// is one function scope and nothing in it is exported.
function load(file, names, pre) {
  const ctx = sandbox();
  const probe = ["", ";globalThis.__probe = function () {",
    pre || "",
    "  return { " + names.map(n => n + ": " + n).join(", ") + " };",
    "};"].join("\n");
  vm.runInContext(fs.readFileSync(file, "utf8") + probe, ctx, { timeout: 30000 });
  if (typeof ctx.__probe !== "function") throw new Error("no probe");
  return { ctx: ctx, F: ctx.__probe() };
}

module.exports = { el: el, sandbox: sandbox, load: load };
