"""Local regression coverage for the host feedback envelope and legacy boundary."""
import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
import result_envelope as feedback


class ResultEnvelopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=pathlib.Path(self.tmp.name);(self.root/'state').mkdir()
        self.ident='TASK-180000000000'
        self.path=self.root/'state'/(self.ident+'.json')
        self.record=dict(id=self.ident,hash='a'*64,origin='queued',state='PUBLISHED',
            metadata=dict(type='TOOL',action='EXEC'),
            result=dict(status='DONE',output='123 tests passed'),
            files={'products/a.txt':'a'*600000,'products/b.txt':'b'*600000})

    @unittest.skipUnless(hasattr(os,'mkfifo'),'POSIX named pipe')
    def test_nonregular_private_source_is_refused_before_open(self):
        os.mkfifo(self.path)
        with self.assertRaises(ValueError):feedback._safe(self.path)

    def test_envelope_is_small_and_legacy_revision_stays_exact_after_output_truncation(self):
        from initiative import source_revision
        self.record['result']['output']='é'*2001
        self.path.write_text(json.dumps(self.record))
        expected=source_revision('QUEUED_RESULT',self.record)
        feedback.write_result_envelope(self.root,self.record)
        compact=self.root/'state/results'/(self.ident+'.json')
        self.assertLess(compact.stat().st_size,64*1024)
        # The blob journal is not opened once its compact feedback is durable.
        original=pathlib.Path.open
        def guarded(path,*args,**kwargs):
            self.assertNotEqual(path,self.path)
            return original(path,*args,**kwargs)
        with patch.object(pathlib.Path,'open',guarded):
            source=feedback.read_result(self.root,self.path)
        self.assertEqual(source_revision('QUEUED_RESULT',source),expected)
        self.assertTrue(source['output_truncated'])
        self.assertEqual(len(source['result']['output']),2000)
        self.assertNotIn('files',source)
        # Public data can never assert the privileged compact-source revision.
        public=dict(source)
        public['source_version']='f'*64
        self.assertNotEqual(source_revision('QUEUED_RESULT',public)[1],'f'*64)

    def test_complete_result_is_screened_even_when_sensitive_marker_follows_output_prefix(self):
        from controller import Controller
        for marker in (' receipt PRIVATE_VALUE',' credential PRIVATE_VALUE'):
            self.record['result']['output']='a'*3000+marker
            self.path.write_text(json.dumps(self.record))
            feedback.write_result_envelope(self.root,self.record)
            results,_,_=Controller(self.root,None,None,{}).recent_results()
            self.assertEqual(results[0]['output'],'[output redacted]')
            self.assertTrue(results[0]['output_redacted'])

    def test_financial_and_conflicting_classifications_remain_redacted(self):
        from controller import Controller
        for metadata,request in ((dict(type='TOOL',action='SPEND'),None),
                                 (dict(type='TOOL',action='EXEC'),dict(type='TOOL',action='SPEND')),
                                 (None,dict(type='TOOL',action='EXEC'))):
            self.record.update(metadata=metadata,request=request)
            feedback.write_result_envelope(self.root,self.record)
            results,_,_=Controller(self.root,None,None,{}).recent_results()
            self.assertEqual(results[0]['output'],'[output redacted]')

    def test_symlink_and_corrupt_envelopes_cannot_fall_back_to_public_replacement(self):
        from controller import Controller
        feedback.write_result_envelope(self.root,self.record)
        compact=self.root/'state/results'/(self.ident+'.json')
        public=self.root/'work/queue/done'/(self.ident+'.result.json')
        public.parent.mkdir(parents=True)
        public.write_text(json.dumps(dict(self.record['result'],request=dict(type='TOOL',action='EXEC'))))
        compact.write_text('{broken')
        self.assertEqual(Controller(self.root,None,None,{}).recent_results()[0],[])
        compact.unlink();compact.symlink_to(public)
        with self.assertRaises(ValueError):feedback.read_result(self.root,compact)

    def test_oversize_legacy_source_is_refused_before_reading(self):
        with self.path.open('wb') as stream:stream.truncate(feedback.MAX_LEGACY+1)
        with patch.object(pathlib.Path,'open',side_effect=AssertionError('oversize file opened')):
            with self.assertRaises(ValueError):feedback.read_result(self.root,self.path)

    def test_hashless_legacy_observation_remains_visible_without_event_coverage(self):
        from controller import Controller
        from initiative import Store
        del self.record['hash'];del self.record['id']
        self.path.write_text(json.dumps(self.record))
        results,coverage,excluded=Controller(self.root,None,None,{}).recent_results()
        self.assertEqual(len(results),1)
        self.assertEqual(results[0]['output'],'123 tests passed')
        self.assertEqual(coverage,[])
        self.assertEqual(excluded[0]['reason'],'INVALID_SOURCE')
        feedback.write_result_envelope(self.root,self.record)
        self.assertFalse((self.root/'state/results'/(self.ident+'.json')).exists())
        store=Store(self.root,dict(initiative=dict(enabled=True,debounce_seconds=0)))
        store.recorded_result(self.ident,now=1000)
        self.assertEqual(store.events(kind='QUEUED_RESULT'),[])

    def test_legacy_projection_is_cached_once_and_journal_changes_invalidate_it(self):
        self.path.write_text(json.dumps(self.record))
        with patch.object(feedback,'_legacy_projection',wraps=feedback._legacy_projection) as project:
            for _ in range(3):
                self.assertEqual(feedback.read_result(self.root,self.path)['result']['output'],'123 tests passed')
            self.assertEqual(project.call_count,1)
            self.record['result']['output']='124 tests passed'
            self.path.write_text(json.dumps(self.record))
            self.assertEqual(feedback.read_result(self.root,self.path)['result']['output'],'124 tests passed')
            self.assertEqual(project.call_count,2)

    def test_unwritable_cache_keeps_the_valid_legacy_observation(self):
        self.path.write_text(json.dumps(self.record))
        with patch.object(feedback,'write_result_envelope',side_effect=PermissionError('cache unavailable')):
            self.assertEqual(feedback.read_result(self.root,self.path)['result']['output'],'123 tests passed')

    def test_journal_mutation_during_projection_cannot_be_cached_or_returned(self):
        self.path.write_text(json.dumps(self.record))
        original=feedback._legacy_projection
        def changing(path):
            value=original(path)
            self.record['result']['output']='a different completed computation'
            path.write_text(json.dumps(self.record))
            return value
        with patch.object(feedback,'_legacy_projection',changing):
            with self.assertRaises(ValueError):feedback.read_result(self.root,self.path)
        self.assertFalse((self.root/'state/results'/(self.ident+'.json')).exists())

    def test_compact_read_enforces_size_when_file_grows_after_stat(self):
        feedback.write_result_envelope(self.root,self.record)
        compact=self.root/'state/results'/(self.ident+'.json')
        original=pathlib.Path.open
        def changing(path,*args,**kwargs):
            if path==compact:
                with original(path,'ab') as stream:stream.write(b' '*feedback.MAX_ENVELOPE)
            return original(path,*args,**kwargs)
        with patch.object(pathlib.Path,'open',changing):
            with self.assertRaises(ValueError):feedback.read_result(self.root,compact)

    def test_private_symlink_identity_suppresses_same_id_public_replacement(self):
        from controller import Controller
        self.record['metadata']['action']='SPEND'
        feedback.write_result_envelope(self.root,self.record)
        compact=self.root/'state/results'/(self.ident+'.json')
        saved=self.root/'saved-private.json';compact.replace(saved);compact.symlink_to(saved)
        public=self.root/'work/queue/done'/(self.ident+'.result.json')
        public.parent.mkdir(parents=True)
        public.write_text(json.dumps(dict(status='DONE',output='public financial replacement',
                                         request=dict(type='TOOL',action='EXEC'))))
        results,_,excluded=Controller(self.root,None,None,{}).recent_results()
        self.assertEqual(results,[])
        self.assertEqual(excluded[0]['key'],self.ident)

    def test_corrupt_cache_recovers_only_from_safe_host_journal_with_exact_revision(self):
        from controller import Controller
        from initiative import Store,source_revision
        self.path.write_text(json.dumps(self.record))
        expected=source_revision('QUEUED_RESULT',self.record)
        store=Store(self.root,dict(initiative=dict(enabled=True,debounce_seconds=0)))
        feedback.write_result_envelope(self.root,self.record)
        compact=self.root/'state/results'/(self.ident+'.json')
        compact.write_text('{broken')
        results,coverage,_=Controller(self.root,None,None,{}).recent_results()
        self.assertEqual(len(results),1)
        self.assertEqual(results[0]['output'],'123 tests passed')
        self.assertEqual((coverage[0]['key'],coverage[0]['version']),expected)
        store.recorded_result(self.ident,now=1000)
        self.assertEqual(len(store.events(kind='QUEUED_RESULT')),1)
        self.assertEqual(store.events(kind='QUEUED_RESULT')[0]['version'],expected[1])
        # A corrupt journal and corrupt derived cache cannot use public text.
        self.path.write_text('{broken');compact.write_text('{broken')
        public=self.root/'work/queue/done'/(self.ident+'.result.json')
        public.parent.mkdir(parents=True)
        public.write_text(json.dumps(dict(status='DONE',output='public replacement',request=dict(action='EXEC'))))
        self.assertEqual(Controller(self.root,None,None,{}).recent_results()[0],[])

    def test_unsafe_cache_is_never_followed_or_overwritten_during_journal_recovery(self):
        self.path.write_text(json.dumps(self.record))
        compact=self.root/'state/results'/(self.ident+'.json');compact.parent.mkdir()
        outside=self.root/'outside.json';outside.write_text('PRIVATE-OUTSIDE')
        compact.symlink_to(outside)
        try:source=feedback.read_result(self.root,self.path)
        except ValueError:self.fail('valid host journal must survive an unsafe derived cache')
        self.assertEqual(source['result']['output'],'123 tests passed')
        self.assertTrue(compact.is_symlink())
        self.assertEqual(outside.read_text(),'PRIVATE-OUTSIDE')


if __name__=='__main__':unittest.main()
