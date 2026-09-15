// What a painter PRODUCES for a line carrying a reference.
//
// patch6 wrote the mark, patch7 wrote a second one and the landing place, patch8 put
// them on two more terminals - and every check those releases ran asked whether the
// mark was WRITTEN. None asked whether anything read it. The Proxy terminal never
// learned to, so from patch7 to patch10 it printed the mark as text; and one painter
// served three feeds while naming every landing place as if it were the Thinking one,
// so two terminals held one id. Neither throws. Both are visible only here.
// (v3.76 patch11)
const S = require("./page-sandbox.js");

const L = String.fromCodePoint(0x27E8), R = String.fromCodePoint(0x27E9);
const P1 = String.fromCodePoint(0x27E6), P2 = String.fromCodePoint(0x27E7);
const BOLT = String.fromCodePoint(0x26A1), SPEAK = String.fromCodePoint(0x1F4AC);
const MID = String.fromCharCode(0x251C);
const NLX = String.fromCharCode(10);

// Does any element carrying data-act sit INSIDE another that does? The click
// dispatcher takes the innermost, so a second action within the first silently
// replaces it - which is how a provider link swallowed a payload hook in
// patch16. Walked as a stack: nesting is a tree question, not a text one.
function nestedAct(html) {
  const tag = new RegExp("<(/?)(\\w+)([^>]*)>", "g");
  let m, depth = [], worst = 0;
  while ((m = tag.exec(html))) {
    if (m[1] === "/") { if (depth.length) depth.pop(); continue; }
    if (m[0].slice(-2) === "/>") continue;
    const has = m[3].indexOf("data-act=") >= 0;
    if (has && depth.filter(Boolean).length > 0) worst = depth.filter(Boolean).length + 1;
    depth.push(has);
  }
  return worst;
}

// the same heading with the stamp hidden, which is this terminal's DEFAULT
const STAMPS_OFF = "dashboard,thinking,tts,ptipme,splitd,splitt,ttscal";

const STATE = { slots: [], gpus: [], models: [], paramDefs: [], launchers: [],
  history: [], cast: ["Maxxor"], stack: {}, version: "test",
  settings: { ttsPlayerTags: "on", ttsMoodEval: "on", ttsThoughtOut: "on",
              ttsActionOut: "on" },
  routing: [{ id: "s1", providers: [
    { id: "p1", title: "NE-Director", emoji: SPEAK },
    { id: "p2", title: "Vision", emoji: "!" },
    { id: "p3", title: "NE", emoji: "?" }] }] };

let F = null, loadErr = "";
try {
  F = S.load(process.argv[2],
  ["paintTail", "refName", "refTake", "refChip", "REF_KIND", "TERM_NAME",
   "MARK", "dashColor"],
    // the two shared lists are built by load() in the real page; a harness that
    // skips them tests a panel where no character and no provider is known
    "  state = " + JSON.stringify(STATE) + "; paintCast(state.cast);"
    + " paintProvs(state.routing);").F;
} catch (e) {
  // a name the page no longer defines is a FAILURE with a name, not a stack trace
  // the caller has to read out of stderr
  loadErr = e.constructor.name + ": " + e.message.slice(0, 160);
}
if (!F) {
  console.log(JSON.stringify({ harnessRan: false, why: loadErr }));
  process.exit(1);
}

// A second panel with termStampsOff as it ships. Loaded rather than poked at:
// `state` lives inside the sandbox, and the setting is read during the paint.
let FOFF = null;
try {
  const OFF = JSON.parse(JSON.stringify(STATE));
  OFF.settings.termStampsOff = STAMPS_OFF;
  FOFF = S.load(process.argv[2], ["paintTail"],
    "  state = " + JSON.stringify(OFF) + "; paintCast(state.cast);"
    + " paintProvs(state.routing);").F;
} catch (e) { FOFF = null; }

function paintOff(which, text) {
  if (!FOFF) return "";
  const e = S.el();
  FOFF.paintTail(which, text, e, which);
  return e.innerHTML;
}

