#!/usr/bin/python3
"""Portable, versioned Omarchy customization backups; no external symlink traversal."""
import signal,uuid,time,traceback
import argparse,datetime,hashlib,json,os,pathlib,shutil,subprocess,tarfile,tempfile
HOME=pathlib.Path.home()
DEFAULT=HOME/'Downloads'
def output(command):
 try:
  r=subprocess.run(command,capture_output=True,text=True,timeout=30)
  return r.stdout if r.returncode==0 else 'Unavailable: '+r.stderr
 except (OSError,subprocess.TimeoutExpired) as e:return 'Unavailable: '+str(e)
def excluded(name):
 parts=pathlib.PurePosixPath(name).parts
 return any(x in parts for x in ('__pycache__','node_modules','backups')) or '.before-' in name or name.endswith('.bak')
def payload_size(entries):
 total=0
 for path,name in entries:
  if excluded(name) or path.is_symlink() or not path.exists():continue
  if path.is_file():total+=path.stat().st_size;continue
  for directory,dirs,files in os.walk(path,followlinks=False):
   relative=pathlib.Path(directory).relative_to(path)
   dirs[:]=[d for d in dirs if not excluded(str(pathlib.PurePosixPath(name)/relative/d))]
   for filename in files:
    child=pathlib.Path(directory)/filename
    if child.is_symlink() or excluded(str(pathlib.PurePosixPath(name)/relative/filename)):continue
    try:total+=child.stat().st_size
    except FileNotFoundError:pass
 return total
class CountingReader:
 def __init__(self,source,callback):self.source=source;self.callback=callback
 def read(self,length):
  data=self.source.read(length);self.callback(len(data));return data
class ProgressTarFile(tarfile.TarFile):
 def addfile(self,info,fileobj=None):
  print(info.name,flush=True)
  if fileobj is not None and getattr(self,'progress_callback',None):fileobj=CountingReader(fileobj,self.progress_callback)
  return super().addfile(info,fileobj)
def archive(target,entries,callback=None):
 with ProgressTarFile.open(target,'w:gz',dereference=False) as tar:
  tar.progress_callback=callback
  for path,name in entries:
   if path.exists() or path.is_symlink():tar.add(path,arcname=name,filter=lambda t: None if excluded(t.name) else t)
