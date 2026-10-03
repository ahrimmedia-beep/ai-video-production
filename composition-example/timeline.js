/* =====================================================================
   SETTINGS. Change them here.
   All times are seconds of the video. In production they come from the word
   timings of the voice track (Whisper), so scenes and captions land on words.
   ===================================================================== */
const DURATION = 17.0;
const T = { s1: 0, s2: 3.2, flip: 4.9, s3: 6.6, s4: 9.6, s5: 11.8, s6: 14.6 };
// Frame layout from a given second. The video starts in "split".
// split: graphic + captions + presenter below; face: presenter full frame;
// graphic: graphic full frame; circle: graphic + presenter in a circle
const MODES = [[T.s2, "graphic"], [T.s5, "circle"], [T.s6, "split"]];
const XF = 0.5; // length of every crossfade and layout change
// Captions: [start, text]. *key* is big and yellow, _key_ is big and red (losses). "" clears the band.
const CAPTIONS = [
  [0.15, "Each scene is plain *HTML*"], [1.25, "moved by one *GSAP timeline*"], [2.4, "seekable to *any frame*"], [3.15, ""],
  [3.3, "A card can *flip* in 3D"], [4.85, "and the clock keeps _running_"], [6.5, ""],
  [6.7, "Tiles are built in *JavaScript*"], [7.75, "every fifth one turns _red_"], [8.7, "then a *card* comes up"], [9.5, ""],
  [9.7, "A counter tied to *timeline time*"], [10.6, "lands on *five* exactly"], [11.7, ""],
  [11.9, "Steps light up *one by one*"], [13.2, "timed to the *voice*"], [14.5, ""],
  [14.7, "The last scene holds the *call to action*"], [16.0, "and the *key words*"],
];

/* ===================================================================== */
const $ = (s) => document.querySelector(s);
const NS = "http://www.w3.org/2000/svg";
const pad = (n) => String(n).padStart(2, "0");
const clamp = (x) => Math.max(0, Math.min(1, x));

const tl = gsap.timeline({ paused: true });

/* ---------- themes: the plate, the caption band and the presenter panel follow the background ---------- */
const TH = {
  L: { pBg: "#ffffff", pFg: "#1a1d24", pBd: "#e2e6ee", cap: "#1e2330", fBg: "#eceff4" },
  B: { pBg: "#2a3658", pFg: "#ffffff", pBd: "#3e4b72", cap: "#1a2440", fBg: "#243157" },
  D: { pBg: "#1a1f2b", pFg: "#ffffff", pBd: "#2a3140", cap: "#0b0e13", fBg: "#11151d" },
};
const theme = (k, t) => {
  const c = TH[k], o = { duration: XF, ease: "sine.inOut" }, s = t - XF / 2;
  tl.to("#plateBox", { backgroundColor: c.pBg, color: c.pFg, borderColor: c.pBd, ...o }, s);
  tl.to("#capbg", { backgroundColor: c.cap, ...o }, s);
  tl.to("#facePanel", { backgroundColor: c.fBg, ...o }, s);
};

/* ---------- frame layouts: the presenter box, the caption band and the scene camera move together ---------- */
const SPLIT_BOX = { left: 36, top: 1256, width: 1008, height: 632, borderRadius: 44, borderWidth: 2 };
const SPLIT_MEDIA = { left: -46, top: -593, width: 1100, height: 1956 };
const GEO = {
  split:   { box: SPLIT_BOX, media: SPLIT_MEDIA, boxO: 1, panel: 1, cap: 1060, capO: 1, cam: 0 },
  face:    { box: { left: 0, top: 0, width: 1080, height: 1920, borderRadius: 0, borderWidth: 0 }, media: { left: 0, top: 0, width: 1080, height: 1920 }, boxO: 1, panel: 0, cap: 1478, capO: 0.62, cam: 0 },
  graphic: { box: SPLIT_BOX, media: SPLIT_MEDIA, boxO: 0, panel: 0, cap: 1478, capO: 1, cam: 240 },
  circle:  { box: { left: 612, top: 1190, width: 280, height: 280, borderRadius: 140, borderWidth: 3 }, media: { left: -215, top: -372, width: 703, height: 1250 }, boxO: 1, panel: 0, cap: 1478, capO: 1, cam: 240 },
};
const mode = (name, t) => {
  const g = GEO[name], o = { duration: XF, ease: "power2.inOut" }, s = t - XF / 2;
  tl.to("#faceBox", { ...g.box, opacity: g.boxO, ...o }, s);
  tl.to("#faceMedia", { ...g.media, ...o }, s);
  tl.to("#facePanel", { opacity: g.panel, ...o }, s);
  tl.to("#capband", { y: g.cap - 1060, ...o }, s);
  tl.to("#capbg", { opacity: g.capO, ...o }, s);
  tl.to(".scene > .cam", { y: g.cam, ...o }, s);
  tl.to("#faceTag", { opacity: name === "circle" ? 0 : 1, ...o }, s);
};
MODES.forEach(([t, name]) => mode(name, t));

