import pathlib, tempfile, unittest, sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
class ToolsTests(unittest.TestCase):
 def test_broad_exec_schema_keeps_arguments_and_rejects_host_paths(self):
  from tools import validate_envelope
  t={'id':'TASK-0100','type':'TOOL','submitted_by':'BUILDER','created_at':'2026-10-31T00:00:00Z','action':'EXEC','args':{'argv':['bash','-lc','printf hello > products/hello.txt'],'outputs':['products/hello.txt']},'estimated_cost_cad':0,'approved_by':None}
  self.assertEqual(validate_envelope(t)['args']['argv'][1],'-lc')
  for patch in [{'cwd':'../oria'},{'outputs':['../oria/key']},{'argv':[]},{'outputs':['scripts/supervisor.py']}]:
   with self.assertRaises(ValueError):validate_envelope({**t,'args':{**t['args'],**patch}})
 def test_public_network_denies_local_and_rebinding_resolution(self):
  from tools import public_target
  resolver=lambda *a,**k:[(2,1,6,'',('127.0.0.1',443))]
  for url in ['file:///etc/passwd','https://localhost/','http://169.254.169.254/','https://example.com/']:
   with self.assertRaises(ValueError):public_target(url,resolver)
  self.assertEqual(public_target('https://example.com/',lambda *a,**k:[(2,1,6,'',('93.184.216.34',443))])[2],'93.184.216.34')
 def test_artifacts_reject_symlinks_secrets_and_protected_paths(self):
  from tools import collect_outputs
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);(root/'products').mkdir();(root/'products/a.txt').write_text('hello')
   self.assertEqual(collect_outputs(root,['products/a.txt']),{'products/a.txt':'hello'})
   (root/'products/link').symlink_to('/etc/passwd')
   with self.assertRaises(ValueError):collect_outputs(root,['products/link'])
   (root/'products/a.txt').write_text('sk-'+'x'*30)
   with self.assertRaises(ValueError):collect_outputs(root,['products/a.txt'])
 def test_sandbox_command_has_no_control_or_credentials_mount(self):
  from tools import sandbox_command
  args=sandbox_command('TASK-0100',pathlib.Path('/opt/globalland/jobs/TASK-0100/workspace'),'node:22-bookworm@sha256:'+'1'*64,{'argv':['node','product.js']})
  self.assertIn('none',args);self.assertIn('65534:65534',args);self.assertIn('1g',args)
  mounts=[args[i+1] for i,a in enumerate(args[:-1]) if a=='--mount'];self.assertEqual(len(mounts),3);self.assertTrue(all('readonly' in m for m in mounts));self.assertTrue(any('/workspace:rw' in a and 'size=256m' in a for a in args))
  self.assertNotIn('dst=/control',' '.join(args));self.assertNotIn('docker.sock',' '.join(args))
 def test_completed_exec_does_not_retain_source_copy(self):
  from tools import Toolbox
  from unittest.mock import patch
  class Bank:
   def snapshot(self):return {'state':'UNFUNDED'}
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);(root/'work/products').mkdir(parents=True);(root/'control').mkdir()
   t={'id':'TASK-0100','type':'TOOL','submitted_by':'BUILDER','created_at':'2026-10-31T00:00:00Z','action':'EXEC','args':{'argv':['node','-p','1'],'outputs':[]},'estimated_cost_cad':0,'approved_by':None}
   with patch('tools.bounded_run',return_value=(0,b'{"status":"DONE","output":"ok","files":{}}')),patch('tools.subprocess.run',return_value=type('Result',(),{'returncode':0})()):
    from world import World
    world=World(root/'world.db');world.bootstrap()
    result,files=Toolbox(root,world,Bank(),{'executor_enabled':True,'executor_image':'node@sha256:'+'1'*64}).run(t)
   self.assertEqual(result['status'],'DONE');self.assertFalse((root/'jobs/TASK-0100').exists())
 def test_failed_exec_diagnostic_is_checked_for_secrets_before_reporting(self):
  import json
  from tools import Toolbox
  from unittest.mock import patch
  class Bank:
   def snapshot(self):return {'state':'UNFUNDED'}
  for output in ['AssertionError: expected 4 issues, got 5','API_KEY='+'x'*30]:
   with self.subTest(secret=output.startswith('API_KEY=')),tempfile.TemporaryDirectory() as d:
    root=pathlib.Path(d);(root/'work/products').mkdir(parents=True);(root/'control').mkdir()
    task={'id':'TASK-0100','type':'TOOL','submitted_by':'BUILDER','created_at':'2026-10-31T00:00:00Z','action':'EXEC','args':{'argv':['node','-e','process.exit(1)'],'outputs':[]},'estimated_cost_cad':0,'approved_by':None}
    response=json.dumps({'status':'FAILED','output':output,'files':{}}).encode()
    with patch('tools.bounded_run',return_value=(0,response)),patch('tools.subprocess.run',return_value=type('Result',(),{'returncode':0})()):
     from world import World
     world=World(root/'world.db');world.bootstrap()
     box=Toolbox(root,world,Bank(),{'executor_enabled':True,'executor_image':'node@sha256:'+'1'*64})
     if output.startswith('API_KEY='):
      with self.assertRaisesRegex(ValueError,'secret pattern detected'):box.run(task)
     else:
      result,files=box.run(task);self.assertEqual(result,{'status':'FAILED','output':output});self.assertEqual(files,{})
    self.assertFalse((root/'jobs/TASK-0100').exists())
