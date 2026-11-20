"""Local-only Ollama HTTP client; generation calls have no retry path."""
import json
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler


class LocalAPIError(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise LocalAPIError('Redirect rejected for local Ollama endpoint')


class OllamaClient:
    def __init__(self, endpoint='http://127.0.0.1:11434'):
        parsed=urlparse(endpoint)
        if parsed.scheme!='http' or parsed.hostname not in ('127.0.0.1','localhost','::1') or parsed.username or parsed.password:
            raise ValueError('Ollama endpoint must be loopback HTTP without credentials')
        self.endpoint=endpoint.rstrip('/')
        self.opener=build_opener(ProxyHandler({}),NoRedirect())

    def request(self,path,payload=None,timeout=10,raw_path=None):
        data=None if payload is None else json.dumps(payload,ensure_ascii=False).encode()
        request=Request(self.endpoint+path,data=data,headers={'Content-Type':'application/json'})
        started=time.monotonic(); body=b''
        try:
            with self.opener.open(request,timeout=timeout) as response:
                body=response.read()
            value=json.loads(body)
            if isinstance(value,dict) and value.get('error'):
                raise LocalAPIError(str(value['error']))
            return value,time.monotonic()-started
        except HTTPError as exc:
            body=exc.read()
            raise LocalAPIError(f'HTTP {exc.code}: {body.decode(errors="replace")}') from exc
        except (OSError,ValueError) as exc:
            raise LocalAPIError(str(exc)) from exc
        finally:
            if raw_path is not None:
                Path(raw_path).write_bytes(body)

    def chat_once(self,payload,timeout,raw_path):
        # Exactly one HTTP request. Metadata calls never generate text.
        return self.request('/api/chat',payload,timeout,raw_path)


def metric_snapshot(response):
    fields={'input_tokens':'prompt_eval_count','output_tokens':'eval_count',
            'api_total_seconds':'total_duration','api_load_seconds':'load_duration',
            'api_prompt_eval_seconds':'prompt_eval_duration','api_eval_seconds':'eval_duration'}
    values={}; unavailable={}
    for target,source in fields.items():
        value=response.get(source)
        if type(value) not in (int,float) or value<0:
            values[target]=None; unavailable[target]=f'API field {source} missing or invalid'
        else:
            values[target]=value/1e9 if target.endswith('_seconds') else value
    return values,unavailable
