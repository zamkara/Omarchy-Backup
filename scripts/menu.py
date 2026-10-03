#!/usr/bin/env python3
"""Optional user-owned Setup menu integration; preserves unrelated entries."""
import argparse,datetime,json,pathlib,re,shutil
ENTRY={'icon':'󰁯','label':'Backup & Restore','description':'Selective backup and restore','action':'omarchy-shell shell summon zam.backup','when':'test -f "$HOME/.config/omarchy/plugins/zam.backup/manifest.json"'}
def jsonc(text):
 pattern=r'("(?:\\.|[^"\\])*")|//[^\n]*|/\*[\s\S]*?\*/'
 text=re.sub(pattern,lambda match:match.group(1) or '',text)
 text=re.sub(r'("(?:\\.|[^"\\])*")|,(?=\s*[}\]])',lambda match:match.group(1) or '',text)
 return json.loads(text)
def main():
 parser=argparse.ArgumentParser();group=parser.add_mutually_exclusive_group(required=True);group.add_argument('--install',action='store_true');group.add_argument('--remove',action='store_true');args=parser.parse_args()
 path=pathlib.Path.home()/'.config/omarchy/extensions/omarchy-menu.jsonc'
 data=jsonc(path.read_text()) if path.exists() else {}
 if args.install:
  if 'setup.backup' in data and data['setup.backup'].get('action')!=ENTRY['action']:raise SystemExit('Setup backup entry belongs to another tool; left unchanged.')
  existing=data.get('setup.backup',{})
  entry={**ENTRY,**existing}
  if existing==entry:return
  data['setup.backup']=entry
 else:
  if data.get('setup.backup',{}).get('action')!=ENTRY['action']:return
  del data['setup.backup']
 path.parent.mkdir(parents=True,exist_ok=True)
 if path.exists():shutil.copy2(path,path.with_name(path.name+'.before-backup-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')))
 temporary=path.with_name(path.name+'.tmp');temporary.write_text(json.dumps(data,indent=2)+'\n');temporary.replace(path)
 print('Setup menu updated: '+str(path))
if __name__=='__main__':main()
