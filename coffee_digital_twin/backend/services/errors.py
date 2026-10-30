"""Public error vocabulary; internal exception details stay in server logs."""
import uuid

ERRORS={
 'E_PLOT_REQUIRED':('请选择当前地块',False),
 'E_PARAM_INVALID':('请核对输入条件',False),
 'E_TOOL_NOT_ALLOWED':('工具请求未被允许',False),
 'E_HYDRUS_TIMEOUT':('计算超时，已保留输入，可重试或改用历史结果',True),
 'E_HYDRUS_FAILED':('HYDRUS计算失败，请查看原因或改用历史结果',True),
 'E_HYDRUS_UNAVAILABLE':('HYDRUS引擎不可用，可使用历史回放',True),
 'E_EVIDENCE_TIMEOUT':('本地循证服务超时，可重试',True),
 'E_EVIDENCE_DOWN':('智能解释暂不可用，可直接查询农情',True),
 'E_EVIDENCE_INVALID':('循证服务响应格式不符',True),
 'E_EVIDENCE_NOT_FOUND':('证据未找到：该主张未核验',False),
 'E_DATA_EMPTY':('该地块暂无已入库的数据',False),
 'E_INTERNAL':('服务暂时出错，请重试',True),
}

def envelope(code,message=None,trace_id=None):
    text,retry=ERRORS.get(code,ERRORS['E_INTERNAL'])
    return {'status':'error','code':code if code in ERRORS else 'E_INTERNAL',
            'message':message or text,'retryable':retry,'trace_id':trace_id or 'tr_'+uuid.uuid4().hex}

def hydrus_code(results):
    if any(r.get('status')=='timeout' for r in results): return 'E_HYDRUS_TIMEOUT'
    if any('unavailable' in r.get('model_version','') or any('引擎不存在' in w or 'engine_unavailable' in w for w in r.get('warnings',[])) for r in results): return 'E_HYDRUS_UNAVAILABLE'
    return 'E_HYDRUS_FAILED'
