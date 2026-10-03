import pathlib,tempfile,tarfile,io,json,hashlib,subprocess
with tempfile.TemporaryDirectory(prefix='restore-cancel-test-') as temp:
 root=pathlib.Path(temp);backup=root/'backup';(backup/'archives').mkdir(parents=True);(backup/'metadata').mkdir();home=root/'home';home.mkdir();(home/'.bashrc').write_text('original configuration')
 archive=backup/'archives/test.tar.gz'
 with tarfile.open(archive,'w:gz') as tar:
  for name,data in [('.bashrc',b'restored configuration'),('.config',None),('.config/new-file',b'x'*(32*1024*1024))]:
   item=tarfile.TarInfo(name)
   if data is None:item.type=tarfile.DIRTYPE;item.mode=0o755;tar.addfile(item)
   else:item.size=len(data);tar.addfile(item,io.BytesIO(data))
 digest=hashlib.file_digest(archive.open('rb'),'sha256').hexdigest();(backup/'metadata/manifest.json').write_text(json.dumps({'user':'test','checksums':{'archives/test.tar.gz':digest}}))
 log=root/'restore.log'
 command=['python3',str(pathlib.Path(__file__).resolve().parents[1]/'scripts/omarchy-restore.py'),'--backup',str(backup),'--target',str(home),'--restore','--yes','--log-file',str(log)]
 p=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 while True:
  line=p.stdout.readline()
  if line.startswith('restore .config/new-file'):break
  if not line:raise AssertionError('Restore did not reach file copy: '+p.stderr.read())
 p.terminate();stdout,stderr=p.communicate(timeout=20)
 assert p.returncode==130,(p.returncode,stderr)
 assert (home/'.bashrc').read_text()=='original configuration'
 assert not (home/'.config/new-file').exists()
 assert not (home/'.config').exists()
 text=log.read_text();assert 'rollback .bashrc' in text and 'Traceback' in text
 print('PASS: cancel restore rolls back old files, removes new files, preserves raw diagnostic log')
