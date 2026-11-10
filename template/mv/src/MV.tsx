// Music video: 1920x1080 (FHD landscape), 30 fps.
// - Song: public/song.wav.  Analysis (bpm, beats, energy/low/mid/high per frame): data/analysis.json (mkmv analyze).
// - Plan: data/mv.json  { title, artist, theme, credits[], lyrics[{t,end?,text}], sections[{start,end,kind,...}] }
// Section kinds: title | visualizer | pulse | lyrics | text | clip | credits
// "clip" plays a 1080p video from public/ (AI clip from `mkmv clips`, or your own footage), looped to fill the section.
import React from "react";
import { AbsoluteFill, Audio, Easing, Loop, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame } from "remotion";
import mvData from "../data/mv.json";
import analysis from "../data/analysis.json";

export const W = 1920;
export const H = 1080;
export const FPS = 30;

type Section = { start: number; end: number; kind: string; text?: string; sub?: string; clip?: string; clipSeconds?: number; prompt?: string };
type Lyric = { t: number; end?: number; text: string };
type Plan = { title?: string; artist?: string; theme?: string; credits?: string[]; lyrics?: Lyric[]; sections: Section[] };
type Analysis = { fps: number; duration: number; bpm: number; beats: number[]; downbeats: number[]; energy: number[]; low: number[]; mid: number[]; high: number[] };

const P = mvData as unknown as Plan;
const A = analysis as unknown as Analysis;
export const FRAMES = Math.max(30, Math.ceil(A.duration * FPS));

const THEMES: Record<string, { top: string; bottom: string; a: string; b: string; text: string }> = {
  neon: { top: "#12052e", bottom: "#000000", a: "#ff3df2", b: "#3df2ff", text: "#ffffff" },
  gold: { top: "#1b1638", bottom: "#05060c", a: "#e8c26a", b: "#fff1c9", text: "#f5ecd7" },
  mono: { top: "#151515", bottom: "#000000", a: "#ffffff", b: "#8a8a8a", text: "#ffffff" },
  sunset: { top: "#3a1f2b", bottom: "#120a10", a: "#ffb36b", b: "#ff5e7e", text: "#fff1e0" },
};
const TH = THEMES[P.theme ?? "neon"] ?? THEMES.neon;
const FONT = "'Apple SD Gothic Neo','Noto Sans KR','Noto Sans CJK KR','Helvetica Neue',sans-serif";

const CL = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const EASE = Easing.bezier(0.16, 1, 0.3, 1);
const rise = (f: number, a: number, d = 20) => interpolate(f, [a, a + d], [0, 1], { ...CL, easing: EASE });
const val = (arr: number[], f: number) => (arr.length ? arr[Math.min(arr.length - 1, Math.max(0, f))] : 0);

// time since the last beat in `list` before t (seconds), or a large number
const sinceLast = (list: number[], t: number) => {
  let lo = 0;
  let hi = list.length - 1;
  if (hi < 0 || t < list[0]) return 99;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (list[mid] <= t) lo = mid;
    else hi = mid - 1;
  }
  return t - list[lo];
};
const beatPulse = (t: number) => Math.exp(-sinceLast(A.beats, t) * 7);
const barPulse = (t: number) => Math.exp(-sinceLast(A.downbeats, t) * 4);

const Svg: React.FC<{ children: React.ReactNode; o?: number }> = ({ children, o = 1 }) => (
  <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} style={{ position: "absolute", left: 0, top: 0, opacity: o }}>
    {children}
  </svg>
);

const Background: React.FC = () => {
  const gf = useCurrentFrame();
  const low = val(A.low, gf);
  return (
    <Svg>
      <defs>
        <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={TH.top} />
          <stop offset="1" stopColor={TH.bottom} />
        </linearGradient>
        <radialGradient id="glow" cx="50%" cy="50%" r="50%">
          <stop offset="0" stopColor={TH.a} stopOpacity="0.35" />
          <stop offset="1" stopColor={TH.a} stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width={W} height={H} fill="url(#bg)" />
      <g opacity={0.06 + 0.08 * low} transform={`translate(0 ${(gf * 1.2) % 80})`}>
        {Array.from({ length: 16 }, (_, i) => (
          <line key={i} x1={0} y1={i * 80 - 80} x2={W} y2={i * 80 - 80} stroke={TH.b} strokeWidth={1} />
        ))}
      </g>
      <circle cx={W / 2} cy={H / 2} r={380 + 160 * low} fill="url(#glow)" />
    </Svg>
  );
};

type SP = { f: number; gf: number; dur: number; s: Section };

