"""Script + scene-plan writers for mkshort.

Two backends return the same JSON plan:
  ollama  local model through the Ollama HTTP API (structured output with a JSON schema). No account, no key.
  claude  Claude Code CLI in headless mode (`claude -p`). Uses your Claude Code login.

Plan JSON:
  {"title", "theme", "mood", "facts": [{"claim", "source"}], "lines": [str, ...], "scenes": [{"type", "line", ...}]}
"""
import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
if not OLLAMA_HOST.startswith("http"):
    OLLAMA_HOST = "http://" + OLLAMA_HOST
DEFAULT_OLLAMA_MODEL = os.environ.get("MKSHORT_OLLAMA_MODEL", "gemma4:e4b-mlx")

SCENE_TYPES = ["title", "person", "timeline", "number", "statement", "chips", "compare", "code", "image", "ending"]
THEMES = ["sacred", "tech", "news", "warm"]
MOODS = ["sacred", "march", "calm", "tension", "none"]

_side = {"type": "object", "properties": {"title": {"type": "string"}, "text": {"type": "string"}}}
SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "theme": {"type": "string", "enum": THEMES},
        "mood": {"type": "string", "enum": MOODS},
        "facts": {"type": "array", "items": {"type": "object", "properties": {
            "claim": {"type": "string"}, "source": {"type": "string"}}, "required": ["claim", "source"]}},
        "lines": {"type": "array", "items": {"type": "string"}},
        "scenes": {"type": "array", "items": {"type": "object", "properties": {
            "type": {"type": "string", "enum": SCENE_TYPES},
            "line": {"type": "integer"},
            "kicker": {"type": "string"}, "title": {"type": "string"}, "subtitle": {"type": "string"},
            "icon": {"type": "string", "enum": ["none", "temple", "star", "globe"]},
            "role": {"type": "string"}, "name": {"type": "string"}, "years": {"type": "string"}, "note": {"type": "string"},
            "points": {"type": "array", "items": {"type": "object", "properties": {
                "year": {"type": "string"}, "label": {"type": "string"}}}},
            "value": {"type": "number"}, "prefix": {"type": "string"}, "suffix": {"type": "string"}, "label": {"type": "string"},
            "text": {"type": "string"}, "sub": {"type": "string"},
            "items": {"type": "array", "items": {"type": "string"}},
            "left": _side, "right": _side,
            "code": {"type": "string"}, "caption": {"type": "string"}, "source": {"type": "string"},
        }, "required": ["type", "line"]}},
    },
    "required": ["title", "theme", "mood", "facts", "lines", "scenes"],
}

SYSTEM = """너는 한국어 팩트 쇼츠(세로 영상) 작가이자 연출가다. 반드시 JSON 하나만 출력한다.
규칙:
- 사실만 쓴다. 확실하지 않은 숫자, 날짜, 인용은 쓰지 말고 빼라. 지어내지 마라.
- facts 배열에 나레이션에 쓴 핵심 사실과 출처(문서/기관 이름)를 적는다.
- lines: 나레이션 문장 목록. 한 항목은 한두 문장, 40자 안팎. 숫자는 읽기 좋게 한글 단위로 쓴다(예: 10만 줄).
- 첫 줄은 강한 훅, 마지막 줄은 여운 있는 마무리.
- scenes: 화면 계획. line은 그 장면이 시작되는 나레이션 줄 번호(1부터). 첫 장면은 line 1.
  장면 하나가 1~2줄을 덮게 하라. 화면 글자는 짧게(한 줄 12자 이내).
- 장면 type과 필드:
  title {kicker, title, subtitle, icon: none|temple|star|globe}
  person {role, name, years, note}
  timeline {title, points: [{year, label}] 최대 5개}
  number {kicker, value(숫자), prefix, suffix, label}
  statement {text, sub}
  chips {title, items: [짧은 단어 최대 6개]}
  compare {title, left: {title, text}, right: {title, text}}
  code {code, caption}
  ending {title, subtitle, icon}
  모든 장면에 선택적으로 source(짧은 출처 이름)를 넣을 수 있다.
- theme: sacred(경건/역사/종교), tech(기술), news(시사/정치/전쟁), warm(사람/문화).
- mood: sacred, march(결의/진취), calm(설명), tension(사건/갈등), none."""

EXAMPLE = {
    "title": "TempleOS",
    "theme": "sacred",
    "mood": "sacred",
    "facts": [{"claim": "2005년 J Operating System으로 처음 공개", "source": "Wikipedia: TempleOS"}],
    "lines": ["신의 계시를 받아 만들었다고 주장한 운영체제가 있습니다. 이름은 템플 OS입니다.",
              "만든 사람은 테리 A. 데이비스. 그는 거의 혼자서 이 시스템을 만들었습니다."],
    "scenes": [{"type": "title", "line": 1, "kicker": "신의 계시?", "title": "TempleOS", "subtitle": "한 사람이 만든 운영체제", "icon": "temple"},
               {"type": "person", "line": 2, "role": "프로그래머", "name": "테리 A. 데이비스", "years": "1969 — 2018"}],
}


