from pathlib import Path

FRONTEND_SRC = Path('/root/ramos-ca/src/App.jsx')
FRONTEND_DIST = Path('/tmp/timesheet-next/frontend/dist')


def test_phase2_frontend_has_week_view_and_required_api_paths():
    source = FRONTEND_SRC.read_text()

    required_markers = [
        'function WeekPicker',
        'function EventCard',
        'function MatchControls',
        'function WeekTimeGauge({ events = [], fillerPlans = [], weekStart })',
        'mondayFor(new Date(`${weekStart}T00:00:00`))',
        'function MappingRulesPanel',
        'function FillerPanel',
        'function SubmitBar',
        '/api/week/events',
        '/api/match/suggest',
        '/api/week/approve',
        '/api/mappings',
        '/api/filler/plan',
        '/api/filler/insert',
        '/api/week/submit',
        '/api/auth/login',
        '/api/auth/token/status',
    ]
    missing = [marker for marker in required_markers if marker not in source]
    assert missing == []


def test_phase2_frontend_dist_is_built_for_fastapi_mount():
    index = FRONTEND_DIST / 'index.html'
    assert index.exists()
    html = index.read_text()
    assert 'Timesheet Matcher' in html or '/assets/' in html
    assert any((FRONTEND_DIST / 'assets').glob('*.js'))
    assert any((FRONTEND_DIST / 'assets').glob('*.css'))
