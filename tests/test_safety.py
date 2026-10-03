import hashlib,importlib.util,io,json,pathlib,subprocess,sys,tarfile,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
def load(name):
 spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/name);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
class SafetyTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.temp.name);self.backup=self.root/'backup';(self.backup/'archives').mkdir(parents=True);(self.backup/'metadata').mkdir();self.home=self.root/'home';self.home.mkdir()
 def tearDown(self):self.temp.cleanup()
 def fixture(self,sections):
  checks={}
  for section,files in sections.items():
   archive=self.backup/'archives'/(section+'.tar.gz')
   with tarfile.open(archive,'w:gz') as tar:
    for name,data in files.items():
     data=data.encode();entry=tarfile.TarInfo(name);entry.size=len(data);tar.addfile(entry,io.BytesIO(data))
   checks['archives/'+archive.name]=hashlib.sha256(archive.read_bytes()).hexdigest()
  (self.backup/'metadata/manifest.json').write_text(json.dumps({'user':'test','sections':list(sections),'checksums':checks}))
 def run_restore(self,*args):
  return subprocess.run([sys.executable,str(ROOT/'scripts/omarchy-restore.py'),'--backup',str(self.backup),*args],capture_output=True,text=True)
 def test_selective_restore(self):
  self.fixture({'git':{'.gitconfig':'new'},'terminals':{'.bashrc':'unselected'}})
  result=self.run_restore('--restore','--yes','--target',str(self.home),'--sections','git')
  self.assertEqual(result.returncode,0,result.stderr);self.assertTrue((self.home/'.gitconfig').exists());self.assertFalse((self.home/'.bashrc').exists())
 def test_checksum_and_unknown_section_rejected(self):
  self.fixture({'git':{'.gitconfig':'new'}})
  self.assertNotEqual(self.run_restore('--sections','unknown','--extract',str(self.root/'out')).returncode,0)
  (self.backup/'archives/git.tar.gz').write_bytes(b'corrupted')
  self.assertNotEqual(self.run_restore('--check').returncode,0);self.assertFalse((self.root/'out').exists())
 def test_archive_traversal_rejected(self):
  self.fixture({'git':{'../escape':'unsafe'}})
  result=self.run_restore('--extract',str(self.root/'out'))
  self.assertNotEqual(result.returncode,0);self.assertFalse((self.root/'escape').exists())
 def test_desktop_deferred_then_explicit_apply(self):
  self.fixture({'desktop':{'.config/hypr/hyprland.conf':'new','.gitconfig':'git'}})
  old=self.home/'.config/hypr/hyprland.conf';old.parent.mkdir(parents=True);old.write_text('old')
  result=self.run_restore('--restore','--yes','--target',str(self.home),'--defer-desktop')
  self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(old.read_text(),'old')
  pending=next((self.home/'.local/state/omarchy/restore-pending').iterdir())
  result=subprocess.run([sys.executable,str(ROOT/'scripts/omarchy-restore.py'),'--backup',str(pending),'--restore','--yes','--target',str(self.home),'--apply-desktop'],capture_output=True,text=True)
  self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(old.read_text(),'new')
 def test_portable_single_script(self):
  engine=load('omarchy-backup.py');engine.HOME=self.home;engine.output=lambda command:'test\n';(self.home/'.gitconfig').write_text('portable')
  backup=engine.backup(self.root/'out',['git'],'test-job')
  self.assertEqual(sorted(p.name for p in backup.iterdir() if p.suffix in ('.sh','.py')),['restore.sh'])
  result=subprocess.run(['bash',str(backup/'restore.sh'),'--check'],capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr)
  result=subprocess.run(['bash',str(backup/'restore.sh'),'--extract',str(self.root/'extracted')],capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr)
  self.assertEqual((self.root/'extracted/.gitconfig').read_text(),'portable')
 def test_cancellation_rolls_back(self):
  result=subprocess.run([sys.executable,str(ROOT/'tests/cancel_fixture.py')],capture_output=True,text=True,timeout=30)
  self.assertEqual(result.returncode,0,result.stderr)

class MenuIntegrationTests(unittest.TestCase):
 def test_install_preserves_entries_and_is_idempotent(self):
  from unittest.mock import patch
  engine=load('menu.py')
  with tempfile.TemporaryDirectory() as tmp:
   home=pathlib.Path(tmp);path=home/'.config/omarchy/extensions/omarchy-menu.jsonc';path.parent.mkdir(parents=True);path.write_text('{// comment\n"custom.item":{"label":"Keep","action":"echo x,}"},}')
   with patch.object(pathlib.Path,'home',return_value=home),patch.object(sys,'argv',['menu.py','--install']):
    engine.main();first=path.read_bytes();engine.main();self.assertEqual(first,path.read_bytes())
   data=json.loads(path.read_text());self.assertEqual(data['custom.item']['action'],'echo x,}');self.assertIn('when',data['setup.backup'])
   self.assertEqual(len(list(path.parent.glob('*.before-backup-*'))),1)

