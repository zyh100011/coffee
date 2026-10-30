def test_plot_completeness_and_no_defaults(client):
    assert client.post('/api/plot/init',json={}).status_code==400
    r=client.post('/api/plot/init',json={'plot_id':'p','plot_name':'真实待补地块','latitude':0,'field_sources':{'latitude':'field_record'}}).get_json()
    assert r['plot']['area_mu'] is None and r['plot']['tree_age'] is None and r['plot']['latitude']==0
    p=client.get('/api/plot/p').get_json()['plot']
    assert p['completeness']['filled']==2 and p['completeness']['total']==12
    assert 'area_mu' in p['completeness']['missing']
    assert client.get('/api/plot/list').get_json()['items'][0]['plot_id']=='p'
    from services.plot_context import load_plot_context
    assert load_plot_context('p')['known']=={'latitude':0}
def test_farm_requires_plot_and_positive_quantity(client):
    assert client.get('/api/farmop/list').status_code==400
    assert client.post('/api/farmop/add',json={}).status_code==400
    client.post('/api/plot/init',json={'plot_id':'p','plot_name':'p'})
    for value in (None,'',0,-1,True):
        assert client.post('/api/farmop/add',json={'plot_id':'p','date':'2026-09-01','amount':value,'unit':'mm'}).status_code==400
    assert client.post('/api/farmop/add',json={'plot_id':'p','date':'2026-09-01','amount':20,'unit':'mm'}).status_code==200
    assert client.get('/api/farmop/list?plot_id=p').get_json()['items'][0]['amount']==20
