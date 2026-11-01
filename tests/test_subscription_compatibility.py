import os,pathlib,sys,unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from controller import Controller,brain_command
from supervisor import bounded_run
CODEX_HELP=b'--ignore-user-config --ignore-rules --sandbox --ephemeral --skip-git-repo-check --output-schema'
CLAUDE_HELP=b'--safe-mode --tools --disallowedTools --strict-mcp-config --mcp-config --json-schema --no-session-persistence --max-turns --permission-prompts'
class SubscriptionCompatibilityTests(unittest.TestCase):
 def make(self,provider):
  return Controller('/tmp/gl-compat',None,None,{'controller':{'mode':'subscriptions','providers':[provider],'image':'sha256:'+'a'*64,'subscriptions_confirmed':True,'extra_usage_disabled':True}})
 def test_codex_exec_options_follow_exec_subcommand(self):
  argv=brain_command('/tmp/gl-compat','sha256:'+'a'*64,'codex')
  self.assertLess(argv.index('exec'),argv.index('--ignore-user-config'))
  self.assertLess(argv.index('exec'),argv.index('--ignore-rules'))
 def test_codex_login_status_has_no_exec_options_and_no_shell(self):
  seen=[]
  def run(argv,**kwargs):
   command=argv[argv.index('sha256:'+'a'*64)+1:];seen.append((command,kwargs))
   if command==['codex','exec','--help']:return 0,CODEX_HELP
   if command==['codex','login','status']:return 0,b'Logged in using ChatGPT'
   return 2,b'unexpected argument'
  with patch('controller.run_brain',side_effect=run):self.make('codex').check_provider('codex')
  self.assertEqual([c for c,_ in seen],[['codex','exec','--help'],['codex','login','status']])
  self.assertTrue(all(kw.get('merge_stderr') for _,kw in seen))
 def test_claude_auth_status_uses_documented_default_json(self):
  def run(argv,**kwargs):
   command=argv[argv.index('sha256:'+'a'*64)+1:]
   if command==['claude','--help']:return 0,CLAUDE_HELP
   if command==['claude','--max-turns','2','auth','status']:return 0,b'{"loggedIn":true,"authMethod":"claude.ai"}'
   return 1,b'unknown option --json'
  with patch('controller.run_brain',side_effect=run):self.make('claude').check_provider('claude')
 def test_hidden_max_turns_is_probed_by_status_without_inference(self):
  commands=[]
  def run(argv,**kwargs):
   command=argv[argv.index('sha256:'+'a'*64)+1:];commands.append(command)
   if command==['claude','--help']:return 0,CLAUDE_HELP.replace(b'--max-turns',b'')
   if command==['claude','--globalland-invalid-option-probe','auth','status']:return 1,b"error: unknown option '--globalland-invalid-option-probe'"
   if command==['claude','--max-turns','2','auth','status']:return 0,b'{"loggedIn":true,"authMethod":"claude.ai"}'
   raise AssertionError('Only help and option-bearing auth status may run')
  with patch('controller.run_brain',side_effect=run):result=self.make('claude').check_provider('claude')
  self.assertTrue(result['subscription_auth_verified']);self.assertEqual(len(commands),3)
  runtime=brain_command('/tmp/gl-compat','sha256:'+'a'*64,'claude')
  self.assertEqual(runtime[runtime.index('--max-turns')+1],'2')
 def test_hidden_option_rejected_by_parser_keeps_provider_unverified(self):
  c=self.make('claude')
  with patch('controller.run_brain',side_effect=[(0,CLAUDE_HELP.replace(b'--max-turns',b'')),(1,b'unknown option --globalland-invalid-option-probe'),(1,b'unknown option --max-turns')]):
   with self.assertRaisesRegex(ValueError,'status exit=1'):c.check_provider('claude')
  self.assertFalse(c.readiness()['verified'])
 def test_hidden_option_probe_does_not_accept_api_auth(self):
  c=self.make('claude')
  with patch('controller.run_brain',side_effect=[(0,CLAUDE_HELP.replace(b'--max-turns',b'')),(1,b'unknown option --globalland-invalid-option-probe'),(0,b'{"loggedIn":true,"authMethod":"api_key"}')]):
   with self.assertRaisesRegex(ValueError,'authentication'):c.check_provider('claude')
  self.assertFalse(c.readiness()['verified'])
 def test_hidden_option_probe_rejects_cli_that_silently_ignores_unknown_flags(self):
  c=self.make('claude')
  with patch('controller.run_brain',side_effect=[(0,CLAUDE_HELP.replace(b'--max-turns',b'')),(0,b'{"loggedIn":true,"authMethod":"claude.ai"}')]) as run:
   with self.assertRaisesRegex(ValueError,'probe inconclusive'):c.check_provider('claude')
   self.assertEqual(run.call_count,2)
  self.assertFalse(c.readiness()['verified'])
 def test_failed_negative_control_must_name_the_rejected_flag(self):
  c=self.make('claude')
  with patch('controller.run_brain',side_effect=[(0,CLAUDE_HELP.replace(b'--max-turns',b'')),(1,b'network error')]):
   with self.assertRaisesRegex(ValueError,'probe inconclusive'):c.check_provider('claude')
  self.assertFalse(c.readiness()['verified'])
 def test_missing_flags_identify_provider_and_exact_options(self):
  with patch('controller.run_brain',return_value=(0,b'--tools')):
   with self.assertRaisesRegex(ValueError,r'claude:.*--safe-mode'):self.make('claude').check_provider('claude')
 def test_auth_failure_identifies_provider_and_exit_without_printing_account(self):
  with patch('controller.run_brain',side_effect=[(0,CLAUDE_HELP),(1,b'private account text')]):
   with self.assertRaisesRegex(ValueError,r'claude:.*exit=1') as error:self.make('claude').check_provider('claude')
  self.assertNotIn('private account',str(error.exception))
 def test_merge_stderr_collects_help_written_to_stderr(self):
  code,out=bounded_run([sys.executable,'-c','import sys;sys.stderr.write("--safe-mode")'],env=os.environ,merge_stderr=True)
  self.assertEqual((code,out),(0,b'--safe-mode'))
 def test_default_capture_keeps_diagnostic_stderr_out_of_model_json(self):
  code,out=bounded_run([sys.executable,'-c','import sys;sys.stderr.write("warning");sys.stdout.write("{}")'],env=os.environ)
  self.assertEqual((code,out),(0,b'{}'))
 def test_merged_stderr_obeys_combined_output_limit(self):
  with self.assertRaisesRegex(ValueError,'output limit'):
   bounded_run([sys.executable,'-c','import sys;sys.stderr.write("x"*2000)'],env=os.environ,limit=1000,merge_stderr=True)
if __name__=='__main__':unittest.main()
