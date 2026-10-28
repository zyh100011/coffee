"""Additive scientific provenance tables; no seed observations."""
SQL = '''
CREATE TABLE IF NOT EXISTS raw_files(file_id TEXT PRIMARY KEY,path TEXT,sha256 TEXT,rows INTEGER,imported_at TEXT,data_version TEXT,source_type TEXT);
CREATE TABLE IF NOT EXISTS obs_long(obs_id TEXT PRIMARY KEY,plot_id TEXT,device_id TEXT,ts TEXT,date TEXT,parameter TEXT,depth_cm REAL,value_raw TEXT,value REAL,unit TEXT,source_file_id TEXT,source_row INTEGER,qc_flag TEXT,data_version TEXT,priority INTEGER);
CREATE UNIQUE INDEX IF NOT EXISTS obs_key ON obs_long(device_id,ts,parameter,ifnull(depth_cm,-1),data_version);
CREATE INDEX IF NOT EXISTS obs_query ON obs_long(plot_id,parameter,date);
CREATE TABLE IF NOT EXISTS device_plot_map(device_id TEXT,plot_id TEXT,depth_cm REAL,valid_from TEXT,valid_to TEXT);
CREATE TABLE IF NOT EXISTS lai_obs(plot_id TEXT,date TEXT,quadrat TEXT,plant TEXT,repeat_no TEXT,lai REAL,method TEXT,source_file_id TEXT,source_row INTEGER);
CREATE TABLE IF NOT EXISTS farm_events(plot_id TEXT,date TEXT,op_type TEXT,amount REAL,unit TEXT,source TEXT,source_ref TEXT,verified INTEGER);
CREATE TABLE IF NOT EXISTS soil_reports(plot_id TEXT,sample_date TEXT,depth_top_cm REAL,depth_bottom_cm REAL,item TEXT,value REAL,unit TEXT,method TEXT,report_ref TEXT,status TEXT);
CREATE TABLE IF NOT EXISTS data_release_sources(data_version TEXT,file_id TEXT,source_version TEXT,sha256 TEXT,PRIMARY KEY(data_version,file_id));
CREATE TABLE IF NOT EXISTS data_versions(data_version TEXT PRIMARY KEY,created_at TEXT,file_hashes_json TEXT,row_counts_json TEXT,note TEXT);
CREATE TABLE IF NOT EXISTS observation_sources(device_id TEXT PRIMARY KEY,label TEXT,location TEXT,identity_kind TEXT,missing_fields_json TEXT);
CREATE TABLE IF NOT EXISTS import_rejections(file_id TEXT,source_row INTEGER,reason TEXT,raw_json TEXT,PRIMARY KEY(file_id,source_row));
CREATE TABLE IF NOT EXISTS soil_lab_results(result_id TEXT PRIMARY KEY,plot_id TEXT,sample_label TEXT,lab_sample_id TEXT,item TEXT,value REAL,unit TEXT,method TEXT,sample_date TEXT,received_date TEXT,report_date TEXT,depth_top_cm REAL,depth_bottom_cm REAL,source_file_id TEXT,source_page INTEGER);
'''


def init_schema(conn):
    conn.executescript(SQL)


def version_frozen(conn, version):
    return bool(conn.execute('SELECT 1 FROM data_versions WHERE data_version=?',(version,)).fetchone()
                or conn.execute('SELECT 1 FROM data_release_sources WHERE source_version=?',(version,)).fetchone())