const TitleScene: React.FC<SP> = ({ f, gf }) => {
  const t = gf / FPS;
  const k = 1 + 0.025 * beatPulse(t);
  return (
    <Svg>
      <g transform={`translate(${W / 2} ${H / 2}) scale(${k})`}>
        <text y={-10} textAnchor="middle" fontFamily={FONT} fontWeight={900} fontSize={170} letterSpacing={12} fill={TH.text} opacity={rise(f, 6, 40)}>
          {P.title ?? ""}
        </text>
        <rect x={-360 * rise(f, 20, 40)} y={40} width={720 * rise(f, 20, 40)} height={4} fill={TH.a} />
        <text y={130} textAnchor="middle" fontFamily={FONT} fontWeight={700} fontSize={56} letterSpacing={8} fill={TH.a} opacity={rise(f, 34, 30)}>
          {P.artist ?? ""}
        </text>
      </g>
    </Svg>
  );
};

const VisualizerScene: React.FC<SP> = ({ f, gf }) => {
  const N = 64;
  const low = val(A.low, gf);
  const mid = val(A.mid, gf);
  const high = val(A.high, gf);
  const t = gf / FPS;
  const bw = (W - 240) / N;
  return (
    <Svg o={rise(f, 0, 12)}>
      <defs>
        <linearGradient id="bar" x1="0" y1="1" x2="0" y2="0">
          <stop offset="0" stopColor={TH.a} />
          <stop offset="1" stopColor={TH.b} />
        </linearGradient>
      </defs>
      {Array.from({ length: N }, (_, i) => {
        const x = i / (N - 1);
        const band = x < 0.33 ? low * (1 - x / 0.33) + mid * (x / 0.33) : x < 0.66 ? mid * (1 - (x - 0.33) / 0.33) + high * ((x - 0.33) / 0.33) : high;
        const wob = 0.75 + 0.25 * Math.sin(i * 1.7 + gf * 0.21) * Math.cos(i * 0.6 - gf * 0.13);
        const h = 30 + 360 * Math.min(1, band * wob * (0.85 + 0.3 * beatPulse(t)));
        return (
          <g key={i}>
            <rect x={120 + i * bw + 2} y={H / 2 - h} width={bw - 4} height={h} rx={3} fill="url(#bar)" />
            <rect x={120 + i * bw + 2} y={H / 2 + 8} width={bw - 4} height={h * 0.45} rx={3} fill="url(#bar)" opacity={0.25} />
          </g>
        );
      })}
    </Svg>
  );
};

const PulseScene: React.FC<SP> = ({ f, gf }) => {
  const t = gf / FPS;
  const low = val(A.low, gf);
  const rings = A.beats.filter((b) => b <= t && t - b < 2.4).slice(-6);
  return (
    <Svg o={rise(f, 0, 12)}>
      {rings.map((b, i) => {
        const age = t - b;
        return <circle key={i} cx={W / 2} cy={H / 2} r={80 + age * 420} fill="none" stroke={i % 2 ? TH.b : TH.a} strokeWidth={6} opacity={Math.max(0, 1 - age / 2.4)} />;
      })}
      <g transform={`translate(${W / 2} ${H / 2}) rotate(${gf * 0.6}) scale(${1 + 0.35 * low + 0.15 * barPulse(t)})`}>
        <polygon points="0,-140 121,70 -121,70" fill="none" stroke={TH.text} strokeWidth={5} />
        <polygon points="0,140 121,-70 -121,-70" fill="none" stroke={TH.a} strokeWidth={5} opacity={0.8} />
      </g>
    </Svg>
  );
};

const lyricAt = (t: number) => {
  const L = P.lyrics ?? [];
  for (let i = L.length - 1; i >= 0; i--) {
    const end = L[i].end ?? (i + 1 < L.length ? L[i + 1].t : L[i].t + 4);
    if (t >= L[i].t && t < end) return { ...L[i], end };
  }
  return null;
};

const LyricsScene: React.FC<SP> = ({ f, gf, s }) => {
  const t = gf / FPS;
  const ly = lyricAt(t);
  const text = ly?.text ?? s.text ?? "";
  const o = ly ? Math.min(1, (t - ly.t) / 0.2, (ly.end - t) / 0.2) : rise(f, 0, 15);
  return (
    <>
      <PulseScene f={f} gf={gf} dur={0} s={s} />
      <Svg>
        <rect x={0} y={H / 2 - 110} width={W} height={220} fill="rgba(0,0,0,0.35)" opacity={o} />
        <text x={W / 2} y={H / 2 + 30} textAnchor="middle" fontFamily={FONT} fontWeight={900} fontSize={96} fill={TH.text} opacity={o}>
          {text}
        </text>
      </Svg>
    </>
  );
};

