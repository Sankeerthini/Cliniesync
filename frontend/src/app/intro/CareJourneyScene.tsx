// Scroll-driven intro on the sign-in page: "from population to person, through time".
//   1. a rotating 3D globe of 600 dots - one per mother in the (synthetic) registry, coloured by stage
//   2. scrolling zooms the camera into one mother's dot
//   3. her dot becomes a pregnancy clock: scrolling advances time (week 1 -> 40 -> birth -> PNC -> vaccines);
//      milestones light up and show which ClinieSync feature helps at that moment
// Canvas 2D (no WebGL dependency) + SVG; honours prefers-reduced-motion.
import { useEffect, useRef, useState } from "react";

const clamp = (v: number, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const seg = (p: number, a: number, b: number) => clamp((p - a) / (b - a));
const ease = (t: number) => t * t * (3 - 2 * t);
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

// stages in the synthetic cohort (220 antenatal, 44 delivered, 236 postnatal completed, 100 no recent contact)
export const STAGES = [
  { key: "antenatal", label: "Antenatal", color: [20, 163, 160], n: 220 },
  { key: "delivered", label: "Recently delivered", color: [235, 104, 52], n: 44 },
  { key: "postnatal", label: "Postnatal completed", color: [74, 140, 240], n: 236 },
  { key: "nocontact", label: "No recent contact", color: [237, 161, 0], n: 100 },
] as const;

interface Pt { x: number; y: number; z: number; s: number }
function makePoints(): { pts: Pt[]; links: [number, number][] } {
  const N = STAGES.reduce((a, s) => a + s.n, 0);
  const stage: number[] = [];
  STAGES.forEach((s, i) => { for (let k = 0; k < s.n; k++) stage.push(i); });
  let seed = 7;                                                   // deterministic shuffle
  const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  for (let i = stage.length - 1; i > 0; i--) { const j = Math.floor(rnd() * (i + 1)); [stage[i], stage[j]] = [stage[j], stage[i]]; }
  const pts: Pt[] = [];
  const g = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < N; i++) {                                   // Fibonacci sphere
    const y = 1 - (i / (N - 1)) * 2, r = Math.sqrt(1 - y * y), th = g * i;
    pts.push({ x: Math.cos(th) * r, y, z: Math.sin(th) * r, s: stage[i] });
  }
  const links: [number, number][] = [];                           // "linked records": nearby pairs
  for (let i = 0; i < N; i += 2) {
    for (let j = i + 1; j < Math.min(N, i + 40); j++) {
      const d = (pts[i].x - pts[j].x) ** 2 + (pts[i].y - pts[j].y) ** 2 + (pts[i].z - pts[j].z) ** 2;
      if (d < 0.012) { links.push([i, j]); break; }
    }
  }
  return { pts, links };
}

// the mother we zoom into: an antenatal dot near the equator
function pickSelected(pts: Pt[]) {
  let best = 0, bd = 9;
  pts.forEach((p, i) => { const d = Math.abs(p.y - 0.12) + Math.abs(p.z - 0.6) * 0.2; if (p.s === 0 && d < bd) { bd = d; best = i; } });
  return best;
}

