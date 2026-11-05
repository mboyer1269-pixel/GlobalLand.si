"""Strict provider schemas and lossless conversion to internal tool actions.

Tool arguments travel as native JSON. Arbitrary finance object keys use entry
arrays so the provider schema can close every object without JSON-in-JSON.
The controller and toolbox still validate the resulting internal decisions.
"""
import math
import re


def _object(properties):
    return {'type': 'object', 'additionalProperties': False,
            'required': list(properties), 'properties': properties}


def _nullable(schema):
    result = dict(schema, type=[schema['type'], 'null'])
    if 'enum' in schema:
        result['enum'] = schema['enum'] + [None]
    return result


def _text(limit=4000):
    return {'type': 'string', 'minLength': 1, 'maxLength': limit, 'pattern': r'\S'}


def _integer(maximum=10**12, minimum=0):
    return {'type': 'integer', 'minimum': minimum, 'maximum': maximum}


_AGENT = {'type': 'string', 'pattern': '^[A-Z0-9_-]{1,64}$'}
_ID = {'type': 'string', 'minLength': 1, 'maxLength': 128,
       'pattern': '^[A-Za-z0-9][A-Za-z0-9_.:-]*$'}
_EVIDENCE = {'type': 'array', 'minItems': 1, 'maxItems': 100, 'items': _text()}

_WORLD_FIELDS = {
    'register_agent': {'agent_id': _AGENT, 'role': _text(500)},
    'create_mission': {
        'mission_id': _ID, 'goal': _text(10000), 'agent_id': _nullable(_ID),
        'parent_id': _nullable(_ID), 'priority': _nullable(_integer(10000)),
    },
    'claim_mission': {
        'mission_id': _ID, 'agent_id': _ID,
        'lease_seconds': _nullable(_integer(3600, 1)),
    },
    'complete_mission': {'mission_id': _ID, 'agent_id': _ID,
                         'lease_token': _text(128), 'evidence': _EVIDENCE,
                         'lesson': _nullable(_text(1000))},
    'fail_mission': {'mission_id': _ID, 'agent_id': _ID,
                     'lease_token': _text(128), 'reason': _text(),
                     'lesson': _nullable(_text(1000))},
    'record_lesson': {'agent_id': _ID, 'lesson': _text(1000), 'mission_id': _nullable(_ID),
                      'tags': _nullable({'type': 'array', 'maxItems': 8, 'items': _text(40)})},
    'message': {'from_agent': _ID, 'to_agent': _ID, 'body': _text(10000)},
    'transfer_glc': {'from_agent': _ID, 'to_agent': _ID, 'amount': _integer()},
    'reward_glc': {'agent_id': _ID, 'amount': _integer(), 'evidence': _EVIDENCE},
    'set_policy': {'maintenance_glc': _integer(10000), 'interest_basis_points': _integer(10000)},
    'cycle': {'cycle_id': _ID},
    'raise_blocker': {
        'blocker_id': _ID, 'agent_id': _ID, 'title': _text(200),
        'category': {'type': 'string', 'enum': ['ACCOUNT', 'CREDENTIAL', 'IDENTITY', 'PAYMENT', 'DECISION', 'CAPABILITY', 'OTHER']},
        'needs_founder': {'type': 'boolean'}, 'detail': _text(2000),
        'mission_id': _nullable(_ID), 'expected_gain': _nullable(_text(500)),
    },
    'resolve_blocker': {'blocker_id': _ID, 'agent_id': _ID, 'resolution': _text(2000)},
    'review': {'reviewer': _ID,
               'subject': {'type': 'string', 'pattern': '^(actor|site|mission):[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$'},
               'digest': {'type': 'string', 'pattern': '^[0-9a-f]{64}$'},
               'verdict': {'type': 'string', 'enum': ['APPROVE', 'NEEDS_WORK']},
               'notes': _nullable(_text(2000))},
}
_WORLD_SCHEMAS = {
    op: _object({'op': {'type': 'string', 'enum': [op]}, **fields})
    for op, fields in _WORLD_FIELDS.items()
}
_TOOL_SCHEMAS = {
    'EXEC': _object({
        'argv': {'type': 'array', 'minItems': 1, 'maxItems': 128,
                 'items': {'type': 'string', 'maxLength': 8192, 'pattern': '^[^\u0000]*$'}},
        'outputs': {'type': 'array', 'maxItems': 64, 'items': {'type': 'string'}},
        'inputs': _nullable({'type': 'array', 'maxItems': 128, 'items': {'type': 'string'},
            'description': 'Public repository files or directory prefixes ending in /. Null preserves legacy whole-source selection subject to the 128 MiB job input budget; [] starts empty. Select only the inputs this program needs.'}),
        'cwd': _nullable({'type': 'string', 'description':
            'Use null for the /workspace root. Otherwise use a relative directory '
            'inside /workspace, without empty, dot, dot-dot or .git segments '
            'or backslashes. Exact root aliases ., ./, /workspace and '
            '/workspace/ are accepted and normalized to the default root.'}),
        'mission_id': _nullable({'type': 'string'}),
    }),
    'FETCH': _object({
        'url': {'type': 'string', 'maxLength': 8192}, 'output': {'type': 'string'},
        'encoding': _nullable({'type': 'string', 'enum': ['utf-8', 'base64']}),
    }),
    'STATUS': _object({}),
    'RECONCILE': _object({'operation_id': {'type': 'string', 'pattern': '^TASK-[0-9]{4,12}$'}}),
    'SPEND': _object({'request_entries': {'type': 'array', 'items': {'$ref': '#/$defs/json_entry'}}}),
    'PUBLISH_ACTOR': _object({
        'actor': {'type': 'string', 'pattern': '^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$',
                  'description': 'Folder name under products/actors/; also the Apify Actor name.'},
        'title': _text(60), 'description': _text(300),
        'public': {'type': 'boolean', 'description': 'List in Apify Store after a successful build.'},
        'events': _nullable({'type': 'array', 'maxItems': 5, 'items': _object({
            'name': {'type': 'string', 'pattern': '^[a-z0-9][a-z0-9-]{0,39}$'},
            'title': _text(60), 'description': _text(300),
            'price_microusd': _integer(10_000_000, 1)})}),
    }),
    'ACTOR_STATS': _object({'actor': {'type': 'string', 'pattern': '^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$'}}),
    'PUBLISH_SITE': _object({
        'site': {'type': 'string', 'pattern': '^[a-z0-9](?:[a-z0-9-]{0,38}[a-z0-9])?$',
                 'description': 'Folder name under products/sites/.'},
        'dry_run': _nullable({'type': 'boolean', 'description': 'Validate only and return the review_digest.'}),
        'online': _nullable({'type': 'boolean', 'description': 'false takes the site offline.'}),
    }),
}


