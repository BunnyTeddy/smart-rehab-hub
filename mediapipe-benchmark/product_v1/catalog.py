"""Versioned source for runtime, generated clients, voice prompts and Rules."""
import json
from pathlib import Path
CATALOG = json.loads(Path(__file__).with_name('exercises.json').read_text())
CATALOG_VERSION = CATALOG['version']
EXERCISE_CATALOG = {e['id']: e for e in CATALOG['exercises']}
LEGACY_EXERCISES = ('squat', 'biceps_curl')
CAPABILITIES = dict(protocol_version=2, catalog_version=CATALOG_VERSION,
                    exercises={key: True for key in EXERCISE_CATALOG},
                    modes={'time': True, 'sets': True},
                    bilateral={key: bool(e.get('bilateral')) for key, e in EXERCISE_CATALOG.items()})