class InputStagingTests(unittest.TestCase):
 def test_empty_selection_never_enumerates_unrelated_corpus_and_is_public(self):
  import os
  from unittest.mock import patch
  from tools import stage_inputs
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);(root/'work').mkdir()
   previous=os.umask(0o077)
   try:
    with patch('pathlib.Path.rglob',side_effect=AssertionError('empty selection scanned corpus')):
     manifest=stage_inputs(root,root/'input',[])
   finally:os.umask(previous)
   self.assertEqual(manifest['total_bytes'],0)
   self.assertEqual((root/'input').stat().st_mode & 0o777,0o755)

 def test_fallback_selected_files_do_not_scan_unrelated_paths(self):
  from unittest.mock import patch
  from tools import stage_inputs
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);(root/'work/products').mkdir(parents=True)
   (root/'work/products/safe').write_text('safe')
   with patch('pathlib.Path.rglob',side_effect=AssertionError('selected file scanned corpus')):
    manifest=stage_inputs(root,root/'input',['products/safe'])
   self.assertEqual(manifest['total_bytes'],4)
   self.assertEqual((root/'input/products/safe').read_text(),'safe')

 def test_fallback_rejects_invalid_legacy_paths_and_destination_links_before_copy(self):
  from tools import stage_inputs
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);(root/'work/.git').mkdir(parents=True)
   (root/'work/.git/config').write_text('private git config')
   with self.assertRaises(ValueError):stage_inputs(root,root/'input',None)
   self.assertFalse((root/'input').exists())
   (root/'work/safe').write_text('safe')
   (root/'outside').mkdir();(root/'linked').symlink_to(root/'outside',target_is_directory=True)
   with self.assertRaises(ValueError):stage_inputs(root,root/'linked/input',['safe'])
   self.assertEqual(list((root/'outside').iterdir()),[])

 def test_fallback_growth_during_copy_is_refused_and_staging_removed(self):
  import os
  from unittest.mock import patch
  from tools import stage_inputs
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);(root/'work').mkdir()
   source=root/'work/safe';source.write_bytes(b'safe')
   original_read=os.read;changed=False
   def growing_read(fd,limit):
    nonlocal changed
    if not changed:
     changed=True
     with source.open('ab') as stream:stream.write(b'grew beyond preflight')
    return original_read(fd,limit)
   with patch('tools.os.read',side_effect=growing_read):
    with self.assertRaises(ValueError):stage_inputs(root,root/'input',['safe'])
   self.assertFalse((root/'input').exists())
   self.assertEqual(list(root.glob('.public-source-*')),[])

 def test_fallback_budget_is_checked_before_any_copy_and_overlaps_are_deduplicated(self):
  import os
  from unittest.mock import patch
  from tools import stage_inputs
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);(root/'work/products/nested').mkdir(parents=True)
   (root/'work/products/nested/a').write_bytes(b'1234')
   (root/'work/products/b').write_bytes(b'5678')
   with patch('tools.INPUT_BUDGET',7),patch('tools.os.read',side_effect=AssertionError('overflow read body')):
    with self.assertRaisesRegex(ValueError,'selected inputs exceed job capacity') as caught:
     stage_inputs(root,root/'input',['products/'])
   self.assertEqual(caught.exception.code,'EXEC_INPUT_CAPACITY')
   self.assertEqual(caught.exception.selected_bytes,8)
   from tools import rejection_reason
   message=rejection_reason(caught.exception)
   self.assertIn('selected_bytes=8',message)
   self.assertIn('budget_bytes=7',message)
   self.assertFalse((root/'input').exists())
   previous=os.umask(0o077)
   try:manifest=stage_inputs(root,root/'input',['products/','products/nested/','products/nested/a'])
   finally:os.umask(previous)
   self.assertEqual(manifest['total_bytes'],8)
   self.assertEqual(len(manifest['entries']),2)
   for part in ['input','input/products','input/products/nested']:
    self.assertEqual((root/part).stat().st_mode & 0o777,0o755)

 def test_fallback_rejects_source_symlink_swap_after_preflight_without_partial_input(self):
  import os
  from unittest.mock import patch
  from tools import stage_inputs
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);(root/'work/products').mkdir(parents=True)
   source=root/'work/products/safe';source.write_text('safe')
   (root/'private').write_text('host secret')
   original_open=os.open;opens=0
   def racing_open(path,*args,**kwargs):
    nonlocal opens
    if str(path)=='safe':
     opens+=1
     if opens==2:
      source.unlink();source.symlink_to(root/'private')
    return original_open(path,*args,**kwargs)
   with patch('tools.os.open',side_effect=racing_open):
    with self.assertRaises(ValueError):stage_inputs(root,root/'input',['products/safe'])
   self.assertFalse((root/'input').exists())


if __name__=='__main__':unittest.main()
