from datetime import date, timedelta
from database.init_db import get_connection


def get_demo_weather_series(latitude=None, longitude=None, days=7, start=None):
    today = date.fromisoformat(start) if start else date.today()
    base_tavg = 24.5
    series = []
    for i in range(days):
        current = today + timedelta(days=i)
        rain = 0 if i not in [2, 5] else 8 + i
        tavg = base_tavg + (i % 3 - 1) * 0.8
        series.append(
            {
                "date": current.isoformat(),
                "tmax": round(tavg + 5.8, 1),
                "tmin": round(tavg - 5.9, 1),
                "tavg": round(tavg, 1),
                "rain_mm": rain,
                "radiation_mj": round(18.5 - i * 0.25, 2),
                "vpd_kpa": round(1.2 + i * 0.04, 2),
                "wind_m_s": 1.5,
                "source": "demo",
                "latitude": latitude,
                "longitude": longitude,
            }
        )
    return series


def get_observed_weather(plot_id, start, end):
    with get_connection() as conn:
        exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='obs_long'").fetchone()
        if not exists:
            return []
        rows = conn.execute("""SELECT o.date,o.parameter,AVG(o.value) value,SUM(o.value) total FROM obs_long o
            JOIN raw_files r ON r.file_id=o.source_file_id
            WHERE o.plot_id=? AND o.date BETWEEN ? AND ? AND o.qc_flag IN ('ok','rain_reset')
            AND o.value IS NOT NULL AND r.source_type='observation' GROUP BY o.date,o.parameter
            HAVING COUNT(DISTINCT o.device_id)=1 AND COUNT(DISTINCT o.unit)=1
            AND COUNT(DISTINCT o.data_version)=1""", (plot_id,start,end)).fetchall()
    days = {}
    mapping = {'rainfall':'rain_mm','rain':'rain_mm','air_temperature':'tavg','tmin':'tmin',
               'tmax':'tmax','radiation':'radiation_mj','wind_speed':'wind_ms'}
    for row in rows:
        key = mapping.get(row['parameter'])
        if key:
            days.setdefault(row['date'], {'date':row['date'],'source':'observation'})[key] = row['total'] if key=='rain_mm' else row['value']
    return [days[key] for key in sorted(days)]
