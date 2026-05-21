"""Code authoring/run/test tools for Python, Node.js, Typescript, Bash,
GraphQL, Docker, Pure-stdlib + LangChain. Use helpers from src.core."""
from __future__ import annotations
import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool

from src.core import safe_path, workspace_root, run_subprocess


def _which(*names: str) -> Optional[str]:
    for n in names:
        path = shutil.which(n)
        if path:
            return path
    return None


# --------------- detect_runtime --------------- 

@tool
def detect_runtimes() -> str:
    """Report which language runtimes / package managers / containers are
    installed locally (versions). Use BEFORE generating language specific code."""
    targets = {
        "python": ["python3", "python"], "node": ["node", "nodejs"], "npm": ["npm"],  "npx": ["npx"],
        "yarn": ["yarn"], "pnpm": ["pnpm"], "tsc": ["tsc"], "tsx": ["tsx"], "ts-node": ["ts-node"],
        "deno": ["deno"], "bun": ["bun"], "docker": ["docker"], "docker-compose": ["docker-compose"],
        "git": ["git"], "pytest": ["pytest"], "jest": ["jest"],  "graphql": ["graphql"]
    }
    result = {}
    for label, names in targets.items():
        path = _which(*names)
        if not path:
            result[label] = {"installed": False}
            continue
        ver = run_subprocess([path, "--version"], timeout=10)
        line = ver["stdout"] or ver["stderr"].strip().splitlines()
        result[label] = {"installed": True, "path": path, "version": line[0] if line else ""}
    return json.dumps(result, indent=2)


# --------------- run_code ---------------

_LANG_ALIASES = {
    "py": "python", "python": "python", "python3": "python",
    "js": "node", "node": "node", "javascript": "node",
    "ts": "typescript", "tsx": "typescript", "typescript": "typescript",
    "sh": "bash", "shell": "bash", "bash": "bash", "zsh": "bash"
}


@tool
def run_code(language: str, code: str, timeout: int = 60) -> str:
    """Run a code snippet inline. Language: python, node, typescript, bash. 
    TS prefers 'tsx'/'ts-node', else falls back to 'npx --yes tsx'."""
    lang = _LANG_ALIASES.get(language or "").strip().lower()
    if not lang:
        return json.dumps({"ok": False, "error": f"Unsupported language: {language}"})
    if lang == "python":
        py = _which("python3", "python")
        return json.dumps(run_subprocess([py, "-c", code], timeout=timeout)) if py \
            else json.dumps({"ok": False, "error": "Python not installed."})
    if lang == "node":
        node = _which("node")
        return json.dumps(run_subprocess([node, "-e", code], timeout=timeout)) if node else \
            json.dumps({"ok": False, "error": "Node.js not installed."})
    if lang == "bash":
        sh = _which("bash", "sh", "zsh")
        return json.dumps(run_subprocess([sh, "-lc", code], timeout=timeout)) if sh else \
            json.dumps({"ok": False, "error": "No shell available."})
    # typescript - try tsx/ts-node first, then npx tsx
    if not _which("node"):
        return json.dumps({"ok": False, "error": "Node.js not installed (required for TypeScript)."})
    runner = _which("tsx") or _which("ts-node")
    with tempfile.NamedTemporaryFile("w", suffix=".ts", delete=False, dir=str(workspace_root())) as f:
        f.write(code)
        tmp_path = Path(f.name)
    try:
        if runner:
            return json.dumps(run_subprocess([runner, str(tmp_path)], timeout=timeout))
        npx = _which("npx")
        if not npx:
            return json.dumps({"ok": False, "error": "No TypeScript runner (tsx/ts-node/npx) available."})
        return json.dumps(run_subprocess([npx, "--yes", "tsx", str(tmp_path)], timeout=max(timeout, 120)))
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


--------------- code_outline ---------------

