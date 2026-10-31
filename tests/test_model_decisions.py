import json,pathlib,sys,unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
import controller
class ModelDecisionTests(unittest.TestCase):
 def model_schema(self):return getattr(controller,'MODEL_SCHEMA',controller.SCHEMA)
 def controller(self):return controller.Controller('/tmp/gl-model',None,None,{'controller':{'image':'sha256:'+'a'*64}})
 def decision(self,args=None):return {'summary':'Build','actions':[{'agent':'BUILDER','action':'EXEC','args':args or {'argv':['node','-p','1'],'outputs':[]}}]}
 def wire(self,decision=None):
  decision=decision or self.decision()
  actions=[]
  for action in decision['actions']:
   item={'agent':action['agent'],'action':action['action'],'args':dict(action['args'])}
   if action['action']=='EXEC':item['args'].update(cwd=None,mission_id=None)
   actions.append(item)
  return {'summary':decision['summary'],'actions':actions}
 def test_provider_schema_closes_every_object_and_requires_all_fields(self):
  # External OpenAI strict-output contract, including native action variants.
  def walk(node):
   if isinstance(node,dict):
    if node.get('type')=='object':
     self.assertIs(node.get('additionalProperties'),False,'OpenAI requires closed objects')
     self.assertEqual(set(node.get('required',[])),set(node.get('properties',{})))
    for value in node.values():walk(value)
   elif isinstance(node,list):
    for value in node:walk(value)
  walk(self.model_schema())
  variants=self.model_schema()['properties']['actions']['items'].get('anyOf',[])
  self.assertTrue(variants,'Actions must have typed native argument variants')
  for variant in variants:
   self.assertIn('args',variant['properties']);self.assertNotIn('args_json',variant['properties'])
  execute=next(v for v in variants if v['properties']['action'].get('enum')==['EXEC'])
  self.assertEqual(execute['properties']['args']['properties']['argv']['items']['type'],'string')
 def test_codex_file_and_claude_schema_describe_the_same_wire_contract(self):
  image='sha256:'+'a'*64;argv=controller.brain_command('/tmp',image,'claude')
  cli=json.loads(argv[argv.index('--json-schema')+1]);installed=json.loads((pathlib.Path(__file__).resolve().parents[1]/'scripts/decision.schema.json').read_text())
  self.assertEqual(cli,self.model_schema());self.assertEqual(installed,cli)
 def test_all_providers_decode_wire_arguments_to_normal_tasks(self):
  wanted=self.decision();wire=self.wire(wanted)
  for provider in ('codex','claude','cursor'):
   value=wire if provider=='codex' else {'type':'result','subtype':'success','is_error':False,('structured_output' if provider=='claude' else 'result'):(wire if provider=='claude' else json.dumps(wire))}
   c=self.controller()
   with patch.object(c,'check_provider'),patch('controller.run_brain',return_value=(0,json.dumps(value).encode())):self.assertEqual(c.plan(provider,'context'),wanted)
 def test_nested_arbitrary_args_preserved_without_narrowing_agent_tools(self):
  wanted={'summary':'Explore','actions':[{'agent':'DIRECTOR','action':'SPEND','args':{'request':{'market':'worldwide','custom':{'symbols':['A','B'],'limit':0}}}}]}
  c=self.controller()
  wire={'summary':'Explore','actions':[{'agent':'DIRECTOR','action':'SPEND','args':{'request_entries':[
   {'key':'market','value':'worldwide'},
   {'key':'custom','value':{'object_entries':[{'key':'symbols','value':['A','B']},{'key':'limit','value':0}]}}
  ]}}]}
  with patch.object(c,'check_provider'),patch('controller.run_brain',return_value=(0,json.dumps(wire).encode())):self.assertEqual(c.plan('codex','context'),wanted)
 def test_nested_json_rejects_duplicates_nonfinite_arrays_and_mixed_fields(self):
  for args in ('{"a":1,"a":2}','{"cost":NaN}','{"cost":1e999}','[]','null'):
   wire={'summary':'Build','actions':[{'agent':'BUILDER','action':'EXEC','args_json':args}]}
   c=self.controller()
   with patch.object(c,'check_provider'),patch('controller.run_brain',return_value=(0,json.dumps(wire).encode())):
    with self.assertRaises(ValueError):c.plan('codex','context')
  wire=self.wire();wire['actions'][0]['args_json']='{}'
  c=self.controller()
  with patch.object(c,'check_provider'),patch('controller.run_brain',return_value=(0,json.dumps(wire).encode())):
   with self.assertRaises(ValueError):c.plan('codex','context')
 def test_quote_heavy_javascript_round_trips_without_nested_json_parsing(self):
  code='const csv = `=HYPERLINK("https://example.com", "CSV")`;\nconsole.log(/^[=+@\\-]/.test(csv));'
  wanted=self.decision({'argv':['node','-e',code],'outputs':[]});c=self.controller()
  raw=json.dumps(self.wire(wanted)).encode()
  with patch.object(c,'check_provider'),patch('controller.run_brain',return_value=(0,raw)):
   self.assertEqual(c.plan('codex','context'),wanted)
 def test_claude_error_wrapper_never_executes_embedded_structured_output(self):
  value={'type':'result','subtype':'error_max_turns','is_error':True,'structured_output':self.decision()}
  c=self.controller()
  with patch.object(c,'check_provider'),patch('controller.run_brain',return_value=(0,json.dumps(value).encode())):
   with self.assertRaises(ValueError):c.plan('claude','context')
 def test_legacy_internal_decisions_still_decode_for_recovery_compatibility(self):
  c=self.controller();wanted=self.decision()
  with patch.object(c,'check_provider'),patch('controller.run_brain',return_value=(0,json.dumps(wanted).encode())):self.assertEqual(c.plan('codex','context'),wanted)
 def test_claude_budget_allows_structured_output_tool_round_trip(self):
  argv=controller.brain_command('/tmp','sha256:'+'a'*64,'claude')
  self.assertGreaterEqual(int(argv[argv.index('--max-turns')+1]),2)
if __name__=='__main__':unittest.main()
