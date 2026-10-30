"""Local evidence transport and contract checks; no external fallback."""
import json
import os
import requests
from config import EVIDENCE_SERVICE_URL
class EvidenceServiceError(Exception):
    def __init__(self,code,msg,detail=''):
        super().__init__(msg); self.code=code; self.detail=detail
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
        if 'retrieval_trace' in r and (not isinstance(r['retrieval_trace'],dict) or ('status' in r['retrieval_trace'] and not isinstance(r['retrieval_trace']['status'],str))): raise ValueError('invalid retrieval trace')
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
        if kind=='health':
            response=requests.get(url+'/health',timeout=budget,allow_redirects=False)
        else:
            if not isinstance(payload,dict) or not isinstance(payload.get('message'),str) or not 1<=len(payload['message'])<=4000:
                raise ValueError('message must contain 1 to 4000 characters')
            if len(json.dumps(payload,allow_nan=False).encode('utf-8'))>262144:
                raise ValueError('request exceeds service byte limit')
            token=os.environ.get('EVIDENCE_API_TOKEN','').strip()
            headers={'Authorization':'Bearer '+token} if token else {}
            response=requests.post(url+'/v1/'+kind,json=payload,headers=headers,timeout=budget,allow_redirects=False)
        if response.status_code in (401,403):
            raise EvidenceServiceError('E_EVIDENCE_DOWN','循证服务鉴权失败，请在后端配置有效的访问令牌')
        if 300<=response.status_code<400:
            raise EvidenceServiceError('E_EVIDENCE_DOWN','循证服务地址发生重定向，请确认业务API地址')
        if response.status_code>=400:
            try: body=response.json(); info=str(body.get('error',''))+':'+str(body.get('message',''))
            except ValueError: info=response.text
            code='E_EVIDENCE_DOWN' if response.status_code>=500 else 'E_EVIDENCE_INVALID'
            raise EvidenceServiceError(code,'循证服务返回错误',(kind+':HTTP '+str(response.status_code)+':'+info)[:200])
        try: data=response.json()
        except ValueError as e: raise EvidenceServiceError('E_EVIDENCE_INVALID','本地循证响应格式不符',kind+':non-json') from e
        try: return validate(kind,data)
        except (ValueError,TypeError) as e: raise EvidenceServiceError('E_EVIDENCE_INVALID','本地循证响应格式不符',(kind+':'+str(e))[:200]) from e
    except requests.Timeout as e: raise EvidenceServiceError('E_EVIDENCE_TIMEOUT','本地循证服务超时') from e
    except requests.RequestException as e: raise EvidenceServiceError('E_EVIDENCE_DOWN','本地循证服务不可用') from e
    except (ValueError,TypeError) as e: raise EvidenceServiceError('E_EVIDENCE_INVALID','本地循证响应格式不符') from e
def route(payload,timeout=None): return _request('route',payload,timeout)
def answer(payload,timeout=None): return _request('answer',payload,timeout)
def health(timeout=None): return _request('health',timeout=timeout)
