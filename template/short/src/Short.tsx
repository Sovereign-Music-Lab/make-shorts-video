// Data-driven Korean fact Short: 1080x1920, 30 fps.
// - Narration timing comes from ../voice/lines.json (written by `mkshort voice`).
// - Scenes come from ../data/scenes.json (written by `mkshort write` or by hand / by an agent).
// - Audio is public/mix.wav (narration + music, written by `mkshort music`).
// Each scene starts 0.25 s before its narration line ("line" is 1-based) and lasts until the next scene.
// Layout rule: keep graphics above y = 1450. Captions sit at y 1490-1790, the source line at y 1860.
import React from "react";
import { AbsoluteFill, Audio, Easing, Img, Sequence, interpolate, staticFile, useCurrentFrame } from "remotion";
import timing from "../voice/lines.json";
import plan from "../data/scenes.json";
import { FONT, MONO, SERIF, THEMES, Theme } from "./theme";

export const W = 1080;
export const H = 1920;
export const FPS = 30;

type Line = { s: number; e: number; text: string };
type SceneData = { type: string; line: number; source?: string; [k: string]: unknown };
type Plan = { title?: string; theme?: string; captions?: boolean; scenes: SceneData[] };

const LINES = (timing as unknown as { lines: Line[] }).lines;
const TOTAL = (timing as unknown as { total: number }).total;
const PLAN = plan as unknown as Plan;
const TH: Theme = THEMES[PLAN.theme ?? "sacred"] ?? THEMES.sacred;
export const FRAMES = Math.max(30, Math.ceil(TOTAL * FPS));

const OVERLAP = 10; // crossfade frames between scenes
const CL = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const EASE = Easing.bezier(0.16, 1, 0.3, 1);
const rise = (f: number, a: number, d = 20) => interpolate(f, [a, a + d], [0, 1], { ...CL, easing: EASE });
const clamp01 = (v: number) => Math.max(0, Math.min(1, v));

// ---------- data helpers (scenes.json is loose JSON from an LLM, so read defensively) ----------
const str = (d: SceneData, k: string, def = "") => (typeof d[k] === "string" ? (d[k] as string) : typeof d[k] === "number" ? String(d[k]) : def);
const num = (d: SceneData, k: string, def = 0) => {
  const v = d[k];
  if (typeof v === "number") return v;
  if (typeof v === "string") {
    const n = Number(v.replace(/[^0-9.\-]/g, ""));
    return Number.isFinite(n) ? n : def;
  }
  return def;
};
const arr = <T,>(d: SceneData, k: string): T[] => (Array.isArray(d[k]) ? (d[k] as T[]) : []);
const commas = (n: number) => Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");

// Word-wrap Korean/English text to rows of at most `n` characters (breaks on spaces).
const wrap = (text: string, n: number): string[] => {
  const out: string[] = [];
  let cur = "";
  for (const w of text.split(/\s+/).filter(Boolean)) {
    const next = cur ? cur + " " + w : w;
    if (next.length > n && cur) {
      out.push(cur);
      cur = w;
    } else cur = next;
  }
  if (cur) out.push(cur);
  return out;
};

// ---------- shared pieces ----------
const Svg: React.FC<{ children: React.ReactNode; style?: React.CSSProperties }> = ({ children, style }) => (
  <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} style={{ position: "absolute", left: 0, top: 0, ...style }}>
    {children}
  </svg>
);

const T: React.FC<{
  x: number; y: number; size: number; children: React.ReactNode; color?: string; o?: number; weight?: number;
  font?: string; anchor?: "start" | "middle" | "end";
}> = ({ x, y, size, children, color = TH.text, o = 1, weight = 800, font = FONT, anchor = "middle" }) => (
  <text x={x} y={y} fontSize={size} fill={color} opacity={o} fontWeight={weight} fontFamily={font} textAnchor={anchor}>
    {children}
  </text>
);

