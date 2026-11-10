"""Read-only bounded probes; missing optional tools are reports, not code failures."""
import json
import platform
import shutil
import subprocess
from datetime import datetime, timezone

PROBES = {
    "cpu": ["lscpu", "--json"],
    "ram": ["free", "-b"],
    "disk": ["df", "-h", "."],
    "gpu": ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
    "docker": ["docker", "version", "--format", "{{json .}}"],
    "containerlab": ["containerlab", "version"],
    "ollama_cli": ["ollama", "--version"],
    "ollama_service": ["curl", "--noproxy", "*", "--max-time", "3", "--silent", "--show-error", "--fail", "http://127.0.0.1:11434/api/version"],
    "frr_cli": ["vtysh", "--version"],
}


def probe(argv, timeout=5):
    executable = shutil.which(argv[0])
    if executable is None:
        return {"status": "missing", "argv": argv}
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "argv": argv}
    except OSError as exc:
        return {"status": "unavailable", "argv": argv, "error": str(exc)}
    return {"status": "available" if result.returncode == 0 else "unavailable",
            "argv": argv, "returncode": result.returncode,
            "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}


def main():
    report = {"observed_at": datetime.now(timezone.utc).isoformat(),
              "python": platform.python_version(), "platform": platform.platform(),
              "probes": {name: probe(argv) for name, argv in PROBES.items()},
              "not_checked": ["Batfish service/API and feature coverage", "FRR image/syntax", "container creation/network privileges", "model inference", "lab connectivity"],
              "meaning": "Dependency observations only; no lab/model/verifier was run. Missing tools do not block offline work."}
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
