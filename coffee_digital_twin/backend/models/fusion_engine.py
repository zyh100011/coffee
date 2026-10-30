"""
三模型结果融合引擎（机理互证升级版）
融合规则整合自 JGY（江桂源）的联合规则集 + 蔡济远原始框架
本届T2.5：保留原规则阈值，仅以可用证据计算，移除缺项默认和无依据处方。
"""
from services.tool_registry import AVAILABLE, wrap_legacy_result, legacy_inputs


def _number(d,key):
    value=d.get(key)
    return value if isinstance(value,(int,float)) and not isinstance(value,bool) else None


def _fuse_risk(a,h,b):
    stress=_number(a,'water_stress'); uptake=_number(h,'root_uptake_ratio')
    score=_number(b.get('summary',b),'growth_score'); gpp=_number(b,'gpp_today')
    nitrogen=a.get('nitrogen_status'); water=h.get('water_status','')
    reasons=[]; levels=[]
    def add(level,text):
        levels.append(level); reasons.append(text+'（工程规则，需现场核查）')
    if stress is not None and uptake is not None and stress>.6 and uptake<.5:
        add('高','APSIM水分胁迫>0.6且HYDRUS吸水比<0.5')
    elif stress is not None and stress>.3 and ('中度' in water or '偏干' in water):
        add('中等','APSIM水分胁迫>0.3且HYDRUS根区偏干')
    if nitrogen in ('偏低','不足') and uptake is not None and uptake<.6:
        add('中等','氮素偏低且根系吸水比<0.6')
    if gpp is not None and gpp<7 and ('干旱' in water or (uptake is not None and uptake<.6)):
        add('中等','BEPS GPP<7且HYDRUS水分受限')
    if score is not None and score<60 and stress is not None and stress<.3 and nitrogen=='正常':
        add('中等','BEPS长势评分<60且APSIM水肥胁迫不明显')
    if '重度' in water or '严重' in water:
        add('高','HYDRUS工程水分分级为重度')
    if b.get('summary',{}).get('risk_level')=='high':
        add('高','BEPS简化模型风险为高')
    if not levels and stress is not None and uptake is not None and score is not None:
        add('低','已提供的指标未触发当前工程风险规则')
    return max(levels,key={'低':1,'中等':2,'高':3}.get) if levels else None,reasons,(['核对实测根区水分、模型假设和现场状态'] if reasons else [])


def merge(apsim_result,hydrus_result,beps_result,task_id=None,plot_id=None):
    ctx={'task_id':task_id,'plot_id':plot_id}
    tools={}
    for name,raw in [('apsim',apsim_result),('hydrus',hydrus_result),('beps',beps_result)]:
        tools[name]=raw if name=='hydrus' else wrap_legacy_result(name,raw,ctx)
    available={name:r for name,r in tools.items() if r.get('status') in AVAILABLE and r.get('source_type')!='demo'}
    a,h,b=[legacy_inputs(available.get(name,{})) for name in ('apsim','hydrus','beps')]
    risk,reasons,suggestions=_fuse_risk(a,h,b)
    fields={'apsim':('stage','water_stress','nitrogen_status','lai'),
            'hydrus':('water_status','root_uptake_ratio','infiltration_depth_cm'),
            'beps':('gpp_today','growth_score')}
    basis={name:'；'.join(f'{key}={r["outputs"][key]}' for key in fields[name] if r['outputs'].get(key) is not None)
           for name,r in available.items()}
    mechanism={name+'_evidence':{'summary':text,'evidence_id':available[name]['evidence_id'],
                               'source_type':available[name]['source_type']} for name,text in basis.items()}
    mechanism['integrated_reason']='；'.join(reasons) or '可用条件不足，无法判断综合风险'
    if 'beps' in available:
        mechanism['dependency_note']='BEPS可能读取APSIM LAI与HYDRUS吸水因子；实际上游：'+str(available['beps']['inputs'].get('upstream',{}))+'；不是相互独立证据'
    status='success' if len(available)==3 else 'partial' if available else 'failed'
    return {'task_id':task_id,'plot_id':plot_id,'status':status,
        'available_evidence':[r['evidence_id'] for r in available.values()],
        'tool_status':{name:{'status':r.get('status'),'source_type':r.get('source_type')} for name,r in tools.items()},
        'dashboard':{'stage':a.get('stage'),'harvest_days':a.get('harvest_days'),'yield_pred_kg_mu':a.get('yield_pred_kg_mu'),
                     'risk_level':risk,'growth_score':b.get('growth_score')},
        'fusion':{'risk_level':risk,'risk_reasons':reasons,'suggestions':suggestions,'model_basis':basis},
        'mechanism_explanation':mechanism,'model_basis':basis,**tools,
        'advice':{'what':'可用工具：'+','.join(available),'how':'请核对实测资料及假设条件',
                  'why':mechanism['integrated_reason'],'model_basis':basis,'source':'rule_fallback_not_evidence',
                  'confidence_note':'规则摘要，非循证建议；未校准、代理和简化模型需区分'}}