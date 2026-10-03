#!/usr/bin/env python3
"""Apply staged desktop configuration and refresh Omarchy only on explicit request."""
import argparse,pathlib,subprocess,sys,traceback
parser=argparse.ArgumentParser();parser.add_argument('--pending');parser.add_argument('--log-file',required=True);args=parser.parse_args()
log=pathlib.Path(args.log_file);log.parent.mkdir(parents=True,exist_ok=True)
with log.open('a') as output:
 try:
  if args.pending:
   subprocess.run([sys.executable,str(pathlib.Path(__file__).with_name('omarchy-restore.py')),'--backup',args.pending,'--restore','--yes','--apply-desktop'],stdout=output,stderr=output,check=True)
  for command in [['omarchy','restart','hyprctl'],['systemctl','--user','daemon-reload'],['omarchy','restart','shell']]:
   print('Running: '+' '.join(command),file=output,flush=True)
   subprocess.run(command,stdout=output,stderr=output,check=True)
 except Exception:
  traceback.print_exc(file=output);raise SystemExit(1)
