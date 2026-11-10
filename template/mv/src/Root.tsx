import React from "react";
import { Composition } from "remotion";
import { MusicVideo, FRAMES, W, H, FPS } from "./MV";

export const Root: React.FC = () => (
  <Composition id="MusicVideo" component={MusicVideo} durationInFrames={FRAMES} fps={FPS} width={W} height={H} />
);