def _action_schema(action, args):
    return _object({'agent': _AGENT, 'action': {'type': 'string', 'enum': [action]}, 'args': args})


MODEL_SCHEMA = _object({
    'summary': {'type': 'string'},
    'actions': {
        'type': 'array', 'maxItems': 5,
        'items': {'anyOf': [
            *[_action_schema(action, args) for action, args in _TOOL_SCHEMAS.items()],
            *[_action_schema('WORLD', args) for args in _WORLD_SCHEMAS.values()],
        ]},
    },
})
MODEL_SCHEMA['$defs'] = {
    'json_entry': _object({'key': {'type': 'string'}, 'value': {'$ref': '#/$defs/json_value'}}),
    'json_object': _object({'object_entries': {'type': 'array', 'items': {'$ref': '#/$defs/json_entry'}}}),
    'json_value': {'anyOf': [
        {'type': 'null'}, {'type': 'boolean'}, {'type': 'number'}, {'type': 'string'},
        {'type': 'array', 'items': {'$ref': '#/$defs/json_value'}},
        {'$ref': '#/$defs/json_object'},
    ]},
}

_MAX_JSON_DEPTH = 64


def _closed(value, required, optional=()):
    if type(value) is not dict or not set(required) <= value.keys() or value.keys() - set(required) - set(optional):
        raise ValueError('Invalid or unknown action fields')


def _validate_field(value, schema):
    """Check the scalar/array tool fields; stateful checks remain in the tools."""
    kind = schema['type']
    if isinstance(kind, list):
        kind = next(item for item in kind if item != 'null')
    expected = {'string': str, 'integer': int, 'array': list, 'boolean': bool, 'object': dict}[kind]
    if type(value) is not expected:
        raise ValueError('Invalid argument type')
    if 'enum' in schema and value not in schema['enum']:
        raise ValueError('Invalid argument option')
    if kind == 'string':
        if not schema.get('minLength', 0) <= len(value) <= schema.get('maxLength', len(value)):
            raise ValueError('Invalid argument length')
        if 'pattern' in schema and not re.search(schema['pattern'], value):
            raise ValueError('Invalid argument format')
    elif kind == 'boolean':
        return
    elif kind == 'object':
        _closed(value, set(schema['required']), set(schema['properties']) - set(schema['required']))
        for key, item in value.items():
            _validate_field(item, schema['properties'][key])
    elif kind == 'integer':
        if not schema.get('minimum', value) <= value <= schema.get('maximum', value):
            raise ValueError('Invalid integer argument')
    else:
        if not schema.get('minItems', 0) <= len(value) <= schema.get('maxItems', len(value)):
            raise ValueError('Invalid argument count')
        for item in value:
            _validate_field(item, schema['items'])


