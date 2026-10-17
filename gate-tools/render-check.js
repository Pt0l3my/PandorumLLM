// Render the server cards for real.
//
// `const bad = (key !== "model") ? ...` shipped inside optFor(m, wantKey, cur2) and
// emptied the Servers page for three releases. The page PARSED - every check was
// textual, and the line is only wrong when it runs. This runs it.
//
// The window and the element stub moved into page-sandbox.js in patch11, where the
// reference harness reads them too. One page, loaded one way.
const S = require("./page-sandbox.js");

// the shape the broken line actually ran on: a slot with a model, a drafter whose
// width does not fit it, and a projector
const STATE = {
  slots: [{ id: "s1", title: "Server 1", port: 1234, gpu: "g0", scriptExists: true,
    status: { state: "down" }, speeds: null, actualPort: null, providers: [],
    params: { model: "m.gguf", draft: "d.gguf", vision: "v.gguf" } }],
  gpus: [{ id: "g0", name: "GPU", uuid: "GPU-x", index: 0 }],
  models: [
    { path: "m.gguf", name: "m.gguf", kind: "main", arch: "gemma4",
      archLabel: "Gemma 4", blocks: 40, archCtx: 262144, embd: 2816, embdOut: 0 },
    { path: "d.gguf", name: "d.gguf", kind: "draft", arch: "gemma4-assistant",
      archLabel: "Gemma 4 assistant", blocks: 4, archCtx: 262144,
      embd: 1024, embdOut: 5376 },
    { path: "v.gguf", name: "v.gguf", kind: "vision", arch: "clip",
      archLabel: "CLIP", blocks: 0, archCtx: 0, embd: 0, embdOut: 0 }],
  routing: [], paramDefs: [], launchers: [], history: [],
  cast: ["Maxxor", "Onmund"], settings: {}, stack: {}, version: "test",
};

function run(file) {
  const faults = [];
  let F;
  try {
    F = S.load(file,
      ["renderSlots", "paramEditor", "ctlApply", "paintCast", "paintThink",
       "markAt", "drawSegs", "paintTail"],
      "  state = " + JSON.stringify(STATE) + "; models = state.models;"
      + " curTab = 'servers'; curSsub = 'slots';").F;
  } catch (e) {
    faults.push("the page did not finish loading: " + e.constructor.name
      + ": " + e.message.slice(0, 160));
    return faults;
  }
  const CALL = {
    paintCast: f => f(STATE.cast),
    renderSlots: f => f(true),
    paramEditor: f => f(STATE.slots[0]),
    ctlApply: f => f(STATE.slots[0].id),
    // the term is the terminal being drawn: one painter serves three feeds, and
    // the landing places it names carry it (patch11)
    paintThink: f => f(S.el(), "[09:41:18] Maxxor waited 4872ms for NE-Director [1238]",
                       "thinking"),
    paintTail: f => f("dashboard", "[09:41:18] Maxxor waited 4872ms [1238]",
                      S.el(), "dashboard"),
  };
  for (const name in CALL) {
    if (typeof F[name] !== "function") { faults.push(name + " is not reachable"); continue; }
    try { CALL[name](F[name]); }
    catch (e) { faults.push(name + "(): " + e.constructor.name + ": "
      + e.message.slice(0, 160)); }
  }
  return faults;
}

const faults = run(process.argv[2]);
console.log(faults.length
  ? "FAILED\n  " + faults.join("\n  ")
  : "the page loads and every terminal and card renders without throwing");
process.exit(faults.length ? 1 : 0);
