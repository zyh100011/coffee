import json


def test_no_plot_no_invented_records(client):
    from api.model_api import build_model_input
    assert client.post('/api/model/run',json={}).status_code==400
    client.post('/api/plot/init',json={'plot_id':'p','plot_name':'fixture'})
    result=build_model_input('task',start_date='2026-09-01')
    assert result['farm_operations']==[] and result['weather_series']==[]
    assert result['data_sources']=={'weather':'none','farm_operations':'none'}
    assert 'farm_operations' in result['missing_fields'] and result['warnings']


def test_selection_is_plot_scoped(client):
    from database.init_db import get_connection
    for plot in ('p','q'):
        client.post('/api/plot/init',json={'plot_id':plot,'plot_name':plot})
    assert client.get('/api/dashboard').status_code==400
    assert client.post('/api/advice/generate',json={}).status_code==400
    with get_connection() as conn:
        for plot in ('p','q'):
            conn.execute('INSERT INTO model_results VALUES (?,?,?,?)',
                (plot,plot,json.dumps({'task_id':plot,'plot_id':plot,'dashboard':{'marker':plot}}),'2026-09-01'))
    result=client.get('/api/dashboard?plot_id=p').get_json()
    assert result['plot_id']=='p' and result['result_selected_by']=='plot_latest'
    assert client.get('/api/model/result/q?plot_id=p').status_code==404
