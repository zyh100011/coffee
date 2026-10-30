"""Expose a boolean launch decision, without printing service URLs or credentials."""
from pathlib import Path
import sys
from urllib.parse import urlsplit
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config


def local_mock_target(url):
    parsed = urlsplit(url)
    return (parsed.scheme == 'http' and parsed.hostname in ('localhost', '127.0.0.1')
            and (parsed.port or 80) == 8001 and not parsed.username and not parsed.password
            and parsed.path in ('', '/') and not parsed.query and not parsed.fragment)


if __name__ == '__main__':
    print(int(local_mock_target(config.EVIDENCE_SERVICE_URL)))
