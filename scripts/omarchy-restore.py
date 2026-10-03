#!/usr/bin/env python3
import signal,traceback
import argparse,hashlib,json,os,pathlib,shutil,tarfile,tempfile,datetime
BASE=pathlib.Path(__file__).resolve().parent
SELECTED=None
DEFER_DESKTOP=False

def verify():
 manifest=json.loads((BASE/'metadata/manifest.json').read_text())
 for name,expected in manifest['checksums'].items():
  path=BASE/name
  if pathlib.PurePosixPath(name).is_absolute() or '..' in pathlib.PurePosixPath(name).parts:raise RuntimeError('Invalid manifest path')
  with path.open('rb') as f:actual=hashlib.file_digest(f,'sha256').hexdigest()
  if actual!=expected:raise RuntimeError('Checksum mismatch: '+name)
 return manifest

def extract(destination,report=False):
 archives=sorted(p for p in (BASE/'archives').glob('*.tar.gz') if SELECTED is None or p.name.removesuffix('.tar.gz') in SELECTED)
 # Validate the complete selected archive set before writing any entry.
 # A symlink in one section must not redirect entries in another section.
 inspected=[];links=set()
 for path in archives:
  with tarfile.open(path) as tar:
   members=tar.getmembers()
   for member in members:
    name=pathlib.PurePosixPath(member.name)
    if name.is_absolute() or '..' in name.parts or member.islnk() or not (member.isfile() or member.isdir() or member.issym()):raise RuntimeError('Unsafe archive entry: '+member.name)
    if member.issym():links.add(str(name))
   inspected.append((path,members))
 for path,members in inspected:
  for member in members:
   if (str(pathlib.PurePosixPath(member.name)) in links and not member.issym()) or any(str(parent) in links for parent in pathlib.PurePosixPath(member.name).parents):raise RuntimeError('Archive entry beneath symlink: '+member.name)
 for archive_index,(path,members) in enumerate(inspected):
  with tarfile.open(path) as tar:
   for index,member in enumerate(members):
    tar.extract(member,destination,set_attrs=not member.isdir(),filter='fully_trusted')
    if report:
     print('extract '+member.name,flush=True)
     if index%50==0 or index==len(members)-1:print('[progress] '+str(int((archive_index+(index+1)/max(1,len(members)))/max(1,len(archives))*40))+'/100',flush=True)
   for member in reversed(members):
    if member.isdir():os.chmod(pathlib.Path(destination)/member.name,member.mode)

