"""Active web vulnerability scanner.

Runs well-known security tools against a *domain* (externally, e.g.
``nmap -sV https://midominio.com``) and normalizes their output into findings.

Every tool is optional: if the binary is not installed in the image the tool is
reported as ``available: false`` and skipped gracefully, so the engine never
crashes on a missing dependency.

NOTE on BurpSuite: Burp Suite has no free CLI for automated scanning (only the
commercial Pro REST API). We use ``nuclei`` (ProjectDiscovery) as the automated
template-based web scanner that plays the same role; a Burp Pro REST endpoint
can be wired in later if available.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlparse

_WORDLIST = Path(__file__).with_name("gobuster_common.txt")

# Tool catalog (also used by the UI). ``binary`` is what we look up on PATH.
SCAN_TOOLS: list[dict] = [
    {
        "id": "nmap",
        "binary": "nmap",
        "label": "NMAP (Ports)",
        "description": "Descubrimiento de puertos y servicios expuestos.",
        "bruteforce": False,
    },
    {
        "id": "nuclei",
        "binary": "nuclei",
        "label": "Automated Web Scan",
        "description": "Escaneo automático de vulnerabilidades por plantillas (estilo Burp).",
        "bruteforce": False,
    },
    {
        "id": "wpscan",
        "binary": "wpscan",
        "label": "WPScan (WordPress)",
        "description": "Plugins, temas, enumeración de usuarios y versiones.",
        "bruteforce": False,
    },
    {
        "id": "gobuster",
        "binary": "gobuster",
        "label": "Gobuster (Directories)",
        "description": "Enumeración de directorios y rutas ocultas.",
        "bruteforce": False,
    },
    {
        "id": "hydra",
        "binary": "hydra",
        "label": "Hydra (Brute force)",
        "description": "Fuerza bruta de credenciales (apps Node.js, Python, etc). Requiere confirmación.",
        "bruteforce": True,
    },
]

_TOOL_BINARY = {t["id"]: t["binary"] for t in SCAN_TOOLS}


@dataclass
class ScanFinding:
    title: str
    severity: str  # info|low|medium|high|critical
    detail: str
    recommendation: str = ""


@dataclass
class ToolResult:
    tool: str
    label: str
    available: bool
    status: str  # ok|skipped|timeout|error|not_installed
    summary: str = ""
    findings: list[ScanFinding] = field(default_factory=list)
    raw: str = ""


def tool_available(tool_id: str) -> bool:
    binary = _TOOL_BINARY.get(tool_id)
    return bool(binary and shutil.which(binary))


def catalog_with_availability() -> list[dict]:
    return [{**t, "available": tool_available(t["id"])} for t in SCAN_TOOLS]


def _host(target: str) -> str:
    t = target.strip()
    if "://" not in t:
        t = f"//{t}"
    parsed = urlparse(t)
    return (parsed.hostname or target).strip()


def _url(target: str) -> str:
    t = target.strip()
    if t.startswith("http://") or t.startswith("https://"):
        return t
    return f"https://{t}"


def _run(cmd: list[str], timeout: int) -> tuple[int, str, str]:
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        text=True,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def run_tool(tool_id: str, target: str, options: dict | None = None) -> ToolResult:
    options = options or {}
    meta = next((t for t in SCAN_TOOLS if t["id"] == tool_id), None)
    label = meta["label"] if meta else tool_id
    if not tool_available(tool_id):
        return ToolResult(tool=tool_id, label=label, available=False, status="not_installed",
                          summary="Herramienta no instalada en el servidor.")
    try:
        if tool_id == "nmap":
            return _scan_nmap(target, label)
        if tool_id == "nuclei":
            return _scan_nuclei(target, label)
        if tool_id == "wpscan":
            return _scan_wpscan(target, label)
        if tool_id == "gobuster":
            return _scan_gobuster(target, label)
        if tool_id == "hydra":
            return _scan_hydra(target, label, options)
    except subprocess.TimeoutExpired:
        return ToolResult(tool=tool_id, label=label, available=True, status="timeout",
                          summary="El escaneo superó el tiempo límite.")
    except Exception as exc:  # noqa: BLE001 - never let a tool crash the scan
        return ToolResult(tool=tool_id, label=label, available=True, status="error", summary=str(exc)[:300])
    return ToolResult(tool=tool_id, label=label, available=False, status="skipped", summary="Tool desconocida")


_RISKY_PORTS = {
    "21": ("FTP", "high"), "23": ("Telnet", "high"), "3306": ("MySQL", "medium"),
    "5432": ("PostgreSQL", "medium"), "6379": ("Redis", "high"), "27017": ("MongoDB", "high"),
    "9200": ("Elasticsearch", "high"), "3389": ("RDP", "high"), "22": ("SSH", "low"),
}


def _scan_nmap(target: str, label: str) -> ToolResult:
    host = _host(target)
    code, out, err = _run(["nmap", "-sV", "-Pn", "-T4", "--top-ports", "200", host], timeout=240)
    findings: list[ScanFinding] = []
    open_ports: list[str] = []
    for line in out.splitlines():
        line = line.strip()
        if "/tcp" in line and "open" in line:
            parts = line.split()
            portproto = parts[0]
            port = portproto.split("/")[0]
            service = parts[2] if len(parts) > 2 else "unknown"
            version = " ".join(parts[3:]) if len(parts) > 3 else ""
            open_ports.append(f"{port} ({service})")
            risky = _RISKY_PORTS.get(port)
            if risky:
                name, sev = risky
                findings.append(ScanFinding(
                    title=f"Puerto {port}/{name} expuesto",
                    severity=sev,
                    detail=f"{service} {version}".strip(),
                    recommendation=f"Cierre el puerto {port} en el firewall si no es necesario públicamente.",
                ))
    summary = f"{len(open_ports)} puertos abiertos: " + ", ".join(open_ports) if open_ports else "Sin puertos abiertos detectados."
    return ToolResult(tool="nmap", label=label, available=True, status="ok",
                      summary=summary, findings=findings, raw=out[-4000:])


_NUCLEI_SEV = {"info": "low", "low": "low", "medium": "medium", "high": "high", "critical": "critical"}


def _scan_nuclei(target: str, label: str) -> ToolResult:
    url = _url(target)
    code, out, err = _run(
        ["nuclei", "-u", url, "-silent", "-jsonl", "-timeout", "10", "-rate-limit", "60",
         "-severity", "low,medium,high,critical"],
        timeout=420,
    )
    findings: list[ScanFinding] = []
    for line in out.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            item = json.loads(line)
        except ValueError:
            continue
        info = item.get("info", {})
        sev = _NUCLEI_SEV.get(str(info.get("severity", "info")).lower(), "low")
        findings.append(ScanFinding(
            title=info.get("name") or item.get("template-id", "Finding"),
            severity=sev,
            detail=item.get("matched-at") or item.get("host", url),
            recommendation=(info.get("remediation") or "Revise la plantilla afectada y aplique el parche correspondiente."),
        ))
    summary = f"{len(findings)} hallazgos por plantillas." if findings else "Sin hallazgos por plantillas."
    return ToolResult(tool="nuclei", label=label, available=True, status="ok",
                      summary=summary, findings=findings, raw=out[-4000:])


def _scan_wpscan(target: str, label: str) -> ToolResult:
    url = _url(target)
    code, out, err = _run(
        ["wpscan", "--url", url, "--no-banner", "--random-user-agent", "-f", "json",
         "--enumerate", "vp,vt,u", "--disable-tls-checks"],
        timeout=300,
    )
    findings: list[ScanFinding] = []
    summary = "WPScan completado."
    try:
        data = json.loads(out) if out.strip().startswith("{") else {}
    except ValueError:
        data = {}
    if data:
        version = (data.get("version") or {})
        if version.get("number"):
            findings.append(ScanFinding(
                title=f"WordPress {version.get('number')}",
                severity="low",
                detail="Versión de WordPress detectada.",
                recommendation="Mantenga el núcleo de WordPress actualizado.",
            ))
        for slug, plug in (data.get("plugins") or {}).items():
            vulns = plug.get("vulnerabilities") or []
            for v in vulns:
                findings.append(ScanFinding(
                    title=f"Plugin vulnerable: {slug}",
                    severity="high",
                    detail=v.get("title", "Vulnerabilidad conocida"),
                    recommendation="Actualice o elimine el plugin afectado.",
                ))
        users = list((data.get("users") or {}).keys())
        if users:
            findings.append(ScanFinding(
                title="Usuarios enumerables",
                severity="medium",
                detail="Usuarios detectados: " + ", ".join(users[:10]),
                recommendation="Oculte la enumeración de usuarios y use nombres no obvios.",
            ))
        summary = f"{len(findings)} hallazgos en WordPress."
    return ToolResult(tool="wpscan", label=label, available=True, status="ok",
                      summary=summary, findings=findings, raw=out[-4000:])


def _scan_gobuster(target: str, label: str) -> ToolResult:
    url = _url(target)
    if not _WORDLIST.is_file():
        return ToolResult(tool="gobuster", label=label, available=True, status="skipped",
                          summary="Wordlist no disponible.")
    code, out, err = _run(
        ["gobuster", "dir", "-u", url, "-w", str(_WORDLIST), "-q", "-t", "20", "-k",
         "--no-error", "-s", "200,204,301,302,307,401,403"],
        timeout=240,
    )
    findings: list[ScanFinding] = []
    paths: list[str] = []
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("/"):
            paths.append(line.split()[0])
    sensitive = [p for p in paths if any(k in p.lower() for k in (".git", ".env", "backup", "admin", "config", ".sql"))]
    for p in sensitive:
        findings.append(ScanFinding(
            title=f"Ruta sensible expuesta: {p}",
            severity="medium",
            detail="Recurso potencialmente sensible accesible.",
            recommendation="Restrinja o elimine el acceso público a esta ruta.",
        ))
    summary = f"{len(paths)} rutas encontradas ({len(sensitive)} sensibles)." if paths else "Sin rutas encontradas."
    return ToolResult(tool="gobuster", label=label, available=True, status="ok",
                      summary=summary, findings=findings, raw=out[-4000:])


def _scan_hydra(target: str, label: str, options: dict) -> ToolResult:
    if not options.get("bruteforce"):
        return ToolResult(tool="hydra", label=label, available=True, status="skipped",
                          summary="Brute force desactivado (requiere confirmación explícita).")
    login_path = options.get("login_path") or "/login"
    user = options.get("username") or "admin"
    fail = options.get("fail_string") or "Invalid"
    host = _host(target)
    # http-post-form requires the form fields; we use a sane default for common apps.
    form = f"{login_path}:username=^USER^&password=^PASS^:{fail}"
    code, out, err = _run(
        ["hydra", "-l", user, "-P", str(_WORDLIST), "-f", "-t", "4", host, "https-post-form", form],
        timeout=300,
    )
    findings: list[ScanFinding] = []
    for line in out.splitlines():
        if "login:" in line and "password:" in line:
            findings.append(ScanFinding(
                title="Credenciales débiles encontradas",
                severity="critical",
                detail=line.strip(),
                recommendation="Cambie la contraseña por una robusta y active bloqueo por intentos.",
            ))
    summary = "Credenciales débiles detectadas." if findings else "No se encontraron credenciales débiles."
    return ToolResult(tool="hydra", label=label, available=True, status="ok",
                      summary=summary, findings=findings, raw=out[-2000:])


_SCORE_WEIGHTS = {"critical": 25, "high": 15, "medium": 5, "low": 2, "info": 0}


def aggregate(results: list[ToolResult]) -> dict:
    findings: list[dict] = []
    for r in results:
        for f in r.findings:
            findings.append({**asdict(f), "tool": r.tool})
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    penalty = 0
    for f in findings:
        sev = f.get("severity", "low")
        counts[sev] = counts.get(sev, 0) + 1
        penalty += _SCORE_WEIGHTS.get(sev, 0)
    score = max(0, min(100, 100 - penalty))
    return {
        "score": score,
        "high": counts.get("high", 0) + counts.get("critical", 0),
        "medium": counts.get("medium", 0),
        "low": counts.get("low", 0),
        "findings": findings,
        "tools_result": [
            {
                "tool": r.tool,
                "label": r.label,
                "available": r.available,
                "status": r.status,
                "summary": r.summary,
                "findings_count": len(r.findings),
            }
            for r in results
        ],
    }
