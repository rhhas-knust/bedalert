// Animated illustrations for the BedAlert video. Everything is drawn once as
// SVG and then posed for a given time t by the scene's update function, so
// every frame is deterministic (the renderer seeks frame by frame).

const NS = "http://www.w3.org/2000/svg";
const C = { navy: "#0B2545", ink: "#071a33", mint: "#8FE3C6", amber: "#E8A33D", coral: "#E15554", paper: "#F4F7FA", muted: "#9FB3C8", teal: "#0F6E6E" };

function E(tag, attrs = {}, parent = null) {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  if (parent) parent.appendChild(el);
  return el;
}
const cl = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const ez = p => { p = cl(p); return p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2; };  // ease in-out
const eo = p => 1 - Math.pow(1 - cl(p), 3);                                                         // ease out
const span = (t, a, b) => cl((t - a) / (b - a));
function rng(seed) { let s = seed; return () => (s = (s * 16807) % 2147483647) / 2147483647; }
function smooth(pts) {  // Catmull-Rom through points -> cubic bezier path
  let d = `M${pts[0][0]},${pts[0][1]}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2;
    d += ` C${p1[0] + (p2[0] - p0[0]) / 6},${p1[1] + (p2[1] - p0[1]) / 6} ${p2[0] - (p3[0] - p1[0]) / 6},${p2[1] - (p3[1] - p1[1]) / 6} ${p2[0]},${p2[1]}`;
  }
  return d;
}
function defs(svg) {
  const d = E("defs", {}, svg);
  d.innerHTML = `
    <radialGradient id="glowR"><stop offset="0" stop-color="#ff4d4d" stop-opacity=".9"/><stop offset="1" stop-color="#ff4d4d" stop-opacity="0"/></radialGradient>
    <radialGradient id="glowB"><stop offset="0" stop-color="#4da3ff" stop-opacity=".9"/><stop offset="1" stop-color="#4da3ff" stop-opacity="0"/></radialGradient>
    <radialGradient id="glowW"><stop offset="0" stop-color="#fff6d8" stop-opacity="1"/><stop offset="1" stop-color="#fff6d8" stop-opacity="0"/></radialGradient>
    <radialGradient id="lamp"><stop offset="0" stop-color="#ffd98a" stop-opacity=".55"/><stop offset="1" stop-color="#ffd98a" stop-opacity="0"/></radialGradient>
    <linearGradient id="beam" x1="0" x2="1"><stop offset="0" stop-color="#fff2c4" stop-opacity=".55"/><stop offset="1" stop-color="#fff2c4" stop-opacity="0"/></linearGradient>
    <linearGradient id="night" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#040d1c"/><stop offset="1" stop-color="#123a66"/></linearGradient>
    <radialGradient id="land" cx=".5" cy=".4" r=".8"><stop offset="0" stop-color="#15375f"/><stop offset="1" stop-color="#0a1f3b"/></radialGradient>`;
}

// ---------------------------------------------------------------- characters

function makePerson(parent, color = C.paper, s = 1) {
  const g = E("g", {}, parent);
  const st = { stroke: color, "stroke-width": 11, "stroke-linecap": "round", fill: "none" };
  const legL = E("line", { x1: 0, y1: -46, x2: 0, y2: 0, ...st }, g);
  const legR = E("line", { x1: 0, y1: -46, x2: 0, y2: 0, ...st }, g);
  const body = E("line", { x1: 0, y1: -46, x2: 0, y2: -96, ...st, "stroke-width": 13 }, g);
  const armL = E("line", { x1: 0, y1: -90, x2: 0, y2: -52, ...st, "stroke-width": 9 }, g);
  const armR = E("line", { x1: 0, y1: -90, x2: 0, y2: -52, ...st, "stroke-width": 9 }, g);
  const head = E("circle", { cx: 0, cy: -114, r: 15, fill: color }, g);
  return { g, legL, legR, body, armL, armR, head, s };
}
function posePerson(p, { x, y, phase = 0, walk = 0, rot = 0, kneel = 0, op = 1, reach = 0 }) {
  const sw = Math.sin(phase) * 28 * walk;
  const drop = 34 * kneel;
  p.g.setAttribute("transform", `translate(${x},${y}) scale(${p.s}) rotate(${rot} 0 -30)`);
  p.g.setAttribute("opacity", op);
  p.legL.setAttribute("transform", `translate(0,${drop}) rotate(${sw + 70 * kneel} 0 -46)`);
  p.legR.setAttribute("transform", `translate(0,${drop}) rotate(${-sw - 10 * kneel} 0 -46)`);
  for (const k of ["body", "armL", "armR", "head"]) p[k].setAttribute("transform", `translate(${18 * kneel},${drop})`);
  p.armL.setAttribute("transform", `translate(${18 * kneel},${drop}) rotate(${-sw * 0.8 - 70 * reach} 0 -90)`);
  p.armR.setAttribute("transform", `translate(${18 * kneel},${drop}) rotate(${sw * 0.8 - 55 * reach} 0 -90)`);
}

function makeCar(parent) {  // faces right
  const g = E("g", {}, parent);
  E("polygon", { points: "262,-52 640,-110 640,10 262,-30", fill: "url(#beam)" }, g);
  E("path", { d: "M8,-20 L8,-50 Q12,-60 40,-62 L80,-92 Q90,-98 110,-98 L178,-98 Q192,-98 202,-90 L232,-64 L258,-58 Q266,-56 266,-46 L266,-22 Q266,-16 258,-16 L14,-16 Q8,-16 8,-20 Z", fill: "#6f8199" }, g);
  E("path", { d: "M90,-88 L112,-88 L112,-64 L64,-64 Z M122,-88 L182,-88 L212,-64 L122,-64 Z", fill: "#1d2c40" }, g);
  E("rect", { x: 252, y: -54, width: 14, height: 8, rx: 3, fill: "#fff2c4" }, g);
  E("rect", { x: 8, y: -50, width: 8, height: 10, rx: 2, fill: C.coral }, g);
  const wheels = [55, 205].map(x => {
    const w = E("g", {}, g);
    E("circle", { cx: 0, cy: 0, r: 23, fill: "#0b1320" }, w);
    E("circle", { cx: 0, cy: 0, r: 11, fill: "#5b6b80" }, w);
    E("line", { x1: -11, y1: 0, x2: 11, y2: 0, stroke: "#0b1320", "stroke-width": 4 }, w);
    E("line", { x1: 0, y1: -11, x2: 0, y2: 11, stroke: "#0b1320", "stroke-width": 4 }, w);
    return { w, x };
  });
  const blur = [0, 1, 2].map(i => E("line", { x1: -40 - i * 30, y1: -40 - i * 18, x2: -160 - i * 40, y2: -40 - i * 18, stroke: "#9FB3C8", "stroke-width": 4, "stroke-linecap": "round" }, g));
  return { g, wheels, blur };
}
function poseCar(c, x, y, spin, speed) {
  c.g.setAttribute("transform", `translate(${x},${y})`);
  c.wheels.forEach(({ w, x: wx }) => w.setAttribute("transform", `translate(${wx},-16) rotate(${spin})`));
  c.blur.forEach(b => b.setAttribute("opacity", cl(speed) * 0.5));
}

function makeAmbulance(parent, faceLeft = true) {
  const outer = E("g", {}, parent);
  const g = E("g", { transform: faceLeft ? "" : "scale(-1,1)" }, outer);
  const glowR = E("circle", { cx: 112, cy: -160, r: 120, fill: "url(#glowR)" }, g);
  const glowB = E("circle", { cx: 150, cy: -160, r: 120, fill: "url(#glowB)" }, g);
  E("path", { d: "M4,-22 L4,-78 L36,-122 Q40,-126 50,-126 L96,-126 L96,-150 Q96,-156 102,-156 L318,-156 Q326,-156 326,-148 L326,-22 Z", fill: C.paper }, g);
  E("path", { d: "M14,-80 L42,-116 L86,-116 L86,-80 Z", fill: "#1d2c40" }, g);
  E("rect", { x: 4, y: -66, width: 322, height: 14, fill: C.coral }, g);
  E("path", { d: "M196,-136 h20 v20 h20 v20 h-20 v20 h-20 v-20 h-20 v-20 h20 Z", fill: C.coral, transform: "translate(8,10) scale(.85)" }, g);
  E("rect", { x: 104, y: -168, width: 56, height: 12, rx: 4, fill: "#2a3a50" }, g);
  const lR = E("rect", { x: 106, y: -170, width: 24, height: 12, rx: 4, fill: "#ff4d4d" }, g);
  const lB = E("rect", { x: 134, y: -170, width: 24, height: 12, rx: 4, fill: "#4da3ff" }, g);
  E("rect", { x: 4, y: -40, width: 10, height: 12, rx: 3, fill: "#fff2c4" }, g);
  const wheels = [64, 266].map(x => {
    const w = E("g", {}, g);
    E("circle", { cx: 0, cy: 0, r: 25, fill: "#0b1320" }, w);
    E("circle", { cx: 0, cy: 0, r: 12, fill: "#5b6b80" }, w);
    E("line", { x1: -12, y1: 0, x2: 12, y2: 0, stroke: "#0b1320", "stroke-width": 4 }, w);
    return { w, x };
  });
  return { outer, g, glowR, glowB, lR, lB, wheels, faceLeft };
}
function poseAmbulance(a, x, y, t, spin, lights = 1, scale = 1) {
  a.outer.setAttribute("transform", `translate(${x},${y}) scale(${scale})`);
  const on = Math.floor(t * 6) % 2 === 0;
  a.glowR.setAttribute("opacity", lights * (on ? 0.9 : 0.15));
  a.glowB.setAttribute("opacity", lights * (on ? 0.15 : 0.9));
  a.lR.setAttribute("opacity", lights ? (on ? 1 : 0.35) : 0.35);
  a.lB.setAttribute("opacity", lights ? (on ? 0.35 : 1) : 0.35);
  a.wheels.forEach(({ w, x: wx }) => w.setAttribute("transform", `translate(${wx},-20) rotate(${spin})`));
}

// ---------------------------------------------------------------- night street (Circle overpass)

function buildStreet(svg, { roadY = 760, skyline = true, overpass = true } = {}) {
  defs(svg);
  E("rect", { x: 0, y: 0, width: 1920, height: 1080, fill: "url(#night)" }, svg);
  const r = rng(7);
  for (let i = 0; i < 70; i++) E("circle", { cx: r() * 1920, cy: r() * 300, r: r() * 1.8 + 0.4, fill: "#cfe0ff", opacity: r() * 0.6 + 0.2 }, svg);
  if (skyline) {
    let x = -20;
    while (x < 1940) {
      const w = 60 + r() * 110, h = 140 + r() * 300, y = roadY - 120 - h;
      E("rect", { x, y, width: w, height: h + 10, fill: "#0b1d36" }, svg);
      for (let wy = y + 18; wy < roadY - 150; wy += 28) for (let wx = x + 12; wx < x + w - 14; wx += 24)
        if (r() < 0.32) E("rect", { x: wx, y: wy, width: 10, height: 14, fill: "#f6d38a", opacity: 0.25 + r() * 0.5 }, svg);
      x += w + 6;
    }
  }
  if (overpass) {
    for (const px of [180, 640, 1100, 1560]) E("rect", { x: px, y: roadY - 300, width: 46, height: 200, fill: "#14294a" }, svg);
    E("rect", { x: 0, y: roadY - 340, width: 1920, height: 46, fill: "#1b355c" }, svg);
    E("rect", { x: 0, y: roadY - 350, width: 1920, height: 10, fill: "#284a78" }, svg);
  }
  const lamps = [];
  for (const lx of [120, 620, 1120, 1620]) {
    E("rect", { x: lx, y: roadY - 330, width: 8, height: 230, fill: "#24395a" }, svg);
    E("rect", { x: lx, y: roadY - 334, width: 70, height: 8, fill: "#24395a" }, svg);
    lamps.push(E("circle", { cx: lx + 66, cy: roadY - 320, r: 120, fill: "url(#lamp)" }, svg));
  }
  E("rect", { x: 0, y: roadY - 100, width: 1920, height: 24, fill: "#2b3b52" }, svg);   // far kerb
  E("rect", { x: 0, y: roadY - 76, width: 1920, height: 200, fill: "#18222f" }, svg);   // road
  for (let x = 0; x < 1920; x += 140) E("rect", { x, y: roadY + 20, width: 80, height: 8, fill: "#c9d3dd", opacity: 0.6 }, svg);
  E("rect", { x: 0, y: roadY + 124, width: 1920, height: 300, fill: "#223146" }, svg);   // near pavement
  return { lamps };
}

// ---------------------------------------------------------------- maps

function hospitalMarker(parent, x, y, label, { small = false } = {}) {
  const g = E("g", { transform: `translate(${x},${y})` }, parent);
  const R = small ? 30 : 46;
  const ring = E("circle", { cx: 0, cy: 0, r: R + 14, fill: "none", stroke: C.amber, "stroke-width": 4, opacity: 0 }, g);
  const disc = E("circle", { cx: 0, cy: 0, r: R, fill: C.navy, stroke: C.mint, "stroke-width": 4 }, g);
  const k = R / 40;
  E("path", { d: `M${-8 * k},${-22 * k} h${16 * k} v${14 * k} h${14 * k} v${16 * k} h${-14 * k} v${14 * k} h${-16 * k} v${-14 * k} h${-14 * k} v${-16 * k} h${14 * k} Z`, fill: C.paper }, g);
  const text = E("text", { x: 0, y: R + 40, "text-anchor": "middle", fill: C.paper, "font-family": "Inter", "font-weight": 600, "font-size": small ? 24 : 30 }, g);
  text.textContent = label;
  const pill = E("g", { opacity: 0 }, g);
  const pillBg = E("rect", { x: -78, y: -R - 68, width: 156, height: 50, rx: 10, fill: C.coral }, pill);
  const pillTx = E("text", { x: 0, y: -R - 33, "text-anchor": "middle", fill: "#fff", "font-family": "Plex Mono", "font-weight": 700, "font-size": small ? 24 : 28 }, pill);
  return { g, ring, disc, pill, pillBg, pillTx, R };
}
function setMarker(m, { pill = null, color = C.coral, txColor = "#fff", pillP = 1, ring = 0, disc = null, pulse = 0 }) {
  if (pill) { m.pillTx.textContent = pill; m.pillBg.setAttribute("fill", color); m.pillTx.setAttribute("fill", txColor);
    const w = Math.max(120, pill.length * 18 + 40); m.pillBg.setAttribute("x", -w / 2); m.pillBg.setAttribute("width", w); }
  m.pill.setAttribute("opacity", pill ? pillP : 0);
  m.pill.setAttribute("transform", `scale(${pill ? 1 + 0.5 * (1 - eo(pillP)) : 1})`);
  m.ring.setAttribute("opacity", ring);
  m.ring.setAttribute("r", m.R + 14 + 10 * pulse);
  if (disc) m.disc.setAttribute("stroke", disc);
  m.disc.setAttribute("fill", disc === C.coral ? "#4a1d2a" : C.navy);
}

function makeTopAmbulance(parent) {
  const g = E("g", {}, parent);
  const halo = E("circle", { cx: 0, cy: 0, r: 46, fill: "url(#glowR)" }, g);
  const body = E("g", {}, g);
  E("rect", { x: -34, y: -18, width: 68, height: 36, rx: 9, fill: C.paper }, body);
  E("rect", { x: 14, y: -14, width: 14, height: 28, rx: 4, fill: "#1d2c40" }, body);
  E("path", { d: "M-18,-4 h20 v8 h-20 Z M-12,-10 h8 v20 h-8 Z", fill: C.coral }, body);
  const lr = E("rect", { x: 2, y: -16, width: 8, height: 14, rx: 2, fill: "#ff4d4d" }, body);
  const lb = E("rect", { x: 2, y: 2, width: 8, height: 14, rx: 2, fill: "#4da3ff" }, body);
  return { g, halo, body, lr, lb };
}
function poseTopAmbulance(a, x, y, ang, t, lights = 1) {
  a.g.setAttribute("transform", `translate(${x},${y})`);
  a.body.setAttribute("transform", `rotate(${ang})`);
  const on = Math.floor(t * 6) % 2 === 0;
  a.halo.setAttribute("fill", on ? "url(#glowR)" : "url(#glowB)");
  a.halo.setAttribute("opacity", 0.8 * lights);
  a.lr.setAttribute("opacity", on || !lights ? 1 : 0.3);
  a.lb.setAttribute("opacity", !on || !lights ? 1 : 0.3);
}

function buildMapBase(svg, w, h, seed = 3, coast = true) {
  defs(svg);
  E("rect", { x: 0, y: 0, width: w, height: h, fill: "url(#land)" }, svg);
  const r = rng(seed);
  const grid = E("g", { stroke: "#1d4170", "stroke-width": 3, opacity: 0.55 }, svg);
  for (let i = 0; i < 26; i++) { const y = r() * h; E("line", { x1: 0, y1: y, x2: w, y2: y + (r() - 0.5) * 240 }, grid); }
  for (let i = 0; i < 30; i++) { const x = r() * w; E("line", { x1: x, y1: 0, x2: x + (r() - 0.5) * 240, y2: h }, grid); }
  for (let i = 0; i < 90; i++) E("rect", { x: r() * w, y: r() * h, width: 18 + r() * 40, height: 14 + r() * 30, rx: 4, fill: "#173a63", opacity: 0.6 }, svg);
  let waves = [];
  if (coast) {
    E("path", { d: `M0,${h * 0.86} C${w * 0.18},${h * 0.8} ${w * 0.32},${h * 0.92} ${w * 0.5},${h * 0.86} S${w * 0.8},${h * 0.8} ${w},${h * 0.83} L${w},${h} L0,${h} Z`, fill: "#071629" }, svg);
    for (let i = 0; i < 3; i++) waves.push(E("path", { d: `M0,${h * (0.9 + i * 0.03)} C${w * 0.25},${h * (0.87 + i * 0.03)} ${w * 0.5},${h * (0.93 + i * 0.03)} ${w},${h * (0.89 + i * 0.03)}`, fill: "none", stroke: "#1d4170", "stroke-width": 3, "stroke-dasharray": "30 40" }, svg));
  }
  return { waves };
}
function routePath(parent, pts, { color = C.amber, width = 9, dash = null } = {}) {
  const d = smooth(pts);
  E("path", { d, fill: "none", stroke: "#2c5788", "stroke-width": width + 10, "stroke-linecap": "round", opacity: 0.6 }, parent);
  const p = E("path", { d, fill: "none", stroke: color, "stroke-width": width, "stroke-linecap": "round" }, parent);
  const len = p.getTotalLength();
  if (dash) p.setAttribute("stroke-dasharray", dash);
  else { p.setAttribute("stroke-dasharray", len); p.setAttribute("stroke-dashoffset", len); }
  return { p, len };
}
function along(route, prog) {
  const L = route.len * cl(prog);
  const a = route.p.getPointAtLength(L), b = route.p.getPointAtLength(Math.min(route.len, L + 2)), c = route.p.getPointAtLength(Math.max(0, L - 2));
  const ang = Math.atan2(b.y - c.y, b.x - c.x) * 180 / Math.PI;
  return { x: a.x, y: a.y, ang };
}
function drawRoute(route, prog) { route.p.setAttribute("stroke-dashoffset", route.len * (1 - cl(prog))); }


// ---------------------------------------------------------------- friendly cartoon avatars

function limb(parent, color, w) {
  const g = E("g", {}, parent);
  const upper = E("line", { x1: 0, y1: 0, x2: 0, y2: 62, stroke: color, "stroke-width": w, "stroke-linecap": "round" }, g);
  const lowG = E("g", { transform: "translate(0,62)" }, g);
  const lower = E("line", { x1: 0, y1: 0, x2: 0, y2: 58, stroke: color, "stroke-width": w * 0.9, "stroke-linecap": "round" }, lowG);
  return { g, upper, lowG, lower };
}
function makeAvatar(parent, o = {}) {
  const skin = o.skin || "#8d5524", shirt = o.shirt || "#2a9d8f", pants = o.pants || "#264653", hairC = o.hairColor || "#1b1b1b";
  const root = E("g", {}, parent);
  const body = E("g", {}, root);
  const legs = [-20, 20].map(x => {
    const g = E("g", { transform: `translate(${x},-128)` }, body);
    E("rect", { x: -15, y: 0, width: 30, height: 120, rx: 14, fill: o.skirt && x < 0 ? pants : pants }, g);
    E("ellipse", { cx: 6, cy: 124, rx: 22, ry: 11, fill: "#1a1a1a" }, g);
    return g;
  });
  if (o.skirt) E("path", { d: "M-52,-150 L52,-150 L64,-70 L-64,-70 Z", fill: o.skirt }, body);
  const armBack = limb(body, shirt, 26);
  armBack.g.setAttribute("transform", "translate(-46,-236)");
  const handBack = E("circle", { cx: 0, cy: 58, r: 13, fill: skin }, armBack.lowG);
  E("rect", { x: -52, y: -258, width: 104, height: 140, rx: 38, fill: shirt }, body);
  if (o.scrubs) E("rect", { x: -16, y: -250, width: 32, height: 26, rx: 6, fill: "#ffffff", opacity: 0.25 }, body);
  if (o.collar) E("path", { d: "M-22,-258 L0,-226 L22,-258 Z", fill: o.collar }, body);
  E("rect", { x: -12, y: -280, width: 24, height: 28, rx: 8, fill: skin }, body);
  const headG = E("g", { transform: "translate(0,-318)" }, body);
  if (o.hair === "wrap") { E("ellipse", { cx: 0, cy: -30, rx: 52, ry: 36, fill: o.wrap || "#e76f51" }, headG); E("circle", { cx: 34, cy: -54, r: 16, fill: o.wrap || "#e76f51" }, headG); }
  E("circle", { cx: 0, cy: 0, r: 44, fill: skin }, headG);
  E("ellipse", { cx: -44, cy: 4, rx: 8, ry: 12, fill: skin }, headG);
  E("ellipse", { cx: 44, cy: 4, rx: 8, ry: 12, fill: skin }, headG);
  if (o.hair === "short") E("path", { d: "M-44,-6 Q-46,-48 0,-50 Q46,-48 44,-6 Q36,-30 0,-32 Q-36,-30 -44,-6 Z", fill: hairC }, headG);
  if (o.hair === "wrap") E("path", { d: "M-46,-4 Q-48,-50 0,-52 Q48,-50 46,-4 Q30,-26 0,-28 Q-30,-26 -46,-4 Z", fill: o.wrap || "#e76f51" }, headG);
  if (o.hair === "cap") { E("path", { d: "M-44,-10 Q-42,-52 0,-52 Q42,-52 44,-10 Z", fill: o.capColor || "#e9c46a" }, headG); E("rect", { x: 10, y: -18, width: 50, height: 10, rx: 5, fill: o.capColor || "#e9c46a" }, headG); }
  if (o.hair === "nurse") { E("path", { d: "M-44,-6 Q-46,-48 0,-50 Q46,-48 44,-6 Q36,-30 0,-32 Q-36,-30 -44,-6 Z", fill: hairC }, headG);
    E("rect", { x: -30, y: -62, width: 60, height: 20, rx: 6, fill: "#fff" }, headG); E("path", { d: "M-5,-58 h10 v4 h4 v8 h-4 v4 h-10 v-4 h-4 v-8 h4 Z", fill: C.coral, transform: "translate(0,2) scale(.8)" }, headG); }
  if (o.beard) E("path", { d: "M-30,14 Q0,52 30,14 Q20,34 0,36 Q-20,34 -30,14 Z", fill: "#cfcfcf" }, headG);
  const eyes = [-15, 15].map(x => E("ellipse", { cx: x, cy: -2, rx: 5, ry: 6, fill: "#1a1a1a" }, headG));
  E("circle", { cx: -24, cy: 14, r: 7, fill: "#ff8f8f", opacity: 0.35 }, headG);
  E("circle", { cx: 24, cy: 14, r: 7, fill: "#ff8f8f", opacity: 0.35 }, headG);
  const mouth = E("path", { d: "M-12,16 Q0,24 12,16", fill: "none", stroke: "#3b1f12", "stroke-width": 4, "stroke-linecap": "round" }, headG);
  const armFront = limb(body, shirt, 26);
  armFront.g.setAttribute("transform", "translate(46,-236)");
  const handFront = E("circle", { cx: 0, cy: 58, r: 13, fill: skin }, armFront.lowG);
  let phone = null, screen = null;
  if (o.phone === "smart") {
    phone = E("g", { transform: "translate(0,52)" }, armFront.lowG);
    E("rect", { x: -16, y: -30, width: 32, height: 56, rx: 6, fill: "#111" }, phone);
    screen = E("rect", { x: -12, y: -25, width: 24, height: 44, rx: 3, fill: C.mint, opacity: 0.85 }, phone);
  } else if (o.phone === "feature") {
    phone = E("g", { transform: "translate(0,50)" }, armFront.lowG);
    E("rect", { x: -14, y: -32, width: 28, height: 58, rx: 8, fill: "#3a4a5f" }, phone);
    screen = E("rect", { x: -10, y: -27, width: 20, height: 18, rx: 2, fill: "#b9d3a6" }, phone);
    for (let r = 0; r < 3; r++) for (let c = 0; c < 3; c++) E("rect", { x: -9 + c * 7, y: -4 + r * 8, width: 5, height: 5, rx: 1, fill: "#9fb0c4" }, phone);
  }
  return { root, body, legs, armBack, armFront, headG, eyes, mouth, phone, screen };
}
function setLimb(l, a1, a2) { l.upper.setAttribute("transform", `rotate(${a1})`); l.lowG.setAttribute("transform", `rotate(${a1}) translate(0,62) rotate(${a2})`); }
function poseAvatar(a, { x, y, s = 1, walk = 0, phase = 0, front = [10, 0], back = [-10, 0], smile = 0.5, blink = false, lean = 0, op = 1, flip = false, head = 0 }) {
  const bob = walk ? Math.abs(Math.sin(phase)) * -6 : 0;
  a.root.setAttribute("transform", `translate(${x},${y + bob}) scale(${flip ? -s : s},${s}) rotate(${lean})`);
  a.root.setAttribute("opacity", op);
  const sw = Math.sin(phase) * 22 * walk;
  a.legs[0].setAttribute("transform", `translate(-20,-128) rotate(${sw})`);
  a.legs[1].setAttribute("transform", `translate(20,-128) rotate(${-sw})`);
  setLimb(a.armFront, front[0] - sw * 0.6, front[1]);
  setLimb(a.armBack, back[0] + sw * 0.6, back[1]);
  a.headG.setAttribute("transform", `translate(0,-318) rotate(${head})`);
  a.eyes.forEach(e => e.setAttribute("ry", blink ? 1 : 6));
  const m = 6 + 16 * smile;
  a.mouth.setAttribute("d", `M-14,16 Q0,${m + 10} 14,16`);
}

window.ANIM = { E, C, cl, ez, eo, span, rng, defs, makePerson, posePerson, makeCar, poseCar, makeAmbulance, poseAmbulance,
  buildStreet, hospitalMarker, setMarker, makeTopAmbulance, poseTopAmbulance, buildMapBase, routePath, along, drawRoute, makeAvatar, poseAvatar };