const Background: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <Svg>
      <defs>
        <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={TH.bgTop} />
          <stop offset="1" stopColor={TH.bgBottom} />
        </linearGradient>
        <radialGradient id="glow" cx="50%" cy="50%" r="50%">
          <stop offset="0" stopColor={TH.accent} stopOpacity="0.35" />
          <stop offset="1" stopColor={TH.accent} stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width={W} height={H} fill="url(#bg)" />
      {TH.bg === "rays" && (
        <g transform={`translate(${W / 2} ${H * 0.4}) rotate(${f * 0.1})`} opacity={0.07}>
          {Array.from({ length: 12 }, (_, i) => (
            <polygon key={i} points="0,0 -45,-1200 45,-1200" fill={TH.accent} transform={`rotate(${i * 30})`} />
          ))}
        </g>
      )}
      {TH.bg === "grid" && (
        <g opacity={0.09}>
          {Array.from({ length: 21 }, (_, i) => (
            <line key={"v" + i} x1={i * 54} y1={0} x2={i * 54} y2={H} stroke={TH.accent} strokeWidth={1} />
          ))}
          {Array.from({ length: 38 }, (_, i) => (
            <line key={"h" + i} x1={0} y1={i * 54 + ((f * 0.5) % 54)} x2={W} y2={i * 54 + ((f * 0.5) % 54)} stroke={TH.accent} strokeWidth={1} />
          ))}
        </g>
      )}
      {(TH.bg === "rays" || TH.bg === "dots") &&
        Array.from({ length: 60 }, (_, i) => {
          const sp = 0.5 + ((i * 13) % 7) * 0.12;
          return (
            <circle key={i} cx={(i * 379) % W} cy={H + 100 - ((f * sp + i * 97) % (H + 200))} r={1 + (i % 3) * 0.9}
              fill={TH.accent} opacity={0.2 + (i % 4) * 0.1} />
          );
        })}
      <circle cx={W / 2} cy={H * 0.4} r={520 + 25 * Math.sin(f / 30)} fill="url(#glow)" />
    </Svg>
  );
};

// Icons for title / ending scenes
const Icon: React.FC<{ kind: string; f: number; cx: number; cy: number }> = ({ kind, f, cx, cy }) => {
  if (kind === "temple") {
    const cols = [-270, -162, -54, 54, 162, 270];
    return (
      <g transform={`translate(${cx} ${cy}) scale(0.7)`}>
        <circle cx={0} cy={-640} r={58} fill={TH.accent} opacity={0.5 * rise(f, 40, 30)} />
        <polygon points="-300,-420 0,-560 300,-420" fill={TH.text} opacity={rise(f, 40, 22)} />
        <rect x={-300} y={-420} width={600} height={40} fill={TH.accent} opacity={rise(f, 36, 20)} />
        {cols.map((x, i) => {
          const p = rise(f, i * 5, 26);
          return <rect key={i} x={x - 20} y={-380 * p} width={40} height={380 * p} fill={TH.accent} />;
        })}
        <rect x={-340} y={0} width={680} height={22} fill={TH.accent} opacity={rise(f, 36, 20)} />
      </g>
    );
  }
  if (kind === "star") {
    const p = rise(f, 0, 30);
    const pts = Array.from({ length: 10 }, (_, i) => {
      const r = i % 2 === 0 ? 150 : 62;
      const a = (Math.PI / 5) * i - Math.PI / 2;
      return `${cx + r * p * Math.cos(a)},${cy - 250 + r * p * Math.sin(a)}`;
    }).join(" ");
    return <polygon points={pts} fill={TH.accent} transform={`rotate(${f * 0.3} ${cx} ${cy - 250})`} />;
  }
  if (kind === "globe") {
    const p = rise(f, 0, 30);
    return (
      <g transform={`translate(${cx} ${cy - 250})`} opacity={p} fill="none" stroke={TH.accent} strokeWidth={6}>
        <circle r={150} />
        <ellipse rx={150 * Math.abs(Math.cos(f / 40))} ry={150} />
        <line x1={-150} y1={0} x2={150} y2={0} />
        <ellipse rx={150} ry={55} />
      </g>
    );
  }
  return null;
};

type SP = { f: number; dur: number; d: SceneData };

// ---------- scene types ----------
const TitleScene: React.FC<SP> = ({ f, d }) => {
  const rows = wrap(str(d, "title"), 8);
  const icon = str(d, "icon", "none");
  const y0 = icon !== "none" ? 920 : 760;
  return (
    <Svg>
      <Icon kind={icon} f={f} cx={W / 2} cy={600} />
      <T x={W / 2} y={y0 - 140} size={46} color={TH.accent} o={rise(f, 6)}>{str(d, "kicker")}</T>
      {rows.map((r, i) => (
        <T key={i} x={W / 2} y={y0 + i * 150} size={136} weight={900} o={rise(f, 12 + i * 6)}>{r}</T>
      ))}
      <T x={W / 2} y={y0 + rows.length * 150 + 30} size={50} color={TH.muted} o={rise(f, 30)}>{str(d, "subtitle")}</T>
    </Svg>
  );
};