class RestoreCancelled(RuntimeError):pass
def cancelled(signum,frame):raise RestoreCancelled('Restore cancelled')
def restore(target):
 target=target.absolute()
 if target.is_symlink():raise RuntimeError('Target home must not be a symlink')
 target.mkdir(parents=True,exist_ok=True)
 rollback=target/'omarchy-restore-backups'/datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
 changed=[];created_dirs=[];pending=None
 try:
  with tempfile.TemporaryDirectory(prefix='omarchy-restore-') as tmp:
   staging=pathlib.Path(tmp);extract(staging,report=True)
   if DEFER_DESKTOP:
    live_paths=['.config/hypr','.config/omarchy','.config/uwsm','.local/lib/omarchy-shell','.local/bin/omarchy-restore.py','.local/bin/omarchy-backup','.local/bin/omarchy-shell']
    present=[name for name in live_paths if (staging/name).exists() or (staging/name).is_symlink()]
    if present:
     pending=target/'.local/state/omarchy/restore-pending'/datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S_%f')
     pending.mkdir(parents=True,mode=0o700);(pending/'archives').mkdir(mode=0o700);(pending/'metadata').mkdir()
     archive=pending/'archives/desktop.tar.gz'
     with tarfile.open(archive,'w:gz',dereference=False) as tar:
      for name in present:tar.add(staging/name,arcname=name)
     with archive.open('rb') as reader:checksum=hashlib.file_digest(reader,'sha256').hexdigest()
     (pending/'metadata/manifest.json').write_text(json.dumps({'user':target.name,'created':datetime.datetime.now().isoformat(),'sections':['desktop'],'checksums':{'archives/desktop.tar.gz':checksum}}))
     for name in present:
      source=staging/name
      if source.is_dir() and not source.is_symlink():shutil.rmtree(source)
      else:source.unlink()
     print('Desktop configuration staged without triggering live reload: '+str(pending),flush=True)
     import shlex,sys
     command=['bash',str(BASE/'restore.sh')] if (BASE/'restore.sh').exists() else [sys.executable,str(pathlib.Path(__file__).resolve())]
     print('Apply after restore completes: '+shlex.join(command+['--backup',str(pending),'--restore','--apply-desktop']),flush=True)
   sources=sorted(staging.rglob('*'),key=lambda p:len(p.parts))
   total=max(1,sum(p.stat().st_size for p in sources if p.is_file() and not p.is_symlink()));written=0
   for source in sources:
    relative=source.relative_to(staging);dest=target/relative
    parent=dest.parent
    while parent!=target:
     if parent.is_symlink():raise RuntimeError('Refusing redirected destination: '+str(parent))
     parent=parent.parent
    if source.is_dir() and not source.is_symlink():
     if dest.is_symlink() or (dest.exists() and not dest.is_dir()):raise RuntimeError('Destination directory conflict: '+str(dest))
     if not dest.exists():created_dirs.append(dest);dest.mkdir(mode=source.stat().st_mode & 0o777)
     continue
    saved=None
    if dest.exists() or dest.is_symlink():
     if dest.is_dir() and not dest.is_symlink():raise RuntimeError('Destination file conflict: '+str(dest))
     saved=rollback/relative;saved.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dest,saved,follow_symlinks=False)
    changed.append((dest,saved))
    if dest.exists() or dest.is_symlink():dest.unlink()
    print('restore '+str(relative),flush=True)
    if source.is_symlink():dest.symlink_to(os.readlink(source))
    else:
     with source.open('rb') as reader,dest.open('wb') as writer:
      while chunk:=reader.read(1024*1024):
       writer.write(chunk);written+=len(chunk);print('[progress] '+str(40+int(min(1,written/total)*55))+'/100',flush=True)
     shutil.copystat(source,dest)
   if target==pathlib.Path.home():
    import subprocess
    for cmd in (['fc-cache','-f'],['systemctl','--user','daemon-reload']):
     if shutil.which(cmd[0]):
      try:
       result=subprocess.run(cmd,check=False)
       if result.returncode:print('Warning: optional session refresh failed: '+' '.join(cmd),flush=True)
      except OSError as error:print('Warning: optional session refresh unavailable: '+str(error),flush=True)
 except BaseException:
  previous=signal.signal(signal.SIGTERM,signal.SIG_IGN)
  if pending:shutil.rmtree(pending,ignore_errors=True)
  try:
   for dest,saved in reversed(changed):
    if dest.exists() or dest.is_symlink():dest.unlink()
    if saved:shutil.copy2(saved,dest,follow_symlinks=False)
    print('rollback '+str(dest.relative_to(target)),flush=True)
   for directory in reversed(created_dirs):
    try:directory.rmdir()
    except FileNotFoundError:pass
   print('Rollback complete: previous files restored.',flush=True)
  finally:signal.signal(signal.SIGTERM,previous)
  raise
 print('[progress] 100/100',flush=True)
 print('Restored to: '+str(target),flush=True);print('Previous files saved to: '+str(rollback),flush=True)
 print('Review device paths, then run: omarchy restart shell',flush=True)

class Tee:
 def __init__(self,stream,log):self.stream=stream;self.log=log
 def write(self,text):
  self.log.write(text);self.log.flush();return self.stream.write(text)
 def flush(self):self.log.flush();self.stream.flush()
 def isatty(self):return False
def attach_log(path):
 if not path:return
 path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
 log=path.open('a');os.chmod(path,0o600)
 import sys
 sys.stdout=Tee(sys.stdout,log);sys.stderr=Tee(sys.stderr,log)

