"""Export a source-grounded development handoff; never touch formal evaluation data."""
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DATABASE_PATH
from services.data_service import query

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / '实验资料/05_开发与训练资料'
MODEL = ROOT / 'coffee_digital_twin/backend/data/hydrus_cases'


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def export():
    OUT.mkdir(parents=True, exist_ok=True)
    args = dict(plot_id='plot_catimor_project', parameter='soil_humidity_layer1_raw',
                start='2026-06-01', end='2026-06-07', agg='daily_mean',
                device_id='source:lujiangba:soil2', unit='%RH',
                data_version='lujiangba-original-20261020')
    result = query(args)
    if result['status'] != 'success' or result['source_type'] != 'observation':
        raise ValueError('本机真实历史查询不可用，不能生成虚构案例')
    db = sqlite3.connect(DATABASE_PATH.as_uri() + '?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    sql = """SELECT COUNT(*) n, AVG(value)/100 mean FROM obs_long
        WHERE plot_id=? AND parameter=? AND date BETWEEN ? AND ?
        AND device_id=? AND unit=? AND data_version=?
        AND value IS NOT NULL AND qc_flag IN ('ok','rain_reset')"""
    params = [args[k] for k in ('plot_id','parameter','start','end','device_id','unit','data_version')]
    check = dict(db.execute(sql, params).fetchone())
    assert check['n'] == result['outputs']['n']
    assert abs(check['mean'] - result['outputs']['mean']) < 1e-9
    lineage = [dict(db.execute('''SELECT o.obs_id,o.value_raw,o.source_row,o.data_version,
        r.path,r.sha256 FROM obs_long o JOIN raw_files r ON r.file_id=o.source_file_id
        WHERE o.obs_id=?''', (oid,)).fetchone()) for oid in result['outputs']['source_obs_ids']]
    db.close()
    sources = {}
    for row in lineage:
        path = Path(row['path'])
        if not path.is_absolute():
            path = ROOT / path
        assert path.is_file(), str(path)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256']
        sources[row['path']] = row['sha256']
    files = {name: json.loads((MODEL / (name + '.json')).read_text(encoding='utf-8'))
             for name in ('case_baseline_0mm','case_irrig_20mm','case_compare_0_vs_20','case_missing_input')}
    b, v, diff = (files[k] for k in ('case_baseline_0mm','case_irrig_20mm','case_compare_0_vs_20'))
    assert b['parameter_version'] == v['parameter_version']
    assert v['inputs']['daily_prec_cm'][0] - b['inputs']['daily_prec_cm'][0] == 2
    for name, value in files.items():
        write(OUT / (name + '.json'), value)
    write(OUT / 'case_history_soil_moisture.json', {
        'case_id':'history_soil_moisture', 'title':'0–15cm 历史土壤水分查询',
        'request':{'method':'POST','path':'/api/data/query','json':args},
        'route_tool':{'name':'query_observation','arguments':args},
        'response':result, 'lineage':lineage, 'source_sha256':sources,
        'verification':{'sql':sql,'parameters':params,'independent_result':check},
        'note':'实测原始百分数按用户指定口径÷100；保留sensor_calibration缺项。n为记录数；daily_mean只聚合曲线，mean为全部有效记录均值。此为开发展示导出，未冻结为data-v1.0。'})
    cases = [
        {'case_id':'history_soil_moisture','input':args,'output_file':'case_history_soil_moisture.json',
         'summary':{k:result['outputs'][k] for k in ('n','mean','min','max','missing_days')},
         'source_type':'observation','page':'coffee_digital_twin/miniprogram/pages/data/data'},
        {'case_id':'hydrus_compare','input':{'start_date':'2026-09-01','baseline_extra_irrigation_mm':0,'variant_extra_irrigation_mm':20},
         'output_files':['case_baseline_0mm.json','case_irrig_20mm.json','case_compare_0_vs_20.json'],
         'summary':diff,'source_type':'simulation_uncalibrated',
         'note':'已有引擎成功运行的历史快照，plot_id=null；不是当前地块的新预测。回放须保留原日期、参数及来源。',
         'page':'coffee_digital_twin/miniprogram/pages/scenario/scenario'},
        {'case_id':'missing_start_date','input':{'adapter_input':{},'entry':'models.hydrus_adapter.run_hydrus_model'},
         'output_file':'case_missing_input.json','summary':{'status':'missing_input','missing_fields':['start_date'],'outputs':{}},
         'source_type':'simulation_uncalibrated','note':'适配层缺参返回案例；不是完整聊天HTTP响应。页面应提示补充日期，不展示数值。',
         'page':'coffee_digital_twin/miniprogram/pages/advice/advice'}]
    write(OUT / 'coffee_cases_zyh.json', {'purpose':'开发训练/小程序展示交接，不是正式测试集', 'cases':cases})
    specs = [
        ('knowledge','监测的第1、2、3层分别是什么深度？',[],{},
         ['第1层0–15cm，第2层15–30cm，第3层30–45cm，来源为用户确认。','监测层号与化学检测报告样品名是两套编号，不能互换。'],
         ['三层对应正确','不把报告样品绑定监测层']),
        ('knowledge','展示用C06土样有哪些检测结果，能代表整块咖啡地吗？',[],{},
         ['C06编号2026T108008；pH 5.0，有机质20.4g/kg，有效磷23.8mg/kg，速效钾129mg/kg。','它是九项化学指标相对九样品中位数/MAD距离最小的工程展示选择，不是全地块统计代表性结论。','报告无采样日期及样品深度，不能套用监测层深度。'],
         ['数值和单位准确','说明工程选择与缺失深度']),
        ('data','查第1层0–15cm在2026年6月1至7日soil2来源的日均土壤水分。',['query_observation'],args,
         [f"共{check['n']}条有效记录，记录均值{result['outputs']['mean']:.8f}cm3/cm3，缺测0天。",'先确认设备、原单位、版本；按用户口径原始百分数÷100，保留标定缺项。','曲线日均值与全记录均值不是同一种加权方式。'],
         ['参数完整且不混来源','数值与真实输出一致','保留换算依据']),
        ('data','降雨表同一天很多行都写25.8mm，能把这些读数直接相加吗？',[],{},
         ['不能直接相加；环境1/2/3表现出日累计计数器特征，并有瞬时归零异常。','environment3在2026-06-11末读数25.8mm，而逐行相加为2598.2mm，不能把重复累计当增量。','按来源核验计数器、日界与复位规则；另一站点变化规律不同。当前尚未生成HYDRUS日雨量。'],
         ['识别累计与增量区别','不将异常归零一概作为复位','不声称已完成日雨量转换']),
        ('model_explain','C06化学报告能直接给HYDRUS提供Ks和持水曲线吗？',[],{},
         ['化学报告没有Ks、持水曲线或van Genuchten水力参数，不能由pH或养分数值直接填写。','当前HYDRUS沿用模板通用水力参数，区域文献只能按来源和适用条件引用，不能冒充本站实测。'],
         ['区分化学与水力指标','不编造参数']),
        ('model_explain','HYDRUS曲线和监测曲线有什么区别？',[],{},
         ['监测曲线来自历史传感器记录，需说明日期、来源及换算口径。','HYDRUS曲线是给定边界、初值及土壤参数下的模拟，案例用simulation_uncalibrated标识。','工程干旱等级阈值没有本站持水量依据，不能作为现场诊断或产量结论。'],
         ['区分实测与模拟','说明模拟输入和默认阈值边界']),
        ('scenario','已有0mm与20mm灌溉案例在40cm第7天差多少？',[],{},
         ['同一参数版本、起始2026-09-01，day7是2026-09-08；7天模拟有day0–7共8个点。','40cm基线0.1342、变化组0.1457cm3/cm3，差0.0115cm3/cm3，即1.15个百分点。','这是模拟差异，不是实测节水/增产效果或实际灌溉处方。'],
         ['数值与单位正确','区分百分点与相对百分比','不外推实际收益']),
        ('scenario','怎么确认额外20mm灌溉确实进入HYDRUS对比？',[],{},
         ['反读两组inputs.daily_prec_cm，首日差为2.0cm，其余6天差0；20mm=2cm。','两组时间窗及parameter_version必须一致，其他输入不变。','差值校验失败时应显示失败并停止解释输出。'],
         ['核验实际反读输入','单位换算正确','控制对比条件']),
        ('missing_or_conflict','帮我看看墒情。',[],{},
         ['先从当前地块目录取得可查询来源、层和日期范围；缺少的来源、层、时间需要澄清。','不默认为40cm，不将最近7天硬套在只有历史数据的时间窗；补充一次仍缺条件则给核查事项。','没有有效数据时明确说明，不补0值或生成曲线。'],
         ['识别真正缺项','不虚构当前日期观测','只进行必要追问']),
        ('missing_or_conflict','不知道模拟开始日期，可以直接先算多浇20mm吗？',[],{},
         ['缺start_date返回missing_input，outputs为空，不调用引擎。','聊天场景还需确认plot_id和灌溉变化量，缺项列出并追问。','引擎失败也不能当成功或静默补演示值。'],
         ['识别start_date缺项','不输出虚构模拟数值'])]
    rows=[]
    refs={}
    paths={
        1:['coffee_digital_twin/backend/data_pipeline/real_data_profile.json'],
        2:['coffee_digital_twin/backend/data_pipeline/soil_report_2026T108.json','coffee_digital_twin/docs/zyh/降雨与土样口径复核_20261022.md'],
        3:['实验资料/05_开发与训练资料/case_history_soil_moisture.json'],
        4:['coffee_digital_twin/docs/zyh/降雨与土样口径复核_20261022.md'],
        5:['coffee_digital_twin/backend/data_pipeline/soil_report_2026T108.json','coffee_digital_twin/docs/zyh/HYDRUS工具说明.md'],
        6:['coffee_digital_twin/backend/services/data_service.py','coffee_digital_twin/docs/zyh/HYDRUS工具说明.md'],
        7:['实验资料/05_开发与训练资料/case_compare_0_vs_20.json'],
        8:['实验资料/05_开发与训练资料/case_compare_0_vs_20.json'],
        9:['coffee_digital_twin/docs/zyh/本地服务接口契约.md','coffee_digital_twin/backend/services/data_service.py'],
        10:['实验资料/05_开发与训练资料/case_missing_input.json']}
    for i,(kind,question,tools,arguments,answer,scoring) in enumerate(specs,1):
        eid = [result['evidence_id']] if i==3 else [b['evidence_id'],v['evidence_id']] if i in (6,7,8) else []
        qid=f'dev_soil_zyh_{i:03d}'
        rows.append(dict(qid=qid,任务类型=kind,问题=question,情境='本项目咖啡基地开发问答；资料证据见配套索引。',
                         证据ID=eid,期望工具=tools,期望参数=arguments,参考回答要点=answer,
                         评分项=scoring,出题人='张源皓（Codex依据已有资料整理，待本人/蔡济远审核）'))
        refs[qid]={'paths':paths[i],'note':'空证据ID表示文档未入循证服务，使用路径定位；不得伪造已检索引用。期望工具为空表示本题使用给定文档/案例，不要求运行模型。'}
        for path in paths[i]:
            assert (ROOT/path).is_file(),path
    (OUT/'dev_soil_zyh.jsonl').write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in rows)+'\n',encoding='utf-8')
    write(OUT/'dev_soil_zyh_evidence.json',refs)
    with (OUT/'发蔡济远_问答与展示案例.md').open('w',encoding='utf-8') as f:
        f.write('# 张源皓：补充训练与展示交接\n\n10条开发问答沿用原JSONL字段，五类各两条。为已有资料整理稿，尚未做人工/专家审核，不属于正式测试集。\n\n')
        f.write('直接发送本目录生成的JSONL、证据索引、案例索引和5份案例JSON即可；无需发送原始数据库或引擎。案例与问答共享证据，不能再当独立正式评测集。\n\n')
        f.write('## 文件\n\n- dev_soil_zyh.jsonl：10题，含问题、参考回答要点与评分项。\n- dev_soil_zyh_evidence.json：每题仓库相对证据路径；空ID待蔡入库后分配，不能伪造。\n- coffee_cases_zyh.json：3个完整展示案例索引。\n- case_history_soil_moisture.json：真实历史查询输入、完整输出、来源行与哈希、独立SQL核验。\n- case_baseline_0mm.json / case_irrig_20mm.json / case_compare_0_vs_20.json：已有HYDRUS输入输出及对比。\n- case_missing_input.json：缺日期的适配层输入输出。\n\n')
        f.write('## 案例摘要\n\n')
        f.write(f"1. 第1层0–15cm，2026-06-01至07，soil2：{check['n']}条，均值{result['outputs']['mean']:.8f}cm³/cm³（约{result['outputs']['mean']*100:.2f}%），无整日缺测；日内记录数并不相同。按用户口径÷100，保留标定缺项，不代表目前墒情。\n")
        f.write('2. HYDRUS第1天额外0/20mm，起始2026-09-01，day7为09-08：40cm含水率0.1342→0.1457，差0.0115cm³/cm³（1.15个百分点）；首日输入差2cm。原始案例plot_id=null，是历史假设模拟；实时生成时mode=live，展示快照时应注明历史回放。不能改写成当前地块的新预测或灌溉处方。\n')
        f.write('3. 适配层不传start_date：missing_input，missing_fields=[start_date]，outputs={}；用于展示缺参追问。不冒充已完成真实大模型聊天联调。\n\n')
        for row in rows:
            f.write(f"## {row['qid']} · {row['任务类型']}\n\n问：{row['问题']}\n\n答："+' '.join(row['参考回答要点'])+'\n\n')
    print(json.dumps({'questions':len(rows),'cases':len(cases),'history_records':check['n'],'mean':check['mean'],'verified_source_files':len(sources)},ensure_ascii=False))


if __name__ == '__main__':
    export()
