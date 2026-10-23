#!/usr/bin/env python3
"""Offline profile validation and deterministic title rendering; no app/network writes."""
import argparse
import json
import math
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

VERSION = '1.0.0+20261023.1'
FORMATS = {'{date} | {category} | {topic}', '{category} | {topic}', '{date} | {topic}'}
DAYS = {'MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU'}

def load_zone(name):
    if not isinstance(name, str) or not name:
        raise ValueError('timezone must be a selected IANA zone')
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        try:
            ZoneInfo('UTC')
        except ZoneInfoNotFoundError:
            raise ValueError('IANA time-zone data is unavailable in this Python runtime; use an existing runtime with tzdata or report the missing dependency. Do not substitute a fixed offset.') from None
        raise ValueError(f'unknown IANA timezone: {name}') from None
    except (TypeError, ValueError):
        raise ValueError('timezone must be a valid IANA zone identifier') from None

def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def draft():
    return {
        'schemaVersion': 1, 'profileId': str(uuid.uuid4()), 'setupStatus': 'draft',
        'skillVersionAtCreation': VERSION, 'displayName': '', 'platforms': [], 'timezone': None,
        'naming': {'format': '{date} | {category} | {topic}', 'dateFormat': '%y%m%d', 'categories': []},
        'authorization': {'rename': False, 'unknownOriginFirstRename': False,
                          'allowNaturalOrderChanges': False, 'evidence': None},
        'scope': {'mode': 'new_only', 'historyAuthorizationFile': None},
        'schedule': {'kind': 'manual', 'times': [], 'days': [], 'confirmed': False,
                     'automationId': None, 'requestedText': None},
        'storage': {'stateDirectory': 'state'},
    }