const TextScene: React.FC<SP> = ({ f, gf, s }) => {
  const words = (s.text ?? "").split(/\s+/).filter(Boolean);
  const t = gf / FPS;
  const startT = s.start;
  const shown = A.beats.filter((b) => b >= startT && b <= t).length;
  return (
    <>
      <PulseScene f={f} gf={gf} dur={0} s={s} />
      <Svg>
        <rect x={0} y={H / 2 - 120} width={W} height={240} fill="rgba(0,0,0,0.45)" opacity={rise(f, 0, 10)} />
        <text x={W / 2} y={H / 2 + 40} textAnchor="middle" fontFamily={FONT} fontWeight={900} fontSize={120} fill={TH.text}>
          {words.slice(0, Math.max(1, shown)).join(" ")}
        </text>
        {s.sub && (
          <text x={W / 2} y={H / 2 + 200} textAnchor="middle" fontFamily={FONT} fontWeight={700} fontSize={48} fill={TH.a} opacity={rise(f, 20)}>
            {s.sub}
          </text>
        )}
      </Svg>
    </>
  );
};

const ClipScene: React.FC<SP> = (p) => {
  const { gf, s } = p;
  if (!s.clip) return <PulseScene {...p} />;
  const t = gf / FPS;
  const loopFrames = Math.max(1, Math.round((s.clipSeconds ?? 5) * FPS));
  return (
    <AbsoluteFill>
      <Loop durationInFrames={loopFrames}>
        <OffthreadVideo src={staticFile(s.clip)} muted style={{ width: W, height: H, objectFit: "cover" }} />
      </Loop>
      <AbsoluteFill style={{ background: "radial-gradient(ellipse at center, rgba(0,0,0,0) 55%, rgba(0,0,0,0.55) 100%)" }} />
      <AbsoluteFill style={{ background: "#ffffff", opacity: 0.08 * barPulse(t) }} />
    </AbsoluteFill>
  );
};

const CreditsScene: React.FC<SP> = ({ f, dur }) => {
  const lines = [P.title ?? "", P.artist ?? "", ...(P.credits ?? [])].filter(Boolean);
  const fade = interpolate(f, [dur - 45, dur], [1, 0], CL);
  return (
    <Svg o={fade}>
      {lines.map((l, i) => (
        <text key={i} x={W / 2} y={H / 2 - (lines.length - 1) * 40 + i * 80} textAnchor="middle" fontFamily={FONT}
          fontWeight={i === 0 ? 900 : 600} fontSize={i === 0 ? 96 : 44} fill={i === 0 ? TH.text : TH.a} opacity={rise(f, 6 + i * 8, 30)}>
          {l}
        </text>
      ))}
    </Svg>
  );
};

const KINDS: Record<string, React.FC<SP>> = {
  title: TitleScene, visualizer: VisualizerScene, pulse: PulseScene, lyrics: LyricsScene, text: TextScene, clip: ClipScene, credits: CreditsScene,
};

// lyric subtitle at the bottom for every section except "lyrics" (which shows them big)
const LyricLine: React.FC = () => {
  const gf = useCurrentFrame();
  const t = gf / FPS;
  const sec = P.sections.find((s) => t >= s.start && t < s.end);
  if (!sec || sec.kind === "lyrics" || sec.kind === "title" || sec.kind === "credits") return null;
  const ly = lyricAt(t);
  if (!ly) return null;
  const o = Math.min(1, (t - ly.t) / 0.2, (ly.end - t) / 0.2);
  return (
    <Svg o={o}>
      <text x={W / 2} y={H - 90} textAnchor="middle" fontFamily={FONT} fontWeight={800} fontSize={54} fill="#ffffff" stroke="rgba(0,0,0,0.7)" strokeWidth={8} paintOrder="stroke">
        {ly.text}
      </text>
    </Svg>
  );
};

const XF = 8; // crossfade frames
const Section_: React.FC<{ s: Section; start: number; len: number; first: boolean }> = ({ s, start, len, first }) => {
  const f = useCurrentFrame();
  const C = KINDS[s.kind] ?? VisualizerScene;
  const o = first ? 1 : Math.min(1, f / XF);
  return (
    <AbsoluteFill style={{ opacity: o }}>
      <C f={f} gf={start + f} dur={len} s={s} />
    </AbsoluteFill>
  );
};

export const MusicVideo: React.FC = () => (
  <AbsoluteFill style={{ background: TH.bottom }}>
    <Background />
    {P.sections.map((s, i) => {
      const start = Math.max(0, Math.round(s.start * FPS) - (i > 0 ? XF : 0));
      const end = Math.min(FRAMES, Math.round(s.end * FPS));
      if (end - start < 2) return null;
      return (
        <Sequence key={i} from={start} durationInFrames={end - start}>
          <Section_ s={s} start={start} len={end - start} first={i === 0} />
        </Sequence>
      );
    })}
    <LyricLine />
    <Audio src={staticFile("song.wav")} />
  </AbsoluteFill>
);