/* ---------- motion helpers ---------- */
const cam = (id) => id + " > .cam";
// slow push-in for the whole scene, so a still frame never looks frozen
const drift = (id, t0, t1, to = 1.025) => tl.fromTo(cam(id), { scale: 1 }, { scale: to, duration: t1 - t0, ease: "sine.inOut" }, t0);
const rise = (sel, t, d = 0.6, y = 24, st = 0) => tl.fromTo(sel, { opacity: 0, y, scale: 0.96 }, { opacity: 1, y: 0, scale: 1, duration: d, ease: "power3.out", stagger: st }, t);
const xfade = (a, b, t, m = "fade") => {
  const s = t - XF / 2;
  if (m === "rise") tl.fromTo(b, { autoAlpha: 0, y: 40 }, { autoAlpha: 1, y: 0, duration: XF, ease: "power2.out", immediateRender: false }, s);
  else tl.fromTo(b, { autoAlpha: 0, scale: 1.02 }, { autoAlpha: 1, scale: 1, duration: XF, ease: "sine.inOut", immediateRender: false }, s);
  tl.set(a, { autoAlpha: 0 }, s + XF);
};
const tick = (sel, t) => tl.fromTo(sel, { opacity: 0, scale: 0.6 }, { opacity: 1, scale: 1, duration: 0.35, ease: "back.out(1.6)" }, t);
const lit = (sel, t, c = "rgba(111,214,160,0.7)") => tl.to(sel, { borderColor: c, backgroundColor: "rgba(111,214,160,0.10)", duration: 0.35, ease: "sine.out" }, t);

/* ---------- two-tier captions ---------- */
const capHTML = (txt) => {
  const m = txt.match(/^(.*?)([*_])(.+?)\2(.*)$/);
  if (!m) return '<div class="capIn"><div class="t-m">' + txt + "</div></div>";
  const pre = m[1].trim(), red = m[2] === "_";
  let key = m[3], post = m[4].trim();
  if (/^[.,!?…—-]*$/.test(post)) { key += post; post = ""; }
  const tiers = 1 + (pre ? 1 : 0) + (post ? 1 : 0);
  const max = tiers === 3 ? 80 : 100;
  const size = Math.max(56, Math.min(max, Math.floor(845 / (key.length * 0.6))));   // key word width stays under ~820 px (fits x 50-895)
  return '<div class="capIn">' + (pre ? '<div class="t-s">' + pre + "</div>" : "") +
         '<div class="t-b' + (red ? " red" : "") + '" style="font-size:' + size + 'px">' + key + "</div>" +
         (post ? '<div class="t-s">' + post + "</div>" : "") + "</div>";
};
const capEls = CAPTIONS.map(([, txt]) => { const el = document.createElement("div"); el.className = "cap"; el.innerHTML = capHTML(txt); $("#capband").appendChild(el); return el; });
CAPTIONS.forEach(([t, txt], i) => {
  if (!txt) return;
  const el = capEls[i], end = i + 1 < CAPTIONS.length ? CAPTIONS[i + 1][0] : DURATION;
  tl.fromTo(el, { opacity: 0, y: 8 }, { opacity: 1, y: 0, duration: 0.15, ease: "power2.out" }, t);
  tl.set(el, { opacity: 0 }, end);
});

/* ================= 1 · L · title and chips (0-3.2, split) ================= */
{
  tl.fromTo("#s1Tile", { opacity: 0, scale: 0.85 }, { opacity: 1, scale: 1, duration: 0.5, ease: "power3.out" }, 0.1);
  rise("#s1Head .w", 0.25, 0.5, 24, 0.6);
  rise(["#s1c1", "#s1c2", "#s1c3"], 1.3, 0.5, 24, 0.15);
  drift("#sc1", 0, T.s2 + XF / 2);
}

