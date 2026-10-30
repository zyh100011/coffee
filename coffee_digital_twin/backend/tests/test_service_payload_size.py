import json
from services.assistant_service import service_context, service_route_payload
from services import evidence_client


def _catalog(n):
    return [{'parameter': 'p%d' % (i % 20), 'parameter_label': 'L', 'depth_cm': None, 'start': '2026-05-10', 'end': '2026-06-15',
             'valid_start': '2026-05-10', 'valid_end': '2026-06-15', 'device_id': 'd%d' % i, 'devices': ['d%d' % i], 'unit': '%',
             'data_version': 'data-v1.0', 'data_versions': ['data-v1.0'], 'source_label': 's', 'display_source': 's',
             'identity_kind': 'x', 'n': 10, 'usable_count': 10, 'hidden_reason': None, 'depth_top_cm': 0, 'depth_bottom_cm': 15,
             'display_unit': 'cm3/cm3'} for i in range(n)]


def test_service_context_is_compact_and_full_context_untouched():
    context = {'plot_id': 'p', 'exists': True, 'observation_catalog': _catalog(83), 'data_end': '2026-06-15'}
    compact = service_context(context)
    assert len(context['observation_catalog']) == 83
    assert len(compact['observation_catalog']) == 20
    assert len(json.dumps(compact, ensure_ascii=False).encode()) < 4000
    payload = service_route_payload({'message': 'q', 'plot_context': context, 'history': [{'role': 'user', 'content': 'x' * 900}] * 10})
    assert len(payload['history']) == 6 and len(payload['history'][0]['content']) == 300


def test_http_4xx_detail_is_kept(monkeypatch):
    class R:
        status_code = 400
        text = ''
        def json(self):
            return {'error': 'AssertionError', 'message': 'too long'}
    monkeypatch.setattr(evidence_client.requests, 'post', lambda *a, **k: R())
    try:
        evidence_client.route({'message': 'q'})
    except evidence_client.EvidenceServiceError as error:
        assert error.code == 'E_EVIDENCE_INVALID'
        assert 'HTTP 400' in error.detail and 'AssertionError' in error.detail
    else:
        raise AssertionError('expected error')
