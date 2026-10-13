#!/usr/bin/env node
// entity-diff: does one build resolve every entity to the same ink as another?
//
// The entity side answers two questions - what is in the READY SET after a
// routing build, and what ink does entInk hand back for any name, known or
// not. This harness asks both of a build and compares the answers byte for
// byte, the way term-diff compares a painted feed. Self against self must be
// identical; a build with one palette byte moved must be DIFFERENT.
//
// usage: node entity-diff.js old.js new.js state.json
// exit 0 identical, 1 different, 2 usage/failure. (v3.76 patch28)
const fs = require("fs");
const S = require("./page-sandbox.js");
function snap(jsf, statef) {
  // a build from before the resolver answers through the derivation itself -
  // which makes an old-vs-new run the consolidation proof: dashColor's answers
  // and entInk's must be the same bytes
  let R;
  try { R = S.load(jsf, ["paintProvs", "entInk", "MARK"], ""); }
  catch (e) { R = S.load(jsf, ["paintProvs", "dashColor", "MARK"], ""); }
  const F = R.F;
  const ink = F.entInk || F.dashColor;
  const st = JSON.parse(fs.readFileSync(statef, "utf8"));
  F.paintProvs(st.routing || []);
  const set = (F.MARK.provs || [])
    .map(p => ({ t: p.title, id: p.id, e: p.emoji, c: p.c }))
    .sort((a, b) => (a.t < b.t ? -1 : a.t > b.t ? 1 : 0));
  const probes = {};
  for (const p of set) probes[p.t] = ink(p.t);
  const D = String.fromCodePoint(0x2937);
  probes["<drill>"] = set.length ? ink(set[0].t + D) : "";
  probes["<unknown>"] = ink("NoSuchProvider_ZZ");
  probes["<empty>"] = ink("");
  return JSON.stringify({ set: set, probes: probes });
}
const a = process.argv[2], b = process.argv[3], st = process.argv[4];
if (!a || !b || !st) {
  console.error("usage: entity-diff.js old.js new.js state.json");
  process.exit(2);
}
let A, B;
try { A = snap(a, st); B = snap(b, st); }
catch (e) { console.error("THREW " + (e && e.message)); process.exit(2); }
if (A === B) {
  console.log("entity   " + JSON.parse(A).set.length + " providers, identical");
  process.exit(0);
}
let i = 0;
while (i < A.length && i < B.length && A[i] === B[i]) i++;
console.log("entity   DIFFERENT");
console.log("  first divergence at byte " + i);
console.log("  was " + JSON.stringify(A.slice(Math.max(0, i - 20), i + 60)));
console.log("  now " + JSON.stringify(B.slice(Math.max(0, i - 20), i + 60)));
process.exit(1);
