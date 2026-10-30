from tools.verify_hydrus_stability import decision


def test_stability_decision_rejects_failure_timeout_and_parameter_drift():
    runs=[{'status':'success','duration_s':.1,'contract_ok':True,'input_verified':True,'parameter_version':'p'} for _ in range(10)]
    assert decision(runs)=='live'
    for key,value in [('status','failed'),('duration_s',31),('input_verified',False),('parameter_version','different')]:
        changed=[dict(r) for r in runs]; changed[9][key]=value
        assert decision(changed)=='replay'
    assert decision(runs[:8])=='replay'
