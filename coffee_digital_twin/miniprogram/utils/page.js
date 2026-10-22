const { request } = require('./request');
const { getPlotId, savePlotId } = require('./storage');
const session = require('./session');
const { normalizeError } = require('./errors');
const defaults = { plot: null, health: {}, state: 'loading', error: null };
async function context(page, explicitPlotId) {
 const id = explicitPlotId || getPlotId();
 const healthPromise = session.getHealth().catch(() => null);
 let plot = null;
 try { if (id) plot = (await request({ url: '/api/plot/' + encodeURIComponent(id) })).plot; }
 catch (error) { if (error.code !== 'E_PLOT_REQUIRED') throw error; }
 if (!plot) {
   const listed = await request({ url: '/api/plot/list' });
   if (listed.items && listed.items.length === 1) { plot = listed.items[0]; savePlotId(plot.plot_id); }
 }
 const health = await healthPromise;
 page.setData({plot,health:health||{}});return plot;
}
function fail(page,error) { const normalized = normalizeError(error);page.setData({error:normalized,state:normalized.code==='E_OFFLINE'?'offline':'error'}); }
function missingLabels(keys) { const { FIELDS }=require('./labels');return (keys||[]).map(k=>FIELDS[k]||k).join('、'); }
function openEvidence(id,obsId) { wx.navigateTo({url:'/pages/evidence/evidence?'+(obsId?'obs_id='+encodeURIComponent(obsId):'evidence_id='+encodeURIComponent(id))}); }
module.exports={defaults,context,fail,missingLabels,openEvidence};
