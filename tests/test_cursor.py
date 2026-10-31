import json,pathlib,sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from controller import Controller,brain_command
class CursorTests(unittest.TestCase):
 def make(self):return Controller('/tmp/gl-cursor-test',None,None,{'controller':{'mode':'subscriptions','providers':['cursor'],'image':'sha256:'+'a'*64,'subscriptions_confirmed':True,'extra_usage_disabled':True}})
 def test_cursor_command_persists_whole_private_home_without_hiding_binary(self):
  argv=brain_command('/opt/globalland','sha256:'+'a'*64,'cursor');text=' '.join(argv)
  self.assertIn('dst=/home/node',text);self.assertIn('src=/opt/globalland/credentials/cursor,',text);self.assertIn('CURSOR_CONFIG_DIR=/home/node/.cursor',argv);self.assertIn('agent',text)
  self.assertIn('--mode',argv);self.assertEqual(argv[argv.index('--mode')+1],'ask')
  self.assertNotIn('API_KEY',text);self.assertNotIn('/ssh',text);self.assertNotIn('globalland/state',text)
 def test_cursor_docker_options_precede_image_and_are_retained_for_auth_checks(self):
  image='sha256:'+'a'*64
  argv=brain_command('/opt/globalland',image,'cursor')
  self.assertLess(max(i for i,x in enumerate(argv) if x=='--mount'),argv.index(image))
  self.assertEqual(argv[argv.index(image)+1],'cursor-agent')
  seen=[]
  def run(command,**kwargs):
   seen.append(command)
   return (0,b'--print --mode --output-format') if '--help' in command else (0,b'Logged in as user@example.com')
  with patch('controller.run_brain',side_effect=run):self.make().check_provider('cursor')
  for command in seen:self.assertIn('dst=/home/node/.cursor/cli-config.json,readonly',' '.join(command[:command.index(image)]))
 def test_cursor_nonobject_wrapper_is_rejected_as_structured_output(self):
  c=self.make()
  with patch.object(c,'check_provider'),patch('controller.run_brain',return_value=(0,b'[]')):
   with self.assertRaisesRegex(ValueError,'structured output'):c.plan('cursor','context')
 def test_cursor_rejects_duplicate_fields_in_wrapper_or_decision(self):
  decision='{"summary":"first","summary":"second","actions":[]}'
  wrapper=json.dumps({'type':'result','subtype':'success','is_error':False,'result':decision})
  duplicate=json.dumps({'type':'result','subtype':'success','is_error':False,'result':'{"summary":"ok","actions":[]}'}).replace('"subtype": "success"','"subtype": "error", "subtype": "success"')
  json.loads(duplicate)
  for raw in (wrapper,duplicate):
   c=self.make()
   with patch.object(c,'check_provider'),patch('controller.run_brain',return_value=(0,raw.encode())):
    with self.assertRaisesRegex(ValueError,'structured output'):c.plan('cursor','context')
 def test_cursor_policy_confines_reads_and_searches_without_user_overrides(self):
  scripts=pathlib.Path(__file__).resolve().parents[1]/'scripts'
  cli=json.loads((scripts/'cursor-cli-config.json').read_text());sandbox=json.loads((scripts/'cursor-sandbox.json').read_text())
  self.assertEqual(cli['approvalMode'],'allowlist');self.assertEqual(cli['sandbox']['readBoundary'],'workspace')
  self.assertEqual(cli['permissions']['allow'],[]);self.assertEqual(sandbox,{'readBoundary':'workspace','additionalReadPaths':[]})
  argv=brain_command('/opt/globalland','sha256:'+'a'*64,'cursor')
  self.assertIn('dst=/home/node/.cursor/sandbox.json,readonly',' '.join(argv))
 def test_cursor_readiness_recognizes_provider_but_not_fake_login(self):
  status=self.make().readiness();self.assertTrue(status['configured']);self.assertFalse(status['verified'])
 def test_cursor_status_rejects_negative_auth_and_api_key(self):
  for status in [b'Not authenticated',b'Unauthenticated',b'Logged out',b'Authenticated using API key']:
   c=self.make()
   with patch('controller.run_brain',side_effect=[(0,b'--print --mode --output-format'),(0,status)]):
    with self.assertRaisesRegex(ValueError,'authentication'):c.check_provider('cursor')
 def test_cursor_status_verifies_browser_login_without_echoing_identity(self):
  c=self.make()
  with patch('controller.run_brain',side_effect=[(0,b'--print --mode --output-format'),(0,b'Logged in as user@example.com')]):result=c.check_provider('cursor')
  self.assertTrue(result['subscription_auth_verified']);self.assertNotIn('user@example.com',json.dumps(result))
 def test_cursor_unwraps_result_and_validates_local_decision(self):
  c=self.make();decision={'summary':'Build product','actions':[{'agent':'BUILDER','action':'EXEC','args':{'argv':['node','-p','1'],'outputs':[]}}]}
  response={'type':'result','subtype':'success','is_error':False,'result':json.dumps(decision)}
  with patch.object(c,'check_provider'),patch('controller.run_brain',return_value=(0,json.dumps(response).encode())):self.assertEqual(c.plan('cursor','context'),decision)
 def test_cursor_malformed_or_error_result_is_not_a_decision(self):
  for response in [{'type':'result','subtype':'success','is_error':False,'result':'Not JSON'},{'type':'result','subtype':'error','is_error':True,'result':'{}'}, {'type':'result','subtype':'success','is_error':False,'result':{}}, {'type':'result','subtype':'success','is_error':False,'result':'{"summary":"x","actions":[],"x":NaN}'}]:
   c=self.make()
   with patch.object(c,'check_provider'),patch('controller.run_brain',return_value=(0,json.dumps(response).encode())):
    with self.assertRaisesRegex(ValueError,'structured output'):c.plan('cursor','context')
if __name__=='__main__':unittest.main()
