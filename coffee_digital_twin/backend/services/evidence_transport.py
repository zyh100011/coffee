"""Business-client compatibility only; preserve original results and service algorithms."""
from copy import deepcopy
import math

ANSWER_LABELS={
    'generated_unreviewed':'模型解释，待专业核验；引用有效不代表语义正确。',
    'verified_numeric_summary':'工程校验数值摘要：从工具结果提取，不是模型独立预测。',
    'needs_tool_evidence':'缺少可用工具证据，本轮不能给出数值解释。',
    'generation_check_failed':'生成回答未通过核查，请查看原始证据。'}
REJECTED_ANSWERS={'needs_tool_evidence','generation_check_failed'}


def answer_results(results):
    """Add explicit units/aliases for the delivered scalar contract; never fill data."""
    prepared=deepcopy(results);annotations=[]
    for result in prepared:
        outputs=result['outputs'];units=result['units'];added={};aliases={}
        if result['tool']=='data_query':
            unit=units.get('value')
            if isinstance(unit,str) and unit:
                for key in ('mean','min','max','first','last'):
                    if key in outputs and key not in units:units[key]=unit;added[key]='units.value'
            for key,unit in {'n':'条','missing_days':'天','excluded_count':'条','series_total':'条','offset':'条','limit':'条','next_offset':'条'}.items():
                if key in outputs and key not in units:units[key]=unit;added[key]='query_count_definition'
        elif result['tool']=='hydrus':
            if 'infiltration_depth_cm' in outputs and 'infiltration_depth_cm' not in units and units.get('depth')=='cm':
                units['infiltration_depth_cm']='cm';added['infiltration_depth_cm']='units.depth'
            theta_unit=units.get('theta')
            if isinstance(theta_unit,str) and theta_unit:
                # Fixed documented profile fields; nested series remain original evidence.
                for index,point in enumerate(outputs.get('soil_profile_current',[])):
                    depth=point.get('depth_cm');theta=point.get('theta')
                    if depth not in (10,20,40,60,100) or isinstance(theta,bool) or not isinstance(theta,(int,float)) or not math.isfinite(theta):continue
                    name=f'profile_theta_{int(depth)}cm'
                    if name not in outputs:
                        outputs[name]=theta;units[name]=theta_unit
                        aliases[name]=f'outputs.soil_profile_current[{index}].theta'
        if added or aliases:
            annotations.append({'evidence_id':result['evidence_id'],'adapter':'scalar-units-v1',
                'unit_mappings':added,'output_aliases':aliases})
    return prepared,annotations


def citation_source(citation,results,mock=False):
    for result in results:
        if result['evidence_id']==citation['evidence_id']:return result['source_type']
    if mock:return 'demo'
    if citation.get('doc_id') in {'TOOL-APSIM','TOOL-HYDRUS','TOOL-BEPS'}:
        return 'internal_tool_description'
    return citation.get('source_type') if citation.get('source_type') in {'literature','internal_tool_description'} else 'literature'
