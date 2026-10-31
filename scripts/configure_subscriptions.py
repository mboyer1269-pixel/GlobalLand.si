#!/usr/bin/env python3
"""Explicit administrator setup. Checks official CLI auth; performs no inference."""
import argparse,json,os,pathlib,sys
from controller import Controller
from supervisor import atomic_json

def main():
 p=argparse.ArgumentParser();p.add_argument('--image',required=True);p.add_argument('--providers',default='codex,claude');p.add_argument('--confirm-extra-usage-disabled',action='store_true');args=p.parse_args()
 if os.geteuid()!=0:raise ValueError('administrator required')
 if not args.confirm_extra_usage_disabled:raise ValueError('First disable paid extra usage/API fallback in both accounts; do not attest without checking')
 root=pathlib.Path('/opt/globalland');path=root/'control'/'config.json';config=json.loads(path.read_text()) if path.exists() else {}
 config['controller']={'mode':'subscriptions','providers':args.providers.split(','),'image':args.image,'subscriptions_confirmed':True,'extra_usage_disabled':True}
 controller=Controller(root,None,None,config)
 statuses=[controller.check_provider(provider) for provider in config['controller']['providers']]
 atomic_json(path,config);print(json.dumps({'subscription_checks':statuses,'inference_performed':False,'next':'Run supervisor.py think manually; then verify its tasks and artifacts before enabling think cron.'},indent=2))
if __name__=='__main__':
 try:main()
 except Exception as e:print('Subscription setup stopped: '+str(e),file=sys.stderr);sys.exit(1)
