import React from "react";
import { Composition } from "remotion";
import { Short, FRAMES, W, H, FPS } from "./Short";

export const Root: React.FC = () => (
  <Composition id="Short" component={Short} durationInFrames={FRAMES} fps={FPS} width={W} height={H} />
);
