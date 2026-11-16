"""Shared product contract; no camera, credentials or cloud side effects."""
import json
import re

ROOT = 'rehab_v1'
from .catalog import EXERCISE_CATALOG, LEGACY_EXERCISES
EXERCISES = {k: v['name'] for k, v in EXERCISE_CATALOG.items()}
DURATIONS = (180, 300, 600)
SERVICE_UUID = '8273ed51-236b-4f1d-80ce-507265686162'
CHALLENGE_UUID = '8273ed52-236b-4f1d-80ce-507265686162'
REQUEST_UUID = '8273ed53-236b-4f1d-80ce-507265686162'
RESPONSE_UUID = '8273ed54-236b-4f1d-80ce-507265686162'


def safe_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', value):
        raise ValueError('invalid_identifier')
    return value


def dumps(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def validate_command(command, owner_uid, now_ms):
    if not isinstance(command, dict):
        raise ValueError('invalid_command')
    action = command.get('action')
    if action not in ('start', 'stop') or command.get('patient_uid') != owner_uid:
        raise ValueError('command_not_authorized')
    created, expires = command.get('created_at'), command.get('expires_at')
    if any(type(v) is not int for v in (created, expires)):
        raise ValueError('invalid_command_time')
    if not created <= now_ms + 5000 or not now_ms < expires <= created + 30000:
        raise ValueError('command_expired')
    common = {'action', 'patient_uid', 'created_at', 'expires_at'}
    allowed = common | ({'exercise', 'duration_s'} if command.get('protocol_version') is None else {'protocol_version', 'exercise', 'requested_side', 'goal'}) if action == 'start' else common | {'session_id'}
    if set(command) != allowed:
        raise ValueError('invalid_command_fields')
    if action == 'start':
        exercise = command.get('exercise')
        if command.get('protocol_version') is None:
            if exercise not in LEGACY_EXERCISES or type(command.get('duration_s')) is not int or command['duration_s'] not in DURATIONS or any(k in command for k in ('goal', 'requested_side')):
                raise ValueError('invalid_exercise_or_duration')
        else:
            if type(command['protocol_version']) is not int or command['protocol_version'] != 2:
                raise ValueError('unsupported_protocol')
            if not isinstance(exercise, str) or exercise not in EXERCISES or 'duration_s' in command:
                raise ValueError('invalid_exercise_or_duration')
            side = command.get('requested_side')
            required = EXERCISE_CATALOG[exercise]['side_mode'] == 'required'
            allowed_sides = ('left', 'right', 'both') if EXERCISE_CATALOG[exercise].get('bilateral') else ('left', 'right') if required else ('auto',)
            if side not in allowed_sides:
                raise ValueError('invalid_requested_side')
            validate_goal(command.get('goal'))
    else:
        safe_id(command.get('session_id'))
    return command


def validate_goal(goal):
    if not isinstance(goal, dict):
        raise ValueError('invalid_goal')
    if goal.get('mode') == 'time':
        d = goal.get('duration_s')
        ok = set(goal) == {'mode', 'duration_s'} and type(d) is int and 60 <= d <= 600 and d % 60 == 0
    elif goal.get('mode') == 'sets':
        r, s, rest = (goal.get(k) for k in ('reps_per_set', 'sets', 'rest_s'))
        ok = (set(goal) == {'mode', 'reps_per_set', 'sets', 'rest_s'} and
              all(type(v) is int for v in (r, s, rest)) and r in (5, 10, 15) and
              s in (1, 2, 3) and 15 <= rest <= 120 and rest % 15 == 0)
    else:
        ok = False
    if not ok:
        raise ValueError('invalid_goal')
    return goal


def command_goal(command):
    return command.get('goal') or {'mode': 'time', 'duration_s': command['duration_s']}
