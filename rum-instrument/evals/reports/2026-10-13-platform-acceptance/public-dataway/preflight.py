"""Credential-free verified-TLS preflight. Never reads an authorization code or Token."""
import importlib.util
import json
import os
from pathlib import Path
import ssl
import sys

skill = Path(os.environ.get('RUM_SKILL_DIR', '/Users/oneandonly/Workspace/ai-skills/rum-instrument'))
spec = importlib.util.spec_from_file_location('rum_control_preflight', skill / 'scripts/resolve_rum_application.py')
helper = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = helper
spec.loader.exec_module(helper)
# urllib uses Python's default trust settings, including SSL_CERT_FILE when supplied.
# There is deliberately no unverified TLS context or insecure option.
try:
    trust = ssl.create_default_context()
    assert trust.verify_mode == ssl.CERT_REQUIRED and trust.check_hostname
    site = helper.resolve_site('http://testing-openway.dataflux.cn')
    result = helper.preflight_site(site, ai_api_tls_context=trust)
    print(json.dumps({'status': 'passed', 'tls_verification': 'verified', 'evidence': result}, sort_keys=True))
except (helper.ResolutionError, ssl.SSLError, OSError) as error:
    print(json.dumps({'status': 'blocked_preflight', 'tls_verification': 'verified', 'error': str(error)}, sort_keys=True))
    raise SystemExit(1)
