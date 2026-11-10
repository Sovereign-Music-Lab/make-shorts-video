"""Run FastVideo's mlx_wan22_generate.py with a memory-safe, tiled TAEHV decode.

The stock MLX TAEHV decode runs all frames at full resolution in one graph. For 121 frames at
1280x704 that needs well over 20 GB, so on a 24 GB Mac it fails with Metal "Insufficient Memory"
right after denoising. TAEHV is fully convolutional in space (its memory blocks only mix frames),
so we decode overlapping spatial tiles one at a time and feather-blend them. The result matches a
full decode except for tiny differences in the overlap areas.

Usage (same arguments as the FastVideo script):
    ai/.venv/bin/python tools/ai_generate.py <path/to/mlx_wan22_generate.py> --prompt ... [--output-path ...]
Env: MKMV_AI_TILE (latent tile size, default 20 → 320 px, about 6 GB per tile), MKMV_AI_OVERLAP (default 8 → 128 px).
"""
import os
import runpy
import sys
from pathlib import Path

import numpy as np

TILE = int(os.environ.get("MKMV_AI_TILE", "20"))
OVERLAP = int(os.environ.get("MKMV_AI_OVERLAP", "8"))


def _starts(size: int, tile: int, overlap: int) -> list[int]:
    if size <= tile:
        return [0]
    step = tile - overlap
    s = list(range(0, size - tile, step))
    s.append(size - tile)
    return sorted(set(s))


def _ramp(n: int, ov: int, lo_edge: bool, hi_edge: bool) -> np.ndarray:
    w = np.ones(n, np.float32)
    if ov > 0:
        r = (np.arange(ov, dtype=np.float32) + 0.5) / ov
        if not lo_edge:
            w[:ov] = np.minimum(w[:ov], r)
        if not hi_edge:
            w[-ov:] = np.minimum(w[-ov:], r[::-1])
    return w


def tiled_decode(latents_np, *, z_dim=None, checkpoint_path=None):
    import mlx.core as mx
    from fastvideo.mlx_runtime import wan_vae

    if latents_np.ndim != 5:
        raise ValueError(f"expected [B,C,T,H,W], got {latents_np.shape}")
    b, c, t, h, w = latents_np.shape
    z = z_dim if z_dim is not None else c
    dec = wan_vae.MLXTAEHVDecoder(wan_vae.ensure_taehv_checkpoint(z_dim=z, checkpoint_path=checkpoint_path), z_dim=z)
    ys, xs = _starts(h, TILE, OVERLAP), _starts(w, TILE, OVERLAP)
    print(f"[tiled-decode] latent {h}x{w}, {len(ys)}x{len(xs)} tiles of {TILE} (overlap {OVERLAP})", flush=True)
    out = acc = None
    scale = None
    for yi, y0 in enumerate(ys):
        for xi, x0 in enumerate(xs):
            th, tw = min(TILE, h - y0), min(TILE, w - x0)
            tile = latents_np[:, :, :, y0:y0 + th, x0:x0 + tw]
            x = mx.array(np.ascontiguousarray(tile.transpose(0, 2, 1, 3, 4)).astype(np.float32))
            px = dec.decode_ntchw(x)  # N T C H W
            mx.eval(px)
            px = np.array(px).transpose(0, 1, 3, 4, 2)  # N T H W C
            del x
            mx.clear_cache()
            if out is None:
                scale = px.shape[2] // th
                out = np.zeros((b, px.shape[1], h * scale, w * scale, 3), np.float32)
                acc = np.zeros((h * scale, w * scale), np.float32)
            ov = OVERLAP * scale
            wy = _ramp(px.shape[2], ov, yi == 0, yi == len(ys) - 1)
            wx = _ramp(px.shape[3], ov, xi == 0, xi == len(xs) - 1)
            wgt = np.outer(wy, wx)
            py, pxx = y0 * scale, x0 * scale
            out[:, :, py:py + px.shape[2], pxx:pxx + px.shape[3]] += px * wgt[None, None, :, :, None]
            acc[py:py + px.shape[2], pxx:pxx + px.shape[3]] += wgt
    out /= acc[None, None, :, :, None]
    return np.clip(out, 0.0, 1.0)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    script = Path(sys.argv[1]).resolve()
    from fastvideo.mlx_runtime import wan_vae

    wan_vae.decode_latents_taehv_mlx = tiled_decode
    sys.path.insert(0, str(script.parent))
    sys.argv = [str(script), *sys.argv[2:]]
    runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()
