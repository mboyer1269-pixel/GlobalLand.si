"""Rebuild maintenance without changing agents, accounts or custom schedules."""
import fcntl
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
import install_maintenance as maintenance


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=pathlib.Path(self.tmp.name)
        self.root=self.base/'opt/globalland'
        self.paths=maintenance.Paths(self.root,self.base/'etc/cron.d/globalland',
                                     self.base/'etc/logrotate.d/globalland',self.base/'var/log/globalland')
        for path in (self.root/'control',self.root/'state',self.paths.cron.parent,self.paths.rotation.parent):
            path.mkdir(parents=True,mode=0o700)
        self.git(['init','--bare',str(self.root/'source.git')])
        tree=self.git(['--git-dir='+str(self.root/'source.git'),'mktree'],input='').strip()
        self.revision=self.git(['--git-dir='+str(self.root/'source.git'),'-c','user.name=Test',
                                '-c','user.email=test@example.invalid','commit-tree',tree,'-m','fixture']).strip()
        self.git(['--git-dir='+str(self.root/'source.git'),'update-ref','refs/heads/main',self.revision])
        self.git(['--git-dir='+str(self.root/'source.git'),'symbolic-ref','HEAD','refs/heads/main'])
        (self.root/'control/REVISION').write_text(self.revision+'\n')
        (self.root/'control/supervisor.py').write_text('# fixture target; never executed\n')
        self.config={'executor_enabled':True,'executor_image':'node:22-bookworm@sha256:'+'1'*64,
                     'controller':{'mode':'external_grok'}}
        self.save_config()
        self.unrelated=self.paths.cron.parent/'oria'
        self.unrelated.write_text('custom unrelated schedule\n')
        self.think=self.paths.cron.parent/'globalland-think'
        self.think.write_text('independently managed model schedule\n')
        self.calls=[]

    def git(self,args,**kw):
        return subprocess.run(['git',*args],capture_output=True,text=True,check=True,**kw).stdout

    def save_config(self):
        path=self.root/'control/config.json'
        path.write_text(json.dumps(self.config));path.chmod(0o600)

    def run(self,args=None,**kwargs):
        if not isinstance(args,list):
            return super().run(args,**kwargs)
        self.calls.append(args)
        if args[0]=='git':return subprocess.run(args,**kwargs)
        self.assertIn(args[0],('systemctl','logrotate','docker'))
        return subprocess.CompletedProcess(args,0,stdout='',stderr='')

    def tree(self):
        return {str(p.relative_to(self.base)):(p.stat().st_mode & 0o777,hashlib.sha256(p.read_bytes()).hexdigest())
                for p in self.base.rglob('*') if p.is_file()}

    def install(self,**kw):
        return maintenance.install(self.paths,run=self.run,**kw)

    def test_preview_is_read_only_and_fresh_install_creates_only_maintenance(self):
        before=self.tree()
        preview=maintenance.preview(self.paths)
        self.assertEqual(self.tree(),before)
        self.assertFalse(preview['mail_enabled'])
        self.assertEqual(set(preview['changes']),{'cron','rotation'})
        report=self.install()
        self.assertEqual(report['revision'],self.revision)
        self.assertEqual(set(report['changes']),{'cron','rotation'})
        self.assertTrue(pathlib.Path(report['backup']).is_dir())
        cron=self.paths.cron.read_text()
        self.assertIn('*/5 * * * * root ',cron)
        self.assertIn('0 8 * * * root ',cron)
        self.assertIn('supervisor.py queue',cron);self.assertIn('supervisor.py daily',cron)
        self.assertNotIn('supervisor.py mail',cron);self.assertNotIn('supervisor.py think',cron)
        self.assertIn('flock -n ',cron)
        for path in (self.paths.cron,self.paths.rotation):self.assertEqual(path.stat().st_mode & 0o777,0o644)
        for path in (self.paths.logs/'queue.log',self.paths.logs/'daily.log',self.paths.logs/'think.log',
                     self.root/'state/private/mail-cron.log'):
            self.assertEqual(path.stat().st_mode & 0o777,0o600)
        self.assertEqual(json.loads((self.root/'control/config.json').read_text()),self.config)
        self.assertEqual(self.unrelated.read_text(),'custom unrelated schedule\n')
        self.assertEqual(self.think.read_text(),'independently managed model schedule\n')
        self.assertTrue(any(c[:4]==['systemctl','is-active','--quiet','cron'] for c in self.calls))
        self.assertTrue(any(c[:4]==['systemctl','is-active','--quiet','logrotate.timer'] for c in self.calls))
        self.assertTrue(any(c[0]=='logrotate' and '--debug' in c for c in self.calls))

    def test_idempotence_does_not_rewrite_or_create_backups(self):
        self.install();before=self.tree();mtime=self.paths.cron.stat().st_mtime_ns
        report=self.install()
        self.assertEqual(report['changes'],[]);self.assertIsNone(report['backup'])
        self.assertEqual(self.tree(),before);self.assertEqual(self.paths.cron.stat().st_mtime_ns,mtime)

    def test_mail_needs_configuration_and_is_preserved_on_later_default_call(self):
        self.install();before=self.tree()
        with self.assertRaises(ValueError):self.install(with_mail=True)
        self.assertEqual(self.tree(),before)
        self.config['agentmail']={'enabled':True,'inbox_id':'fixture','inbox_address':'fixture@example.invalid'}
        self.save_config()
        credential=self.root/'credentials/agentmail/token'
        credential.parent.mkdir(parents=True,mode=0o700);credential.write_text('synthetic-fixture');credential.chmod(0o600)
        self.install(with_mail=True)
        self.assertIn('supervisor.py mail',self.paths.cron.read_text())
        before=self.tree();self.install()
        self.assertEqual(self.tree(),before)
        self.assertTrue(maintenance.preview(self.paths)['mail_enabled'])

    def test_custom_configs_are_preserved_before_any_installation_write(self):
        for path in (self.paths.cron,self.paths.rotation):
            with self.subTest(path=path.name):
                path.write_text('operator custom content\n');path.chmod(0o644)
                before=self.tree()
                with self.assertRaises(ValueError):self.install()
                self.assertEqual(self.tree(),before)
                path.unlink()

    def test_symlink_destinations_and_writable_parent_are_refused(self):
        sentinel=self.base/'sentinel';sentinel.write_text('unchanged')
        self.paths.cron.symlink_to(sentinel)
        with self.assertRaises(ValueError):self.install()
        self.assertEqual(sentinel.read_text(),'unchanged');self.paths.cron.unlink()
        self.paths.rotation.parent.chmod(0o777)
        with self.assertRaises(ValueError):self.install()
        self.assertFalse(self.paths.cron.exists())

    def test_missing_services_and_source_fail_before_publication(self):
        for failed in ('cron','logrotate.timer'):
            with self.subTest(service=failed):
                before=self.tree()
                def reject(command,**kw):
                    if command[:3]==['systemctl','is-active','--quiet'] and command[-1]==failed:
                        return subprocess.CompletedProcess(command,3,stdout='',stderr='inactive')
                    return self.run(command,**kw)
                with self.assertRaises(ValueError):maintenance.install(self.paths,run=reject)
                self.assertEqual(self.tree(),before)
        (self.root/'source.git/HEAD').unlink()
        with self.assertRaises(ValueError):self.install()
        self.assertFalse(self.paths.cron.exists())

    def test_failure_after_schedule_replacement_restores_both_files(self):
        real_write=maintenance._replace
        failed=False
        def interrupted(path,data,mode=0o644):
            nonlocal failed
            real_write(path,data,mode)
            if path==self.paths.cron and not failed:
                failed=True
                raise OSError('injected directory fsync failure')
        with patch.object(maintenance,'_replace',side_effect=interrupted):
            with self.assertRaises(OSError):self.install()
        self.assertFalse(self.paths.cron.exists());self.assertFalse(self.paths.rotation.exists())
        self.assertTrue(any((self.root/'backups').iterdir()))
        self.install()
        self.assertTrue(self.paths.cron.is_file())

    def test_supervisor_lock_prevents_simultaneous_activation(self):
        with (self.root/'state/supervisor.lock').open('w') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(ValueError):self.install()
        self.assertFalse(self.paths.cron.exists())

    def test_non_bare_source_is_not_accepted_as_finalized_installation(self):
        self.git(['--git-dir='+str(self.root/'source.git'),'config','core.bare','false'])
        before=self.tree()
        with self.assertRaises(ValueError):self.install()
        self.assertEqual(self.tree(),before)

    def test_rollback_when_enabling_mail_keeps_previous_schedule_and_content(self):
        self.install()
        previous=self.paths.cron.read_bytes();rotation=self.paths.rotation.read_bytes()
        self.config['agentmail']={'enabled':True,'inbox_id':'fixture','inbox_address':'fixture@example.invalid'}
        self.save_config()
        credential=self.root/'credentials/agentmail/token'
        credential.parent.mkdir(parents=True,mode=0o700);credential.write_text('synthetic-fixture');credential.chmod(0o600)
        real_write=maintenance._replace
        failed=False
        def interrupted(path,data,mode=0o644):
            nonlocal failed
            real_write(path,data,mode)
            if path==self.paths.cron and not failed:
                failed=True;raise OSError('injected failure after rename')
        with patch.object(maintenance,'_replace',side_effect=interrupted):
            with self.assertRaises(OSError):self.install(with_mail=True)
        self.assertEqual(self.paths.cron.read_bytes(),previous)
        self.assertEqual(self.paths.rotation.read_bytes(),rotation)
        self.assertEqual(json.loads((self.root/'control/config.json').read_text()),self.config)

    def test_rotation_targets_only_diagnostic_logs_and_preserves_open_writers(self):
        view=maintenance.preview(self.paths)
        config=view['templates']['rotation']
        for required in ('daily','rotate 7','maxsize 10M','delaycompress','create 0600 root root','su root root'):
            self.assertIn(required,config)
        for forbidden in ('copytruncate','*.json','*.sqlite','*','postrotate','prerotate'):
            self.assertNotIn(forbidden,config)

    def test_log_validation_uses_metadata_without_reading_growing_log_content(self):
        self.install()
        log=self.paths.logs/'queue.log'
        original=pathlib.Path.read_bytes
        def read(path):
            if path==log:raise AssertionError('maintenance must not load diagnostic log contents')
            return original(path)
        with patch.object(pathlib.Path,'read_bytes',read):
            maintenance.preview(self.paths)
            self.install()

    def test_cron_recreates_a_missing_log_privately_even_with_default_host_umask(self):
        self.paths.logs.mkdir(parents=True,mode=0o700)
        cron=maintenance.preview(self.paths)['templates']['cron']
        line=next(line for line in cron.splitlines() if 'supervisor.py queue' in line)
        command=line.split(maxsplit=6)[6]
        self.assertIn(str(self.root/'control/supervisor.py'),command)
        subprocess.run(['/bin/sh','-c','umask 022; '+command],check=True,capture_output=True)
        self.assertEqual((self.paths.logs/'queue.log').stat().st_mode & 0o777,0o600)

    def test_versioned_installed_control_is_supported_but_outside_link_is_refused(self):
        release=self.root/'releases'/self.revision
        release.parent.mkdir();(self.root/'control').rename(release)
        (self.root/'control').symlink_to(release,target_is_directory=True)
        self.install()
        (self.root/'control').unlink()
        (self.root/'control').symlink_to(self.base,target_is_directory=True)
        with self.assertRaises(ValueError):maintenance.preview(self.paths)

    def test_image_changed_before_lock_is_rechecked_before_scheduling(self):
        changed=False
        def concurrent_admin(command,**kwargs):
            nonlocal changed
            if command[:3]==['docker','image','inspect']:
                if changed:return subprocess.CompletedProcess(command,1,stdout='',stderr='image absent')
                changed=True
                self.config['executor_image']='node:22-bookworm@sha256:'+'2'*64
                self.save_config()
            return self.run(command,**kwargs)
        with self.assertRaises(ValueError):maintenance.install(self.paths,run=concurrent_admin)
        self.assertFalse(self.paths.cron.exists());self.assertFalse(self.paths.rotation.exists())

    def test_rerun_repairs_missing_log_directory_without_rewriting_configs(self):
        self.install()
        previous={name:(path.read_bytes(),path.stat().st_mtime_ns)
                  for name,path in (('cron',self.paths.cron),('rotation',self.paths.rotation))}
        backups=list((self.root/'backups').iterdir())
        self.assertTrue(self.paths.logs.resolve().is_relative_to(self.base.resolve()))
        for name in ('queue','daily','think'):(self.paths.logs/(name+'.log')).unlink()
        self.paths.logs.rmdir()
        (self.root/'state/private/mail-cron.log').unlink()
        self.calls=[]
        report=self.install()
        line=next(line for line in self.paths.cron.read_text().splitlines() if 'supervisor.py queue' in line)
        run=subprocess.run(['/bin/sh','-c',line.split(maxsplit=6)[6]],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertEqual(report['changes'],[]);self.assertIsNone(report['backup'])
        self.assertEqual(set(report['created_logs']),{str(self.paths.logs/(name+'.log')) for name in ('queue','daily','think')}
                         |{str(self.root/'state/private/mail-cron.log')})
        self.assertTrue(any(c[0]=='logrotate' for c in self.calls))
        for name,path in (('cron',self.paths.cron),('rotation',self.paths.rotation)):
            self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),previous[name])
        self.assertEqual(list((self.root/'backups').iterdir()),backups)
        for name in report['created_logs']:self.assertEqual(pathlib.Path(name).stat().st_mode & 0o777,0o600)

    def test_rerun_repairs_individually_missing_logs_before_any_cycle(self):
        self.install()
        for path in (self.paths.logs/'think.log',self.root/'state/private/mail-cron.log'):path.unlink()
        report=self.install()
        self.assertEqual(set(report['created_logs']),{str(self.paths.logs/'think.log'),str(self.root/'state/private/mail-cron.log')})
        for name in report['created_logs']:
            self.assertTrue(pathlib.Path(name).is_file())
            self.assertEqual(pathlib.Path(name).stat().st_mode & 0o777,0o600)

    @unittest.skipUnless(os.environ.get('GLOBALLAND_LOGROTATE_SMOKE')=='1',
                         'real logrotate requires explicit isolated root verification')
    def test_real_logrotate_preserves_writer_and_private_permissions(self):
        self.assertEqual(os.geteuid(),0,'run this isolated test as root')
        self.assertIsNotNone(shutil.which('logrotate'))
        def real_logrotate(command,**kwargs):
            if command[0]=='logrotate':return subprocess.run(command,**kwargs)
            return self.run(command,**kwargs)
        maintenance.install(self.paths,run=real_logrotate)
        self.assertTrue(self.paths.rotation.resolve().is_relative_to(self.base.resolve()))
        config=self.paths.rotation.read_text()
        for name in (self.paths.logs/'queue.log',self.paths.logs/'daily.log',self.paths.logs/'think.log',
                     self.root/'state/private/mail-cron.log'):
            self.assertTrue(name.resolve().is_relative_to(self.base.resolve()))
            self.assertIn('"'+str(name)+'"',config)
        command=['logrotate','--state',str(self.base/'rotation-state'),str(self.paths.rotation)]
        subprocess.run([*command,'--debug'],capture_output=True,text=True,check=True)
        log=self.paths.logs/'queue.log'
        with log.open('a') as writer:
            writer.write('before rotation\n');writer.flush()
            subprocess.run([*command,'--force'],capture_output=True,text=True,check=True)
            writer.write('writer finishes safely\n');writer.flush()
        self.assertEqual(log.read_text(),'')
        self.assertEqual((self.paths.logs/'queue.log.1').read_text(),'before rotation\nwriter finishes safely\n')
        self.assertEqual(log.stat().st_mode & 0o777,0o600)
        self.assertFalse((self.paths.logs/'queue.log.1.gz').exists())


if __name__=='__main__':unittest.main()
