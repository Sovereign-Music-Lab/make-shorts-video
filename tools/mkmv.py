#!/usr/bin/env python3
"""mkmv: make a landscape music video (1920x1080 FHD) locally from your own song.

Routine:
  ./mkmv make <name> --song my_song.wav --title "제목" --artist "이름"     # analyze → render motion graphics
  ./mkmv make <name> --song my_song.wav --plan                              # + Ollama shot plan
  ./mkmv make <name> --song my_song.wav --plan --clips                      # + local AI 720p clips → 1080p
  ./mkmv make demo --demo-song                                              # try it with a generated song

Step by step:
  ./mkmv new <name> --song <file> [--title T --artist A --theme neon|gold|mono|sunset]
  ./mkmv analyze <name> [--bpm 120] [--draft] [--bars 8]
  ./mkmv lyrics <name> --file lyrics.lrc        # LRC ([mm:ss.xx] line) or plain text (spread evenly)
  ./mkmv plan <name> [--llm ollama|claude] [--concept "..."] [--max-clips 6]
  ./mkmv clips <name>                           # needs ./install_ai.sh (Apple Silicon, ~20 GB model)
  ./mkmv stills <name>  /  ./mkmv render <name> [--draft]  /  ./mkmv studio <name>
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
TEMPLATE = ROOT / "template" / "mv"
PROJECTS = ROOT / "projects"
AI = ROOT / "ai"
AI_PY = AI / ".venv" / "bin" / "python"
AI_SCRIPT = AI / "FastVideo" / "examples" / "inference" / "basic" / "mlx_wan22_generate.py"
AI_MODEL = AI / "models" / "FastMetal-5B-QAD"
AI_FILES = ["mlx_dit.json", "mlx_dit.safetensors", "text_encoder/model-00001-of-00003.safetensors",
            "text_encoder/model-00002-of-00003.safetensors", "text_encoder/model-00003-of-00003.safetensors",
            "vae/diffusion_pytorch_model.safetensors", "tokenizer/tokenizer.json"]
sys.path.insert(0, str(TOOLS))
import llm  # noqa: E402

PY = sys.executable
KINDS = ["title", "visualizer", "pulse", "lyrics", "text", "clip", "credits"]
THEMES = ["neon", "gold", "mono", "sunset"]


def say(msg):
    print(f"\033[1;35m▶ {msg}\033[0m", flush=True)


def run(cmd, cwd=None):
    print("  $ " + " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], cwd=cwd, check=True)


def remotion():
    exe = ROOT / "node_modules" / ".bin" / "remotion"
    if not exe.exists():
        sys.exit("Remotion이 설치되지 않았습니다. 먼저 ./install.sh 를 실행하세요.")
    return exe


def project(name, must_exist=True):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_\-]*", name):
        sys.exit(f"프로젝트 이름은 영문/숫자/-/_ 만 쓸 수 있습니다: {name}")
    p = PROJECTS / name
    if must_exist and not (p / "data" / "mv.json").exists():
        sys.exit(f"뮤직비디오 프로젝트가 없습니다: {p}\n먼저 ./mkmv new {name} --song <파일> 을 실행하세요.")
    return p


def load(p):
    return json.load(open(p / "data" / "mv.json", encoding="utf-8"))


def save(p, mv):
    json.dump(mv, open(p / "data" / "mv.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def ai_ready():
    return AI_PY.exists() and AI_SCRIPT.exists() and all((AI_MODEL / f).exists() and (AI_MODEL / f).stat().st_size > 0 for f in AI_FILES)


# ---------------------------------------------------------------- commands
def cmd_new(a):
    p = project(a.name, must_exist=False)
    if p.exists():
        sys.exit(f"이미 있습니다: {p}")
    if not a.song and not a.demo_song:
        sys.exit("--song <음원 파일> 또는 --demo-song 이 필요합니다.")
    say(f"새 뮤직비디오 {p.relative_to(ROOT)}")
    shutil.copytree(TEMPLATE, p)
    (p / "out").mkdir(exist_ok=True)
    (p / "public" / "clips").mkdir(parents=True, exist_ok=True)
    song = p / "public" / "song.wav"
    if a.demo_song:
        run([PY, TOOLS / "demo_song.py", song, "--seconds", str(a.seconds)])
    else:
        src = Path(a.song).expanduser()
        if not src.exists():
            sys.exit(f"음원 파일이 없습니다: {src}")
        run(["ffmpeg", "-loglevel", "error", "-y", "-i", src, "-vn", "-ac", "2", "-ar", "48000", song])
    mv = load(p)
    mv["title"] = a.title or ("Demo Song" if a.demo_song else src.stem)
    mv["artist"] = a.artist or ""
    mv["theme"] = a.theme or mv.get("theme", "neon")
    mv["credits"] = [c for c in [f"Music: {mv['artist']}" if mv["artist"] else "", "Video: make-shorts-video"] if c]
    mv["sections"] = []
    save(p, mv)
    cmd_analyze(argparse.Namespace(name=a.name, bpm=a.bpm, draft=True, bars=a.bars))


def cmd_analyze(a):
    p = project(a.name)
    say("음원 분석 (BPM · 비트 · 에너지)")
    cmd = [PY, TOOLS / "mv_analyze.py", p, "--bars", str(a.bars)]
    if a.bpm:
        cmd += ["--bpm", str(a.bpm)]
    if a.draft:
        cmd.append("--draft")
    run(cmd)
    mv = load(p)
    for i, s in enumerate(mv["sections"]):
        print(f"  [{i}] {s['start']:7.2f}–{s['end']:7.2f}s  {s['kind']:10s} energy {s.get('energy', 0):.2f}")


def parse_lyrics(text, duration, sections):
    lrc = re.compile(r"^\[(\d+):(\d+(?:\.\d+)?)\]\s*(.*)$")
    out = []
    plain = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = lrc.match(line)
        if m:
            out.append({"t": round(int(m.group(1)) * 60 + float(m.group(2)), 2), "text": m.group(3)})
        else:
            plain.append(line)
    if out:
        return sorted(out, key=lambda x: x["t"])
    # plain text: spread evenly over everything except the title and credits sections
    body = [s for s in sections if s["kind"] not in ("title", "credits")] or sections
    a, b = body[0]["start"], body[-1]["end"]
    step = (b - a) / max(1, len(plain))
    return [{"t": round(a + i * step, 2), "end": round(a + (i + 1) * step - 0.2, 2), "text": t} for i, t in enumerate(plain)]


def cmd_lyrics(a):
    p = project(a.name)
    mv = load(p)
    meta = json.load(open(p / "data" / "analysis.json"))
    mv["lyrics"] = parse_lyrics(Path(a.file).read_text(encoding="utf-8"), meta["duration"], mv["sections"])
    save(p, mv)
    say(f"가사 {len(mv['lyrics'])}줄 저장")
    for l in mv["lyrics"][:8]:
        print(f"  {l['t']:7.2f}s  {l['text']}")


MV_SYSTEM = """너는 뮤직비디오 연출가다. JSON 하나만 출력한다.
주어진 구간(index) 각각에 연출(kind)을 정한다. 구간 시간은 바꾸지 않는다.
kind: title(곡 제목, 첫 구간), visualizer(스펙트럼 막대, 에너지 높은 구간), pulse(비트 링, 잔잔한 구간),
lyrics(가사를 크게), text(짧은 문구가 비트마다 한 단어씩), clip(실사 AI 영상), credits(마지막 구간).
clip 구간에는 prompt를 영어로 쓴다: 5초짜리 실사 장면 하나(피사체, 동작, 장소, 빛, 카메라 움직임), "photorealistic, cinematic" 포함.
실존 인물, 유명인, 브랜드 로고, 폭력/선정적 장면은 쓰지 않는다. text 구간에는 text(한국어 4~8단어)를 쓴다."""

MV_SCHEMA = {
    "type": "object",
    "properties": {
        "theme": {"type": "string", "enum": THEMES},
        "sections": {"type": "array", "items": {"type": "object", "properties": {
            "index": {"type": "integer"}, "kind": {"type": "string", "enum": KINDS},
            "text": {"type": "string"}, "prompt": {"type": "string"}}, "required": ["index", "kind"]}},
    },
    "required": ["theme", "sections"],
}


def cmd_plan(a):
    p = project(a.name)
    mv = load(p)
    meta = json.load(open(p / "data" / "analysis.json"))
    secs = "\n".join(f"{i}: {s['start']:.1f}-{s['end']:.1f}s, energy {s.get('energy', 0):.2f}" for i, s in enumerate(mv["sections"]))
    lyr = "\n".join(f"{l['t']:.1f}s {l['text']}" for l in mv.get("lyrics", [])[:60]) or "(가사 없음)"
    prompt = (f"곡: {mv.get('title', '')} / {mv.get('artist', '')}\n길이 {meta['duration']:.0f}초, {meta['bpm']} BPM\n"
              f"콘셉트: {a.concept or '곡의 분위기에 맞게 자유롭게'}\n"
              f"clip 구간은 최대 {a.max_clips}개.\n구간:\n{secs}\n가사:\n{lyr}\n"
              "첫 구간은 title, 마지막 구간은 credits. 모든 index에 대해 하나씩 답하라.")
    say(f"연출 계획 ({a.llm}{' / ' + a.model if a.model else ''})")
    plan = llm.claude_json(MV_SYSTEM, prompt + "\nJSON 객체 하나만.", a.model) if a.llm == "claude" else llm.ollama_json(MV_SYSTEM, prompt, MV_SCHEMA, a.model)
    (p / "out").mkdir(exist_ok=True)
    json.dump(plan, open(p / "out" / "mv_plan_raw.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    by_index = {int(s.get("index", -1)): s for s in plan.get("sections", []) if isinstance(s, dict)}
    clips = 0
    n = len(mv["sections"])
    for i, s in enumerate(mv["sections"]):
        g = by_index.get(i, {})
        kind = g.get("kind") if g.get("kind") in KINDS else s["kind"]
        if i == 0:
            kind = "title"
        elif i == n - 1:
            kind = "credits"
        if kind == "clip":
            if clips >= a.max_clips or not str(g.get("prompt", "")).strip():
                kind = "visualizer"
            else:
                clips += 1
                s["prompt"] = str(g["prompt"]).strip()
        s["kind"] = kind
        if kind == "text":
            s["text"] = str(g.get("text") or s.get("text") or mv.get("title", ""))
    if plan.get("theme") in THEMES and not a.keep_theme:
        mv["theme"] = plan["theme"]
    save(p, mv)
    for i, s in enumerate(mv["sections"]):
        extra = s.get("prompt") or s.get("text") or ""
        print(f"  [{i}] {s['start']:7.2f}–{s['end']:7.2f}s  {s['kind']:10s} {extra[:90]}")
    print(f"  theme={mv['theme']}, AI 클립 {clips}개" + ("" if ai_ready() or clips == 0 else "  (AI 엔진 미설치: ./install_ai.sh 후 ./mkmv clips)"))


def cmd_clips(a):
    p = project(a.name)
    if not ai_ready():
        sys.exit("로컬 AI 영상 엔진이 준비되지 않았습니다. ./install_ai.sh 를 먼저 실행하세요 (Apple Silicon, 모델 약 20 GB).")
    mv = load(p)
    todo = [(i, s) for i, s in enumerate(mv["sections"]) if s["kind"] == "clip" and s.get("prompt")
            and (a.force or not s.get("clip") or not (p / "public" / s["clip"]).exists())]
    if a.only:
        keep = {int(x) for x in a.only.split(",")}
        todo = [(i, s) for i, s in todo if i in keep]
    if not todo:
        print("만들 클립이 없습니다 (kind=clip + prompt 인 구간이 필요: ./mkmv plan).")
        return
    raw_dir = p / "out" / "clips_raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for i, s in todo:
        raw = raw_dir / f"s{i}.mp4"
        fhd = p / "public" / "clips" / f"s{i}.mp4"
        say(f"AI 클립 [{i}] 720p 생성: {s['prompt'][:80]}")
        t0 = time.time()
        run([AI_PY, AI_SCRIPT, "--mlx-checkpoint", AI_MODEL, "--text-encoder-root", AI_MODEL, "--vae-root", AI_MODEL / "vae",
             "--prompt", s["prompt"], "--height", "704", "--width", "1280", "--num-frames", str(a.frames), "--fps", "24",
             "--seed", str(a.seed + i), "--output-path", raw], cwd=AI / "FastVideo")
        print(f"  생성 {time.time() - t0:.0f}s")
        say(f"업스케일 [{i}] → 1920x1080")
        run(["bash", TOOLS / "upscale.sh", raw, fhd, "30"])
        s["clip"] = f"clips/s{i}.mp4"
        s["clipSeconds"] = round(a.frames / 24, 3)
        save(p, mv)


def section_frames(p):
    return [int((s["start"] + (s["end"] - s["start"]) * 0.5) * 30) for s in load(p)["sections"]]


def cmd_stills(a):
    p = project(a.name)
    frames = a.frames or ",".join(str(f) for f in section_frames(p))
    say(f"스틸 {frames}")
    shutil.rmtree(p / "out" / "stills", ignore_errors=True)
    run(["node", TOOLS / "stills.mjs", p, frames, "0.25", "MusicVideo"], cwd=ROOT)
    imgs = sorted((p / "out" / "stills").glob("f_*.jpg"), key=lambda x: int(x.stem[2:]))
    if not imgs:
        return
    cols = min(4, len(imgs))
    inputs = []
    for im in imgs:
        inputs += ["-i", str(im)]
    if len(imgs) == 1:
        filt = "[0:v]scale=480:-1"
    else:
        filt = "".join(f"[{i}:v]scale=480:270[v{i}];" for i in range(len(imgs)))
        filt += "".join(f"[v{i}]" for i in range(len(imgs))) + f"xstack=inputs={len(imgs)}:layout="
        filt += "|".join(f"{(i % cols) * 480}_{(i // cols) * 270}" for i in range(len(imgs))) + ":fill=black"
    sheet = p / "out" / "stills" / "sheet.jpg"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *inputs, "-filter_complex", filt, "-frames:v", "1", str(sheet)], check=True)
    print(f"  시트: {sheet.relative_to(ROOT)}")


def cmd_render(a):
    p = project(a.name)
    out = p / "out" / f"{a.name}{'_draft' if a.draft else ''}.mp4"
    say(f"렌더 1920x1080{' (draft 960x540)' if a.draft else ''} → {out.relative_to(ROOT)}")
    cmd = [remotion(), "render", p / "src" / "index.ts", "MusicVideo", out, "--public-dir", p / "public",
           "--codec", "h264", "--crf", str(a.crf), "--timeout", "180000"]
    if a.draft:
        cmd += ["--scale", "0.5"]
    run(cmd, cwd=ROOT)
    dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
                         capture_output=True, text=True).stdout.strip()
    print(f"\n✅ 완성: {out}  ({float(dur or 0):.1f} s)")


def cmd_make(a):
    p = project(a.name, must_exist=False)
    if not (p / "data" / "mv.json").exists():
        cmd_new(a)
    if a.lyrics:
        cmd_lyrics(argparse.Namespace(name=a.name, file=a.lyrics))
    if a.plan:
        cmd_plan(a)
    if a.clips:
        cmd_clips(argparse.Namespace(name=a.name, only=None, force=False, frames=121, seed=1234))
    if a.stills:
        cmd_stills(argparse.Namespace(name=a.name, frames=None))
    cmd_render(a)


def cmd_studio(a):
    p = project(a.name)
    run([remotion(), "studio", p / "src" / "index.ts", "--public-dir", p / "public"], cwd=ROOT)


def cmd_doctor(a):
    say("뮤직비디오 도구")
    print(f"  {'✓' if (ROOT / 'node_modules' / 'remotion').exists() else '✗'} Remotion (./install.sh)")
    print(f"  {'✓' if shutil.which('ffmpeg') else '✗'} ffmpeg")
    ready = ai_ready()
    print(f"  {'✓' if ready else '-'} 로컬 AI 영상 엔진 (FastMetal-5B-QAD) {'준비됨' if ready else '미설치 → ./install_ai.sh (선택)'}")
    models = llm.ollama_available()
    print(f"  {'✓' if models is not None else '-'} Ollama {'연결됨' if models is not None else '없음 (선택)'}")


def main():
    ap = argparse.ArgumentParser(prog="mkmv", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def new_args(s):
        s.add_argument("--song", default=None, help="음원 파일 (wav/mp3/m4a/flac)")
        s.add_argument("--demo-song", action="store_true", help="코드로 만든 데모 곡 사용")
        s.add_argument("--seconds", type=float, default=48.0, help="데모 곡 길이")
        s.add_argument("--title", default=None)
        s.add_argument("--artist", default=None)
        s.add_argument("--theme", choices=THEMES, default=None)
        s.add_argument("--bpm", type=float, default=None, help="BPM을 알면 지정 (자동 감지 생략)")
        s.add_argument("--bars", type=int, default=8, help="구간당 마디 수")

    def plan_args(s):
        s.add_argument("--llm", choices=["ollama", "claude"], default="ollama")
        s.add_argument("--model", default=None)
        s.add_argument("--concept", default="", help="영상 콘셉트 (예: 새벽 도시, 바다, 우주)")
        s.add_argument("--max-clips", type=int, default=6)
        s.add_argument("--keep-theme", action="store_true")

    s = sub.add_parser("doctor"); s.set_defaults(fn=cmd_doctor)
    s = sub.add_parser("new", help="새 뮤직비디오 (음원 복사 + 분석 + 구간 초안)"); s.add_argument("name"); new_args(s); s.set_defaults(fn=cmd_new)
    s = sub.add_parser("analyze", help="BPM/비트/에너지 분석"); s.add_argument("name")
    s.add_argument("--bpm", type=float, default=None); s.add_argument("--draft", action="store_true", help="구간 다시 만들기")
    s.add_argument("--bars", type=int, default=8); s.set_defaults(fn=cmd_analyze)
    s = sub.add_parser("lyrics", help="가사 넣기 (LRC 또는 일반 텍스트)"); s.add_argument("name"); s.add_argument("--file", required=True)
    s.set_defaults(fn=cmd_lyrics)
    s = sub.add_parser("plan", help="LLM 연출 계획 (구간별 kind, AI 클립 프롬프트)"); s.add_argument("name"); plan_args(s); s.set_defaults(fn=cmd_plan)
    s = sub.add_parser("clips", help="로컬 AI 720p 클립 생성 → 1080p 업스케일"); s.add_argument("name")
    s.add_argument("--only", default=None, help="구간 번호들, 예: 2,5"); s.add_argument("--force", action="store_true")
    s.add_argument("--frames", type=int, default=121, help="4n+1, 121 = 5초"); s.add_argument("--seed", type=int, default=1234)
    s.set_defaults(fn=cmd_clips)
    s = sub.add_parser("stills", help="구간별 스틸 시트"); s.add_argument("name"); s.add_argument("--frames", default=None); s.set_defaults(fn=cmd_stills)
    s = sub.add_parser("render", help="1920x1080 렌더"); s.add_argument("name"); s.add_argument("--draft", action="store_true", help="절반 크기 빠른 확인용")
    s.add_argument("--crf", type=int, default=18); s.set_defaults(fn=cmd_render)
    s = sub.add_parser("make", help="전체 루틴"); s.add_argument("name"); new_args(s); plan_args(s)
    s.add_argument("--lyrics", default=None, help="가사 파일"); s.add_argument("--plan", action="store_true", help="LLM 연출 계획")
    s.add_argument("--clips", action="store_true", help="AI 클립 생성"); s.add_argument("--stills", action="store_true")
    s.add_argument("--draft", action="store_true"); s.add_argument("--crf", type=int, default=18); s.set_defaults(fn=cmd_make)
    s = sub.add_parser("studio", help="Remotion Studio 미리보기"); s.add_argument("name"); s.set_defaults(fn=cmd_studio)

    a = ap.parse_args()
    try:
        a.fn(a)
    except subprocess.CalledProcessError as e:
        sys.exit(f"\n✗ 명령 실패 (exit {e.returncode}): {' '.join(str(c) for c in e.cmd)}")
    except RuntimeError as e:
        sys.exit(f"\n✗ {e}")


if __name__ == "__main__":
    main()