def install_packages():
 import subprocess,re
 official=BASE/'packages/official.txt'
 if not official.exists():
  print('Package inventory was not selected for this backup.');return
 if not shutil.which('pacman'):raise RuntimeError('Package installation requires Arch Linux / Omarchy')
 for filename,label in [('official.txt','official'),('aur-foreign.txt','AUR/foreign')]:
  path=BASE/'packages'/filename
  packages=[name for name in path.read_text().splitlines() if re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9@._+-]*',name)] if path.exists() else []
  if not packages or input('Install '+label+' packages? [y/N] ').lower()!='y':continue
  command=['sudo','pacman'] if label=='official' else [shutil.which('yay') or shutil.which('paru') or '']
  if not command[0]:raise RuntimeError('Install yay or paru first. See packages/aur-foreign.txt')
  subprocess.run(command+['-S','--needed','--']+packages,check=True)
 print('Done. Flatpak inventory: '+str(BASE/'packages/flatpak.txt'))

if __name__=='__main__':
 signal.signal(signal.SIGTERM,cancelled)
 signal.signal(signal.SIGINT,cancelled)
 parser=argparse.ArgumentParser();group=parser.add_mutually_exclusive_group();group.add_argument('--check',action='store_true');group.add_argument('--preview',action='store_true');group.add_argument('--extract',type=pathlib.Path);group.add_argument('--restore',action='store_true');group.add_argument('--install-packages',action='store_true');parser.add_argument('--sections');parser.add_argument('--defer-desktop',action='store_true');parser.add_argument('--apply-desktop',action='store_true');parser.add_argument('--target',type=pathlib.Path,default=pathlib.Path.home());parser.add_argument('--backup',type=pathlib.Path);parser.add_argument('--yes',action='store_true');parser.add_argument('--log-file',type=pathlib.Path);args=parser.parse_args();BASE=args.backup.resolve() if args.backup else BASE;DEFER_DESKTOP=not args.apply_desktop and (args.defer_desktop or args.target.absolute()==pathlib.Path.home());attach_log(args.log_file)
 try:
  info=verify()
  available={p.name.removesuffix('.tar.gz') for p in (BASE/'archives').glob('*.tar.gz')}
  if args.sections is not None:
   SELECTED=set(args.sections.split(','))
   if not SELECTED or not SELECTED <= available:raise RuntimeError('Select valid restore sections: '+', '.join(sorted(available)))
  if not any((args.preview,args.check,args.extract,args.restore,args.install_packages)):
   print('Backup & Restore · '+info.get('created','Unknown'))
   print('1. Restore files\n2. Install packages\n3. Verify backup\n0. Exit')
   choice=input('Choose an action: ').strip()
   if choice=='0':raise SystemExit(0)
   if choice=='1':
    args.restore=True
    names=sorted(available)
    for index,name in enumerate(names,1):print(str(index)+'. '+name)
    selection=input('Sections to restore (comma-separated numbers, Enter for all): ').strip()
    if selection:
     numbers=[int(value.strip()) for value in selection.split(',')]
     if any(n<1 or n>len(names) for n in numbers):raise RuntimeError('Invalid section selection')
     SELECTED={names[n-1] for n in numbers}
   elif choice=='2':args.install_packages=True
   elif choice=='3':args.check=True
   else:raise RuntimeError('Invalid selection')
  if args.install_packages:install_packages()
  elif args.preview:
   archives=[{'name':p.name,'bytes':p.stat().st_size} for p in sorted((BASE/'archives').glob('*.tar.gz'))]
   print(json.dumps({'created':info.get('created','Unknown'),'user':info['user'],'sections':info.get('sections',[]),'archives':archives,'verified':True}))
  elif args.check:print('Checksums verified. Backup user: '+info['user'])
  elif args.extract:
   if args.extract.exists() and any(args.extract.iterdir()):raise RuntimeError('Extract destination must be empty')
   args.extract.mkdir(parents=True,exist_ok=True);extract(args.extract);print('Extracted to: '+str(args.extract))
  else:
   print('Restore configuration and local tools to '+str(args.target)+'? Existing files will be backed up.')
   if not args.yes and input('Type RESTORE to continue: ')!='RESTORE':raise RuntimeError('Cancelled')
   restore(args.target)
 except Exception as e:
  traceback.print_exc()
  print('Restore stopped: '+str(e),flush=True);raise SystemExit(130 if isinstance(e,RestoreCancelled) else 1)
