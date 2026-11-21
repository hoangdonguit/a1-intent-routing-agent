"""Finish only the frozen six-trajectory pilot; never reopen terminal verdicts."""
import argparse,json,os,signal,subprocess,sys,time,fcntl
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runs/bgp-plan-study-20261120-02'
EXPECTED={c+'--'+m for c in ['dev_ebgp_prefix_01','dev_ebgp_prefix_02'] for m in ['B1','A1','A2']}
def progress(state):
    return (state['calls'],sorted((k,v['status'],len(v['rounds'])) for k,v in state['trajectories'].items()))
def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('--resume',action='store_true');a=p.parse_args()
    if os.geteuid()!=0:raise RuntimeError('Start through bash ops/finish_bgp_plan_pilot.sh')
    with (OUT/'finish.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        stop=OUT/'STOP'
        if a.resume:stop.unlink(missing_ok=True)
        signal.signal(signal.SIGINT,lambda *_:stop.touch());signal.signal(signal.SIGTERM,lambda *_:stop.touch())
        batch=OUT/('finish-'+str(time.time_ns()));batch.mkdir()
        for index in range(26):
            state=json.loads((OUT/'state.json').read_text())
            if stop.exists():print('PAUSED: stop flag retained',flush=True);return
            if state.get('blocked'):raise RuntimeError('Calibration blocked; do not generate')
            if any(t.get('inflight') for t in state['trajectories'].values()):raise RuntimeError('Uncertain previous call; audit instead of retry')
            terminal={k for k,v in state['trajectories'].items() if v['status'] in ['pass','fail','environment_error']}
            if EXPECTED<=terminal:print('FINISHED: six trajectories terminal; no retries or best-result selection',flush=True);return
            if state['calls']>=26:raise RuntimeError('Frozen26generation cap reached')
            before=progress(state);log=batch/('session-'+str(index)+'.log');print('START bounded session',index,'log',log,flush=True)
            with log.open('w') as f:
                r=subprocess.run([sys.executable,str(ROOT/'ops/bgp_plan_study.py'),'run','--pilot','--seconds','1800','--calls','2'],stdout=f,stderr=subprocess.STDOUT)
            state=json.loads((OUT/'state.json').read_text());print('END calls_started',state['calls'],'restore',state.get('last_restore',{}).get('status'),flush=True)
            if r.returncode:raise RuntimeError('Session failed; see '+str(log))
            if state.get('last_restore',{}).get('status')!='pass':raise RuntimeError('Restore incomplete; stop before another session')
            if stop.exists():print('PAUSED after restore',flush=True);return
            if progress(state)==before:raise RuntimeError('No generation/trajectory progress; stop instead of looping')
        raise RuntimeError('Bounded session limit reached')
if __name__=='__main__':main()
