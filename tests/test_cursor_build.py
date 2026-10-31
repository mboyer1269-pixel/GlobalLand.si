import json,os,pathlib,subprocess,sys,tempfile,unittest

class CursorBuildTests(unittest.TestCase):
 def run_build(self,missing=False,retagged=False,version_failed=False):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);base='sha256:'+'a'*64;output=root/'cursor-image.txt';source=root/'brain-image.txt';source.write_text(base+'\n');
   if version_failed:output.write_text('sha256:'+'d'*64+'\n')
   log=root/'calls.jsonl'
   docker=root/'docker'
   docker.write_text('#!'+sys.executable+'\n'+'''import json,os,sys,pathlib
args=sys.argv[1:];log=pathlib.Path(os.environ['GL_TEST_LOG'])
with log.open('a') as f:f.write(json.dumps(args)+'\\n')
if args[0]=='build':pathlib.Path(args[args.index('--iidfile')+1]).write_text('sha256:'+'b'*64)
if args[0]=='run' and os.environ.get('GL_TEST_VERSION_FAILED')=='1':sys.exit(1)
if args[:2]==['image','inspect']:
 if os.environ.get('GL_TEST_MISSING')=='1':sys.exit(1)
 target=args[2]
 if target=='globalland-brain:cursor':print('sha256:'+'b'*64)
 elif target.startswith('globalland-brain:cursor-base-') and os.environ.get('GL_TEST_RETAGGED')=='1':print('sha256:'+'c'*64)
 else:print('sha256:'+'a'*64)
''');docker.chmod(0o755)
   env=dict(os.environ,PATH=str(root)+':'+os.environ['PATH'],GL_TEST_LOG=str(log),GL_TEST_VERSION_FAILED='1' if version_failed else '0',GL_TEST_MISSING='1' if missing else '0',GL_TEST_RETAGGED='1' if retagged else '0')
   script=pathlib.Path(__file__).resolve().parents[1]/'scripts/build_cursor_image.sh'
   run=subprocess.run(['bash',str(script),str(source),str(output)],env=env,capture_output=True,text=True)
   return run,[json.loads(x) for x in log.read_text().splitlines()] if log.exists() else [],source.read_text(),output.read_text() if output.exists() else None
 def test_build_uses_verified_local_tag_and_preserves_old_image_id(self):
  run,calls,source,output=self.run_build();self.assertEqual(run.returncode,0,run.stderr)
  build=next(c for c in calls if c[0]=='build');self.assertIn('--pull=false',build)
  arg=build[build.index('--build-arg')+1];self.assertEqual(arg,'EXISTING_BRAIN_IMAGE=globalland-brain:cursor-base-'+'a'*64)
  self.assertTrue(any(c[:2]==['image','tag'] and c[2]==source.strip() for c in calls))
  self.assertEqual(source,'sha256:'+'a'*64+'\n');self.assertEqual(output,'sha256:'+'b'*64+'\n')
  self.assertIn(['run','--rm','--network','none','sha256:'+'b'*64,'cursor-agent','--version'],calls)
 def test_failed_version_preserves_previous_cursor_image_file(self):
  run,_,_,output=self.run_build(version_failed=True);self.assertNotEqual(run.returncode,0);self.assertEqual(output,'sha256:'+'d'*64+'\n')
 def test_missing_base_stops_before_build_and_does_not_record_cursor(self):
  run,calls,_,output=self.run_build(missing=True);self.assertNotEqual(run.returncode,0);self.assertTrue(calls);self.assertFalse(any(c[0]=='build' for c in calls));self.assertIsNone(output)
 def test_local_tag_mismatch_stops_before_build(self):
  run,calls,_,output=self.run_build(retagged=True);self.assertNotEqual(run.returncode,0);self.assertTrue(calls);self.assertFalse(any(c[0]=='build' for c in calls));self.assertIsNone(output)
if __name__=='__main__':unittest.main()
