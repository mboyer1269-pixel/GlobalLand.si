#!/usr/bin/env python3
"""Read-only CLI diagnostics. No inference, login, billing attestation or GlobalLand config writes."""
import argparse,json,pathlib,re
from controller import CLAUDE_MAX_TURNS,auth_command,brain_command,run_brain
from supervisor import SECRET

FLAGS={
 'codex':['--ignore-user-config','--ignore-rules','--sandbox','--ephemeral','--skip-git-repo-check','--output-schema'],
 'claude':['--safe-mode','--tools','--disallowedTools','--strict-mcp-config','--mcp-config','--json-schema','--no-session-persistence','--permission-prompts'],
 'cursor':['--print','--mode','--output-format'],
}

def safe_excerpt(raw,limit=1200):
 text=SECRET.sub(b'[masque]',raw).decode('utf-8',errors='replace')
 text=re.sub(r'\S+@\S+','[courriel]',text)
 text=re.sub(r'[A-Za-z0-9_+/=-]{48,}','[masque]',text)
 return text[:limit].strip()

def diagnose(root,image,provider):
 base=brain_command(root,image,provider);base=base[:base.index(image)+1]
 binary='cursor-agent' if provider=='cursor' else provider
 report={'provider':provider,'inference_performed':False,'globalland_configuration_written':False}
 for label,command in [('version',[binary,'--version']),('help',[binary,'exec','--help'] if provider=='codex' else [binary,'--help']),('auth',auth_command(provider))]:
  code,out=run_brain(base+command,limit=1024*1024,merge_stderr=True)
  text=out.decode('utf-8',errors='replace')
  if label=='auth':
   if provider=='claude':report['option_probe']=['--max-turns',str(CLAUDE_MAX_TURNS)]
   errors={'read_only_filesystem':r'EROFS|read.only file system','permission_denied':r'EACCES|permission denied','unsupported_option':r'unknown option|unexpected argument','not_logged_in':r'not logged in|not authenticated','missing_file':r'ENOENT|no such file'}
   item={'exit':code,'bytes':len(out),'error_categories':[name for name,pattern in errors.items() if re.search(pattern,text,re.I)]}
   try:
    value=json.loads(out)
    if isinstance(value,dict):
     if isinstance(value.get('loggedIn'),bool):item['logged_in']=value['loggedIn']
     if value.get('authMethod') in ('none','claude.ai','oauth_token','api_key','api_key_helper','third_party'):item['method']=value['authMethod']
   except ValueError:pass
  else:
   item={'exit':code,'bytes':len(out),'excerpt':safe_excerpt(out,120 if label=='version' else 1200)}
   if label=='help':item['missing_options']=[f for f in FLAGS[provider] if f not in text]
  report[label]=item
 return report

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--image',required=True)
 parser.add_argument('--provider',choices=FLAGS,required=True)
 parser.add_argument('--root',type=pathlib.Path,default=pathlib.Path('/opt/globalland'))
 args=parser.parse_args()
 print(json.dumps(diagnose(args.root,args.image,args.provider),indent=2,ensure_ascii=False))
if __name__=='__main__':main()