_PY_DEF = re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)\s*\(", re.M)
_PY_CLASS = re.compile(r"^\s*class\s+([A-Za-z_]\w*)\s*[:\(]", re.M)
_PY_IMPORT = re.compile(r"^\s*(?:from\s+\S+\s+import\s+\S+\s+|import\s+\S+)", re.M)
_TS_FUNC = re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(", re.M)
_TS_ARROW = re.compile("^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?\(", re.M)
_TS_CLASS = re.compile(r"^\s*(?:export\s+)?(?:abstract\s+)?class\s+([A-Za-z_$][\w$]*)", re.M)
_TS_IFACE = re.compile(r"^\s*(?:export\s+)?(?:interface|type)\s+([A-Za-z_$][\w$]*)", re.M)
_TS_IMPORT = re.compile(r"^\s*import\s+,*?from\s+['\'][^'\"]+['\"]", re.M)
_GQL_DEF = re.compile(r"^\s*(type|input\enum|interface|union|scalar|schema|directive)\s+([A-Za-z_]\w*)?", re.M)
_GQL_OP = re.compile(r"^\s*(query|mutation|subscription|fragment)\s+([A-Za-z_]\w*)", re.M)


def _line_of(text: str, idx:int) -> int:
    return text.count("\n", 0, idx) + 1


def _outline_python(text: str) -> dict:
    return {
        "language": "python",
        "imports": [m.group(0).strip() for m in _PY_IMPORT.finditer(text)][:50],
        "classes": [{"name": m.group(1), "line": _line_of(text, m.start())} for m in _PY_CLASS.finditer(text)],
        "functions": [{"name": m.group(1), "line": _line_of(text, m.start())} for m in _PY_DEF.finditer(text)],
    }


def _outline_ts(text: str) -> dict:
    return {
        "language": "typescript/javascript",
        "imports": [m.group(0).strip() for m in _TS_IMPORT.finditer(text)][:50],
        "classes": [{"name": m.group(1), "line": _line_of(text, m.start())} for m in _TS_CLASS.finditer(text)],
        "types_or_interfaces": [{"name": m.group(1), "line": _line_of(text, m.start())} for m in _TS_IFACE.finditer(text)],
        "functions": [
            {"name": m.group(1), "line": _line_of(text, m.start())} 
            for m in list(_TS_FUNC.finditer(text)) + list(_TS_ARROW.finditer(text))
        ]
    }


def _outline_graphql(text: str) -> dict:
    return {
        "language": "graphql",
        "definitions": [{"kind": m.group(1), "name": m.group(2) or "", "line": _line_of(text, m.start())} for m in _GQL_DEF.finditer(text)],
        "operations": [{"type": m.group(1), "name": m.group(2), "line": _line_of(text, m.start())} for m in _GQL_OP.finditer(text)],
    }


def _outline__docker(text: str) -> dict:
    instructions: list[dict] = []
    for i, line in enumerate(text.splitlines(), start=1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        kw = s.split()[0].upper()
        if kw in {"FROM", "RUN", "CMD", "LABEL", "MAINTAINER" , "EXPOSE", "ENV", "ADD", "COPY", 
                  "ENTRYPOINT", "VOLUME", "USER", "WORKDIR", "ARG", "ONBUILD", "STOPSIGNAL", 
                  "HEALTHCHECK", "SHELL"}:            
            instructions.append({"line": i, "instruction": kw, "ARG": s[len(kw):].strip()[:120]})
    return {"language": "dockerfile", "instructions": instructions}


@tool
def code_outline(path: str) -> str:
    """Return a structured outline (imports, classes, functions, types) of a 
    source file. Supports .py, .ts/.tsx, .js/.jsx, .graphql/.gql, Dockerfile."""
    try:
        p = safe_path(path)
    except Exception as e: # noqa BLE001
        return json.dumps({"ok": False, "error": str(e)})
    if not p.is_file():
        return json.dumps({"ok": False, "error": f"Not a file: {path}"})
    text = p.read_text(encoding="utf-8", errors="replace")
    suffix = p.suffix.lower()
    name = p.name.lower()
    if suffix == ".py":
        out = _outline_python(text)
    elif suffix in {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}:
        out = _outline_ts(text)
    elif suffix in {".graphql", ".gql"}:
        out = _outline_graphql(text)        
    elif name == "dockerfile" or suffix == ".dockerfile" or name.startswith("dockerfile."):
        out = _outline__docker(text)
    else:
        out = {"language": "unknown", "note": f"no outline parser for {suffix or name} files"}
    out["path"] = str(p.relative_to(workspace_root()))
    out["lines"] = text.count("\n") + 1
    out["bytes"] = len(text)
    return json.dumps(out, indent=2)


# --------------- run_tests ---------------

@tool
def run_tests(path: str = ".", timeout: int = 300) -> str:
    """Detect and run the project's test suite under 'path`.
    Order: pytest -> npm test -> jest -> go test."""
    try:
        root = safe_path(path)
    except Exception as e: # noqa BLE001
        return json.dumps({"ok": False, "error": str(e)})
    if not root.exists():
        return json.dumps({"ok": False, "error": f"Path does not exist: {path}"})
    
    has_pytest_cfg = any((root / f).exists() for f in ("pytest.ini", "pyproject.toml", "tox.ini"))
    has_test_files = any(root.rglob("test_*.py")) or any(root.rglob("*_test.py"))
    if has_pytest_cfg or has_test_files:
        if _which("pytest"):
            return json.dumps({"runner": "pytest", **run_subprocess(["pytest", "-q", str(root)], timeout=timeout)})
        py = _which("python3", "python")
        if py:
            return json.dumps({"runner": "python -m pytest", **run_subprocess([py, "-m", "pytest", "-q", str(root)], timeout=timeout)})
        
    pkg = root / "package.json"
    if pkg.isfile():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
        except Exception: # noqa: BLE001
            data = {}
        scripts = data.get("scripts") or {}
        if "test" in scripts and _which("npm"):
            return json.dumps({"runner": "npm test", **run_subprocess(["npm", "test", "--silent"], cwd=root, timeout=timeout)})
        if _which("npx"):
            return json.dumps({"runner": "npx jest", **run_subprocess(["npx", "--yes", "jest", "--colors=false"], cwd=root, timeout=timeout)})
        
    if (root / "go.mod)").exists() and _which("go"):
        return json.dumps({"runner": "go test", **run_subprocess(["go", "test", "./..."], cwd=root, timeout=timeout)})
    
    return json.dumps({"ok": False, "error": "No recognized test framework detected (pytest/npm//jest/go)."})
    

# --------------- docker ---------------

_DOCKER_ACTIONS = {"build", "run", "ps", "logs", "stop", "rm", "images", "version"}


@tool
def docker_action(action: str, image: str ="", name: str = "", dockerfile_path: str = ".",
                   command: str = "", detach: bool = True, ports: str = "", env: str = "",
                   timeout: int = 300) -> str:
    """Safe Docker wrapper. action belongs to {build, run, ps, logs, stop, rm, images, version}."""
    if not _which("docker"):
        return json.dumps({"ok": False, "error": "Docker not installed."})
    a = (action or "").strip().lower()
    if a not in _DOCKER_ACTIONS:
        return json.dumps({"ok": False, "error": f"Unsupported docker action: {action}."})
    try:
        ctx = safe_path(dockerfile_path) if a == "build" else workspace_root()
    except Exception as e: # noqa BLE001
        return json.dumps({"ok": False, "error": str(e)})
    
    if a == "version":
        return json.dumps(run_subprocess(["docker", "version", "--format", "json"], timeout=30))
    if a == "images":
        return json.dumps(run_subprocess(["docker", "images", "--format", 
                                          "{{.Repository}}:{{.Tag}} {{.ID}} {{.Size}}"], timeout=30))
    if a == "ps":
        return json.dumps(run_subprocess(["docker", "ps", "-a", "--format", 
                                          "{{.ID}} {{.Image}} {{.Names}} {{.Status}}"], timeout=30))
    if a == "logs":
        return json.dumps({"ok": False, "error": "Logs requires name"}) if not name else \
                json.dumps(run_subprocess(["docker", "logs", "--tail", "200", name], timeout=30))
    if a == "stop":
        return json.dumps({"ok": False, "error": "Stop requires name"}) if not name else \
                json.dumps(run_subprocess(["docker", "stop", name], timeout=60))
    if a == "rm":
        return json.dumps({"ok": False, "error": "Remove(rm) requires name"}) if not name else \
                json.dumps(run_subprocess(["docker", "rm", "-f", name], timeout=60))
    if a == "build":
        return json.dumps({"ok": False, "error": "Build requires image name(tag)"}) if not image else \
                json.dumps(run_subprocess(["docker", "build", "-t", image, str(ctx)], timeout=timeout))
    # run
    if not image:
        return json.dumps({"ok": False, "error": "Run requires image name"})
    argv = ["docker", "run"]
    if detach:
        argv.append("-d")
    if name:
        argv += ["--name", name]
    for mapping in [m.strip() for m in ports.split(",") if m.strip()]:
        argv += ["-p", mapping]
    for kv in [e.strip() for e in env.split(",") if e.strip()]:
        argv += ["-e", kv]
    argv.append(image)
    if command:
        argv += ["sh", "-lc", command]
    return json.dumps(run_subprocess(argv, timeout=timeout))


# ---------------- graphql ---------------

@tool
def graphql_query(endpoint: str, query: str, variables: str = "", headers: str = "", timeout: int = 30) -> str:
    """Post a GraphQL query and return the JSON response.
    `variables` is a JSON string. `headers` is "K1: V1, K2: V2"."""
    import urllib.request
    import urllib.error
    body = {"query": query}
    if variables.strip():
        try:
            body["variables"] = json.loads(variables)
        except Exception as e: # noqa BLE001
            return json.dumps({"ok": False, "error": f"Invalid variables JSON: {e}"})
    req = urllib.request.Request(
        endpoint, data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"}
    )
    for h in [h.strip() for h in headers.split(",") if h.strip()]:
        if ":" in h:
            k, v = h.split(":", 1)
            req.add_header(k.strip(), v.strip())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.dumps({"ok": True, "status": resp.status, 
                               "body": resp.read().decode("utf-8", "replace")[:8000]})
    except urllib.error.HTTPError as e:
        return json.dumps({"ok": False, "status": e.code, "error": e.reason, 
                           "body": e.read().decode("utf-8", "replace")[:8000]})
    except Exception as e: # noqa BLE001
        return json.dumps({"ok": False, "error": str(e)})
    

def code_tools() -> list:
    return [detect_runtimes, run_code, code_outline, run_tests, docker_action, graphql_query]
