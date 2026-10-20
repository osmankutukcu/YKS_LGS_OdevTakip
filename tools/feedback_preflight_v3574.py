# -*- coding: utf-8 -*-
"""Offline, read-only, provider-neutral preflight for feedback infrastructure.

Examples:
  python -m tools.feedback_preflight_v3574 --role desktop --json
  python -m tools.feedback_preflight_v3574 --role server --strict

Never prints or writes environment secrets. Does not test live availability.
"""
import argparse
import json
import os
from services.feedback_deployment_v3574 import audit_desktop, audit_server, public_contract


def main(argv=None):
    parser = argparse.ArgumentParser(description='KoçPilot çevrim içi anket kurulum kontrolü (çevrim dışı)')
    parser.add_argument('--role', choices=('desktop', 'server', 'contract'), default='desktop')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--strict', action='store_true', help='Eksik kurulumda çıkış kodu 2 döndür.')
    args = parser.parse_args(argv)
    if args.role == 'contract':
        output = public_contract()
        state = 'pilot'
    else:
        report = audit_desktop(os.environ) if args.role == 'desktop' else audit_server(os.environ)
        output = report.as_dict()
        state = report.state
    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print('KoçPilot anket ön denetim:', args.role, '-', state)
        for check in output.get('checks', []):
            print(' - [%s] %s' % (check['level'], check['text']))
    if args.strict and state != 'configuration_ready':
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