const PersonScene: React.FC<SP> = ({ f, d }) => {
  const bar = rise(f, 14, 30);
  return (
    <Svg>
      <T x={W / 2} y={700} size={46} color={TH.accent} o={rise(f, 0)}>{str(d, "role")}</T>
      <T x={W / 2} y={850} size={110} weight={900} o={rise(f, 6)}>{str(d, "name")}</T>
      <rect x={W / 2 - 260 * bar} y={920} width={520 * bar} height={5} fill={TH.accent} />
      <T x={W / 2} y={1060} size={88} font={SERIF} color={TH.accent} o={rise(f, 24)}>{str(d, "years")}</T>
      <T x={W / 2} y={1170} size={46} color={TH.muted} o={rise(f, 34)}>{str(d, "note")}</T>
    </Svg>
  );
};

const TimelineScene: React.FC<SP> = ({ f, dur, d }) => {
  const pts = arr<{ year?: string | number; label?: string }>(d, "points").slice(0, 5);
  const n = Math.max(1, pts.length);
  const top = 520;
  const gap = Math.min(220, 820 / n);
  const line = rise(f, 0, 30);
  return (
    <Svg>
      <T x={W / 2} y={420} size={52} color={TH.muted} o={rise(f, 0)}>{str(d, "title")}</T>
      <line x1={220} y1={top} x2={220} y2={top + (gap * (n - 1) + 40) * line} stroke={TH.accent} strokeWidth={6} />
      {pts.map((p, i) => {
        const o = rise(f, 8 + (i * Math.max(20, dur * 0.6)) / n, 16);
        const y = top + i * gap;
        return (
          <g key={i} opacity={o}>
            <circle cx={220} cy={y} r={22} fill={TH.accent} />
            <T x={280} y={y + 22} size={64} font={SERIF} color={TH.accent} anchor="start">{String(p.year ?? "")}</T>
            <T x={280} y={y + 92} size={46} anchor="start">{String(p.label ?? "")}</T>
          </g>
        );
      })}
    </Svg>
  );
};

const NumberScene: React.FC<SP> = ({ f, dur, d }) => {
  const target = num(d, "value");
  const p = interpolate(f, [4, Math.min(dur - 10, 70)], [0, 1], { ...CL, easing: Easing.out(Easing.cubic) });
  const isInt = Number.isInteger(target);
  const shown = isInt ? commas(target * p) : (target * p).toFixed(1);
  return (
    <Svg>
      <T x={W / 2} y={640} size={50} color={TH.muted} o={rise(f, 0)}>{str(d, "kicker")}</T>
      <T x={W / 2} y={880} size={190} font={SERIF} color={TH.accent} weight={700}>{str(d, "prefix") + shown + str(d, "suffix")}</T>
      {wrap(str(d, "label"), 14).map((r, i) => (
        <T key={i} x={W / 2} y={1040 + i * 72} size={60} o={rise(f, 40)}>{r}</T>
      ))}
    </Svg>
  );
};

const StatementScene: React.FC<SP> = ({ f, d }) => {
  const rows = wrap(str(d, "text"), 10);
  const y0 = 860 - (rows.length - 1) * 60;
  return (
    <Svg>
      <T x={W / 2} y={y0 - 170} size={130} font={SERIF} color={TH.accent} o={rise(f, 0) * 0.6}>“</T>
      {rows.map((r, i) => (
        <T key={i} x={W / 2} y={y0 + i * 120} size={96} weight={900} o={rise(f, 6 + i * 5)}>{r}</T>
      ))}
      <T x={W / 2} y={y0 + rows.length * 120 + 50} size={48} color={TH.muted} o={rise(f, 30)}>{str(d, "sub")}</T>
    </Svg>
  );
};

