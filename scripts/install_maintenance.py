#!/usr/bin/env python3
"""Explicit administrative bootstrap for queue/daily/mail and diagnostic logs.

Preview is read-only. --apply installs schedules, never invokes a world cycle.
Only exact templates owned by this tool may be replaced on a later invocation.
"""
import argparse
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
import pathlib
import re
import stat
import subprocess
import tempfile


@dataclass(frozen=True)
class Paths:
    root: pathlib.Path = pathlib.Path('/opt/globalland')
    cron: pathlib.Path = pathlib.Path('/etc/cron.d/globalland')
    rotation: pathlib.Path = pathlib.Path('/etc/logrotate.d/globalland')
    logs: pathlib.Path = pathlib.Path('/var/log/globalland')


def _directory(path):
    """Trusted parents only; root-owned sticky /tmp is usable in isolated tests."""
    for current in (path,*path.parents):
        if not current.exists() and not current.is_symlink():continue
        info=current.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid not in (0,os.geteuid())
                or (info.st_mode & 0o022 and not (info.st_uid==0 and info.st_mode & stat.S_ISVTX))):
            raise ValueError('unsafe maintenance directory')


def _file_info(path,limit=65536):
    _directory(path.parent)
    if not path.exists() and not path.is_symlink():return None
    info=path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid not in (0,os.geteuid())
            or info.st_mode & 0o022 or info.st_nlink!=1 or info.st_size>limit):
        raise ValueError('unsafe maintenance file')
    return info


def _read(path,limit=65536):
    return path.read_bytes() if _file_info(path,limit) is not None else None


def _templates(paths,mail):
    root,logs=str(paths.root),str(paths.logs)
    cron=('# GlobalLand maintenance v1; installed control only. Server-local cron time.\n'
          'SHELL=/bin/sh\nPATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\n')
    for mode,schedule,log in (('queue','*/5 * * * *',logs+'/queue.log'),
                              ('daily','0 8 * * *',logs+'/daily.log'),
                              *([('mail','*/5 * * * *',root+'/state/private/mail-cron.log')] if mail else [])):
        cron+=f'{schedule} root umask 077; /usr/bin/flock -n {root}/state/{mode}-schedule.lock /usr/bin/python3 {root}/control/supervisor.py {mode} >> {log} 2>&1\n'
    logfiles=[logs+'/'+name+'.log' for name in ('queue','daily','think')]+[root+'/state/private/mail-cron.log']
    rotation=('# GlobalLand diagnostic logs v1; no runtime databases or receipts.\n'
              +' '.join('"'+name+'"' for name in logfiles)+' {\n'
              '    daily\n    rotate 7\n    maxsize 10M\n    missingok\n    notifempty\n'
              '    compress\n    delaycompress\n    create 0600 root root\n    su root root\n}\n')
    return dict(cron=cron,rotation=rotation)


def _inspect(paths,with_mail):
    if with_mail not in (None,True):raise ValueError('mail may only be explicitly enabled')
    for path in (paths.root,paths.cron,paths.rotation,paths.logs):
        if not path.is_absolute() or '..' in path.parts or not re.fullmatch(r'/[A-Za-z0-9_./-]+',str(path)):
            raise ValueError('absolute simple maintenance paths required')
    for directory in (paths.root,paths.root/'state',paths.root/'backups',paths.root/'state/private',
                      paths.logs,paths.cron.parent,paths.rotation.parent,paths.root/'source.git'):
        _directory(directory)
    # A versioned control symlink is legitimate, but it must stay in this install.
    control=(paths.root/'control').resolve(strict=True)
    if not control.is_relative_to(paths.root):raise ValueError('control must belong to this installation')
    revision=(_read(control/'REVISION',128) or b'').decode().strip()
    if not re.fullmatch(r'[0-9a-f]{40}',revision):raise ValueError('installed revision required')
    config=json.loads(_read(control/'config.json',1024*1024) or b'{}')
    image=config.get('executor_image','')
    if config.get('executor_enabled') is not True or not isinstance(image,str) or not re.fullmatch(r'(?:[A-Za-z0-9./:_-]+@)?sha256:[0-9a-f]{64}',image):
        raise ValueError('enabled executor with pinned image required')
    if not (control/'supervisor.py').is_file() or not (paths.root/'source.git/HEAD').is_file():
        raise ValueError('finalize the installed source and control first')
    previous={key:_read(getattr(paths,key)) for key in ('cron','rotation')}
    plain,mail=_templates(paths,False),_templates(paths,True)
    if previous['cron'] not in (None,plain['cron'].encode(),mail['cron'].encode()):
        raise ValueError('custom base schedule preserved; review manual migration')
    if previous['rotation'] not in (None,plain['rotation'].encode()):
        raise ValueError('custom rotation preserved; review manual migration')
    enabled=with_mail is True or previous['cron']==mail['cron'].encode()
    if enabled:
        from tools import capability_view
        if capability_view(paths.root,config)['PRIVATE_MAIL']['state']!='CONFIGURED_UNVERIFIED':
            raise ValueError('configure and verify private mail before scheduling it')
    for path in (paths.logs/'queue.log',paths.logs/'daily.log',paths.logs/'think.log',
                 paths.root/'state/private/mail-cron.log'):
        info=_file_info(path,limit=2**63-1)
        if info is not None and info.st_mode & 0o077:
            raise ValueError('existing diagnostic log must be private')
    return revision,image,previous,_templates(paths,enabled),enabled


