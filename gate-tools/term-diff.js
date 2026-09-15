// Whole-terminal differ: paintTail over a real feed, two builds, byte for byte.
// paint-diff.js takes one painter; this takes a TERMINAL, which is what a stage-3
// migration actually changes. (v3.76 patch21)
//
// Default is WHOLE-TEXT: the entire feed painted in one call, exactly as
// refreshTail does, so the splice, fixTree and the stamp handling all run - fed
// line by line none of them can, and a spoken line never reaches the Proxy arm at
// all. --lines paints per line instead: the mode that NAMES the line that moved,
// once whole-text has said something did. (v3.76 patch24)
//
// Usage: node term-diff.js <before.js> <after.js> <terminal> <corpus>
//                          [state.json] [tts.log] [--lines]
// state.json replaces the built-in stub state - derive it from the session the
// corpus came from, or the cast and provider branches never fire. tts.log seeds
// lastTtsTail so the splice has something to place.
// Exit 0 when everything paints identically; 1 otherwise; 2 on usage.
const fs = require("fs"), S = require("./page-sandbox.js");
const perLine = process.argv.indexOf("--lines") >= 0;
const args = process.argv.slice(2).filter(x => x !== "--lines");
const [a, b, term, corpus, stateF, ttsF] = args;
if (!a || !b || !term || !corpus) {
  console.log("usage: term-diff.js <before.js> <after.js> <terminal> <corpus>"
    + " [state.json] [tts.log] [--lines]");
  process.exit(2);
}
const SPEAK = "\u{1F4AC}";
const STATE = stateF ? JSON.parse(fs.readFileSync(stateF, "utf8"))
  : { slots: [], gpus: [], models: [], paramDefs: [], launchers: [], history: [],
      cast: ["Brelyna Maryon", "Onmund", "Tolfdir", "Maxxor"], stack: {}, version: "test",
      settings: { ttsPlayerTags: "on", ttsMoodEval: "on", ttsThoughtOut: "on",
                  ttsActionOut: "on" },
      routing: [{ id: "s1", providers: [{ id: "p1", title: "Dialogue", emoji: SPEAK }] }] };
const tts = ttsF ? fs.readFileSync(ttsF, "utf8") : "";
function load(f) {
  return S.load(f, ["paintTail"],
    "  state = " + JSON.stringify(STATE) + ";"
    // an older build may predate the splice buffer; a guard, not a stub
    + " if (typeof lastTtsTail !== \"undefined\") lastTtsTail = "
    + JSON.stringify(tts) + ";"
    + " paintCast(state.cast);"
    + " if (typeof paintProvs === 'function') paintProvs(state.routing);").F.paintTail;
}
const A = load(a), B = load(b);
const text = fs.readFileSync(corpus, "utf8");
function paint(fn, t) { const e = S.el(); try { fn(term, t, e, term); } catch (x) { return "THREW " + x.message; } return e.innerHTML; }
function firstDiff(x, y) { let i = 0; while (i < x.length && i < y.length && x[i] === y[i]) i++; return i; }
let moved = 0;
if (perLine) {
  const lines = text.split("\n").filter(l => l.length);
  const bad = [];
  for (const l of lines) { const x = paint(A, l), y = paint(B, l); if (x !== y) bad.push([l, x, y]); }
  moved = bad.length;
  console.log(term.padEnd(10) + lines.length + " real lines, " + bad.length + " painted differently");
  for (const [l, x, y] of bad.slice(0, 6)) {
    const i = firstDiff(x, y);
    console.log("  IN  " + JSON.stringify(l.slice(0, 78)));
    console.log("  was " + JSON.stringify(x.slice(Math.max(0, i - 12), i + 42)));
    console.log("  now " + JSON.stringify(y.slice(Math.max(0, i - 12), i + 42)));
  }
  if (bad.length > 6) console.log("  ... and " + (bad.length - 6) + " more");
} else {
  const x = paint(A, text), y = paint(B, text);
  moved = x === y ? 0 : 1;
  console.log(term.padEnd(10) + text.split("\n").length + " lines in, " + x.length
    + " bytes out, " + (x === y ? "identical" : "DIFFERENT"));
  if (moved) {
    const i = firstDiff(x, y);
    console.log("  first divergence at byte " + i);
    console.log("  was " + JSON.stringify(x.slice(Math.max(0, i - 30), i + 60)));
    console.log("  now " + JSON.stringify(y.slice(Math.max(0, i - 30), i + 60)));
  }
}
process.exit(moved ? 1 : 0);