const ChipsScene: React.FC<SP> = ({ f, dur, d }) => {
  const items = arr<string>(d, "items").map(String).slice(0, 6);
  const n = Math.max(1, items.length);
  return (
    <Svg>
      <T x={W / 2} y={520} size={60} weight={900} o={rise(f, 0)}>{str(d, "title")}</T>
      {items.map((t, i) => {
        const o = rise(f, 8 + (i * Math.max(16, dur * 0.55)) / n, 14);
        const y = 620 + i * 130;
        const w = Math.min(900, 120 + t.length * 44);
        return (
          <g key={i} opacity={o} transform={`translate(0 ${(1 - o) * 20})`}>
            <rect x={W / 2 - w / 2} y={y} width={w} height={96} rx={48} fill="none" stroke={TH.accent} strokeWidth={4} />
            <T x={W / 2} y={y + 64} size={46} color={TH.accent}>{t}</T>
          </g>
        );
      })}
    </Svg>
  );
};

const CompareScene: React.FC<SP> = ({ f, d }) => {
  const L = (d.left ?? {}) as Record<string, unknown>;
  const R = (d.right ?? {}) as Record<string, unknown>;
  const panel = (x: number, side: Record<string, unknown>, o: number) => (
    <g opacity={o}>
      <rect x={x} y={560} width={440} height={680} rx={28} fill={TH.panel} stroke={TH.accent} strokeOpacity={0.5} strokeWidth={3} />
      <T x={x + 220} y={680} size={64} weight={900} color={TH.accent}>{String(side.title ?? "")}</T>
      {wrap(String(side.text ?? ""), 8).slice(0, 6).map((r, i) => (
        <T key={i} x={x + 220} y={800 + i * 70} size={46}>{r}</T>
      ))}
    </g>
  );
  return (
    <Svg>
      <T x={W / 2} y={460} size={56} weight={900} o={rise(f, 0)}>{str(d, "title")}</T>
      {panel(80, L, rise(f, 6))}
      {panel(560, R, rise(f, 24))}
      <circle cx={W / 2} cy={900} r={52} fill={TH.accent} opacity={rise(f, 16)} />
      <T x={W / 2} y={918} size={44} weight={900} color={TH.bgBottom} o={rise(f, 16)}>VS</T>
    </Svg>
  );
};

const CodeScene: React.FC<SP> = ({ f, d }) => {
  const code = str(d, "code");
  const n = Math.min(code.length, Math.floor(Math.max(0, f - 6) * 0.8));
  const blink = Math.floor(f / 15) % 2 === 0 ? 1 : 0;
  return (
    <AbsoluteFill>
      <div style={{
        position: "absolute", left: 90, top: 560, width: 900, minHeight: 420, boxSizing: "border-box", background: TH.panel,
        border: `3px solid ${TH.accent}88`, borderRadius: 28, padding: 44, fontFamily: MONO, fontSize: 44, lineHeight: 1.45,
        color: TH.text, whiteSpace: "pre-wrap",
      }}>
        {code.slice(0, n)}
        <span style={{ opacity: blink, color: TH.accent }}>█</span>
      </div>
      <Svg>
        <T x={W / 2} y={1200} size={50} color={TH.accent} o={rise(f, 40)}>{str(d, "caption")}</T>
      </Svg>
    </AbsoluteFill>
  );
};