class FreshSystemTests(unittest.TestCase):
 setUp=SafetyTests.setUp
 tearDown=SafetyTests.tearDown
 fixture=SafetyTests.fixture
 run_restore=SafetyTests.run_restore
 def test_empty_home_minimal_commands_and_portable_script(self):
  import os,shutil
  engine=load('omarchy-backup.py');engine.HOME=self.home
  commands=self.root/'commands';commands.mkdir()
  for name in ['python3','bash','dirname']:
   executable=sys.executable if name=='python3' else shutil.which(name)
   (commands/name).symlink_to(executable)
  environment={**os.environ,'PATH':str(commands)}
  previous=os.environ['PATH']
  try:
   os.environ['PATH']=str(commands)
   backup=engine.backup(self.root/'out',engine.DEFAULT_SECTIONS,'fresh-system')
  finally:os.environ['PATH']=previous
  target=self.root/'new-user';target.mkdir()
  for args in [['--check'],['--restore','--yes','--target',str(target)],['--preview']]:
   result=subprocess.run([str(commands/'bash'),str(backup/'restore.sh'),*args],env=environment,capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr)
  self.assertFalse((target/'.local/bin').exists())
 def test_cross_archive_symlink_rejected_before_any_write(self):
  self.fixture({'a':{},'b':{'redirect/escape':'unsafe'}})
  archive=self.backup/'archives/a.tar.gz'
  with tarfile.open(archive,'w:gz') as tar:
   entry=tarfile.TarInfo('redirect');entry.type=tarfile.SYMTYPE;entry.linkname=str(self.root/'outside');tar.addfile(entry)
  (self.root/'outside').mkdir()
  manifest=json.loads((self.backup/'metadata/manifest.json').read_text());manifest['checksums']['archives/a.tar.gz']=hashlib.sha256(archive.read_bytes()).hexdigest();(self.backup/'metadata/manifest.json').write_text(json.dumps(manifest))
  result=self.run_restore('--extract',str(self.root/'out'))
  self.assertNotEqual(result.returncode,0);self.assertFalse((self.root/'outside/escape').exists());self.assertEqual(list((self.root/'out').iterdir()),[])
 def test_session_refresh_failure_does_not_undo_restored_files(self):
  from unittest.mock import patch
  self.fixture({'git':{'.gitconfig':'restored'}})
  engine=load('omarchy-restore.py');engine.BASE=self.backup
  with patch.object(pathlib.Path,'home',return_value=self.home),patch('subprocess.run',return_value=subprocess.CompletedProcess([],1)),patch('shutil.which',return_value='/optional/tool'):
   engine.restore(self.home)
  self.assertEqual((self.home/'.gitconfig').read_text(),'restored')

class PortableInteractiveTests(unittest.TestCase):
 setUp=SafetyTests.setUp
 tearDown=SafetyTests.tearDown
 def test_interactive_script_on_new_home(self):
  import os,pty,select,time
  engine=load('omarchy-backup.py');engine.HOME=self.home;engine.output=lambda command:'test\n';(self.home/'.gitconfig').write_text('interactive')
  backup=engine.backup(self.root/'out',['git'],'interactive-test');target=self.root/'new-user'
  child,terminal=pty.fork()
  if child==0:
   os.execv('/bin/bash',['bash',str(backup/'restore.sh'),'--target',str(target)])
  output=b'';deadline=time.monotonic()+10
  try:
   os.write(terminal,b'1\n1\nRESTORE\n')
   while time.monotonic()<deadline:
    ready,_,_=select.select([terminal],[],[],0.2)
    if ready:
     try:data=os.read(terminal,65536)
     except OSError:break
     if not data:break
     output+=data
   else:
    os.kill(child,15);self.fail('Interactive restore timed out: '+output.decode(errors='replace'))
   _,status=os.waitpid(child,0);self.assertEqual(os.waitstatus_to_exitcode(status),0,output.decode(errors='replace'))
   self.assertEqual((target/'.gitconfig').read_text(),'interactive')
  finally:os.close(terminal)

if __name__=='__main__':unittest.main()
