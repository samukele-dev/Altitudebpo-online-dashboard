"""
Talks to the Call Centre Reporting Suite backend instead of the call-centre
database. That backend is the one already allowlisted at the database, so this
dashboard never connects to the DB itself and needs no IP whitelisting.

Configure with environment variables:
  SUITE_API_URL    e.g. https://call-centre-backend.onrender.com   (no trailing slash needed)
  SUITE_API_TOKEN  from `python manage.py dashboard_api_token` on the Suite backend
"""
import os

import requests

# (connect, read) seconds — the Suite answers in well under a second normally;
# a free-tier host waking from sleep can take longer, so the read side is generous.
TIMEOUT = (5, 30)


class SuiteError(Exception):
    """The Suite backend couldn't be reached or refused the request."""


def _base_url():
    return os.environ.get('SUITE_API_URL', 'http://localhost:8000').rstrip('/')


def _headers():
    token = os.environ.get('SUITE_API_TOKEN')
    if not token:
        raise SuiteError('SUITE_API_TOKEN is not set on the dashboard.')
    return {'Authorization': f'Token {token}'}


def _request(method, path, **kwargs):
    try:
        resp = requests.request(method, f'{_base_url()}{path}', headers=_headers(), timeout=TIMEOUT, **kwargs)
    except requests.RequestException as e:
        raise SuiteError(f'Could not reach the reporting backend: {e}')
    if resp.status_code == 401:
        raise SuiteError('The reporting backend rejected the dashboard token (SUITE_API_TOKEN).')
    if not resp.ok:
        try:
            detail = resp.json().get('error') or resp.text[:200]
        except ValueError:
            detail = resp.text[:200]
        raise SuiteError(f'Reporting backend error ({resp.status_code}): {detail}')
    return resp.json()


def get_team_stats(floor):
    """Today's per-team stats + combined totals for 'Floor 1', 'Floor 2' or 'Global'."""
    return _request('GET', '/api/dashboard/team-stats/', params={'floor': floor})


def set_team_target(floor, team, target):
    return _request('POST', '/api/dashboard/team-targets/', json={'floor': floor, 'team': team, 'target': target})
