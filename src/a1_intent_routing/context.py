"""Exact local Qwen context preflight. Never calls a generation/token-count LLM API."""
import hashlib,json,subprocess
from pathlib import Path

EXPLICIT_REPAIR_INSTRUCTION = 'The previous complete configuration failed verification. Revise it to fix the listed violations while preserving checks already satisfied and all original intent constraints. Do not repeat the failed configuration. Return the complete corrected configs JSON for every router, not an explanation or a patch.'

class ContextBudgetError(RuntimeError):pass

class ContextGuard:
    def __init__(self,root,margin=64):
        self.root=Path(root);self.margin=margin;self.cache={}
    def measure(self,payload):
        text=json.dumps({'messages':payload['messages']},ensure_ascii=False)
        key=hashlib.sha256(text.encode()).hexdigest()
        if key not in self.cache:
            try:
                r=subprocess.run([str(self.root/'runs/tokenizer-venv/bin/python'),str(self.root/'scripts/count_context.py')],input=text,text=True,capture_output=True,timeout=30)
                if r.returncode:raise ContextBudgetError('Local tokenizer preflight unavailable: '+r.stderr[-1000:])
                self.cache[key]=json.loads(r.stdout)
            except (OSError,subprocess.TimeoutExpired,ValueError) as exc:raise ContextBudgetError(str(exc)) from exc
        count=self.cache[key];context=payload['options']['num_ctx'];reserved=payload['options']['num_predict']
        return dict(count,context_limit=context,reserved_output=reserved,margin=self.margin,
                    within_budget=count['prompt_tokens']+reserved+self.margin<=context)


def bounded_feedback(evaluation,max_observed_chars=1200):
    # Evidence stays in the complete local verification report. The model gets
    # bounded observations and a stable prefix of violations, not oracle inventory.
    fields=('device','property','expected','observed','evidence','tool');errors=[]
    for finding in evaluation.get('errors',[]):
        if finding.get('status')!='fail':continue
        error={k:finding.get(k) for k in fields}
        observed=json.dumps(error['observed'],ensure_ascii=False)
        if len(observed)>max_observed_chars:
            error['observed']={'summary':observed[:max_observed_chars],'truncated':True}
        if isinstance(error['evidence'],list):error['evidence']=error['evidence'][:1]
        errors.append(error)
    return errors


def repair_messages(initial,last_response,method,evaluation,request,guard,feedback_instruction=None):
    assistant={'role':'assistant','content':last_response.get('message',{}).get('content','')}
    if method=='A1':
        # Literal payload, independent of tool names/errors/count/expected/observed.
        return [*initial,assistant,{'role':'user','content':'FAIL'}],{'policy':'initial_plus_latest','feedback':'binary'}
    errors=bounded_feedback(evaluation)
    if not errors:raise ContextBudgetError('Failed evaluation lacks structured violations')
    for count in range(len(errors),0,-1):
        body={'status':'fail','errors':errors[:count]}
        if feedback_instruction is not None:body['instruction']=feedback_instruction
        feedback=json.dumps(body,ensure_ascii=False)
        messages=[*initial,assistant,{'role':'user','content':feedback}]
        payload=dict(request,messages=messages)
        if guard.measure(payload)['within_budget']:
            return messages,{'policy':'initial_plus_latest','errors_available':len(errors),'errors_sent':count,'observed_char_limit':1200,'evidence_per_error':1}
    raise ContextBudgetError('Initial public input + latest candidate + one structured violation do not fit with reserved output')
