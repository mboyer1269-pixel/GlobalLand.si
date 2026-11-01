"""Provider transport fidelity and strict schema checks without paid model calls."""
import copy
import importlib
import importlib.util
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))


class DecisionProtocolTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('decision_protocol'),
                             'the native typed decision protocol is not implemented')
        self.protocol = importlib.import_module('decision_protocol')

    def action(self, kind, args):
        return {'agent': 'BUILDER', 'action': kind, 'args': args}

    def normalize(self, kind, args):
        return self.protocol.normalize_model_action(self.action(kind, args))

    def variants(self):
        return self.protocol.MODEL_SCHEMA['properties']['actions']['items']['anyOf']

    def test_embedded_javascript_round_trips_without_a_second_json_parser(self):
        # The old transport can have valid outer JSON and invalid JSON inside
        # args_json when the model emits JS string quotes without another escape.
        broken_args = '{"argv":["node","-e","console.log("world")"],"outputs":[]}'
        old = json.loads(json.dumps({'args_json': broken_args}))
        with self.assertRaises(json.JSONDecodeError):
            json.loads(old['args_json'])
        code = 'const x = {s: "café 🦉", path: "C:\\\\tmp"};\nconsole.log(JSON.stringify(x));'
        wanted = self.action('EXEC', {'argv': ['node', '-e', code], 'outputs': []})
        provider = copy.deepcopy(wanted)
        provider['args'].update(cwd=None, mission_id=None)
        received = json.loads(json.dumps(provider, ensure_ascii=False))
        self.assertEqual(self.protocol.normalize_model_action(received), wanted)
        self.assertEqual(received, provider, 'normalization must not mutate provider data')

    def test_schema_closes_every_object_and_requires_every_defined_property(self):
        def walk(node):
            if isinstance(node, dict):
                if node.get('type') == 'object':
                    self.assertIs(node.get('additionalProperties'), False)
                    self.assertEqual(set(node.get('required', [])), set(node.get('properties', {})))
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)
        schema = self.protocol.MODEL_SCHEMA
        walk(schema)
        self.assertEqual(set(schema['properties']), {'summary', 'actions'})
        self.assertEqual(schema['properties']['actions']['maxItems'], 5)
        self.assertNotIn('args_json', json.dumps(schema))
        for variant in self.variants():
            properties = variant['properties']
            self.assertEqual(set(properties), {'agent', 'action', 'args'})
            self.assertEqual(properties['agent']['pattern'], '^[A-Z0-9_-]{1,64}$')
            self.assertEqual(len(properties['action']['enum']), 1)
            self.assertEqual(properties['args']['type'], 'object')

    def test_schema_covers_all_tools_and_public_world_operations(self):
        kinds = {v['properties']['action']['enum'][0] for v in self.variants()}
        self.assertEqual(kinds, {'EXEC', 'FETCH', 'STATUS', 'RECONCILE', 'SPEND', 'WORLD', 'PUBLISH_ACTOR', 'ACTOR_STATS'})
        world = [v['properties']['args'] for v in self.variants()
                 if v['properties']['action']['enum'] == ['WORLD']]
        self.assertEqual({v['properties']['op']['enum'][0] for v in world}, {
            'register_agent', 'create_mission', 'claim_mission', 'complete_mission',
            'fail_mission', 'message', 'transfer_glc', 'reward_glc', 'set_policy', 'cycle',
            'raise_blocker', 'resolve_blocker', 'record_lesson', 'review',
        })
        self.assertEqual(len(self.variants()), 21)

    def test_schema_represents_finance_json_recursively_with_entries_only(self):
        schema = self.protocol.MODEL_SCHEMA
        spend = next(v['properties']['args'] for v in self.variants()
                     if v['properties']['action']['enum'] == ['SPEND'])
        self.assertEqual(set(spend['properties']), {'request_entries'})
        entries = spend['properties']['request_entries']
        self.assertEqual(entries['type'], 'array')
        self.assertIn('$ref', entries['items'])
        definitions = schema['$defs']
        self.assertGreaterEqual(len(definitions), 2)
        # Every object under the recursive definitions is either an entry or
        # the explicit object wrapper: no arbitrary JSON objects are permitted.
        for definition in definitions.values():
            if definition.get('type') == 'object':
                self.assertIn(set(definition['properties']), ({'key', 'value'}, {'object_entries'}))
        self.assertIn('"type": "null"', json.dumps(definitions))
        self.assertIn('"type": "boolean"', json.dumps(definitions))
        self.assertIn('"type": "number"', json.dumps(definitions))
        self.assertIn('"type": "string"', json.dumps(definitions))
        self.assertIn('"type": "array"', json.dumps(definitions))

    def test_exec_preserves_arbitrary_program_and_optional_absence(self):
        args = {'argv': ['sh', '-c', 'printf \'"\\n$HOME`literal`\\\\\''], 'outputs': []}
        self.assertEqual(self.normalize('EXEC', args), self.action('EXEC', args))
        self.assertEqual(self.normalize('EXEC', {'argv': ['node', '-p', '1']}),
                         self.action('EXEC', {'argv': ['node', '-p', '1']}))
        args.update(cwd='project', mission_id='WORLD-FIRST-REVENUE')
        self.assertEqual(self.normalize('EXEC', args), self.action('EXEC', args))

    def test_nullable_exec_and_fetch_options_become_absent(self):
        self.assertEqual(self.normalize('EXEC', {'argv': ['node'], 'outputs': [], 'cwd': None, 'mission_id': None}),
                         self.action('EXEC', {'argv': ['node'], 'outputs': []}))
        self.assertEqual(self.normalize('FETCH', {'url': 'https://example.com', 'output': 'products/web.txt', 'encoding': None}),
                         self.action('FETCH', {'url': 'https://example.com', 'output': 'products/web.txt'}))

    def test_fetch_status_and_reconcile_preserve_native_arguments(self):
        examples = [
            ('FETCH', {'url': 'https://example.com/é', 'output': 'products/research.txt'}),
            ('FETCH', {'url': 'https://example.com', 'output': 'products/b64.txt', 'encoding': 'base64'}),
            ('FETCH', {'url': 'https://example.com', 'output': 'products/utf8.txt', 'encoding': 'utf-8'}),
            ('STATUS', {}), ('RECONCILE', {'operation_id': 'TASK-0001'}),
        ]
        for kind, args in examples:
            with self.subTest(kind=kind, args=args):
                self.assertEqual(self.normalize(kind, args), self.action(kind, args))

    def test_all_public_world_operations_preserve_fields(self):
        examples = [
            {'op': 'register_agent', 'agent_id': 'helper.1', 'role': 'Build products'},
            {'op': 'create_mission', 'mission_id': 'M1', 'goal': 'Earn', 'agent_id': 'BUILDER', 'parent_id': 'WORLD-FIRST-REVENUE', 'priority': 0},
            {'op': 'claim_mission', 'mission_id': 'M1', 'agent_id': 'BUILDER', 'lease_seconds': 3600},
            {'op': 'complete_mission', 'mission_id': 'M1', 'agent_id': 'BUILDER', 'lease_token': 'existing', 'evidence': ['products/proof.txt']},
            {'op': 'fail_mission', 'mission_id': 'M1', 'agent_id': 'BUILDER', 'lease_token': 'existing', 'reason': 'No demand'},
            {'op': 'message', 'from_agent': 'BUILDER', 'to_agent': 'DIRECTOR', 'body': 'Result'},
            {'op': 'transfer_glc', 'from_agent': 'BUILDER', 'to_agent': 'RESEARCHER', 'amount': 0},
            {'op': 'reward_glc', 'agent_id': 'BUILDER', 'amount': 1, 'evidence': ['products/proof.txt']},
            {'op': 'set_policy', 'maintenance_glc': 0, 'interest_basis_points': 500},
            {'op': 'cycle', 'cycle_id': 'cycle:1'},
        ]
        for args in examples:
            with self.subTest(op=args['op']):
                self.assertEqual(self.normalize('WORLD', args), self.action('WORLD', args))

    def test_world_nullable_options_use_real_world_defaults(self):
        self.assertEqual(self.normalize('WORLD', {'op': 'create_mission', 'mission_id': 'M1', 'goal': 'Earn',
                                                  'agent_id': None, 'parent_id': None, 'priority': None}),
                         self.action('WORLD', {'op': 'create_mission', 'mission_id': 'M1', 'goal': 'Earn'}))
        self.assertEqual(self.normalize('WORLD', {'op': 'claim_mission', 'mission_id': 'M1', 'agent_id': 'BUILDER', 'lease_seconds': None}),
                         self.action('WORLD', {'op': 'claim_mission', 'mission_id': 'M1', 'agent_id': 'BUILDER'}))

    def test_missing_world_options_remain_compatible_with_internal_decisions(self):
        for args in [{'op': 'create_mission', 'mission_id': 'M1', 'goal': 'Earn'},
                     {'op': 'claim_mission', 'mission_id': 'M1', 'agent_id': 'BUILDER'}]:
            self.assertEqual(self.normalize('WORLD', args), self.action('WORLD', args))

    def test_required_nulls_are_rejected_instead_of_silently_removed(self):
        examples = [
            ('EXEC', {'argv': ['node'], 'outputs': []}),
            ('FETCH', {'url': 'https://example.com', 'output': 'products/web.txt', 'encoding': 'utf-8'}),
            ('RECONCILE', {'operation_id': 'TASK-0001'}),
            ('WORLD', {'op': 'register_agent', 'agent_id': 'BUILDER', 'role': 'Build'}),
            ('WORLD', {'op': 'create_mission', 'mission_id': 'M1', 'goal': 'Earn'}),
            ('WORLD', {'op': 'claim_mission', 'mission_id': 'M1', 'agent_id': 'BUILDER'}),
            ('WORLD', {'op': 'complete_mission', 'mission_id': 'M1', 'agent_id': 'BUILDER', 'lease_token': 'existing', 'evidence': ['proof']}),
            ('WORLD', {'op': 'fail_mission', 'mission_id': 'M1', 'agent_id': 'BUILDER', 'lease_token': 'existing', 'reason': 'Failed'}),
            ('WORLD', {'op': 'message', 'from_agent': 'BUILDER', 'to_agent': 'DIRECTOR', 'body': 'result'}),
            ('WORLD', {'op': 'transfer_glc', 'from_agent': 'BUILDER', 'to_agent': 'DIRECTOR', 'amount': 0}),
            ('WORLD', {'op': 'reward_glc', 'agent_id': 'BUILDER', 'amount': 1, 'evidence': ['proof']}),
            ('WORLD', {'op': 'set_policy', 'maintenance_glc': 0, 'interest_basis_points': 500}),
            ('WORLD', {'op': 'cycle', 'cycle_id': 'cycle:1'}),
        ]
        for kind, args in examples:
            for field in args:
                if kind == 'FETCH' and field == 'encoding':
                    continue
                with self.subTest(kind=kind, field=field, op=args.get('op')):
                    invalid = dict(args, **{field: None})
                    with self.assertRaises(ValueError):
                        self.normalize(kind, invalid)

    def test_missing_required_arguments_are_rejected(self):
        for kind, args in [('EXEC', {}), ('FETCH', {'url': 'https://example.com'}),
                           ('RECONCILE', {}), ('WORLD', {'op': 'message', 'body': 'Result'}),
                           ('SPEND', {})]:
            with self.subTest(kind=kind):
                with self.assertRaises(ValueError):
                    self.normalize(kind, args)

    def test_unknown_fields_and_invalid_action_shapes_are_rejected(self):
        examples = [None, [], {}, {'agent': 'builder', 'action': 'STATUS', 'args': {}},
                    {'agent': 'BUILDER', 'action': 'UNKNOWN', 'args': {}},
                    {'agent': 'BUILDER', 'action': 'STATUS', 'args': []},
                    {'agent': 'BUILDER', 'action': 'STATUS', 'args': {}, 'extra': 1},
                    {'agent': 'BUILDER', 'action': 'STATUS', 'args_json': '{}'}]
        for action in examples:
            with self.subTest(action=action):
                with self.assertRaises(ValueError):
                    self.protocol.normalize_model_action(action)
        for kind, args in [('STATUS', {'extra': None}), ('EXEC', {'argv': ['node'], 'shell': True}),
                           ('FETCH', {'url': 'https://example.com', 'output': 'products/web.txt', 'headers': {}}),
                           ('WORLD', {'op': 'extinguish', 'reason': 'model request'}),
                           ('WORLD', {'op': 'cycle', 'cycle_id': '1', 'extra': None})]:
            with self.subTest(kind=kind, args=args):
                with self.assertRaises(ValueError):
                    self.normalize(kind, args)

    def test_typed_fields_reject_invalid_values_and_boolean_integers(self):
        examples = [
            ('EXEC', {'argv': [None], 'outputs': []}),
            ('EXEC', {'argv': ['node'], 'outputs': [None]}),
            ('EXEC', {'argv': ['node'], 'cwd': 1}),
            ('FETCH', {'url': 'https://example.com', 'output': 'products/web.txt', 'encoding': 'binary'}),
            ('WORLD', {'op': 'transfer_glc', 'from_agent': 'BUILDER', 'to_agent': 'DIRECTOR', 'amount': True}),
            ('WORLD', {'op': 'set_policy', 'maintenance_glc': 1.5, 'interest_basis_points': 500}),
            ('WORLD', {'op': 'claim_mission', 'mission_id': 'M1', 'agent_id': 'BUILDER', 'lease_seconds': 0}),
            ('WORLD', {'op': 'complete_mission', 'mission_id': 'M1', 'agent_id': 'BUILDER', 'lease_token': 'existing', 'evidence': []}),
        ]
        for kind, args in examples:
            with self.subTest(kind=kind, args=args):
                with self.assertRaises(ValueError):
                    self.normalize(kind, args)

    def test_finance_entries_decode_every_json_type_and_preserve_nulls(self):
        encoded = [
            {'key': 'market', 'value': 'worldwide'},
            {'key': 'amount', 'value': 0},
            {'key': 'rate', 'value': 0.125},
            {'key': 'flag', 'value': True},
            {'key': 'optional', 'value': None},
            {'key': 'custom', 'value': {'object_entries': [
                {'key': 'symbols', 'value': ['A', 'B', False, None, {'object_entries': []}]},
                {'key': 'limit', 'value': 0},
                {'key': 'object_entries', 'value': {'object_entries': [{'key': '', 'value': []}]}},
            ]}},
        ]
        wanted = {'request': {'market': 'worldwide', 'amount': 0, 'rate': 0.125, 'flag': True, 'optional': None,
                              'custom': {'symbols': ['A', 'B', False, None, {}], 'limit': 0, 'object_entries': {'': []}}}}
        wire = json.loads(json.dumps(encoded))
        self.assertEqual(self.normalize('SPEND', {'request_entries': wire}), self.action('SPEND', wanted))
        self.assertEqual(wire, encoded)
        self.assertEqual(self.normalize('SPEND', {'request_entries': []}), self.action('SPEND', {'request': {}}))

    def test_native_finance_objects_remain_arbitrary_and_unmodified(self):
        request = {'mission_id': None, 'priority': None, 'metadata': {'object_entries': [{'any': None}]},
                   'flags': [True, False], 'debit': 50, 'currency': 'CAD'}
        args = {'request': request}
        self.assertEqual(self.normalize('SPEND', args), self.action('SPEND', args))

    def test_finance_encoder_produces_a_real_transport_for_arbitrary_requests(self):
        request = {'name': 'é', 'metadata': {'empty': {}, 'array': [None, {'quote': '"\\\n'}]}, 'paid': False}
        expected = [
            {'key': 'name', 'value': 'é'},
            {'key': 'metadata', 'value': {'object_entries': [
                {'key': 'empty', 'value': {'object_entries': []}},
                {'key': 'array', 'value': [None, {'object_entries': [{'key': 'quote', 'value': '"\\\n'}]}]},
            ]}},
            {'key': 'paid', 'value': False},
        ]
        encoded = self.protocol.encode_request(request)
        self.assertEqual(encoded, expected)
        self.assertEqual(self.normalize('SPEND', {'request_entries': json.loads(json.dumps(encoded))}),
                         self.action('SPEND', {'request': request}))

    def test_finance_rejects_duplicate_entry_keys_at_every_nesting_level(self):
        duplicate = [{'key': 'cost', 'value': 1}, {'key': 'cost', 'value': 2}]
        examples = [duplicate, [{'key': 'nested', 'value': {'object_entries': duplicate}}],
                    [{'key': 'array', 'value': [{'object_entries': duplicate}]}]]
        for entries in examples:
            with self.subTest(entries=entries):
                with self.assertRaises(ValueError):
                    self.normalize('SPEND', {'request_entries': entries})

    def test_finance_rejects_unknown_shapes_and_mixed_formats(self):
        bad_values = [{}, {'raw': 1}, {'object_entries': [], 'extra': None}, {'object_entries': {}}, (), {1}, object()]
        bad_entries = [None, {}, ['entry'], [{'key': 'a'}], [{'value': 1}],
                       [{'key': 'a', 'value': 1, 'extra': None}], [{'key': 1, 'value': None}]]
        bad_entries += [[{'key': 'x', 'value': value}] for value in bad_values]
        for entries in bad_entries:
            with self.subTest(entries=entries):
                with self.assertRaises(ValueError):
                    self.normalize('SPEND', {'request_entries': entries})
        for args in [{'request': {}, 'request_entries': []}, {'request': None}, {'request_entries': None},
                     {'request': {}, 'extra': 1}]:
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    self.normalize('SPEND', args)

    def test_finance_rejects_nonfinite_and_non_json_native_values(self):
        for value in [float('nan'), float('inf'), float('-inf'), (), {1}, object()]:
            for args in [{'request_entries': [{'key': 'value', 'value': value}]}, {'request': {'value': value}}]:
                with self.subTest(args=args):
                    with self.assertRaises(ValueError):
                        self.normalize('SPEND', args)
            with self.subTest(encode=value):
                with self.assertRaises(ValueError):
                    self.protocol.encode_request({'value': value})
        for request in [[], None, {1: 'non-string key'}]:
            with self.assertRaises(ValueError):
                self.protocol.encode_request(request)
            with self.assertRaises(ValueError):
                self.normalize('SPEND', {'request': request})

    def test_finance_limits_deep_or_cyclic_inputs_with_value_error(self):
        deep = 1
        for _ in range(100):
            deep = [deep]
        cyclic = []
        cyclic.append(cyclic)
        for value in [deep, cyclic]:
            with self.subTest(kind='wire', value_type=type(value)):
                with self.assertRaises(ValueError):
                    self.normalize('SPEND', {'request_entries': [{'key': 'nested', 'value': value}]})
            with self.subTest(kind='native', value_type=type(value)):
                with self.assertRaises(ValueError):
                    self.normalize('SPEND', {'request': {'nested': value}})
            with self.assertRaises(ValueError):
                self.protocol.encode_request({'nested': value})


if __name__ == '__main__':
    unittest.main()
