"""Local evidence transport and contract checks; no external fallback."""
import requests
from config import EVIDENCE_SERVICE_URL
class EvidenceServiceError(Exception):
    def __init__(self,code,msg):
        super().__init__(msg); self.code=code
def validate(kind,r):
    if not isinstance(r,dict): raise ValueError('response must be object')
    if 'mock' in r and not isinstance(r['mock'],bool): raise ValueError('mock must be bool')
    if kind=='route':
        if r.get('intent') not in {'data_query','knowledge','model_explain','scenario','other'}: raise ValueError('invalid intent')
        if not isinstance(r.get('tool_calls'),list) or not isinstance(r.get('missing_fields'),list): raise ValueError('invalid route lists')
        for c in r['tool_calls']:
            if not isinstance(c,dict) or not isinstance(c.get('name'),str) or not isinstance(c.get('arguments'),dict): raise ValueError('invalid tool call')
        if any(not isinstance(k,str) for k in r['missing_fields']): raise ValueError('invalid missing fields')
        if r.get('clarify_question') is not None and not isinstance(r['clarify_question'],str): raise ValueError('invalid clarification')
    elif kind=='answer':
        if not isinstance(r.get('answer'),str): raise ValueError('answer missing')
        for key in ('citations','claims','limitations','check_items'):
            if not isinstance(r.get(key),list): raise ValueError(key+' must be list')
        for c in r['citations']:
            if not isinstance(c,dict) or any(not isinstance(c.get(k),str) for k in ('evidence_id','doc_id','title','locator','snippet')): raise ValueError('invalid citation')
        for c in r['claims']:
            if not isinstance(c,dict) or not isinstance(c.get('text'),str) or not isinstance(c.get('evidence_ids'),list) or any(not isinstance(e,str) for e in c['evidence_ids']): raise ValueError('invalid claim')
        if any(not isinstance(s,str) for key in ('limitations','check_items') for s in r[key]): raise ValueError('invalid limitations/check_items')
    elif kind=='health' and not isinstance(r.get('status'),str): raise ValueError('status missing')
    return r
def _request(kind,payload=None,timeout=None):
    limit=20 if kind=='route' else 60 if kind=='answer' else 5
    budget=min(limit,timeout if timeout is not None else limit)
    if budget<=0: raise EvidenceServiceError('E_EVIDENCE_TIMEOUT','服务时间预算耗尽')
    try:
        url=EVIDENCE_SERVICE_URL.rstrip('/')
        response=requests.get(url+'/health',timeout=budget) if kind=='health' else requests.post(url+'/v1/'+kind,json=payload,timeout=budget)
        response.raise_for_status(); return validate(kind,response.json())
    except requests.Timeout as e: raise EvidenceServiceError('E_EVIDENCE_TIMEOUT','本地循证服务超时') from e
    except requests.RequestException as e: raise EvidenceServiceError('E_EVIDENCE_DOWN','本地循证服务不可用') from e
    except (ValueError,TypeError) as e: raise EvidenceServiceError('E_EVIDENCE_INVALID','本地循证响应格式不符') from e
def route(payload,timeout=None): return _request('route',payload,timeout)
def answer(payload,timeout=None): return _request('answer',payload,timeout)
def health(timeout=None): return _request('health',timeout=timeout)
