"""Authenticated operational probe for health, readiness, and metrics."""
import argparse,json,os,urllib.request
def fetch(url,token=None):
 request=urllib.request.Request(url,headers={"X-Admin-Pin":token} if token else {})
 with urllib.request.urlopen(request,timeout=5) as response:return response.status,response.read().decode()
def main():
 parser=argparse.ArgumentParser();parser.add_argument("--base-url",default=os.environ.get("GREYGUARD_MONITOR_URL","http://127.0.0.1:8000"));args=parser.parse_args();base=args.base_url.rstrip("/");token=os.environ.get("GREYGUARD_MONITOR_TOKEN")
 checks={};healthy=True
 for name,path,protected in (("live","/health/live",False),("ready","/health/ready",False),("metrics","/observability/metrics",True)):
  try:status,body=fetch(base+path,token if protected else None);checks[name]={"status":status,"ok":status==200,"sample":body[:120]};healthy=healthy and status==200
  except Exception as error:checks[name]={"ok":False,"error":type(error).__name__};healthy=False
 print(json.dumps({"healthy":healthy,"checks":checks},indent=2));raise SystemExit(0 if healthy else 1)
if __name__=="__main__":main()