function paint(which, text) {
  const e = S.el();
  F.paintTail(which, text, e, which);
  return e.innerHTML;
}
const chipOf = h => ((h.match(new RegExp("refchip[^>]*>([^<]*)<")) || [])[1] || "");
// the text inside the payload hook, with any colour spans inside it taken off
const hookIn = h => ((h.match(new RegExp(
  'class="plpay"[^>]*>([\\s\\S]*?)</span>')) || [])[1] || "")
  .replace(new RegExp("<[^>]+>", "g"), "").trim();
const idsOf = h => (h.match(new RegExp('id="ref-[^"]*"', "g")) || [])
  .map(x => x.slice(4, -1));

const REC = "[09:41:18] " + SPEAK + " NE-Director [1238]  120 in  40 out  2.1 s";
const ACT = "[09:41:19] " + MID + " " + BOLT + " Maxxor > Attack (target: wolf)";
const THINK = "=".repeat(70) + "\n[09:41:18] NE-Director [1238]  (~30 tok est)  "
  + L + "dlg:1236" + R + "\n" + "=".repeat(70) + "\nthe reasoning";
// ptipme_log is called with the literal "PTI" or "PME" as its who - a job name,
// never a provider and never a character. The fixture said "Maxxor", which is
// neither, and so could not show whether the hook lands on the right word.
const PTIPME = "=".repeat(74) + "\n[09:41:18] PTI  [1238]  0.412 sec  "
  + L + "dlg:1236" + R + "\n" + "=".repeat(74) + "\n--- INPUT ---\nhello";

const proxyThink = paint("dashboard", REC + "  " + L + "think:1236" + R + "  " + P1 + "1236" + P2);
const proxyPlain = paint("dashboard", REC + "  " + P1 + "1236" + P2);
const proxyAct = paint("dashboard", ACT);
const thinkIds = idsOf(paint("thinking", THINK));
// the provider hover-glow target on a line, by the id it carries
const provIn = h => ((h.match(new RegExp(
  'class="provlink"[^>]*data-id="([^"]*)"')) || [])[1] || null);
// the hover-glow colour a provider is drawn in, whichever terminal drew it
const colOf = h => ((h.match(new RegExp(
  'class="provlink" style="--pgl:([^"]*)"')) || [])[1] || null);
const thinkHdr = (paint("thinking", THINK).split(NLX)
  .filter(r => r.indexOf("NE-Director") >= 0)[0] || "");
const provBody = (paint("thinking", "=".repeat(70)
  + NLX + "Visionary plans need no Vision at all.").split(NLX)
  .filter(r => r.indexOf("Visionary") >= 0)[0] || "");
const ptipmeIds = idsOf(paint("ptipme", PTIPME));
const WAVE = String.fromCodePoint(0x3030) + String.fromCodePoint(0xFE0F);
const A1 = String.fromCodePoint(0x27EA), A2 = String.fromCodePoint(0x27EB);
// the audio id FIRST and the reference LAST: aidRx matches its marker anywhere,
// REF_RX is anchored at the end. Reversed, the reference is invisible.
const spokenTts = paint("tts", "[09:41:20] Serana: " + WAVE
  + " The Jarl speaks of dragons. " + WAVE + " " + A1 + "e77" + A2
  + "  " + L + "dlg:1236" + R);

