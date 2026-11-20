"""Local exact tokenizer/template count for the existing pinned Qwen, no inference."""
import hashlib,json,sys
from pathlib import Path
from jinja2 import Environment
from tokenizers import Tokenizer
ROOT=Path(__file__).resolve().parents[1]
config=json.loads((ROOT/'configs/tokenizer.json').read_text());directory=ROOT/'models/tokenizer-qwen3'
for item in config['files']:
 path=directory/item['file']
 if hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:raise SystemExit('Tokenizer file hash mismatch')
template_path=directory/'ollama-template.jinja'
if hashlib.sha256(template_path.read_bytes()).hexdigest()!=config['ollama_template_sha256']:raise SystemExit('Ollama template hash mismatch')
tokenizer=Tokenizer.from_file(str(directory/'tokenizer.json'))
if tokenizer.truncation is not None:raise SystemExit('Tokenizer truncation must be disabled')
request=json.load(sys.stdin)
rendered=Environment().from_string(template_path.read_text()).render(messages=request['messages'],tools=None,add_generation_prompt=True)
print(json.dumps({'prompt_tokens':len(tokenizer.encode(rendered,add_special_tokens=False).ids),'rendered_sha256':hashlib.sha256(rendered.encode()).hexdigest(),'tokenizer_revision':config['revision'],'template_sha256':config['ollama_template_sha256']}))
