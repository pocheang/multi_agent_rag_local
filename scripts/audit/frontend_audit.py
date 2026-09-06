"""Frontend audit: endpoints vs OpenAPI, orphan modules, i18n keys.

Run from the repo root with the rag-local interpreter:
    PYTHONIOENCODING=utf-8 python scripts/audit/frontend_audit.py
"""

import json
import os
import re
import sys

ROOT = "frontend/src"


def _flat(d, pre=""):
    out = {}
    for k, v in d.items():
        key = f"{pre}.{k}" if pre else k
        if isinstance(v, dict):
            out.update(_flat(v, key))
        else:
            out[key] = v
    return out


def _sources():
    for dp, _dn, fn in os.walk(ROOT):
        for f in fn:
            if f.endswith((".ts", ".tsx")) and not f.endswith(".d.ts"):
                yield os.path.join(dp, f).replace("\\", "/")


def check_endpoints():
    import app.api.main as m

    backend = set(m.app.openapi()["paths"])
    pat = re.compile(
        r"""["'`](/(?:api|auth|sessions|documents|admin|prompts|upload|health|ready|metrics|optimization|agent-tracking|circuit-breakers|model-catalog|user)[^"'`\s]*)["'`]"""
    )
    found = {}
    for p in _sources():
        for i, line in enumerate(open(p, encoding="utf-8", errors="ignore"), 1):
            for mm in pat.finditer(line):
                norm = re.sub(r"\$\{[^}]+\}", "{p}", mm.group(1)).split("?")[0]
                found.setdefault(norm, []).append(f"{p}:{i}")

    def hit(fe):
        if fe in backend:
            return True
        fp = fe.strip("/").split("/")
        return any(
            len(bp) == len(fp) and all(b.startswith("{") or f == "{p}" or b == f for b, f in zip(bp, fp, strict=True))
            for bp in (be.strip("/").split("/") for be in backend)
        )

    # Paths built by concatenating a template into a suffix (e.g.
    # `/api/v1/sessions/${id}${suffix}`) cannot be resolved statically. The
    # helper that builds them is checked by hand; see sessionManagement.ts.
    UNRESOLVABLE = {"/api/v1/sessions/{p}{p}"}
    bad = {fe: w for fe, w in found.items() if fe not in UNRESOLVABLE and not hit(fe)}
    print(f"[endpoints] {len(found)} referenced, {len(bad)} not in backend OpenAPI")
    for fe, w in sorted(bad.items()):
        print(f"    MISSING {fe}  ({w[0]})")
    return len(bad)


def check_orphans():
    mods = {p: sum(1 for _ in open(p, encoding="utf-8", errors="ignore")) for p in _sources()}

    def resolve(spec, frm):
        if spec.startswith("@/"):
            base = f"{ROOT}/{spec[2:]}"
        elif spec.startswith("."):
            base = os.path.normpath(os.path.join(os.path.dirname(frm), spec)).replace("\\", "/")
        else:
            return None
        for c in (f"{base}.ts", f"{base}.tsx", f"{base}/index.ts", f"{base}/index.tsx", base):
            if c in mods:
                return c
        return None

    imported = set()
    imp = re.compile(r"""(?:from\s+|import\s*\(\s*)["']([^"']+)["']""")
    for p in mods:
        for m in imp.finditer(open(p, encoding="utf-8", errors="ignore").read()):
            t = resolve(m.group(1), p)
            if t:
                imported.add(t)
    entry = {f"{ROOT}/main.tsx", f"{ROOT}/App.tsx"}
    orph = sorted(((p, n) for p, n in mods.items() if p not in imported and p not in entry), key=lambda x: -x[1])
    print(f"\n[orphans] {len(mods)} modules, {len(orph)} with no importer ({sum(n for _, n in orph)} lines)")
    for p, n in orph:
        print(f"    {n:5d}  {p}")
    return len(orph)


def check_i18n():
    en = _flat(json.load(open(f"{ROOT}/i18n/locales/en.json", encoding="utf-8")))
    zh = _flat(json.load(open(f"{ROOT}/i18n/locales/zh.json", encoding="utf-8")))
    print(f"\n[i18n] en={len(en)} zh={len(zh)} keys")
    for label, diff in (("only-en", set(en) - set(zh)), ("only-zh", set(zh) - set(en))):
        if diff:
            print(f"    {label}: {sorted(diff)}")

    used, miss = set(), {}
    call = re.compile(r"""\bt\(\s*["'`]([A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+)["'`]""")
    for p in _sources():
        for i, line in enumerate(open(p, encoding="utf-8", errors="ignore"), 1):
            for m in call.finditer(line):
                used.add(m.group(1))
                if m.group(1) not in en:
                    miss.setdefault(m.group(1), []).append(f"{p}:{i}")
    unused = sorted(k for k in en if k not in used)
    print(f"    referenced: {len(used)}   missing: {len(miss)}   unused: {len(unused)}")
    for k in sorted(miss):
        print(f"    MISSING {k}  ({miss[k][0]})")
    dyn = [p for p in _sources() if "t(`" in open(p, encoding="utf-8", errors="ignore").read()]
    if dyn:
        print(f"    NOTE: template-literal t(`...`) calls in {len(dyn)} file(s); review before deleting unused keys:")
        for p in dyn:
            print(f"        {p}")
    return len(miss)


if __name__ == "__main__":
    bad = check_endpoints() + check_orphans() + check_i18n()
    print(f"\nexit code {1 if bad else 0}")
    sys.exit(1 if bad else 0)
