// Colour themes for the Short. Pick one with "theme" in data/scenes.json.
export type Theme = {
  bgTop: string;
  bgBottom: string;
  accent: string;
  text: string;
  muted: string;
  panel: string;
  bg: "rays" | "grid" | "plain" | "dots";
};

export const THEMES: Record<string, Theme> = {
  // gold on deep navy, slow light rays: reverent, "sacred" documentary tone
  sacred: { bgTop: "#1b1638", bgBottom: "#05060c", accent: "#e8c26a", text: "#f5ecd7", muted: "#b9a98a", panel: "#0b0e1c", bg: "rays" },
  // terminal green on near-black with a drifting grid: tech / software topics
  tech: { bgTop: "#0d1117", bgBottom: "#06080c", accent: "#3fb950", text: "#e6edf3", muted: "#8b949e", panel: "#0d1117", bg: "grid" },
  // white and red on charcoal: news / politics / history explainers
  news: { bgTop: "#1a1c23", bgBottom: "#0a0b0f", accent: "#ff4d4d", text: "#ffffff", muted: "#a0a4ad", panel: "#15171d", bg: "plain" },
  // sunset tones with floating dots: human stories, culture, light topics
  warm: { bgTop: "#3a1f2b", bgBottom: "#120a10", accent: "#ffb36b", text: "#fff1e0", muted: "#d0a98f", panel: "#22131a", bg: "dots" },
};

export const FONT = "'Apple SD Gothic Neo','Noto Sans KR','Noto Sans CJK KR','Malgun Gothic',sans-serif";
export const SERIF = "Georgia,'Times New Roman',serif";
export const MONO = "'SF Mono',Menlo,Consolas,'DejaVu Sans Mono',monospace";