def _normalize_arguments(args, schema, legacy_optional=()):
    properties = schema['properties']
    nullable = {key for key, spec in properties.items()
                if isinstance(spec.get('type'), list) and 'null' in spec['type']}
    _closed(args, set(properties) - nullable - set(legacy_optional), nullable | set(legacy_optional))
    result = {}
    for key, value in args.items():
        if key in nullable and value is None:
            continue
        _validate_field(value, properties[key])
        result[key] = list(value) if type(value) is list else value
    return result


def _depth(depth):
    if depth > _MAX_JSON_DEPTH:
        raise ValueError('JSON request nesting limit exceeded')


def _primitive(value):
    if value is None or type(value) in (str, bool, int):
        return True
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError('Nonfinite JSON number')
        return True
    return False


def _decode_entries(entries, depth=0):
    _depth(depth)
    if type(entries) is not list:
        raise ValueError('JSON object entries must be an array')
    result = {}
    for entry in entries:
        _closed(entry, {'key', 'value'})
        key = entry['key']
        if type(key) is not str:
            raise ValueError('JSON object keys must be strings')
        if key in result:
            raise ValueError('Duplicate JSON object entry key')
        result[key] = _decode_value(entry['value'], depth + 1)
    return result


def _decode_value(value, depth):
    _depth(depth)
    if _primitive(value):
        return value
    if type(value) is list:
        return [_decode_value(item, depth + 1) for item in value]
    if type(value) is dict:
        _closed(value, {'object_entries'})
        return _decode_entries(value['object_entries'], depth)
    raise ValueError('Invalid JSON request value')


def _native_value(value, depth=0, encode=False):
    _depth(depth)
    if _primitive(value):
        return value
    if type(value) is list:
        return [_native_value(item, depth + 1, encode) for item in value]
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise ValueError('JSON object keys must be strings')
        converted = {key: _native_value(item, depth + 1, encode) for key, item in value.items()}
        if encode:
            return {'object_entries': [{'key': key, 'value': item} for key, item in converted.items()]}
        return converted
    raise ValueError('Invalid JSON request value')


def encode_request(request):
    """Encode a native finance request as the provider's request_entries array."""
    if type(request) is not dict:
        raise ValueError('Finance request must be an object')
    return _native_value(request, encode=True)['object_entries']


def normalize_model_action(action):
    """Convert one native provider/internal action, rejecting ambiguous shapes.

    Legacy args_json must be strict-parsed by the controller before calling
    this function. Nullable optional tool fields and exact workspace-root cwd
    aliases become absent; finance values retain their nulls and JSON fields.
    """
    _closed(action, {'agent', 'action', 'args'})
    _validate_field(action['agent'], _AGENT)
    kind, args = action['action'], action['args']
    if type(kind) is not str or kind not in {*_TOOL_SCHEMAS, 'WORLD'} or type(args) is not dict:
        raise ValueError('Invalid tool action')
    if kind == 'SPEND':
        if set(args) == {'request_entries'}:
            normalized = {'request': _decode_entries(args['request_entries'])}
        elif set(args) == {'request'} and type(args['request']) is dict:
            # Persisted/internal actions already carry ordinary JSON objects.
            normalized = {'request': _native_value(args['request'])}
        else:
            raise ValueError('Finance action requires one request format')
    elif kind == 'WORLD':
        op = args.get('op')
        if type(op) is not str or op not in _WORLD_SCHEMAS:
            raise ValueError('Unknown public world operation')
        normalized = _normalize_arguments(args, _WORLD_SCHEMAS[op])
    else:
        normalized = _normalize_arguments(args, _TOOL_SCHEMAS[kind],
                                          legacy_optional={'outputs'} if kind == 'EXEC' else ())
        if kind == 'EXEC' and normalized.get('cwd') in ('', '.', './', '/workspace', '/workspace/'):
            # These spellings name exactly the executor's fixed container root.
            # Other paths still pass the unchanged envelope confinement checks.
            normalized.pop('cwd', None)
    return {'agent': action['agent'], 'action': kind, 'args': normalized}