def validate(p, allow_draft=False):
    errors = []
    if not isinstance(p, dict): return ['profile must be a JSON object']
    if p.get('schemaVersion') != 1: errors.append('schemaVersion must be 1')
    if not p.get('profileId'): errors.append('profileId is required')
    if p.get('setupStatus') not in ('draft', 'confirmed'): errors.append('invalid setupStatus')
    pending = allow_draft and p.get('setupStatus') == 'draft'
    if not pending and p.get('setupStatus') != 'confirmed': errors.append('user choices are not confirmed')
    platforms = p.get('platforms', [])
    if not isinstance(platforms, list) or any(v not in ('codex', 'chatgpt_web') for v in platforms):
        errors.append('platforms must contain only codex/chatgpt_web')
    elif len(platforms) != len(set(platforms)): errors.append('duplicate platform')
    elif not pending and not platforms: errors.append('select at least one platform')
    tz = p.get('timezone')
    if tz:
        try: load_zone(tz)
        except ValueError as exc: errors.append(str(exc))
    elif not pending: errors.append('timezone is not selected')
    naming = p.get('naming', {})
    if not isinstance(naming, dict): naming = {}; errors.append('naming must be an object')
    fmt = naming.get('format')
    if fmt not in FORMATS: errors.append('unsupported title format; use one of the three documented templates')
    if naming.get('dateFormat') != '%y%m%d': errors.append('dateFormat must be %y%m%d')
    cats = naming.get('categories', [])
    names = []
    if not isinstance(cats, list): errors.append('categories must be a list')
    else:
        for c in cats:
            if not isinstance(c, dict) or not isinstance(c.get('name'), str) or not c.get('description'):
                errors.append('each category needs name and description'); continue
            n = c['name']
            if not n or n != n.strip() or any(t in n for t in ('|', '\n', '\r')):
                errors.append('invalid category name')
            names.append(n)
        if len(names) != len(set(names)): errors.append('duplicate category name')
    if not pending and fmt and '{category}' in fmt and not names: errors.append('confirm categories before use')
    auth = p.get('authorization', {})
    if not isinstance(auth, dict): auth = {}; errors.append('authorization must be an object')
    for k in ('rename', 'unknownOriginFirstRename', 'allowNaturalOrderChanges'):
        if not isinstance(auth.get(k), bool): errors.append(f'authorization.{k} must be boolean')
    if auth.get('rename') and not auth.get('evidence'): errors.append('rename authorization needs traceable human evidence')
    if auth.get('unknownOriginFirstRename') and not auth.get('rename'): errors.append('unknown-origin rename needs rename authorization')
    scope = p.get('scope', {})
    if not isinstance(scope, dict): scope = {}; errors.append('scope must be an object')
    if scope.get('mode') not in ('new_only', 'approved_history_and_new', 'explicit_ids'): errors.append('invalid scope mode')
    if scope.get('mode') != 'new_only' and not scope.get('historyAuthorizationFile'):
        errors.append('historical or explicit scope needs an authorization file')
    sch = p.get('schedule', {})
    if not isinstance(sch, dict): sch = {}; errors.append('schedule must be an object')
    kind = sch.get('kind')
    if kind not in ('manual', 'daily', 'weekdays', 'weekly', 'custom'): errors.append('invalid schedule kind')
    times, days = sch.get('times', []), sch.get('days', [])
    if not isinstance(times, list) or any(not isinstance(t, str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', t) for t in times):
        errors.append('times must be HH:MM values')
    elif len(times) != len(set(times)): errors.append('duplicate run time')
    if not isinstance(days, list) or any(d not in DAYS for d in days): errors.append('invalid weekday')
    if kind == 'manual' and (times or days or sch.get('automationId')):
        errors.append('manual profile must not contain an active schedule or automationId')
    if kind in ('daily', 'weekdays', 'weekly') and not times: errors.append('scheduled runs need selected times')
    if kind == 'weekly' and not days: errors.append('weekly schedule needs days')
    if kind == 'custom' and not sch.get('requestedText'): errors.append('custom schedule needs the user request')
    if kind != 'manual' and sch.get('confirmed') is not True: errors.append('schedule is not confirmed')
    if not isinstance(p.get('storage'), dict) or not p['storage'].get('stateDirectory'): errors.append('stateDirectory is required')
    return errors

def parse_created_at(raw, unit):
    if unit == 'iso8601':
        value = datetime.fromisoformat(raw.replace('Z', '+00:00'))
        if value.tzinfo is None: raise ValueError('naive datetime is not a verified timestamp')
        return value.astimezone(timezone.utc)
    value = float(raw)
    if not math.isfinite(value): raise ValueError('createdAt must be finite')
    if unit == 'milliseconds': value /= 1000
    return datetime.fromtimestamp(value, timezone.utc)

def render(p, created_at, unit, category, topic):
    errors = validate(p)
    if errors: raise ValueError('; '.join(errors))
    if not topic or topic != topic.strip() or any(c in topic for c in ('|', '\n', '\r')):
        raise ValueError('topic must be a single trimmed component without separators')
    if topic[-1] in '。．，、；：！？,.!?;:': raise ValueError('topic must not have trailing punctuation')
    fmt = p['naming']['format']
    allowed = [c['name'] for c in p['naming']['categories']]
    if '{category}' in fmt and category not in allowed: raise ValueError('category must be one confirmed category')
    local = parse_created_at(created_at, unit).astimezone(load_zone(p['timezone']))
    return {'title': fmt.format(date=local.strftime('%y%m%d'), category=category, topic=topic),
            'createdAtLocal': local.isoformat(), 'timezone': p['timezone'],
            'writesPerformed': False, 'note': 'Formatting only: the caller must verify createdAt provenance, content, authorization and target state.'}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('draft', help='print an unconfirmed personal profile; writes no file')
    check = commands.add_parser('validate'); check.add_argument('profile'); check.add_argument('--allow-draft', action='store_true')
    title = commands.add_parser('title'); title.add_argument('profile'); title.add_argument('--created-at', required=True)
    title.add_argument('--unit', choices=['seconds', 'milliseconds', 'iso8601'], required=True)
    title.add_argument('--category', default=''); title.add_argument('--topic', required=True)
    commands.add_parser('locate', help='print profile registry location; do not read private records')
    args = parser.parse_args()
    try:
        if args.command == 'draft': result = draft()
        elif args.command == 'locate':
            root = Path(os.environ.get('CODEX_HOME', str(Path.home()/'.codex')))
            reg = root/'conversation-title-manager'/'active-profile.json'
            result = {'registry': str(reg), 'exists': reg.is_file()}
        elif args.command == 'validate':
            errors = validate(read_json(args.profile), args.allow_draft)
            result = {'valid': not errors, 'errors': errors, 'writesPerformed': False}
            print(json.dumps(result, ensure_ascii=False)); return 1 if errors else 0
        else: result = render(read_json(args.profile), args.created_at, args.unit, args.category, args.topic)
        print(json.dumps(result, ensure_ascii=False, indent=2)); return 0
    except (ValueError, TypeError, OverflowError, OSError) as exc:
        print(json.dumps({'error': str(exc), 'writesPerformed': False}, ensure_ascii=False)); return 2

if __name__ == '__main__': sys.exit(main())