def build_prompt(topic, seconds=60, notes="", theme=None, mood=None):
    n_lines = max(6, min(18, round(seconds / 5.5)))
    chars = int(seconds * 5.5)
    want = []
    if theme:
        want.append(f"theme은 {theme}로 한다.")
    if mood:
        want.append(f"mood는 {mood}로 한다.")
    return (
        f"주제: {topic}\n"
        f"길이: 약 {seconds}초 (나레이션 {n_lines}줄 안팎, 전체 약 {chars}자).\n"
        + (f"추가 요청: {notes}\n" if notes else "")
        + (" ".join(want) + "\n" if want else "")
        + "형식 예시(내용은 따라 하지 말고 형식만 참고):\n"
        + json.dumps(EXAMPLE, ensure_ascii=False)
        + "\n위 규칙대로 JSON만 출력하라."
    )


def _extract_json(text):
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if m:
        text = m.group(1)
    else:
        a, b = text.find("{"), text.rfind("}")
        if a >= 0 and b > a:
            text = text[a:b + 1]
    return json.loads(text)


def ollama_available():
    try:
        with urllib.request.urlopen(OLLAMA_HOST + "/api/tags", timeout=3) as r:
            return [m["name"] for m in json.load(r).get("models", [])]
    except Exception:
        return None


def generate_ollama(prompt, model=None, temperature=0.4):
    model = model or DEFAULT_OLLAMA_MODEL
    models = ollama_available()
    if models is None:
        raise RuntimeError(f"Ollama 서버에 연결할 수 없습니다 ({OLLAMA_HOST}). `ollama serve` 또는 Ollama 앱을 켜세요.")
    if model not in models and model + ":latest" not in models:
        raise RuntimeError(f"Ollama 모델 '{model}'이 없습니다. `ollama pull {model}` 하거나 --model 로 다른 모델을 지정하세요.\n"
                           f"설치된 모델: {', '.join(models) or '(없음)'}")
    body = {
        "model": model,
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
        "format": SCHEMA,
        "stream": False,
        "think": False,
        "options": {"temperature": temperature, "num_ctx": 8192},
    }
    req = urllib.request.Request(OLLAMA_HOST + "/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        # older Ollama builds reject "think" for non-thinking models: retry without it
        if e.code == 400:
            body.pop("think", None)
            req = urllib.request.Request(OLLAMA_HOST + "/api/chat", data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=900) as r:
                data = json.load(r)
        else:
            raise
    return _extract_json(data["message"]["content"])


def generate_claude(prompt, model=None):
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("Claude Code CLI(`claude`)를 찾을 수 없습니다. https://claude.com/claude-code 에서 설치하세요.")
    full = SYSTEM + "\n\n" + prompt + "\n\n사실은 웹에서 확인한 것만 쓰고, 출처를 facts에 적어라. 최종 답은 JSON 객체 하나만."
    cmd = [exe, "-p", full, "--output-format", "json"]
    if model:
        cmd += ["--model", model]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if res.returncode != 0:
        raise RuntimeError("claude -p 실패:\n" + (res.stderr or res.stdout)[-2000:])
    out = json.loads(res.stdout)
    return _extract_json(out.get("result", res.stdout))


def normalize(plan, theme=None, mood=None):
    """Make an LLM plan safe to render: strings only, valid types, line numbers in range."""
    lines = [str(l).strip() for l in plan.get("lines", []) if str(l).strip()]
    if not lines:
        raise ValueError("plan has no narration lines")
    n = len(lines)
    scenes = []
    for s in plan.get("scenes", []):
        if not isinstance(s, dict) or s.get("type") not in SCENE_TYPES:
            continue
        try:
            s["line"] = min(n, max(1, int(s.get("line", 1))))
        except (TypeError, ValueError):
            s["line"] = 1
        scenes.append(s)
    scenes.sort(key=lambda s: s["line"])
    dedup = []
    for s in scenes:  # one scene per start line (the first one wins)
        if not dedup or dedup[-1]["line"] != s["line"]:
            dedup.append(s)
    if not dedup or dedup[0]["line"] != 1:
        dedup.insert(0, {"type": "title", "line": 1, "title": plan.get("title", ""), "icon": "none"})
    out = {
        "title": str(plan.get("title", "")),
        "theme": theme or (plan.get("theme") if plan.get("theme") in THEMES else "sacred"),
        "mood": mood or (plan.get("mood") if plan.get("mood") in MOODS else "sacred"),
        "captions": True,
        "facts": [f for f in plan.get("facts", []) if isinstance(f, dict)],
        "scenes": dedup,
    }
    return lines, out
