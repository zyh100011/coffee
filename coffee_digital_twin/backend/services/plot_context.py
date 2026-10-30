"""Verified meaningful fields only; legacy defaults remain unknown."""
import json
from database.init_db import get_connection
FIELDS=('coffee_variety','tree_age','soil_type','shade_level','row_spacing_m','plant_spacing_m','area_mu','latitude','longitude')
def load_plot_context(plot_id):
    with get_connection() as conn:
        row=conn.execute('SELECT raw_json FROM plots WHERE plot_id=?',(plot_id,)).fetchone() if plot_id else None
    raw=json.loads(row['raw_json']) if row else {}
    verified=raw.get('verified_fields',[])
    sources=raw.get('field_sources',{})
    known={k:raw[k] for k in FIELDS if k in verified and raw.get(k) not in (None,'') and sources.get(k) not in (None,'','demo','estimated','legacy_default')}
    reference_keys=('soil_type','plant_density','soil_bulk_density','soil_texture')
    references={k:{'value':raw[k],'source':sources.get(k),'note':raw.get('field_notes',{}).get(k)}
                for k in reference_keys if raw.get(k) not in (None,'')}
    return {'plot_id':plot_id,'exists':bool(row),'known':known,'unknown':[k for k in FIELDS if k not in known],
            'reference_fields':references,'soil_sampling_context':raw.get('soil_sampling_context',{}),
            'auto_apply_to_hydrus':False}
