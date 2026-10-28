from database.init_db import get_connection

def test_single_base_default_scope_and_edit_preserves_context(client,flask_app,monkeypatch):
    client.post('/api/plot/init',json={'plot_id':'plot_catimor_project','plot_name':'基地'})
    client.post('/api/plot/init',json={'plot_id':'old','plot_name':'旧档案'})
    import json
    with get_connection() as conn:
        raw=json.loads(conn.execute("SELECT raw_json FROM plots WHERE plot_id='plot_catimor_project'").fetchone()[0])
        raw['layer_intervals_cm']=[[0,15],[15,30],[30,45]]
        conn.execute("UPDATE plots SET raw_json=? WHERE plot_id='plot_catimor_project'",(json.dumps(raw),))
    monkeypatch.setitem(flask_app.config,'SINGLE_PLOT_ID','plot_catimor_project')
    rows=client.get('/api/plot/list').get_json()
    assert len(rows['items'])==1 and rows['items'][0]['single_base']
    assert client.get('/api/data/catalog').get_json()['plot_id']=='plot_catimor_project'
    assert client.get('/api/farmop/list').status_code==200
    assert client.post('/api/plot/init',json={'plot_name':'新档案'}).status_code==400
    assert client.get('/api/plot/old').status_code==404
    updated=client.post('/api/plot/init',json={'plot_id':'plot_catimor_project','plot_name':'基地','coffee_variety':'卡蒂姆'}).get_json()
    assert updated['plot']['layer_intervals_cm']==[[0,15],[15,30],[30,45]]
    assert updated['plot']['plot_name']=='云南普洱卡蒂姆咖啡基地'
