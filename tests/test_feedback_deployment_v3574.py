"""No Qt, cloud account, network, secrets, personal records or DB writes."""
import hashlib
import json
from services.feedback_deployment_v3574 import (
    _url_valid, audit_desktop, audit_server, public_contract,
)
from tools.feedback_preflight_v3574 import main


def test_disabled_does_not_require_cloud_settings():
    report = audit_desktop({})
    assert report.state == 'disabled'
    assert report.as_dict()['live_verified'] is False


def test_disabled_even_with_stray_cloud_fields():
    report = audit_desktop({'YKS_FEEDBACK_RELAY_URL': 'http://localhost:1234'})
    assert report.state == 'disabled'


def test_enabled_requires_form_and_secure_settings():
    report = audit_desktop({'YKS_FEEDBACK_RELAY_V14_ENABLED': '1'})
    assert report.state == 'incomplete'
    assert sum(c.level == 'blocked' for c in report.checks) >= 4


def test_https_strict_origin_only():
    for bad in ('http://example.org', 'https://example.org/a',
                'https://x:y@example.org', 'https://example.org?key=X',
                'https://example.org#x', 'https://localhost',
                'https://example.org:abc', ' https://example.org ', ''):
        assert not _url_valid(bad), bad
    assert _url_valid('https://example.org')
    assert _url_valid('https://example.org:443/')


def test_provider_name_not_required_and_never_claims_live():
    env = {'YKS_HOMEWORK_FEEDBACK_V12_ENABLED': '1',
           'YKS_FEEDBACK_RELAY_V14_ENABLED': '1',
           'YKS_FEEDBACK_RELAY_URL': 'https://feedback.example.org',
           'YKS_FEEDBACK_RELAY_TENANT': 'school_alpha',
           'YKS_FEEDBACK_RELAY_KEY': 'A' * 60}
    report = audit_desktop(env)
    assert not any(c.level == 'blocked' for c in report.checks)
    assert report.state == 'incomplete'  # live tests intentionally missing
    raw = json.dumps(report.as_dict())
    assert 'A' * 60 not in raw and 'school_alpha' not in raw
    assert report.as_dict()['live_verified'] is False


def test_server_missing_persistent_storage_and_hashes():
    report = audit_server({'YKS_FEEDBACK_RELAY_PUBLIC_URL': 'https://feedback.example.org',
                           'YKS_FEEDBACK_RELAY_DB': ':memory:'})
    assert report.state == 'incomplete'
    assert any(c.code == 'persistent_db' and c.level == 'blocked' for c in report.checks)


def test_server_valid_syntax_without_deployment_claim(tmp_path):
    secret = 'some-super-secret-password-for-testing-only'
    env = {'YKS_FEEDBACK_RELAY_PUBLIC_URL': 'https://relay.example.org',
           'YKS_FEEDBACK_RELAY_DB': str(tmp_path / 'relay.db'),
           'YKS_FEEDBACK_RELAY_TENANT_HASHES': json.dumps({'school_alpha': hashlib.sha256(secret.encode()).hexdigest()})}
    report = audit_server(env)
    assert not any(c.level == 'blocked' for c in report.checks)
    assert report.state == 'incomplete'
    assert secret not in json.dumps(report.as_dict())
    assert not (tmp_path / 'relay.db').exists()  # no side effects


def test_contract_explicitly_no_hosting_provider_selected():
    result = public_contract()
    assert result['hosting_provider_selected'] is False
    assert 'POST /v14/invites' in result['authenticated_routes']
    assert 'POST /r/{token}' in result['public_routes']


def test_cli_emits_secret_free_json(capsys, monkeypatch):
    monkeypatch.setenv('YKS_FEEDBACK_RELAY_KEY', 'B' * 50)
    assert main(['--role', 'desktop', '--json']) == 0
    output = capsys.readouterr().out
    assert 'B' * 50 not in output
    assert json.loads(output)['state'] == 'disabled'


def test_cli_strict_incomplete_exits_2(monkeypatch):
    monkeypatch.delenv('YKS_FEEDBACK_RELAY_V14_ENABLED', raising=False)
    assert main(['--role', 'desktop', '--strict']) == 2
