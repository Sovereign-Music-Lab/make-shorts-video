#!/usr/bin/env python3
"""mkshort: make Korean fact Shorts locally (script -> male narration -> music -> Remotion render).

Routine:
  ./mkshort make <name> --topic "주제"                 # Ollama writes the script, then everything else
  ./mkshort make <name> --topic "주제" --llm claude    # Claude Code writes the script
  ./mkshort make <name> --from templeos               # start from an example in examples/

Step by step:
  ./mkshort new <name> [--from <example>]
  ./mkshort write <name> --topic "..." [--llm ollama|claude] [--model M] [--seconds 60]
  (edit projects/<name>/voice/lines.txt and data/scenes.json, check FACTS.md)
  ./mkshort voice <name> [--voice ko-KR-InJoonNeural] [--rate +10%]
  ./mkshort music <name> [--mood sacred|march|calm|tension|none]
  ./mkshort stills <name>
  ./mkshort render <name> [--2k]

Other: doctor, list, studio <name>, rm <name>
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
TEMPLATE = ROOT / "template" / "short"
EXAMPLES = ROOT / "examples"
PROJECTS = ROOT / "projects"
sys.path.insert(0, str(TOOLS))
import llm  # noqa: E402

PY = sys.executable
DEFAULT_VOICE = os.environ.get("MKSHORT_VOICE", "ko-KR-InJoonNeural")
DEFAULT_RATE = os.environ.get("MKSHORT_RATE", "+10%")


def say(msg):
    print(f"\033[1;36m▶ {msg}\033[0m", flush=True)


def run(cmd, cwd=None):
    print("  $ " + " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], cwd=cwd, check=True)


def npx():
    local = ROOT / "node_modules" / ".bin" / "remotion"
    if not local.exists():
        sys.exit("Remotion이 설치되지 않았습니다. 먼저 ./install.sh 를 실행하세요.")
    return str(local)


def project(name, must_exist=True):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_\-]*", name):
        sys.exit(f"프로젝트 이름은 영문/숫자/-/_ 만 쓸 수 있습니다: {name}")
    p = PROJECTS / name
    if must_exist and not p.exists():
        sys.exit(f"프로젝트가 없습니다: {p}\n먼저 ./mkshort new {name} 또는 ./mkshort make {name} --topic ... 을 실행하세요.")
    return p


def read_plan(p):
    f = p / "data" / "scenes.json"
    return json.load(open(f, encoding="utf-8")) if f.exists() else {}


# ---------------------------------------------------------------- commands
def cmd_doctor(a):
    ok = True

    def check(label, good, hint=""):
        nonlocal ok
        print(("  ✓ " if good else "  ✗ ") + label + ("" if good else f"  → {hint}"))
        ok = ok and good

    def out(cmd):
        try:
            return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()
        except FileNotFoundError:
            return ""

    say("필수")
    node_v = out(["node", "--version"])
    check(f"Node.js {node_v or '(없음)'}", node_v.startswith("v") and int(node_v[1:].split(".")[0]) >= 18,
          "Node 18 이상 설치 (macOS: brew install node)")
    check("ffmpeg", bool(shutil.which("ffmpeg")) and bool(shutil.which("ffprobe")), "ffmpeg 설치 (macOS: brew install ffmpeg)")
    check("Remotion (node_modules)", (ROOT / "node_modules" / "remotion").exists(), "./install.sh 실행")
    try:
        import edge_tts  # noqa: F401
        import numpy  # noqa: F401
        check("Python 패키지 edge-tts, numpy", True)
    except ImportError:
        check("Python 패키지 edge-tts, numpy", False, "./install.sh 실행 (.venv 에 설치)")
    say("선택 (대본 자동 작성)")
    models = llm.ollama_available()
    if models is None:
        print(f"  - Ollama 서버 없음 ({llm.OLLAMA_HOST})  → Ollama로 대본을 쓰려면 Ollama 설치 후 실행")
    else:
        has = llm.DEFAULT_OLLAMA_MODEL in models
        print(f"  {'✓' if has else '-'} Ollama 연결됨, 기본 모델 {llm.DEFAULT_OLLAMA_MODEL} {'있음' if has else '없음 → ollama pull ' + llm.DEFAULT_OLLAMA_MODEL}")
        print(f"    설치된 모델: {', '.join(models) or '(없음)'}")
    print(f"  {'✓' if shutil.which('claude') else '-'} Claude Code CLI {'있음' if shutil.which('claude') else '없음 (선택)'}")
    print("\n" + ("준비 완료." if ok else "위 ✗ 항목을 먼저 해결하세요."))
    return 0 if ok else 1


def cmd_new(a):
    p = project(a.name, must_exist=False)
    if p.exists():
        sys.exit(f"이미 있습니다: {p}")
    say(f"새 프로젝트 {p.relative_to(ROOT)}")
    shutil.copytree(TEMPLATE, p)
    (p / "public").mkdir(exist_ok=True)
    (p / "out").mkdir(exist_ok=True)
    if a.from_example:
        ex = EXAMPLES / a.from_example
        if not ex.exists():
            sys.exit(f"예제가 없습니다: {ex}  (있는 예제: {', '.join(x.name for x in EXAMPLES.iterdir() if x.is_dir())})")
        shutil.copy(ex / "lines.txt", p / "voice" / "lines.txt")
        shutil.copy(ex / "scenes.json", p / "data" / "scenes.json")
        if (ex / "FACTS.md").exists():
            shutil.copy(ex / "FACTS.md", p / "FACTS.md")
        print(f"  예제 {a.from_example} 의 대본/장면을 복사했습니다.")
    return p


def cmd_write(a):
    p = project(a.name, must_exist=False)
    if not p.exists():
        cmd_new(argparse.Namespace(name=a.name, from_example=None))
    prompt = llm.build_prompt(a.topic, seconds=a.seconds, notes=a.notes or "", theme=a.theme, mood=a.mood)
    say(f"대본 작성 ({a.llm}{' / ' + a.model if a.model else ''}): {a.topic}")
    plan = llm.generate_claude(prompt, a.model) if a.llm == "claude" else llm.generate_ollama(prompt, a.model)
    (p / "out").mkdir(exist_ok=True)
    json.dump(plan, open(p / "out" / "plan_raw.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    lines, scenes = llm.normalize(plan, theme=a.theme, mood=a.mood)
    (p / "voice" / "lines.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    json.dump(scenes, open(p / "data" / "scenes.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    facts = ["# 팩트 시트 (자동 작성, 반드시 직접 확인하세요)", "", f"주제: {a.topic}", f"작성: {a.llm} {a.model or ''}", "",
             "| 내용 | 출처 | 확인 |", "|---|---|---|"]
    facts += [f"| {f.get('claim', '')} | {f.get('source', '')} | ☐ |" for f in scenes.get("facts", [])]
    facts += ["", "LLM이 쓴 사실은 틀릴 수 있습니다. 게시 전에 출처를 직접 열어 확인하고 ☐ 를 ☑ 로 바꾸세요."]
    (p / "FACTS.md").write_text("\n".join(facts) + "\n", encoding="utf-8")
    print(f"  나레이션 {len(lines)}줄, 장면 {len(scenes['scenes'])}개, theme={scenes['theme']}, mood={scenes['mood']}")
    for i, l in enumerate(lines, 1):
        print(f"  {i:2d}. {l}")


def cmd_voice(a):
    p = project(a.name)
    say(f"나레이션 ({a.backend} / {a.voice} / rate {a.rate})")
    cmd = [PY, TOOLS / "build_voice.py", "--backend", a.backend, "--gap", str(a.gap)]
    if a.backend == "edge":
        cmd += ["--voice", a.voice, "--rate", a.rate, "--pitch", a.pitch]
    if a.force:
        cmd.append("--force")
    run(cmd, cwd=p / "voice")


def cmd_music(a):
    p = project(a.name)
    mood = a.mood or read_plan(p).get("mood") or "sacred"
    say(f"음악 ({mood})")
    run([PY, TOOLS / "music.py", p, "--mood", mood, "--music-db", str(a.music_db)])


def scene_frames(p, fps=30):
    meta = json.load(open(p / "voice" / "lines.json", encoding="utf-8"))
    plan = read_plan(p)
    lines = meta["lines"]
    starts = sorted({min(len(lines), max(1, int(s.get("line", 1)))) for s in plan.get("scenes", [])} or {1})
    frames = []
    for i, ln in enumerate(starts):
        a = 0.0 if i == 0 else lines[ln - 1]["s"]
        b = lines[starts[i + 1] - 1]["s"] if i + 1 < len(starts) else meta["total"]
        frames.append(int((a + (b - a) * 0.6) * fps))
    return frames


def cmd_stills(a):
    p = project(a.name)
    frames = a.frames or ",".join(str(f) for f in scene_frames(p))
    say(f"스틸 {frames}")
    shutil.rmtree(p / "out" / "stills", ignore_errors=True)
    run(["node", TOOLS / "stills.mjs", p, frames, a.scale], cwd=ROOT)
    imgs = sorted((p / "out" / "stills").glob("f_*.jpg"), key=lambda x: int(x.stem[2:]))
    if imgs:
        cols = min(6, len(imgs))
        rows = (len(imgs) + cols - 1) // cols
        sheet = p / "out" / "stills" / "sheet.jpg"
        inputs = []
        for im in imgs:
            inputs += ["-i", str(im)]
        filt = "".join(f"[{i}:v]scale=270:-1[v{i}];" for i in range(len(imgs)))
        filt += "".join(f"[v{i}]" for i in range(len(imgs))) + f"xstack=inputs={len(imgs)}:layout="
        filt += "|".join(f"{(i % cols) * 270}_{(i // cols) * 480}" for i in range(len(imgs))) + ":fill=black"
        if len(imgs) == 1:
            filt = "[0:v]scale=270:-1"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *inputs, "-filter_complex", filt, "-frames:v", "1", str(sheet)], check=True)
        print(f"  시트: {sheet.relative_to(ROOT)} ({rows}x{cols})")


def cmd_render(a):
    p = project(a.name)
    if not (p / "public" / "mix.wav").exists():
        sys.exit("public/mix.wav 가 없습니다. 먼저 ./mkshort voice 와 ./mkshort music 을 실행하세요.")
    out = p / "out" / f"{a.name}{'_2k' if a.two_k else ''}.mp4"
    say(f"렌더 → {out.relative_to(ROOT)}")
    # generous timeout: with an Ollama model loaded, a 24 GB Mac can take >30 s to boot the page
    cmd = [npx(), "render", p / "src" / "index.ts", "Short", out, "--public-dir", p / "public",
           "--codec", "h264", "--crf", str(a.crf), "--timeout", "180000"]
    if a.two_k:
        cmd += ["--scale", "1.3333"]
    run(cmd, cwd=ROOT)
    dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
                         capture_output=True, text=True).stdout.strip()
    print(f"\n✅ 완성: {out}  ({float(dur or 0):.1f} s)")
    return out


def cmd_make(a):
    p = project(a.name, must_exist=False)
    if a.from_example:
        if not p.exists():
            cmd_new(argparse.Namespace(name=a.name, from_example=a.from_example))
    elif a.topic:
        cmd_write(a)
    elif not p.exists():
        sys.exit("--topic \"주제\" 또는 --from <예제> 가 필요합니다.")
    cmd_voice(a)
    cmd_music(a)
    if a.stills:
        cmd_stills(argparse.Namespace(name=a.name, frames=None, scale="0.4"))
    cmd_render(a)


def cmd_studio(a):
    p = project(a.name)
    run([npx(), "studio", p / "src" / "index.ts", "--public-dir", p / "public"], cwd=ROOT)


def cmd_list(a):
    if not PROJECTS.exists() or not any(x.is_dir() for x in PROJECTS.iterdir()):
        print("프로젝트 없음. ./mkshort make <name> --topic \"...\" 로 시작하세요.")
        return
    for d in sorted(x for x in PROJECTS.iterdir() if x.is_dir()):
        vids = sorted((d / "out").glob("*.mp4")) if (d / "out").exists() else []
        lj = d / "voice" / "lines.json"
        total = json.load(open(lj))["total"] if lj.exists() else None
        print(f"  {d.name:28s} {'%.1fs' % total if total else '-':>7s}  {', '.join(v.name for v in vids) or '(렌더 없음)'}")


def cmd_rm(a):
    p = project(a.name)
    if not a.yes:
        ans = input(f"{p} 를 영구 삭제합니다 (되돌릴 수 없음). 계속할까요? [y/N] ").strip().lower()
        if ans != "y":
            print("취소했습니다.")
            return
    shutil.rmtree(p)
    print(f"삭제됨: {p}")


# ---------------------------------------------------------------- CLI
def main():
    ap = argparse.ArgumentParser(prog="mkshort", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def llm_args(s):
        s.add_argument("--topic", help="영상 주제 (한 줄)")
        s.add_argument("--llm", choices=["ollama", "claude"], default=os.environ.get("MKSHORT_LLM", "ollama"))
        s.add_argument("--model", default=None, help=f"모델 이름 (ollama 기본 {llm.DEFAULT_OLLAMA_MODEL})")
        s.add_argument("--seconds", type=int, default=60, help="목표 길이(초)")
        s.add_argument("--notes", default="", help="추가 요청 (톤, 강조점 등)")
        s.add_argument("--theme", choices=llm.THEMES, default=None)

    def voice_args(s):
        s.add_argument("--backend", choices=["edge", "elevenlabs", "openai"], default="edge")
        s.add_argument("--voice", default=DEFAULT_VOICE, help="edge 음성 (기본 남성 ko-KR-InJoonNeural)")
        s.add_argument("--rate", default=DEFAULT_RATE, help="말 속도, 예: +10%%, -5%%")
        s.add_argument("--pitch", default="+0Hz")
        s.add_argument("--gap", type=float, default=0.4, help="문장 사이 쉼(초)")
        s.add_argument("--force", action="store_true", help="모든 줄 다시 합성")

    def music_args(s):
        s.add_argument("--mood", choices=llm.MOODS, default=None, help="기본: scenes.json 의 mood")
        s.add_argument("--music-db", type=float, default=0.0)

    s = sub.add_parser("doctor", help="설치 상태 점검")
    s.set_defaults(fn=cmd_doctor)

    s = sub.add_parser("new", help="새 프로젝트")
    s.add_argument("name")
    s.add_argument("--from", dest="from_example", default=None, help="examples/ 안의 예제 이름")
    s.set_defaults(fn=cmd_new)

    s = sub.add_parser("write", help="LLM으로 대본+장면 작성")
    s.add_argument("name")
    llm_args(s)
    s.add_argument("--mood", choices=llm.MOODS, default=None)
    s.set_defaults(fn=cmd_write)

    s = sub.add_parser("voice", help="남성 나레이션 합성 (edge-tts)")
    s.add_argument("name")
    voice_args(s)
    s.set_defaults(fn=cmd_voice)

    s = sub.add_parser("music", help="배경음악 합성 + 믹스")
    s.add_argument("name")
    music_args(s)
    s.set_defaults(fn=cmd_music)

    s = sub.add_parser("stills", help="장면별 스틸 + 시트")
    s.add_argument("name")
    s.add_argument("--frames", default=None, help="예: 30,300,900 (기본: 장면마다 하나)")
    s.add_argument("--scale", default="0.4")
    s.set_defaults(fn=cmd_stills)

    s = sub.add_parser("render", help="MP4 렌더")
    s.add_argument("name")
    s.add_argument("--2k", dest="two_k", action="store_true", help="1440x2560 출력")
    s.add_argument("--crf", type=int, default=18)
    s.set_defaults(fn=cmd_render)

    s = sub.add_parser("make", help="전체 루틴: write → voice → music → render")
    s.add_argument("name")
    s.add_argument("--from", dest="from_example", default=None)
    s.add_argument("--stills", action="store_true", help="렌더 전에 스틸 시트도 만들기")
    s.add_argument("--2k", dest="two_k", action="store_true")
    s.add_argument("--crf", type=int, default=18)
    llm_args(s)
    voice_args(s)
    music_args(s)
    s.set_defaults(fn=cmd_make)

    s = sub.add_parser("studio", help="Remotion Studio로 미리보기/수정")
    s.add_argument("name")
    s.set_defaults(fn=cmd_studio)

    s = sub.add_parser("list", help="프로젝트 목록")
    s.set_defaults(fn=cmd_list)

    s = sub.add_parser("rm", help="프로젝트 삭제")
    s.add_argument("name")
    s.add_argument("--yes", action="store_true")
    s.set_defaults(fn=cmd_rm)

    a = ap.parse_args()
    try:
        r = a.fn(a)
    except subprocess.CalledProcessError as e:
        sys.exit(f"\n✗ 명령 실패 (exit {e.returncode}): {' '.join(str(c) for c in e.cmd)}")
    except RuntimeError as e:
        sys.exit(f"\n✗ {e}")
    sys.exit(r if isinstance(r, int) else 0)


if __name__ == "__main__":
    main()
