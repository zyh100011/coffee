"""Normalized CSV intake; raw instrument format awaits confirmation."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from data_pipeline.ingest_forms import ingest_form
if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('path'); parser.add_argument('--confirmed',action='store_true'); args=parser.parse_args()
    try: print(ingest_form('farm_events',args.path,args.confirmed))
    except ValueError as error: print(str(error)); sys.exit(1)