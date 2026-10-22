from models.fusion_engine import merge
from services.tool_registry import wrap_legacy_result
from services.tool_result import make_tool_result


def test_unavailable_is_not_evidence():
    a=wrap_legacy_result('apsim',{'status':'success','water_stress':.1},{})
    b=wrap_legacy_result('beps',{'status':'ok','growth_score':80},{'weather_series':[
        {'source':'observation','tmin':20,'tmax':30,'radiation_mj':18}]})
    h=make_tool_result(tool='hydrus',status='failed')
    result=merge(a,h,b)
    assert result['status']=='partial' and 'hydrus' not in result['model_basis']
    assert 'hydrus_evidence' not in result['mechanism_explanation']
    assert result['dashboard']['risk_level'] is None
    assert 'dependency_note' in result['mechanism_explanation']


def test_no_default_normal_or_demo_evidence():
    a=wrap_legacy_result('apsim',{'status':'fallback','lai':9},{})
    b=wrap_legacy_result('beps',{'status':'ok','growth_score':80},{})
    result=merge(a,make_tool_result(tool='hydrus'),b)
    assert result['status']=='failed' and result['model_basis']=={}
    assert all(v is None for v in result['dashboard'].values())
    assert result['fusion']['risk_reasons']==[]


def test_expert_record_is_unverified(client):
    assert all(x['verification_status']=='unverified' for x in client.get('/api/model/validation_cases').get_json())