DEFAULT_SECTIONS=['desktop','terminals','editors','fonts','tools','services','preferences','packages','git']
SECTIONS={
 'desktop':['.config/omarchy','.config/hypr','.config/uwsm','.config/fontconfig','.config/gtk-3.0','.config/gtk-4.0','.config/xdg-desktop-portal','.config/mimeapps.list','.config/user-dirs.dirs','.config/user-dirs.locale'],
 'terminals':['.config/foot','.config/alacritty','.config/kitty','.config/ghostty','.config/fish','.config/starship.toml','.bashrc','.bash_profile','.zshrc','.profile'],
 'editors':['.config/nvim','.config/helix','.config/Code/User/settings.json','.config/Code/User/keybindings.json','.config/Code/User/snippets','.config/btop'],
 'fonts':['.local/share/fonts','.local/share/icons','.local/share/themes','.local/share/applications','.local/share/omarchy'],
 'tools':['.local/bin','.local/lib/omarchy-shell','.local/lib/omarchy-keybindings'],
 'services':['.config/systemd/user'],
 'preferences':['.local/state/omarchy/'+n for n in ('current','defaults','toggles','powerprofiles','workspace-layouts','windows','indicators')],
 'git':['.gitconfig','.gitignore','.config/git'],
 'ssh':['.ssh/config','.ssh/known_hosts','.ssh/known_hosts.old','.ssh/config.d'],
 'ssh-keys':['.ssh'],
 'credentials':['.gnupg','.local/share/keyrings','.password-store'],
 'browsers':['.mozilla','.config/chromium','.config/google-chrome','.config/BraveSoftware'],
 'network':['.config/wireguard','.config/openvpn','.config/rclone','.config/syncthing'],
 'documents':['Documents'],
 'projects':['Projects'],
 'media':['Pictures','Music','Videos'],
}
def backup(destination,sections=None,job_id=None):
 job_id=job_id or str(uuid.uuid4())
 sections=DEFAULT_SECTIONS if sections is None else sections
 unknown=set(sections)-set(SECTIONS)-{'packages'}
 if unknown:raise RuntimeError('Unknown backup sections: '+', '.join(unknown))
 if not sections:raise RuntimeError('Select at least one backup section')
 destination=destination.absolute()
 if str(destination).startswith('/run/media/'):
  mount=pathlib.Path(*destination.parts[:5])
  data=json.loads(output(['findmnt','-J','--mountpoint',str(mount)]))
  if not data.get('filesystems'):raise RuntimeError('Backup drive is not mounted: '+str(mount))
  if 'ro' in data['filesystems'][0]['options'].split(','):raise RuntimeError('Backup drive is read-only: '+str(mount))
 destination.mkdir(parents=True,exist_ok=True)
 stamp=datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
 staging=pathlib.Path(tempfile.mkdtemp(prefix='.incomplete-',dir=destination))
 final=destination/("omarchy-backup-"+stamp)
 try:
  for directory in ('archives','packages','system','metadata'): (staging/directory).mkdir()
  steps=len(sections)+2;done=0
  print('[progress] 0/'+str(steps),flush=True)
  print('Preparing timestamped backup: '+str(final),flush=True)
  for section in sections:
   if section in SECTIONS:
    print('Archiving: '+section,flush=True)
    entries=[(HOME/name,name) for name in SECTIONS[section]]
    estimated=max(1,payload_size(entries));transferred=0;last_update=0
    def report(amount):
     nonlocal transferred,last_update
     transferred+=amount;now=time.monotonic()
     if now-last_update>=0.15:
      print('[progress] '+str(int((done+min(0.99,transferred/estimated))*1000))+'/'+str(steps*1000),flush=True);last_update=now
    archive(staging/'archives'/(section+'.tar.gz'),entries,report)
    done+=1;print('[progress] '+str(done)+'/'+str(steps),flush=True)
  if 'packages' in sections:
   print('Collecting package inventories',flush=True)
   for filename,command in [('official.txt',['pacman','-Qqen']),('aur-foreign.txt',['pacman','-Qqem']),('versions.txt',['pacman','-Q']),('flatpak.txt',['flatpak','list','--app','--columns=application,branch,origin'])]:
    (staging/'packages'/filename).write_text(output(command))
  if 'packages' in sections:
   done+=1;print('[progress] '+str(done)+'/'+str(steps),flush=True)
  for filename,command in [('os-release.txt',['cat','/etc/os-release']),('omarchy-version.txt',['omarchy','version']),('mounts.txt',['findmnt']),('block-devices.txt',['lsblk','-f'])]:
   (staging/'system'/filename).write_text(output(command))
  for name in ('fstab','crypttab'):
   path=pathlib.Path('/etc')/name
   try:(staging/'system'/name).write_text(path.read_text())
   except OSError:pass
  tool_dir=pathlib.Path(__file__).resolve().parent
  restore_source=(tool_dir/'omarchy-restore.py').read_text()
  restore_source=restore_source.replace('BASE=pathlib.Path(__file__).resolve().parent', 'import sys\nBASE=pathlib.Path(sys.argv.pop(1)).resolve()')
  runner=staging/'restore.sh'
  runner.write_text('#!/usr/bin/env bash\nset -euo pipefail\nbackup_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\ncommand -v python3 >/dev/null || { printf "Python 3 is required. Install python first.\\n"; exit 1; }\nexec python3 - "$backup_dir" "$@" <<\'OMARCHY_RESTORE_PY\'\n'+restore_source+'\nOMARCHY_RESTORE_PY\n')
  # Python reads code from stdin; interactive prompts use the controlling terminal.
  runner.write_text(runner.read_text().replace("import sys\nBASE=", "import sys\nif sys.stdin.isatty() is False and not any(a in sys.argv for a in ('--check','--preview','--extract','--yes')): sys.stdin=open('/dev/tty')\nBASE="))
  runner.chmod(0o700)
  (staging/'README.txt').write_text('BACKUP & RESTORE\n\nRun: bash restore.sh\nInteractive choices: restore files, install packages, or verify backup.\nFor unattended checks: bash restore.sh --check\nFor extraction: bash restore.sh --extract /path/to/empty-folder\nThe single restore.sh contains all restore and package installation code.\nRequires Bash and Python 3. Existing files are saved under ~/omarchy-restore-backups/.\nArchives preserve permissions and symlinks on exFAT.\nsystem/: reference only; fstab and crypttab are never installed automatically.\nOptional secrets are unencrypted. Keep this backup private.\nOnly selected sections are included; this is not a bootable OS image.\n')
  print('Computing SHA-256 checksums',flush=True)
  checks={}
  for path in staging.rglob('*'):
   if path.is_file():
    with path.open('rb') as reader:checks[str(path.relative_to(staging))]=hashlib.file_digest(reader,'sha256').hexdigest()
  (staging/'metadata/manifest.json').write_text(json.dumps({'created':stamp,'folder_name':final.name,'job_id':job_id,'user':HOME.name,'home':str(HOME),'scope':'Selected user backup sections','sections':sections,'checksums':checks},indent=2)+'\n')
  done+=1;print('[progress] '+str(done)+'/'+str(steps),flush=True)
  staging.rename(final)
  print('[progress] '+str(steps)+'/'+str(steps),flush=True)
  return final
 except BaseException:
  print('Removing incomplete backup',flush=True)
  shutil.rmtree(staging,ignore_errors=True);raise
def discard(path,job_id):
 path=path.absolute()
 if path.is_symlink():raise RuntimeError('Refusing redirected backup folder')
 manifest=json.loads((path/'metadata/manifest.json').read_text())
 if not job_id or manifest.get('job_id')!=job_id or path.name!=manifest.get('folder_name',manifest.get('created')):raise RuntimeError('Refusing to remove a backup from another job')
 shutil.rmtree(path);print('Cancelled backup removed: '+str(path),flush=True)
def cancelled(signum,frame):raise RuntimeError('Backup cancelled')
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

if __name__=='__main__':
 signal.signal(signal.SIGTERM,cancelled)
 signal.signal(signal.SIGINT,cancelled)
 parser=argparse.ArgumentParser();parser.add_argument('--destination',type=pathlib.Path,default=DEFAULT);parser.add_argument('--interactive',action='store_true');parser.add_argument('--sections');parser.add_argument('--job-id');parser.add_argument('--log-file',type=pathlib.Path);parser.add_argument('--discard',type=pathlib.Path);args=parser.parse_args();attach_log(args.log_file)
 try:
  if args.discard:discard(args.discard,args.job_id)
  else:print('Backup complete: '+str(backup(args.destination,None if args.sections is None else [x for x in args.sections.split(',') if x],args.job_id)),flush=True)
 except Exception as e:
  traceback.print_exc()
  print('Backup failed: '+str(e),flush=True);status=1
 else:status=0
 if args.interactive:
  try:input('Press Enter to close.')
  except EOFError:pass
 raise SystemExit(status)
