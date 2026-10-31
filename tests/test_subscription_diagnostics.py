import pathlib,sys,unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
try:
 from diagnose_subscriptions import diagnose,safe_excerpt
except ImportError:
 diagnose=safe_excerpt=None
class DiagnosticTests(unittest.TestCase):
 def test_public_help_excerpt_masks_credentials_and_email(self):
  self.assertIsNotNone(safe_excerpt,'diagnostic redaction missing')
  raw=b'user@example.com sk-'+b'a'*45+b' TOKEN=abcdefghijk '+b'b'*80
  shown=safe_excerpt(raw)
  for sensitive in ('user@example.com','sk-'+ 'a'*45,'abcdefghijk','b'*80):self.assertNotIn(sensitive,shown)
 def test_diagnostic_only_runs_version_help_and_auth_status_and_hides_account(self):
  self.assertIsNotNone(diagnose,'diagnostic command missing')
  calls=[]
  def run(argv,**kwargs):
   cmd=argv[argv.index('sha256:'+'a'*64)+1:];calls.append(cmd)
   if cmd==['claude','--version']:return 0,b'2.1.316 (Claude Code)'
   if cmd==['claude','--help']:return 0,b'Usage: claude --tools --safe-mode'
   if cmd==['claude','--max-turns','1','auth','status']:return 0,b'{"loggedIn":true,"authMethod":"claude.ai","email":"user@example.com","access_token":"private"}'
   raise AssertionError('unexpected command')
  with patch('diagnose_subscriptions.run_brain',side_effect=run):report=diagnose('/tmp/test','sha256:'+'a'*64,'claude')
  self.assertEqual(calls,[['claude','--version'],['claude','--help'],['claude','--max-turns','1','auth','status']])
  self.assertIn('--json-schema',report['help']['missing_options'])
  self.assertEqual(report['auth']['method'],'claude.ai');self.assertNotIn('user@example.com',str(report));self.assertNotIn('private',str(report))
 def test_error_categories_do_not_echo_raw_stderr(self):
  self.assertIsNotNone(diagnose,'diagnostic command missing')
  with patch('diagnose_subscriptions.run_brain',side_effect=[(0,b'2.1.316'),(0,b''),(1,b'EROFS: read-only file system private@example.com')]):report=diagnose('/tmp/test','sha256:'+'a'*64,'claude')
  self.assertEqual(report['auth']['error_categories'],['read_only_filesystem']);self.assertNotIn('private@example.com',str(report))
if __name__=='__main__':unittest.main()
