// Render a few still frames of a project with one bundle (fast look checks).
// usage: node tools/stills.mjs <projectDir> <frame,frame,...> [scale] [compositionId]
// writes <projectDir>/out/stills/f_<frame>.jpg
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import fs from "node:fs";
import path from "node:path";

const [projectDir, frames, scale = "0.5", compId = "Short"] = process.argv.slice(2);
if (!projectDir || !frames) {
  console.error("usage: node tools/stills.mjs <projectDir> <frame,frame,...> [scale] [compositionId]");
  process.exit(1);
}
const proj = path.resolve(projectDir);
const outDir = path.join(proj, "out", "stills");
fs.mkdirSync(outDir, { recursive: true });

const serveUrl = await bundle({ entryPoint: path.join(proj, "src", "index.ts"), publicDir: path.join(proj, "public") });
// generous timeout: with a big Ollama model loaded, page boot can take >30 s on a 24 GB Mac
const composition = await selectComposition({ serveUrl, id: compId, timeoutInMilliseconds: 180000 });
for (const f of frames.split(",").map(Number)) {
  const frame = Math.min(Math.max(0, f), composition.durationInFrames - 1);
  const t0 = Date.now();
  await renderStill({
    composition, serveUrl, frame, output: path.join(outDir, `f_${frame}.jpg`), imageFormat: "jpeg", jpegQuality: 88,
    scale: Number(scale), timeoutInMilliseconds: 180000,
  });
  console.log("still", frame, ((Date.now() - t0) / 1000).toFixed(1) + "s");
}
