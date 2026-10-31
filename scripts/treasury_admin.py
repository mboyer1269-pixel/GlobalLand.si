#!/usr/bin/env python3
"""Import actual provider evidence via a configured trusted verifier. No invented funding."""
import argparse,json,os,pathlib,sys
from treasury import Treasury
from gateway import Gateway

def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['status','funding','revenue','positions']);p.add_argument('--receipt');args=p.parse_args()
 if os.geteuid()!=0:raise ValueError('administrator required')
 root=pathlib.Path('/opt/globalland');private=root/'state/private';private.mkdir(parents=True,exist_ok=True,mode=0o700)
 bank=Treasury(private/'treasury.sqlite3');bank.verifier=Gateway(root,bank).verify
 if args.action=='status':print(json.dumps(bank.snapshot(),indent=2));return
 if not args.receipt:raise ValueError('actual settled provider receipt required')
 receipt=json.loads(pathlib.Path(args.receipt).read_text())
 method={'funding':bank.confirm_funding,'revenue':bank.credit,'positions':bank.record_positions}[args.action]
 print(json.dumps(method(receipt),indent=2))
if __name__=='__main__':
 try:main()
 except Exception:print('Treasury import refused: configure trusted provider verification and inspect evidence privately.',file=sys.stderr);sys.exit(1)