/* ================= 2 · D · incoming call -> missed (3.2-6.6, graphic) ================= */
xfade("#sc1", "#sc2", T.s2); theme("D", T.s2);
{
  const t0 = T.s2;
  rise("#s2Front", 3.4, 0.6, 40);
  rise("#s2Src", 3.9, 0.5, 20);
  rise("#s2Time", 4.1, 0.5, 20);
  ["#rg1", "#rg2", "#rg3"].forEach((r, k) => tl.fromTo(r, { scale: 1, opacity: 0.7 }, { scale: 1.7, opacity: 0, duration: 1.0, ease: "sine.out", repeat: 1 }, 3.55 + k * 0.35));
  tl.fromTo(".cbtn.g", { boxShadow: "0 0 0 0px rgba(47,163,107,0.5)" }, { boxShadow: "0 0 0 22px rgba(47,163,107,0)", duration: 0.9, ease: "sine.out", repeat: 1 }, 3.65);
  // 3D flip: the front turns away, the back turns in
  tl.to("#s2Front", { rotationY: 90, transformPerspective: 1600, duration: 0.3, ease: "power2.in" }, T.flip - 0.3);
  tl.set("#s2Front", { autoAlpha: 0 }, T.flip);
  tl.set("#s2Back", { autoAlpha: 1 }, T.flip);
  tl.fromTo("#s2Back", { rotationY: -90, transformPerspective: 1600 }, { rotationY: 0, duration: 0.4, ease: "power2.out" }, T.flip);
  rise("#s2Miss", 5.05, 0.45, 14);
  tl.to("#s2Time", { color: "#ff8a8f", duration: 0.5, ease: "sine.inOut" }, T.flip + 0.1);
  drift("#sc2", t0 - XF / 2, T.s3 + XF / 2);
}

/* ================= 3 · B · one of five (6.6-9.6, graphic) ================= */
xfade("#sc2", "#sc3", T.s3, "rise"); theme("B", T.s3);
{
  const t0 = T.s3;
  const tiles = [];
  for (let i = 0; i < 20; i++) { const d = document.createElement("div"); d.className = "lead"; d.innerHTML = '<svg class="ic"><use href="#i-user" /></svg><span class="x"><svg class="ic"><use href="#i-x" /></svg></span>'; $("#s3Grid").appendChild(d); tiles.push(d); }
  rise("#s3Head .w", t0 + 0.05, 0.5, 20, 0.1);
  tl.fromTo(tiles, { opacity: 0, scale: 0.85 }, { opacity: 1, scale: 1, duration: 0.4, ease: "power2.out", stagger: 0.02 }, t0 + 0.15);
  rise("#s3Ex", t0 + 0.45, 0.45, 12);
  tl.fromTo("#s3Count", { opacity: 0, scale: 0.9 }, { opacity: 1, scale: 1, duration: 0.5, ease: "power3.out" }, 7.7);   // "every fifth"
  [4, 9, 14, 19].forEach((i, k) => {
    const t = 7.8 + k * 0.12, d = tiles[i];
    tl.to(d, { backgroundColor: "rgba(229,72,77,0.25)", borderColor: "rgba(255,138,143,0.9)", color: "#ffb4b7", duration: 0.35 }, t);
    tl.fromTo(d.querySelector(".x"), { opacity: 0, scale: 0.6 }, { opacity: 1, scale: 1, duration: 0.3, ease: "power2.out" }, t);
  });
  rise("#s3Card", 8.7, 0.6, 40);   // "card"
  tl.to("#s3Card", { scale: 1.02, duration: 0.35, ease: "sine.inOut", yoyo: true, repeat: 1 }, 9.1);
  drift("#sc3", t0 - XF / 2, T.s4 + XF / 2);
}

/* ================= 4 · D · counter (9.6-11.8, graphic) ================= */
const ARC0 = 9.95, ARC_D = 0.7;   // the counter goes 0 -> 5 and lands on the word "five"
xfade("#sc3", "#sc4", T.s4, "rise"); theme("D", T.s4);
{
  const t0 = T.s4;
  rise("#s4Title", t0 + 0.05, 0.5, 20);
  tl.fromTo(["#s4Watch", "#s4Num"], { opacity: 0, scale: 0.94 }, { opacity: 1, scale: 1, duration: 0.5, ease: "power2.out" }, t0 + 0.15);
  const C = 2 * Math.PI * 236; $("#s4Arc").style.strokeDasharray = C;
  tl.fromTo("#s4Arc", { strokeDashoffset: C }, { strokeDashoffset: 0, duration: ARC_D, ease: "power1.inOut" }, ARC0);
  tl.fromTo("#s4Dig", { scale: 1 }, { scale: 1.06, duration: 0.2, ease: "sine.out", yoyo: true, repeat: 1 }, ARC0 + ARC_D);
  rise("#s4Sub", 10.9, 0.45, 14);
  drift("#sc4", t0 - XF / 2, T.s5 + XF / 2);
}