const out = {
  harnessRan: true,
  // the fault this section exists for: the mark is read, not printed
  proxyReadsRef: chipOf(proxyThink) === "Thinking" && proxyThink.indexOf("think:1236") < 0,
  // and the payload button it sits in front of is untouched
  proxyKeepsPayload: proxyPlain.indexOf('data-act="proxyPayload"') >= 0
    && proxyThink.indexOf('data-act="proxyPayload"') >= 0,
  // the action branch carries NOTHING. patch11 gave it a reference to the call
  // that chose it; the record line directly above is that call, in the same
  // terminal, already opening that payload. (patch14)
  actionCarriesNoHook: chipOf(proxyAct) === "" && proxyAct.indexOf("plpay") < 0,
  // one call shown in two feeds is two elements, not one id twice
  idsAreTerminalScoped: thinkIds.length === 1 && ptipmeIds.length === 1
    && thinkIds[0] !== ptipmeIds[0]
    && thinkIds[0].indexOf("thinking") >= 0 && ptipmeIds[0].indexOf("ptipme") >= 0,
  // and the painter and the jump build that name the same way
  oneNameRule: thinkIds[0] === F.refName("thinking", "dlg", "1236"),
  // ONE hook shape: the name of the job is the thing you click, and no chip
  // stands beside it saying a word that is not the provider, not the terminal
  // and not what clicking does. (patch14)
  headingNameIsTheHook: hookIn(paint("thinking", THINK)).indexOf("NE-Director") >= 0
    && hookIn(paint("ptipme", PTIPME)) === "PTI",
  // and the provider inside that hook wears its emoji, as the Proxy record does
  headingHookCarriesTheEmoji: hookIn(paint("thinking", THINK)).indexOf(SPEAK) >= 0,
  // A DISPLAY toggle must not decide whether a link exists. termStampsOff ships
  // with this terminal in it, so the region had no left edge and every heading
  // fell through to a chip. (patch17)
  headingHooksWithStampsHidden: (function () {
    const h = paintOff("thinking", THINK);
    return h.indexOf('class="plpay"') >= 0 && chipOf(h) === "";
  })(),
  // a reference to the call opens it through the dispatcher that works - the
  // arm it used to take called a name outside its scope and threw every time
  callChipUsesTheWorkingDispatcher:
    F.refChip("dlg", "41").indexOf('data-act="proxyPayload"') >= 0
    && F.refChip("think", "41").indexOf('data-act="refJump"') >= 0,
  // and no element with an action sits inside another that has one
  noNestedActions: nestedAct(proxyThink) === 0 && nestedAct(proxyPlain) === 0
    && nestedAct(paint("thinking", THINK)) === 0
    && nestedAct(paint("dashboard", ACT)) === 0,
  headingHasNoChip: chipOf(paint("thinking", THINK)) === ""
    && chipOf(paint("ptipme", PTIPME)) === "",
  // the one chip left points at another TERMINAL, where no word can carry it
  crossTerminalKeepsItsChip: chipOf(proxyThink) === "Thinking",
  // a spoken line reaches the call its words came out of - only here, and only
  // as a chip: the line holds a mood icon, a character name and the words, and
  // a cast name is a colour rather than a link (patch15)
  spokenReachesItsCall: chipOf(spokenTts) === "Request"
    && spokenTts.indexOf("dlg:1236") < 0,
  // and the replay marker it shares the line with is untouched
  spokenKeepsItsReplay: spokenTts.indexOf("e77") >= 0,
  // ONE provider list, longest title first so a short one cannot answer for a
  // long one, and the id carried so every terminal reuses the one handler
  provListIsShared: F.MARK.provs.length === 3
    && F.MARK.provs[0].title === "NE-Director"
    && F.MARK.provs[0].id === "p1",
  // the SAME presentation in both terminals: colour, emoji and hover glow. Not
  // the same ACTION - inside a payload hook the provider carries none, or it
  // would take the click the hook is there for. (patch17)
  provSameInBothTerminals: colOf(thinkHdr) === colOf(proxyPlain)
    && colOf(thinkHdr) !== null
    && thinkHdr.indexOf('class="provlink"') >= 0
    && proxyPlain.indexOf('class="provlink"') >= 0,
  // and a provider named in PROSE, outside any hook, keeps its own action
  provInProseKeepsItsAction:
    provIn(paint("thinking", "=".repeat(70) + NLX + "NE-Director decided to wait."))
      === "p1",
  // markEdge, which the dead branch never called: a provider named Vision must
  // not light up inside the word Visionary
  provRespectsWordEdges: provBody.indexOf("Visionary") >= 0
    && provBody.indexOf(">Visionary") < 0,
  // the emoji is shown once on a heading that had none of its own - the earlier
  // shape of this asserted against the Proxy record, which never passes through
  // markAt, so it could not have failed
  provEmojiShownOnce: (thinkHdr.split(SPEAK).length - 1) === 1,
  // every kind names a pane the name table knows, so no chip offers to open a
  // terminal that is not called that
  kindsNamePanes: Object.keys(F.REF_KIND)
    .every(k => !!F.TERM_NAME[F.REF_KIND[k].term]),
};
console.log(JSON.stringify(out));
process.exit(Object.keys(out).every(k => out[k] === true) ? 0 : 1);