// `avoid` is the hero copy: before the zoom, the globe sits in the free space beside it (wide screens) or below it
// (portrait), so it never overlaps the text whatever the screen size.
export function GlobeCanvas({ progress, reduce, avoid }: { progress: number; reduce: boolean; avoid?: React.RefObject<HTMLElement> }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const prog = useRef(progress);
  prog.current = progress;
  useEffect(() => {
    const cv = ref.current!; const ctx = cv.getContext("2d")!;
    const { pts, links } = makePoints();
    const sel = pickSelected(pts);
    const P = pts[sel];
    const tY = Math.atan2(-P.x, P.z);
    const z1 = -P.x * Math.sin(tY) + P.z * Math.cos(tY);
    const tX = Math.atan2(P.y, z1);
    const ptr = { x: 0, y: 0, tx: 0, ty: 0 };
    const onMove = (e: PointerEvent) => { ptr.tx = (e.clientX / window.innerWidth) * 2 - 1; ptr.ty = (e.clientY / window.innerHeight) * 2 - 1; };
    window.addEventListener("pointermove", onMove);
    let raf = 0, t0 = performance.now(), w = 0, h = 0;
    const home = { x: 0, y: 0, r: 0 };                             // globe position before the zoom
    const place = () => {
      const c = avoid?.current?.getBoundingClientRect(), k = cv.getBoundingClientRect();
      // content column, mirrors --wrap / --gutter in app.css
      const gutter = Math.min(40, Math.max(16, w * 0.04)), wrap = w >= 1600 ? 1320 : 1180;
      const right = Math.min(w - gutter, (w + wrap) / 2) - (w > 900 && w - (w + wrap) / 2 < 150 ? 130 : 0);  // leave room for the chapter dots
      if (!c || !c.width) { home.x = w / 2; home.y = h * 0.55; home.r = Math.min(w, h) * 0.3; return; }
      const side = right - (c.right - k.left), below = h - (c.bottom - k.top) - 76;               // 76: "scroll to explore" hint
      if (side >= 220) { home.x = c.right - k.left + side / 2; home.y = h * 0.52; home.r = Math.min(side * 0.42, h * 0.34, 400); }
      else { home.x = w / 2; home.r = Math.max(48, Math.min(w * 0.38, below * 0.44)); home.y = h - 76 - Math.max(below / 2, home.r + 8); }
    };
    const resize = () => {
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      w = cv.clientWidth; h = cv.clientHeight; cv.width = w * dpr; cv.height = h * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      place();
    };
    resize(); window.addEventListener("resize", resize);
    const ro = avoid?.current ? new ResizeObserver(place) : null;  // web fonts landing change the copy's height
    if (ro && avoid?.current) ro.observe(avoid.current);
    const proj: { X: number; Y: number; Z: number }[] = pts.map(() => ({ X: 0, Y: 0, Z: 0 }));

    const draw = (now: number) => {
      const p = prog.current;
      ptr.x += (ptr.tx - ptr.x) * 0.05; ptr.y += (ptr.ty - ptr.y) * 0.05;
      const zk = ease(seg(p, 0.2, 0.44));                        // zoom phase
      const fade = 1 - seg(p, 0.42, 0.5);                         // canvas hands over to the clock
      ctx.clearRect(0, 0, w, h);
      if (fade <= 0) { raf = requestAnimationFrame(draw); return; }
      const wide = w > 900;
      const cx = lerp(home.x, w * 0.5, zk);
      const cy = lerp(home.y, h * 0.5, zk);
      const auto = reduce ? 0.6 : (now - t0) * 0.00012 + p * 2.2;
      const ry0 = auto + ptr.x * 0.5;
      const tyNear = tY + 2 * Math.PI * Math.round((ry0 - tY) / (2 * Math.PI));
      const ry = lerp(ry0, tyNear, zk), rx = lerp(0.28 + ptr.y * 0.3, tX, zk);
      const base = Math.min(w, h) * (wide ? 0.34 : 0.3);
      const scale = lerp(home.r, base * 16, zk * zk);
      const cyR = Math.cos(ry), syR = Math.sin(ry), cxR = Math.cos(rx), sxR = Math.sin(rx);
      for (let i = 0; i < pts.length; i++) {
        const q = pts[i];
        const x1 = q.x * cyR + q.z * syR, z1_ = -q.x * syR + q.z * cyR;
        const y2 = q.y * cxR - z1_ * sxR, z2 = q.y * sxR + z1_ * cxR;
        const persp = 1 / (1.6 - z2 * 0.6 * (1 - zk * 0.4));
        proj[i].X = cx + x1 * scale * persp; proj[i].Y = cy - y2 * scale * persp; proj[i].Z = z2;
      }
      // links
      ctx.lineWidth = 1;
      for (const [a, b] of links) {
        const A = proj[a], B = proj[b]; if (A.Z < 0 || B.Z < 0) continue;
        ctx.strokeStyle = `rgba(15,124,128,${0.16 * fade * (1 - zk) * (A.Z + B.Z) / 2})`;
        ctx.beginPath(); ctx.moveTo(A.X, A.Y); ctx.lineTo(B.X, B.Y); ctx.stroke();
      }
      // dots, back to front
      const order = proj.map((_, i) => i).sort((a, b) => proj[a].Z - proj[b].Z);
      for (const i of order) {
        if (i === sel) continue;
        const Q = proj[i], depth = (Q.Z + 1) / 2;
        if (Q.X < -20 || Q.X > w + 20 || Q.Y < -20 || Q.Y > h + 20) continue;
        const [r, g, b] = STAGES[pts[i].s].color;
        const a = (0.18 + 0.82 * depth) * fade * (1 - zk * 0.75);
        const size = (1.3 + 2.6 * depth) * (1 + zk * 2.5);
        ctx.fillStyle = `rgba(${r},${g},${b},${a})`;
        ctx.beginPath(); ctx.arc(Q.X, Q.Y, size, 0, Math.PI * 2); ctx.fill();
      }
      // the selected mother: glows, then grows into the clock
      const S = proj[sel];
      const grow = ease(seg(p, 0.3, 0.46));
      const ringR = Math.min(0.78 * h, 0.92 * w, 0.72 * h * 660 / 600) / 660 * 200;
      const sx = lerp(S.X, w / 2, grow), sy = lerp(S.Y, h / 2, grow);
      const rad = lerp(5 + zk * 6, ringR, grow);
      const pulse = reduce ? 0 : (Math.sin(now / 420) + 1) / 2;
      const glow = ctx.createRadialGradient(sx, sy, 0, sx, sy, rad * 3.2);
      glow.addColorStop(0, `rgba(20,163,160,${0.35 * fade})`); glow.addColorStop(1, "rgba(20,163,160,0)");
      ctx.fillStyle = glow; ctx.beginPath(); ctx.arc(sx, sy, rad * 3.2, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = `rgba(255,255,255,${fade})`; ctx.beginPath(); ctx.arc(sx, sy, rad + 3 + pulse * 3 * (1 - grow), 0, Math.PI * 2); ctx.fill();
      const m = ease(seg(grow, 0.35, 1));                        // teal dot -> white clock face with a track
      ctx.fillStyle = `rgba(${lerp(15, 251, m)},${lerp(124, 253, m)},${lerp(128, 253, m)},${fade})`;
      ctx.beginPath(); ctx.arc(sx, sy, rad, 0, Math.PI * 2); ctx.fill();
      if (m > 0) {
        ctx.lineWidth = 14 * m; ctx.strokeStyle = `rgba(219,230,232,${fade * m})`;
        ctx.beginPath(); ctx.arc(sx, sy, rad, 0, Math.PI * 2); ctx.stroke();
        ctx.strokeStyle = `rgba(20,163,160,${fade * m})`; ctx.lineCap = "round";
        ctx.beginPath(); ctx.arc(sx, sy, rad, -Math.PI / 2, -Math.PI / 2 + 0.05); ctx.stroke();
      }
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => { cancelAnimationFrame(raf); ro?.disconnect(); window.removeEventListener("resize", resize); window.removeEventListener("pointermove", onMove); };
  }, [reduce, avoid]);
  return <canvas ref={ref} className="intro-canvas" aria-hidden="true" />;
}

// ---------------------------------------------------------------- the pregnancy clock (time phase)
// tau in [0, END]: 0-0.70 = pregnancy weeks 0-40, 0.70-0.95 = the first 14 weeks after birth (a gap keeps the
// end of the journey from landing on its start)
const PREG = 0.7, END = 0.95;
export const TAU_END = END;
const wk = (w: number) => (w / 40) * PREG;
const after = (w: number) => PREG + (w / 14) * (END - PREG);
export const MILESTONES = [
  { tau: wk(10), label: "Registration · ANC 1", pillar: "Journey", text: "Every visit, lab report and note is linked into one timeline - across clinics." },
  { tau: wk(20), label: "ANC 2 · anomaly scan", pillar: "Ask", text: "“Show her haemoglobin readings” - a cited answer in seconds, not a chart hunt." },
  { tau: wk(26), label: "ANC 3 · OGTT", pillar: "Monitor", text: "Results still awaited? Due visits and pending reports surface on their own." },
  { tau: wk(34), label: "ANC 4", pillar: "Monitor", text: "Missed a visit? A reminder is drafted in her language - sent only after approval." },
  { tau: wk(39), label: "Delivery", pillar: "Communicate", text: "A verified summary goes to the family in ಕನ್ನಡ, हिन्दी or বাংলা." },
  { tau: after(1), label: "PNC · day 3 & 7", pillar: "Monitor", text: "Postnatal contacts are tracked, so no mother slips through after discharge." },
  { tau: after(6), label: "PNC · day 42", pillar: "Journey", text: "Mother and baby stay on one shared record." },
  { tau: after(14), label: "Vaccines · 6-10-14 w", pillar: "Communicate", text: "Vaccination reminders for the baby, approved by a human." },
];

function polar(tau: number, r: number) {
  const a = -Math.PI / 2 + tau * Math.PI * 2;
  return { x: Math.cos(a) * r, y: Math.sin(a) * r, a };
}

export function PregnancyClock({ tau, visible }: { tau: number; visible: number }) {
  const R = 200;
  const preg = Math.min(tau, PREG), post = Math.max(0, tau - PREG);
  const active = [...MILESTONES].reverse().find(m => tau >= m.tau - 0.002);
  const week = Math.max(1, Math.round((Math.min(tau, PREG) / PREG) * 40));
  const weeksAfter = (post / (END - PREG)) * 14;
  const counter = tau < PREG ? { big: `Week ${week}`, small: "of pregnancy" }
    : weeksAfter < 1 ? { big: `Day ${Math.max(1, Math.round(weeksAfter * 7))}`, small: "after birth" }
    : { big: `Week ${Math.round(weeksAfter)}`, small: "after birth" };
  return (
    <div className="intro-clock" style={{ opacity: visible, transform: `scale(${lerp(0.92, 1, visible)})` }} aria-hidden={visible < 0.5}>
      <svg viewBox="-330 -300 660 600" className="clock-svg">
        <defs>
          <linearGradient id="clock-preg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#14a3a0" /><stop offset="1" stopColor="#1f5fd1" /></linearGradient>
        </defs>
        <circle r={R} fill="none" stroke="#dbe6e8" strokeWidth="14" />
        <circle r={R - 26} fill="rgba(255,255,255,.75)" />
        {/* elapsed time: pregnancy (teal->blue) then after birth (coral) */}
        <circle r={R} fill="none" stroke="url(#clock-preg)" strokeWidth="14" strokeLinecap="round" pathLength={1}
          strokeDasharray={`${preg} 1`} transform="rotate(-90)" />
        {post > 0 && <circle r={R} fill="none" stroke="#eb6834" strokeWidth="14" strokeLinecap="round" pathLength={1}
          strokeDasharray={`${post} 1`} strokeDashoffset={-PREG} transform="rotate(-90)" />}
        <text className="clock-start" x="0" y={-R - 30} textAnchor="middle">LMP · week 0</text>
        <line x1="0" y1={-R - 12} x2="0" y2={-R + 12} stroke="#0f7c80" strokeWidth="3" />
        {/* birth marker */}
        {(() => { const b = polar(PREG, R); return <g><line x1={b.x * 0.9} y1={b.y * 0.9} x2={b.x * 1.1} y2={b.y * 1.1} stroke="#c2410c" strokeWidth="3" /></g>; })()}
        {MILESTONES.map(m => {
          const pt = polar(m.tau, R), lit = tau >= m.tau - 0.002, lab = polar(m.tau, R + 34);
          const anchor = Math.abs(lab.x) < 30 ? "middle" : lab.x > 0 ? "start" : "end";
          return (
            <g key={m.label} className={`ms ${lit ? "lit" : ""} ${active === m ? "on" : ""}`}>
              <circle cx={pt.x} cy={pt.y} r={active === m ? 11 : 8} />
              <text x={lab.x} y={lab.y + 4} textAnchor={anchor}>{m.label}</text>
            </g>);
        })}
        <text className="clock-big" y="-6" textAnchor="middle">{counter.big}</text>
        <text className="clock-small" y="26" textAnchor="middle">{counter.small}</text>
        {active && <text className="clock-mlabel" y="70" textAnchor="middle">{active.label}</text>}
      </svg>
      <div className="clock-caption" key={active?.label}>
        {active ? <><span className={`pill-tag p-${active.pillar.toLowerCase()}`}>{active.pillar}</span><span>{active.text}</span></>
          : <span>Scroll to move through her pregnancy.</span>}
      </div>
    </div>
  );
}

// scroll progress (0..1) of a tall container whose child is position: sticky
export function useScrollProgress(ref: React.RefObject<HTMLElement>) {
  const [p, setP] = useState(0);
  useEffect(() => {
    let raf = 0;
    const update = () => {
      raf = 0; const el = ref.current; if (!el) return;
      const r = el.getBoundingClientRect(), span = r.height - window.innerHeight;
      setP(span > 0 ? clamp(-r.top / span) : 0);
    };
    const on = () => { if (!raf) raf = requestAnimationFrame(update); };
    update(); window.addEventListener("scroll", on, { passive: true }); window.addEventListener("resize", on);
    return () => { window.removeEventListener("scroll", on); window.removeEventListener("resize", on); if (raf) cancelAnimationFrame(raf); };
  }, [ref]);
  return p;
}

export { seg, ease };