const ImageScene: React.FC<SP> = ({ f, dur, d }) => {
  const src = str(d, "src");
  const zoom = interpolate(f, [0, dur], [1, 1.08], CL);
  return (
    <AbsoluteFill>
      {src && (
        <div style={{ position: "absolute", left: 90, top: 380, width: 900, height: 900, overflow: "hidden", borderRadius: 28, border: `4px solid ${TH.accent}` }}>
          <Img src={staticFile(src)} style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${zoom})` }} />
        </div>
      )}
      <Svg>
        <T x={W / 2} y={1380} size={52} o={rise(f, 10)}>{str(d, "caption")}</T>
      </Svg>
    </AbsoluteFill>
  );
};

const EndingScene: React.FC<SP> = ({ f, d }) => {
  const g = rise(f, 0, 60);
  const icon = str(d, "icon", "none");
  return (
    <Svg>
      <circle cx={W / 2} cy={820} r={80 + 700 * g} fill={TH.accent} opacity={0.08 * g + 0.02} />
      <Icon kind={icon} f={f} cx={W / 2} cy={700} />
      {wrap(str(d, "title"), 9).map((r, i) => (
        <T key={i} x={W / 2} y={(icon !== "none" ? 900 : 820) + i * 140} size={124} weight={900} o={rise(f, 20 + i * 6)}>{r}</T>
      ))}
      <T x={W / 2} y={icon !== "none" ? 1200 : 1120} size={50} color={TH.accent} o={rise(f, 50)}>{str(d, "subtitle")}</T>
    </Svg>
  );
};

const SCENE_TYPES: Record<string, React.FC<SP>> = {
  title: TitleScene,
  person: PersonScene,
  timeline: TimelineScene,
  number: NumberScene,
  statement: StatementScene,
  chips: ChipsScene,
  compare: CompareScene,
  code: CodeScene,
  image: ImageScene,
  ending: EndingScene,
};

// ---------- captions + source line ----------
const Captions: React.FC = () => {
  const frame = useCurrentFrame();
  const t = frame / FPS;
  const line = LINES.find((l) => t >= l.s - 0.05 && t <= l.e + 0.1);
  if (!line) return null;
  const o = clamp01((t - line.s) / 0.15) * clamp01((line.e + 0.1 - t) / 0.15);
  // long lines get a smaller font so the whole sentence always fits (never truncate narration)
  let rows = wrap(line.text, 16);
  let size = 50;
  let lh = 66;
  if (rows.length > 3) {
    rows = wrap(line.text, 20);
    size = 42;
    lh = 56;
  }
  const boxH = rows.length * lh + 44;
  const top = Math.max(1470, 1640 - boxH / 2);
  return (
    <Svg style={{ opacity: o }}>
      <rect x={60} y={top} width={960} height={boxH} rx={24} fill="rgba(0,0,0,0.6)" />
      {rows.map((r, i) => (
        <T key={i} x={W / 2} y={top + 22 + size * 0.95 + i * lh} size={size} color="#ffffff">{r}</T>
      ))}
    </Svg>
  );
};

// ---------- scene timeline ----------
type Placed = { d: SceneData; from: number; to: number };
const placeScenes = (): Placed[] => {
  const nLines = LINES.length;
  const scenes: SceneData[] = (PLAN.scenes ?? [])
    .filter((s) => s && typeof s.type === "string")
    .map((s) => ({ ...s, line: Math.min(nLines, Math.max(1, Math.round(Number(s.line) || 1))) }))
    .sort((a, b) => a.line - b.line);
  if (scenes.length === 0 || scenes[0].line !== 1) scenes.unshift({ type: "title", line: 1, title: PLAN.title ?? "" });
  const starts = scenes.map((s, i) => (i === 0 ? 0 : Math.max(0, LINES[s.line - 1].s - 0.25)));
  return scenes
    .map((d, i) => ({ d, from: starts[i], to: i + 1 < scenes.length ? starts[i + 1] : TOTAL }))
    .filter((p) => p.to - p.from > 0.2);
};
const PLACED = placeScenes();

const SceneFrame: React.FC<{ p: Placed; i: number; len: number; pre: number }> = ({ p, i, len, pre }) => {
  const f = useCurrentFrame();
  const a = i > 0 ? clamp01(f / OVERLAP) : 1;
  const b = i < PLACED.length - 1 ? clamp01((len - f) / OVERLAP) : clamp01((len - f) / 20);
  const C = SCENE_TYPES[p.d.type] ?? StatementScene;
  return (
    <AbsoluteFill style={{ opacity: Math.min(a, b) }}>
      <C f={Math.max(0, f - pre)} dur={len - pre} d={p.d} />
      {p.d.source ? (
        <Svg>
          <T x={W / 2} y={1868} size={30} weight={500} color={TH.muted}>{"출처: " + p.d.source}</T>
        </Svg>
      ) : null}
    </AbsoluteFill>
  );
};

export const Short: React.FC = () => (
  <AbsoluteFill style={{ background: TH.bgBottom }}>
    <Background />
    {PLACED.map((p, i) => {
      const pre = i > 0 ? OVERLAP : 0;
      const start = Math.round(p.from * FPS) - pre;
      const end = Math.min(FRAMES, Math.round(p.to * FPS) + (i < PLACED.length - 1 ? OVERLAP : 0));
      return (
        <Sequence key={i} from={start} durationInFrames={Math.max(1, end - start)}>
          <SceneFrame p={p} i={i} len={end - start} pre={pre} />
        </Sequence>
      );
    })}
    {PLAN.captions !== false && <Captions />}
    <Audio src={staticFile("mix.wav")} />
  </AbsoluteFill>
);
