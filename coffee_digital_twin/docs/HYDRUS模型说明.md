> 历史文档：本文件保留旧工程设计与归属，不作为当前运行或科学结论依据。当前实现见 zyh/Phase4使用说明.md、zyh/HYDRUS工具说明.md、zyh/功能核对表.md。APSIM为OilPalm代理，BEPS为简化计算，HYDRUS为未校准假设模拟；失败/fallback不进入循证依据。

# HYDRUS 模型说明

文件位置：`backend/models/hydrus_adapter.py`

统一接口：

```python
run_hydrus_model(model_input_json) -> hydrus_result_json
```

张源皓后续对接时，保持返回字段不变即可：

- `water_status`
- `root_uptake_ratio`
- `irrigation_effect`
- `soil_profile_current`
- `soil_moisture_series`
