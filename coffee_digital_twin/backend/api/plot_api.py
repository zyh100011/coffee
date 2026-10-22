import json
import uuid
import math

from flask import Blueprint, jsonify, request

from database.init_db import get_connection, now_iso


plot_bp = Blueprint("plot_api", __name__, url_prefix="/api/plot")


PROFILE_FIELDS=('plot_name','coffee_variety','tree_age','area_mu','latitude','longitude','elevation_m','soil_type','shade_level','plant_density','row_spacing_m','plant_spacing_m')
NUMERIC=('tree_age','area_mu','latitude','longitude','elevation_m','plant_density','row_spacing_m','plant_spacing_m')
def profile_completeness(plot):
    missing=[k for k in PROFILE_FIELDS if plot.get(k) in (None,'')]
    return {'filled':12-len(missing),'total':12,'missing':missing}
def _default_plot(payload):
    if not isinstance(payload.get('plot_name'),str) or not payload['plot_name'].strip(): raise ValueError('名称不能为空')
    plot={'plot_id':payload.get('plot_id') or 'plot_'+uuid.uuid4().hex[:8],'crop':payload.get('crop') or 'coffee'}
    for key in PROFILE_FIELDS:
        value=payload.get(key)
        if value in (None,''): value=None
        elif key in NUMERIC:
            if isinstance(value,bool): raise ValueError(key+'须为数值')
            value=float(value)
            if not math.isfinite(value): raise ValueError(key+'须为有限值')
            if key not in ('latitude','longitude','elevation_m') and value<0: raise ValueError(key+'不能为负')
            if key=='latitude' and not -90<=value<=90: raise ValueError('纬度超范围')
            if key=='longitude' and not -180<=value<=180: raise ValueError('经度超范围')
        elif not isinstance(value,str): raise ValueError(key+'须为文本')
        else: value=value.strip() or None
        plot[key]=value
    sources=payload.get('field_sources') or {}
    if not isinstance(sources,dict) or any(v not in ('field_record','现场记录','estimated','估计','unknown','未知') for v in sources.values()): raise ValueError('来源选项无效')
    plot['field_sources']={k:sources.get(k,'unknown') for k in PROFILE_FIELDS}
    plot['verified_fields']=[k for k in PROFILE_FIELDS if plot[k] is not None and sources.get(k) in ('field_record','现场记录')]
    return plot


@plot_bp.post("/init")
def init_plot():
    payload = request.get_json(silent=True) or {}
    try: plot = _default_plot(payload)
    except (ValueError,TypeError) as error: return jsonify(status='error',code='E_PARAM_INVALID',message=str(error),retryable=False),400
    timestamp = now_iso()

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO plots (
                plot_id, plot_name, crop, coffee_variety, area_mu, tree_age,
                latitude, longitude, elevation_m, soil_type, shade_level,
                plant_density, row_spacing_m, plant_spacing_m, raw_json,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(plot_id) DO UPDATE SET
                plot_name=excluded.plot_name,
                crop=excluded.crop,
                coffee_variety=excluded.coffee_variety,
                area_mu=excluded.area_mu,
                tree_age=excluded.tree_age,
                latitude=excluded.latitude,
                longitude=excluded.longitude,
                elevation_m=excluded.elevation_m,
                soil_type=excluded.soil_type,
                shade_level=excluded.shade_level,
                plant_density=excluded.plant_density,
                row_spacing_m=excluded.row_spacing_m,
                plant_spacing_m=excluded.plant_spacing_m,
                raw_json=excluded.raw_json,
                updated_at=excluded.updated_at
            """,
            (
                plot["plot_id"],
                plot["plot_name"],
                plot["crop"],
                plot["coffee_variety"],
                plot["area_mu"],
                plot["tree_age"],
                plot["latitude"],
                plot["longitude"],
                plot["elevation_m"],
                plot["soil_type"],
                plot["shade_level"],
                plot["plant_density"],
                plot["row_spacing_m"],
                plot["plant_spacing_m"],
                json.dumps(plot, ensure_ascii=False),
                timestamp,
                timestamp,
            ),
        )

    return jsonify({"status": "success", "plot_id": plot["plot_id"], "plot": plot})

@plot_bp.get('/list')
def list_plots():
    with get_connection() as conn: rows=conn.execute('SELECT raw_json FROM plots ORDER BY updated_at DESC,plot_id').fetchall()
    items=[]
    for row in rows:
        plot=json.loads(row['raw_json']); plot['completeness']=profile_completeness(plot); items.append(plot)
    return jsonify(status='success',items=items)

@plot_bp.get('/<plot_id>')
def plot_detail(plot_id):
    with get_connection() as conn: row=conn.execute('SELECT raw_json FROM plots WHERE plot_id=?',(plot_id,)).fetchone()
    if not row: return jsonify(status='error',code='E_PLOT_REQUIRED',message='地块不存在',retryable=False),404
    plot=json.loads(row['raw_json']); plot['completeness']=profile_completeness(plot)
    return jsonify(status='success',plot=plot)


@plot_bp.get("/latest")
def latest_plot():
    with get_connection() as conn:
        row = conn.execute(
            "SELECT raw_json FROM plots ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
    if not row:
        return jsonify({"status": "empty", "plot": None})
    return jsonify({"status": "success", "plot": json.loads(row["raw_json"])})
