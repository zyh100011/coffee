const { request } = require('./request');
let sessionId = '';
let pendingQuestion = '';
let health = null;
let checkedAt = 0;
let lastCompareId = '';
let inFlight = null;
function getSessionId() { if (!sessionId) sessionId = `s_${Date.now()}_${Math.floor(Math.random() * 10000).toString().padStart(4, '0')}`; return sessionId; }
function resetSession() { sessionId = ''; pendingQuestion = ''; return getSessionId(); }
function setPendingQuestion(value) { pendingQuestion = value; }
function consumePendingQuestion() { const value = pendingQuestion; pendingQuestion = ''; return value; }
async function getHealth(force) {
  if (!force && health && Date.now() - checkedAt < 60000) return health;
  if (inFlight) return inFlight;
  inFlight = request({ url: '/api/assistant/health', timeout: 8000 }).then(value => { health = value; checkedAt = Date.now(); return value; }).finally(() => { inFlight = null; });
  return inFlight;
}
module.exports = { getSessionId, resetSession, setPendingQuestion, consumePendingQuestion, getHealth, setLastCompareId: value => { lastCompareId = value; }, getLastCompareId: () => lastCompareId };
