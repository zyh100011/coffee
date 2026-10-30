"""Check the configured business API without printing URLs, tokens or responses."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from services import evidence_client


def check(check_auth=False):
    result={'token_configured':bool(os.environ.get('EVIDENCE_API_TOKEN','').strip()),
            'health':'not_checked','authenticated_route':'not_checked'}
    try:
        health=evidence_client.health()
        result.update(health=health['status'],mock=health.get('mock',False))
        if health['status']!='ok':return result,1
        if check_auth:
            route=evidence_client.route({'session_id':'connection_check','message':'咖啡叶片营养采样需要记录哪些信息？',
                'history':[],'plot_context':{},'available_tools':[],'supplement':None})
            result.update(authenticated_route='passed',mock=bool(result['mock'] or route.get('mock')))
        return result,0
    except evidence_client.EvidenceServiceError as error:
        result.update(error_code=error.code,message=str(error))
        return result,1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-auth',action='store_true',help='Also send one fixed route request; does not execute tools.')
    args=parser.parse_args()
    result,code=check(args.check_auth)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    sys.exit(code)
