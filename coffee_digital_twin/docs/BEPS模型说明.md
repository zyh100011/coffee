> 历史文档：本文件保留旧工程设计与归属，不作为当前运行或科学结论依据。当前实现见 zyh/Phase4使用说明.md、zyh/HYDRUS工具说明.md、zyh/功能核对表.md。APSIM为OilPalm代理，BEPS为简化计算，HYDRUS为未校准假设模拟；失败/fallback不进入循证依据。

# BEPS 模型说明

文件位置：`backend/models/beps_adapter.py`

统一接口：

```python
run_beps_model(model_input_json) -> beps_result_json
```

简光耀后续对接时，保持返回字段不变即可：

- `growth_score`
- `gpp_today`
- `npp_today`
- `et_today`
- `carbon_sink_kgC_mu`
- `gpp_series`
- `npp_series`
- `et_series`
- `beps_risk`