/* ================= 5 · B · path of nodes (11.8-14.6, presenter in a circle) ================= */
xfade("#sc4", "#sc5", T.s5); theme("B", T.s5);
{
  const t0 = T.s5;
  rise("#s5Title", t0 + 0.05, 0.5, 20);
  // a line segment between two nodes, drawn with stroke-dashoffset
  const seg = (y1, y2, t, c = "rgba(111,214,160,0.8)") => {
    const p = document.createElementNS(NS, "path"); p.setAttribute("d", "M192 " + y1 + " V" + y2); p.setAttribute("stroke", c); p.setAttribute("stroke-width", 4); p.setAttribute("stroke-linecap", "round"); p.setAttribute("fill", "none");
    $("#s5Line").appendChild(p); const L = y2 - y1; p.style.strokeDasharray = L; tl.fromTo(p, { strokeDashoffset: L }, { strokeDashoffset: 0, duration: 0.3, ease: "power2.out" }, t);
  };
  rise("#n1", 11.9, 0.45, 16); lit("#n1", 12.05); tick("#n1 .okc", 12.05);
  seg(368, 388, 12.15);
  rise("#n2", 12.05, 0.45, 16); lit("#n2", 12.2); tick("#n2 .okc", 12.2);
  seg(506, 526, 12.3);
  rise("#n3", 12.15, 0.45, 16);
  rise("#q1", 12.25, 0.35, 8); rise("#q2", 12.6, 0.35, 8); rise("#q3", 12.95, 0.35, 8);
  rise(["#n4", "#n5"], 12.7, 0.45, 16, 0.15);
  tl.set(["#n4", "#n5"], { opacity: 0.55 }, 13.3);
  lit("#n3", 13.4); tick("#n3 .okc", 13.43);
  seg(644, 664, 13.6, "rgba(255,255,255,0.35)");
  drift("#sc5", t0 - XF / 2, T.s6 + XF / 2);
}

/* ================= 6 · L · call to action (14.6-17, split) ================= */
xfade("#sc5", "#sc6", T.s6); theme("L", T.s6);
{
  const t0 = T.s6;
  tl.fromTo("#s6Icon", { opacity: 0, scale: 0.85 }, { opacity: 1, scale: 1, duration: 0.5, ease: "power3.out" }, t0);
  rise("#s6Pill", t0 + 0.1, 0.6, 40);
  rise("#s6Sub .w", 15.2, 0.5, 20, 0.8);
  [15.6, 16.4].forEach((t) => tl.fromTo("#s6Ring", { opacity: 0.8, scaleX: 1, scaleY: 1 }, { opacity: 0, scaleX: 1.04, scaleY: 1.2, duration: 0.9, ease: "power2.out", immediateRender: false }, t));
  drift("#sc6", t0 - XF / 2, DURATION);
}

/* ---------- clock and counter: pure functions of timeline time (seek-safe) ---------- */
const ticker = { v: 0 };
tl.fromTo(ticker, { v: 0 }, { v: 1, duration: DURATION, ease: "none", onUpdate: () => {
  const t = tl.time();
  if (t >= T.s2 - 0.3 && t < T.s3 + 0.5) {
    // after the flip the clock runs from 20:40 to 21:30
    const k = gsap.parseEase("power1.inOut")(clamp((t - T.flip - 0.3) / 0.9));
    const mins = 40 + Math.round(k * 50);
    const s = pad(20 + Math.floor(mins / 60)) + ":" + pad(mins % 60); const el = $("#s2Time"); if (el.textContent !== s) el.textContent = s;
  }
  if (t >= T.s4 - 0.3 && t < T.s5 + 0.5) {
    const s = String(Math.min(5, Math.floor(clamp((t - ARC0) / ARC_D) * 5 + 0.0001)));
    const el = $("#s4Dig"); if (el.textContent !== s) el.textContent = s;
  }
} }, 0);

// `tl` is registered by the inline script at the end of index.html,
// where the HyperFrames linter looks for the registration.
