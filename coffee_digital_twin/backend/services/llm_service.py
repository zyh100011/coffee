"""
AI 农技建议服务 —— 智谱 GLM-4-Flash（完全免费）
- 一次性建议：generate_advice()，供 fusion_engine.py 调用
- 多轮聊天：chat_with_context()，供 advice_api.py 的 /chat 接口调用

配置方式：
  backend/.env 文件中写入：ZHIPU_API_KEY=你的Key
  或环境变量：set ZHIPU_API_KEY=xxx

注册地址：https://open.bigmodel.cn  （GLM-4-Flash 完全免费）

升级内容：
  - generate_advice() 接收 mechanism_evidence 参数
  - LLM 输出格式扩展为 what/how/why/model_basis/confidence_note 五段
  - system prompt 强调"只基于三模型结果解释，不编造数值"
  - 规则兜底也同步输出 model_basis 结构
"""
import json
import os
import re
from typing import List, Optional

import requests

_ZHIPU_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
_MODEL = "glm-4-flash"


# ---------------------------------------------------------------------------
# API Key 读取
# ---------------------------------------------------------------------------

def _load_api_key() -> str:
    key = os.getenv("ZHIPU_API_KEY", "")
    if key:
        return key
    env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
    try:
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("ZHIPU_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return ""


# ---------------------------------------------------------------------------
# 系统提示：将三模型结果注入 System Message，整个对话共享
# ---------------------------------------------------------------------------

def build_system_prompt(
    apsim: dict,
    hydrus: dict,
    beps: dict,
    mechanism_evidence: Optional[dict] = None,
) -> str:
    beps_summary = beps.get("summary", {})
    growth_score = beps.get("growth_score", beps_summary.get("growth_score", "-"))
    beps_risk = beps.get("beps_risk", beps_summary.get("risk_level", "-"))
    gpp = beps.get("gpp_today", beps_summary.get("gpp_today", "-"))
    npp = beps.get("npp_today", beps_summary.get("npp_today", "-"))
    canopy_status = beps.get("canopy_status", beps_summary.get("canopy_status", "-"))

    integrated_reason = ""
    if mechanism_evidence:
        integrated_reason = f"""
【三模型机理综合判断】
{mechanism_evidence.get('integrated_reason', '')}
"""

    return f"""你是一位专业的云南咖啡种植 AI 农技顾问，精通 APSIM 作物模型、HYDRUS 土壤水分模型和 BEPS 生态模型。

【重要规则】
1. 你不能替代 APSIM、HYDRUS、BEPS 进行科学计算。
2. 你只能基于后端提供的三模型结果进行解释，不要编造输入中不存在的数值。
3. why 仅引用本轮可用证据，缺项明确说明。
4. model_basis 仅列出可用模型依据。

用户的咖啡园当前三模型模拟结果如下，请基于这些数据回答用户的所有问题：

【APSIM-Coffee 作物生长模型（作物层）】
- 生育期：{apsim.get("stage", "-")}
- 预测亩产：{apsim.get("yield_pred_kg_mu", "-")} kg/亩
- 水分胁迫指数：{apsim.get("water_stress", "-")}（0=无胁迫，1=严重）
- 氮素状态：{apsim.get("nitrogen_status", "正常")}
- 叶面积指数 LAI：{apsim.get("lai", "-")}

【HYDRUS-1D 土壤水分模型（土壤层）】
- 土壤水分状态：{hydrus.get("water_status", "-")}
- 根系吸水效率：{hydrus.get("root_uptake_ratio", "-")}（越接近1越好）
- 入渗深度：{hydrus.get("infiltration_depth_cm", "-")} cm
{integrated_reason}
【BEPS-Lite 生态模型（冠层层）】
- 长势评分：{growth_score}/100
- 生态风险：{beps_risk}
- GPP（总初级生产力）：{gpp} gC/m²/天
- NPP（净初级生产力）：{npp} gC/m²/天
- 冠层状态：{canopy_status}

请用简洁、专业、接地气的语言回答，每条建议控制在 120 字以内。"""


# ---------------------------------------------------------------------------
# LLM 调用（通用，接受完整 messages 列表）
# ---------------------------------------------------------------------------

def _call_glm(messages: List[dict], api_key: str) -> str:
    resp = requests.post(
        _ZHIPU_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": _MODEL, "messages": messages, "temperature": 0.5, "max_tokens": 600},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


# ---------------------------------------------------------------------------
# 一次性建议（升级版：接收机理证据，输出 model_basis）
# ---------------------------------------------------------------------------

def generate_advice(
    apsim_result: dict,
    hydrus_result: dict,
    beps_result: dict,
    mechanism_evidence: Optional[dict] = None,
) -> dict:
    # AI辅助生成-DeepSeek-V3 - 2026年5月1日 14:05:30 - 构建系统提示词并请求大语言模型接口
    if os.getenv('LEGACY_GLM','0') != '1':
        tool, result = next(((name,r) for name,r in [('hydrus',hydrus_result),('apsim',apsim_result),('beps',beps_result)] if r.get('task_id')), (None,{}))
        if result.get('task_id'):
            from services.assistant_service import chat
            response=chat({'message':'解释模型结果','plot_id':result.get('plot_id'),
                'supplement':{'task_id':result['task_id'],'tool':tool},'history':[]})
            texts=[b.get('text','') for b in response['blocks'] if b['type'] in {'text','warning'}]
            return {'what':'；'.join(texts),'how':'查看证据及现场核查事项','why':'本地助手流程',
                    'model_basis':{},'source':'local_assistant','assistant':response}
        return _rule_fallback(apsim_result,hydrus_result,beps_result,mechanism_evidence)
    api_key = _load_api_key() if os.getenv('LEGACY_GLM','0') == '1' else ''
    if api_key:
        try:
            system = build_system_prompt(
                apsim_result, hydrus_result, beps_result, mechanism_evidence
            )
            user_msg = (
                "请基于后端提供的 APSIM/HYDRUS/BEPS 三模型结果，"
                "给出当前咖啡园最重要的一条农技建议。\n"
                "严格按照如下 JSON 格式输出，不要输出 JSON 以外的内容，"
                "不要编造输入数据中没有的数值：\n"
                '{"what":"当前状态（40字）",'
                '"how":"具体操作建议（60字）",'
                '"why":"为什么这样做，仅引用可用证据（80字）",'
                '"model_basis":{'
                '"apsim":"APSIM-Coffee的模型依据（30字）",'
                '"hydrus":"HYDRUS-1D的模型依据（30字）",'
                '"beps":"BEPS-Lite的模型依据（30字）"'
                '},'
                '"confidence_note":"该建议基于三模型机理证据生成"}'
            )
            content = _call_glm(
                [{"role": "system", "content": system},
                 {"role": "user",   "content": user_msg}],
                api_key,
            )
            match = re.search(r"\{[\s\S]*\}", content)
            if match:
                advice = json.loads(match.group())
                for f in ("what", "how", "why"):
                    advice.setdefault(f, "-")
                advice.setdefault("model_basis", {})
                advice.setdefault("confidence_note", "该建议基于三模型机理证据生成")
                advice["source"] = "glm-4-flash"
                return advice
        except Exception as e:
            print(f"[LLM] GLM 调用失败（{e}），使用规则兜底")

    return _rule_fallback(apsim_result, hydrus_result, beps_result, mechanism_evidence)


# ---------------------------------------------------------------------------
# 多轮聊天（供 /api/advice/chat 接口调用）
# ---------------------------------------------------------------------------

def chat_with_context(
    user_message: str,
    history: List[dict],          # [{"role":"user","content":"..."}, {"role":"assistant","content":"..."}]
    apsim_result: dict,
    hydrus_result: dict,
    beps_result: dict,
    mechanism_evidence: Optional[dict] = None,
) -> str:
    if os.getenv('LEGACY_GLM','0') != '1':
        from services.assistant_service import chat
        result=next((r for r in (hydrus_result,apsim_result,beps_result) if r.get('task_id')), {})
        response=chat({'message':user_message,'history':history,'plot_id':result.get('plot_id'),
                      'supplement':{'task_id':result['task_id']} if result.get('task_id') else None})
        return '；'.join(b.get('text','') for b in response['blocks'] if b['type'] in {'text','warning'})
    api_key = _load_api_key() if os.getenv('LEGACY_GLM','0') == '1' else ''
    if not api_key:
        return "本地循证服务待接入；旧外部GLM默认关闭。"

    system = build_system_prompt(apsim_result, hydrus_result, beps_result, mechanism_evidence)
    messages = [{"role": "system", "content": system}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    try:
        return _call_glm(messages, api_key)
    except Exception as e:
        return f"AI 回复失败（{e}），请稍后重试。"


# ---------------------------------------------------------------------------
# 规则兜底（同步输出 model_basis）
# ---------------------------------------------------------------------------

def _rule_fallback(
    apsim: dict,
    hydrus: dict,
    beps: dict,
    mechanism_evidence: Optional[dict] = None,
) -> dict:
    return {
        'what':'规则摘要，非循证建议', 'how':'请核对资料来源和缺项',
        'why':(mechanism_evidence or {}).get('integrated_reason','可用证据不足'),
        'model_basis':{k.replace('_evidence',''):v.get('summary','') for k,v in (mechanism_evidence or {}).items() if k.endswith('_evidence') and isinstance(v,dict)},
        'confidence_note':'规则示例，非循证建议', 'source':'rule_fallback_not_evidence'
    }
