"""Operational fail-closed guard. Does not grade or modify candidate results."""
import datetime
import json
from pathlib import Path
import subprocess
import sys


def require_batfish(root, output, timeout=45):
    root, output = Path(root), Path(output)
    output.mkdir(parents=True, exist_ok=False)
    command = [sys.executable, str(root/'scripts/batfish_health.py'), '--query', '--out', str(output/'query')]
    record = {'at':datetime.datetime.now().astimezone().isoformat(), 'command':command, 'timeout_seconds':timeout}
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        record.update(exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)
    except subprocess.TimeoutExpired:
        record.update(exit_code=None, error='Batfish real-query readiness timed out')
    except OSError as exc:
        record.update(exit_code=None, error=str(exc))
    (output/'command.json').write_text(json.dumps(record, indent=2)+'\n')
    if record['exit_code'] != 0:
        raise RuntimeError('Batfish unavailable: stop before another generation; see '+str(output/'command.json'))
    report = json.loads((output/'query/report.json').read_text())
    if report.get('status') != 'pass':
        raise RuntimeError('Batfish readiness did not pass: '+str(output/'query/report.json'))
    return report


def batfish_incident(result):
    """A transport/API exception halts the campaign, parser coverage stays separate."""
    evaluation = result.get('evaluation', {})
    if result.get('rounds'):
        evaluation = json.loads(Path(result['rounds'][-1]).read_text()).get('evaluation', {})
    checks = evaluation.get('checks', []) + evaluation.get('errors', [])
    checks += [c for r in evaluation.get('reports', []) for c in r.get('checks', [])]
    return next((c for c in checks if c.get('property') == 'batfish_environment' and c.get('status') == 'environment_error'), None)
