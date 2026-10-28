"""Bounded isolated move/stop and combat-pose screenshots, no live data edits."""
from pathlib import Path
import json,os,re,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts/factions/expansion'))
from native_review import prepare
mode=sys.argv[1] if len(sys.argv)>1 else 'stop'
unit=sys.argv[2] if len(sys.argv)>2 else 'Ukraine_Rifleman'
folder=ROOT/'build/new-factions/native/ukraine'/('pose-'+mode+'-'+str(time.time_ns()))
binary=prepare(folder,'ukraine',True)
battle=folder/'battle.txt'
battle.write_text('map Tournament Desert\ncash 10000\nseed 5\nsuperweapons 0\nplayer human FactionUkraine 0 0\nplayer easy FactionAmerica 1 2\n')
env={k:v for k,v in os.environ.items() if not k.startswith(('GENERALS_','D3D8METAL_'))}
env.update(GENERALS_NO_MESSAGEBOX='1',SDL_MAC_BACKGROUND_APP='1',SDL_WINDOW_ACTIVATE_WHEN_SHOWN='0',SDL_WINDOW_ACTIVATE_WHEN_RAISED='0',GENERALS_LOOKAT='0.5,0.5,125',D3D8METAL_SCREENSHOT=str(folder/'scene'),D3D8METAL_SCREENSHOT_EVERY='120')
if mode=='stop':env['GENERALS_PATH_TEST']=unit+':3:0.5:0.5:0.5:0.5'
else:env.update(GENERALS_DUEL=unit+':3,AmericaTankPaladin:1',GENERALS_DUEL_DISTANCE='145',GENERALS_DUEL_SECONDS='15',GENERALS_DUEL_HOLD_SIDE='1')
start=time.monotonic();done=None
with (folder/'native.log').open('w') as f:
 p=subprocess.Popen([str(binary),'-noaudio','-win','-xres','1440','-yres','900','-gamespeed','60','-battle',str(battle)],cwd=Path.home()/'Games/generalszh',env=env,stdout=f,stderr=f)
 try:
  while p.poll() is None and time.monotonic()-start<60:
   log=(folder/'native.log').read_text(errors='replace')
   if 'PATH_TEST_DONE' in log and done is None:done=time.monotonic()
   if mode=='stop' and done and time.monotonic()-done>4:break
   if mode!='stop' and 'DUEL_RESULT' in log:break
   time.sleep(.25)
 finally:
  if p.poll() is None:p.terminate()
  try:p.wait(timeout=4)
  except subprocess.TimeoutExpired:p.kill();p.wait()
log=(folder/'native.log').read_text(errors='replace')
events=[r for r in log.splitlines() if 'PATH_TEST_DONE' in r or 'DUEL_RESULT' in r]
report={'mode':mode,'unit':unit,'status':'passed' if events and not re.search('CRASH|Error parsing|DUEL_RESULT error',log) else 'failed','events':events,'folder':str(folder),'images':[str(p) for p in sorted(folder.glob('scene_*.png'))]}
(folder/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
