// Did a painter's output CHANGE?
//
// Stage 3 moves four painters off text they re-derive meaning from and onto the
// shared vocabulary. Every one of those moves is a chance to silently alter what a
// terminal shows, and "it still renders" proves nothing about that - render-check
// only asks whether something threw. This runs one painter over a corpus of real log
// lines against two builds and diffs the markup byte for byte.
//
// Usage: node paint-diff.js <before.js> <after.js> <painter> <corpus.txt>
// Exit 0 when every line paints identically; 1 otherwise, listing what moved.
// (v3.76 patch19)
const fs = require("fs");
const S = require("./page-sandbox.js");

const SPEAK = String.fromCodePoint(0x1F4AC);
const STATE = {
  slots: [], gpus: [], models: [], paramDefs: [], launchers: [], history: [],
  cast: ["Maxxor", "Serana", "Onmund", "J'zargo"], stack: {}, version: "test",
  settings: { ttsPlayerTags: "on", ttsMoodEval: "on", ttsThoughtOut: "on",
              ttsActionOut: "on" },
  routing: [{ id: "s1", providers: [
    { id: "p1", title: "NE-Director", emoji: SPEAK },
    { id: "p2", title: "SeverActions", emoji: SPEAK }] }],
};

function load(file, painter) {
  return S.load(file, [painter],
    "  state = " + JSON.stringify(STATE) + "; paintCast(state.cast);"
    + " if (typeof paintProvs === 'function') paintProvs(state.routing);").F[painter];
}

const [beforeFile, afterFile, painter, corpusFile] = process.argv.slice(2);
if (!beforeFile || !afterFile || !painter || !corpusFile) {
  console.log("usage: paint-diff.js <before.js> <after.js> <painter> <corpus.txt>");
  process.exit(2);
}

// The corpus is real log text, one line per entry, CR already off. Lines the painter
// never sees in the field would prove nothing, so nothing is invented here.
const corpus = fs.readFileSync(corpusFile, "utf8")
  .split("\n").map(l => l.replace(/\r$/, "")).filter(l => l.length > 0);

let A, B;
try { A = load(beforeFile, painter); } catch (e) {
  console.log("FAILED to load before: " + e.message.slice(0, 160)); process.exit(1);
}
try { B = load(afterFile, painter); } catch (e) {
  console.log("FAILED to load after: " + e.message.slice(0, 160)); process.exit(1);
}

const moved = [];
for (const line of corpus) {
  let a, b;
  try { a = String(A(line)); } catch (e) { a = "THREW: " + e.message; }
  try { b = String(B(line)); } catch (e) { b = "THREW: " + e.message; }
  if (a !== b) moved.push({ line: line, a: a, b: b });
}

console.log(painter + ": " + corpus.length + " real lines, "
  + moved.length + " painted differently");
for (const d of moved.slice(0, 12)) {
  console.log("  IN  " + JSON.stringify(d.line.slice(0, 96)));
  // show only where they diverge, not two walls of markup
  let i = 0;
  while (i < d.a.length && i < d.b.length && d.a[i] === d.b[i]) i++;
  console.log("  was " + JSON.stringify(d.a.slice(Math.max(0, i - 20), i + 60)));
  console.log("  now " + JSON.stringify(d.b.slice(Math.max(0, i - 20), i + 60)));
}
if (moved.length > 12) console.log("  ... and " + (moved.length - 12) + " more");
process.exit(moved.length ? 1 : 0);