def preview(paths=Paths(),with_mail=None):
    revision,_,previous,templates,enabled=_inspect(paths,with_mail)
    return dict(revision=revision,mail_enabled=enabled,templates=templates,
                changes=[name for name in templates if previous[name]!=templates[name].encode()],
                previous_sha256={name:hashlib.sha256(raw).hexdigest() if raw is not None else None
                                 for name,raw in previous.items()},
                prerequisites='Apply checks active cron/logrotate.timer, source revision, local image and logrotate syntax; preview grants no readiness.')


def _sync(directory):
    descriptor=os.open(directory,os.O_DIRECTORY)
    try:os.fsync(descriptor)
    finally:os.close(descriptor)


def _replace(path,data,mode=0o644):
    fd,name=tempfile.mkstemp(prefix='.globalland-maintenance-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.chmod(name,mode);os.replace(name,path);_sync(path.parent)
    finally:
        if os.path.exists(name):os.unlink(name)


def _check(run,command,reason):
    try:result=run(command,capture_output=True,text=True,timeout=30)
    except (OSError,subprocess.TimeoutExpired):raise ValueError(reason) from None
    if result.returncode:raise ValueError(reason)
    return result


def _verify_source_image(paths,revision,image,run):
    bare=_check(run,['git','--git-dir='+str(paths.root/'source.git'),'rev-parse','--is-bare-repository'],
                'initialized bare source required')
    if bare.stdout.strip()!='true':raise ValueError('initialized bare source required')
    _check(run,['git','--git-dir='+str(paths.root/'source.git'),'cat-file','-e',revision+'^{commit}'],
           'installed revision not found in initialized source')
    _check(run,['docker','image','inspect',image,'--format','{{.Id}}'],'executor image missing locally')


def install(paths=Paths(),with_mail=None,run=subprocess.run):
    revision,image,_,_,_=_inspect(paths,with_mail)
    for service in ('cron','logrotate.timer'):
        _check(run,['systemctl','is-active','--quiet',service],'required maintenance service is inactive: '+service)
    _verify_source_image(paths,revision,image,run)
    lockpath=paths.root/'state/supervisor.lock'
    _read(lockpath)
    descriptor=os.open(lockpath,os.O_CREAT|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    with os.fdopen(descriptor,'a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('supervisor busy; retry after the current cycle') from None
        revision,image,previous,templates,enabled=_inspect(paths,with_mail)
        # An administrative upgrade may have completed between preflight and
        # lock acquisition. Validate the current protected configuration too.
        _verify_source_image(paths,revision,image,run)
        changes=[name for name in ('rotation','cron') if previous[name]!=templates[name].encode()]
        if not changes:return dict(revision=revision,mail_enabled=enabled,changes=[],backup=None)
        with tempfile.NamedTemporaryFile(prefix='globalland-logrotate-',mode='w',encoding='utf-8') as candidate:
            candidate.write(templates['rotation']);candidate.flush()
            _check(run,['logrotate','--debug','--state','/dev/null',candidate.name],'logrotate syntax check failed')
        for directory in (paths.root/'backups',paths.root/'state/private',paths.logs):
            directory.mkdir(parents=True,exist_ok=True,mode=0o700)
        for path in (paths.logs/'queue.log',paths.logs/'daily.log',paths.logs/'think.log',paths.root/'state/private/mail-cron.log'):
            try:fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
            except FileExistsError:continue
            else:os.close(fd)
        backup=pathlib.Path(tempfile.mkdtemp(prefix='maintenance-',dir=paths.root/'backups'))
        saved={name:raw.decode() if raw is not None else None for name,raw in previous.items()}
        _replace(backup/'before.json',json.dumps(saved).encode(),0o600)
        attempted=[]
        try:
            for name in changes:
                attempted.append(name)
                _replace(getattr(paths,name),templates[name].encode())
        except Exception:
            try:
                for name in reversed(attempted):
                    path=getattr(paths,name);current=_read(path)
                    if current==previous[name]:continue
                    if current!=templates[name].encode():raise RuntimeError('maintenance file changed concurrently')
                    if previous[name] is None:path.unlink();_sync(path.parent)
                    else:_replace(path,previous[name])
            except Exception as rollback_error:
                raise RuntimeError('Maintenance rollback incomplete; inspect private backup '+str(backup)) from rollback_error
            raise
        return dict(revision=revision,mail_enabled=enabled,changes=changes,backup=str(backup))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true',help='install after review; activates maintenance schedules')
    parser.add_argument('--with-mail',action='store_const',const=True,default=None,help='include configured, manually verified private mail')
    args=parser.parse_args()
    if args.apply and os.geteuid()!=0:parser.error('apply requires the administrator')
    try:result=install(with_mail=args.with_mail) if args.apply else preview(with_mail=args.with_mail)
    except (OSError,ValueError,RuntimeError) as error:parser.exit(1,'Maintenance stopped: '+str(error)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
