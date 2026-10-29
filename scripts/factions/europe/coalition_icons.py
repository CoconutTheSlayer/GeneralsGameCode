"""Reuse existing painted portraits; use the new Blender models for new silhouettes.

Creates a final, additive portrait atlas. Small national tabs identify contingents;
blue borders and portrait dimensions stay compatible with the Generals control bar.
No network access or external image service is required.
"""
from pathlib import Path
import re
from PIL import Image,ImageDraw,ImageEnhance,ImageFilter
import numpy as np

ROOT=Path(__file__).resolve().parents[3]
DATA=ROOT/'resources/macos/GameData'
TEX=DATA/'Art/TexturesHD'
CLIENT=DATA/'Data/INI/Addon/Client'
CELL=(200,160)


def existing(name):
    text=(CLIENT/'EuropeIcons.ini').read_text()
    m=re.search(r'MappedImage '+re.escape(name)+r'\s+.*?Texture = (\S+).*?Coords = Left:(\d+) Top:(\d+) Right:(\d+) Bottom:(\d+)',text,re.S)
    if not m:
        text=(CLIENT/'EuropeArt.ini').read_text();m=re.search(r'MappedImage '+re.escape(name)+r'\s+.*?Texture = (\S+).*?Coords = Left:(\d+) Top:(\d+) Right:(\d+) Bottom:(\d+)',text,re.S)
    if not m:raise KeyError(name)
    return Image.open(TEX/m[1]).convert('RGB').crop(tuple(map(int,m.groups()[1:]))).resize(CELL,Image.Resampling.LANCZOS)


def model_portrait(model):
    im=Image.open(ROOT/'build/models'/f'{model}_0.png').convert('RGB')
    a=np.asarray(im).astype(float);bg=a[0,0];delta=np.max(abs(a-bg),axis=2)
    mask=Image.fromarray(np.uint8(np.clip((delta-4)/12,0,1)*255))
    box=mask.getbbox();im=im.crop(box);mask=mask.crop(box)
    scale=min(194/im.width,140/im.height)
    size=(int(im.width*scale),int(im.height*scale));im=im.resize(size,Image.Resampling.LANCZOS);mask=mask.resize(size,Image.Resampling.LANCZOS)
    out=Image.new('RGB',CELL);d=ImageDraw.Draw(out)
    for y in range(160):
        t=y/160;d.line((0,y,200,y),fill=tuple(int(a*(1-t)+b*t) for a,b in zip((187,211,222),(225,211,181))))
    im=ImageEnhance.Brightness(im).enhance(1.15)
    out.paste(im,((200-size[0])//2,10+(140-size[1])//2),mask)
    return out.filter(ImageFilter.UnsharpMask(radius=1,percent=115,threshold=3))


def flag(country):
    im=Image.new('RGB',(30,20),'white');d=ImageDraw.Draw(im)
    vertical={'France':['#163d8c','white','#dc3e42'],'Belgium':['#242424','#f0ca31','#c63843'],
              'Ireland':['#288655','white','#e48c3b'],'Italy':['#29855d','white','#c4404a'],
              'Romania':['#173878','#f3cf38','#be343b']}
    horizontal={'Austria':['#c53843','white','#c53843'],'Bulgaria':['white','#27845d','#c53843'],
                'Germany':['#222222','#b73735','#e3be3a'],'Netherlands':['#b7393f','white','#264580'],
                'Lithuania':['#e2bb32','#337b4e','#b63842'],'Hungary':['#bb3b46','white','#38765a'],
                'Luxembourg':['#cc3845','white','#49a4d1'],'Slovenia':['white','#244b99','#c83841'],
                'Croatia':['#c83b41','white','#274a90'],'Estonia':['#4585c5','#252525','white']}
    if country in vertical:
        for i,c in enumerate(vertical[country]):d.rectangle((i*10,0,(i+1)*10,20),fill=c)
    elif country in horizontal:
        for i,c in enumerate(horizontal[country]):d.rectangle((0,i*20//3,30,(i+1)*20//3),fill=c)
    elif country=='Poland':d.rectangle((0,10,30,20),fill='#c44050')
    elif country=='Czechia':
        d.rectangle((0,10,30,20),fill='#c23b44');d.polygon([(0,0),(15,10),(0,20)],fill='#254780')
    elif country=='Slovakia':
        d.rectangle((0,7,30,14),fill='#294f92');d.rectangle((0,14,30,20),fill='#c13c47');d.rectangle((5,5,12,15),fill='#bd3943');d.line((8,6,8,13),fill='white',width=2);d.line((5,9,11,9),fill='white',width=2)
    elif country in ['Sweden','Finland','Denmark','Norway','Iceland']:
        base,cross={'Sweden':('#285f9d','#f1cb3c'),'Finland':('white','#2c538a'),'Denmark':('#b62d43','white'),
                    'Norway':('#b63344','#203e76'),'Iceland':('#275e9a','#bc3847')}[country]
        d.rectangle((0,0,30,20),fill=base)
        if country in ['Norway','Iceland']:d.rectangle((7,0,14,20),fill='white');d.rectangle((0,6,30,13),fill='white')
        d.rectangle((9,0,12,20),fill=cross);d.rectangle((0,8,30,11),fill=cross)
    elif country=='United Kingdom':
        d.rectangle((0,0,30,20),fill='#24417a');d.line((0,0,30,20),fill='white',width=5);d.line((0,20,30,0),fill='white',width=5)
        d.rectangle((12,0,18,20),fill='white');d.rectangle((0,7,30,13),fill='white');d.rectangle((14,0,16,20),fill='#c23c47');d.rectangle((0,9,30,11),fill='#c23c47')
    elif country=='Switzerland':
        d.rectangle((0,0,30,20),fill='#c23942');d.rectangle((12,3,17,17),fill='white');d.rectangle((7,7,22,12),fill='white')
    elif country=='Portugal':d.rectangle((0,0,12,20),fill='#286d49');d.rectangle((12,0,30,20),fill='#b53843');d.ellipse((8,6,16,14),fill='#e3bd39')
    elif country=='Spain':d.rectangle((0,0,30,20),fill='#bf3b40');d.rectangle((0,5,30,15),fill='#eac239')
    elif country=='Latvia':d.rectangle((0,0,30,20),fill='#843342');d.rectangle((0,8,30,12),fill='white')
    elif country=='Malta':d.rectangle((15,0,30,20),fill='#c83e47');d.line((3,3,7,3),fill='#888888',width=2);d.line((5,1,5,6),fill='#888888',width=2)
    elif country=='Cyprus':d.polygon([(8,9),(18,7),(25,4),(21,10),(13,13)],fill='#c69a42');d.arc((8,9,22,17),0,180,fill='#467552',width=2)
    elif country=='Greece':
        for y in range(0,20,4):d.rectangle((0,y,30,y+2),fill='#3a70a1')
        d.rectangle((0,0,11,11),fill='#3a70a1');d.rectangle((4,0,6,11),fill='white');d.rectangle((0,4,11,6),fill='white')
    else:raise KeyError(country)
    return im


def main():
    rows=[
        ('Euro_Rifleman','France','Euro_Rifleman'),('Euro_Milan','France','Euro_Milan'),('Euro_Marksman','Finland','Euro_Marksman'),
        ('Euro_Commando','Poland','Euro_Commando'),('Euro_Boxer','Lithuania','EUBOXER'),('Euro_Leopard','Germany','Euro_Leopard'),
        ('Euro_Leclerc','France','Euro_Leclerc'),('Euro_Puls','Netherlands','Euro_Puls'),('Euro_ReconDrone','Estonia','EUDRONE'),
        ('Euro_Typhoon','United Kingdom','Euro_Typhoon'),('Euro_Rafale','France','Euro_Rafale'),('Euro_Tornado','United Kingdom','Euro_Tornado'),
        ('Euro_Tiger','Spain','Euro_Tiger'),('Euro_NH90','Italy','Euro_NH90'),('Euro_Skyranger','Switzerland','Euro_Skyranger'),
        ('Euro_PatriotBattery','Norway','Euro_PatriotBattery'),
        ('Euro_Dana','Czechia','EUDANA'),('Euro_Wiesel','Germany','EUWIEST'),('Euro_Ambulance','Slovenia','EUVALUK'),
        ('Euro_Patria','Latvia','EUPATRIA'),('Euro_MV4','Croatia','EUMV4'),('Euro_Apache','United Kingdom','EUAPACHE'),
        ('Euro_A400M','Luxembourg','EUA400M'),('Euro_Puma','Romania','EUPUMA'),('Euro_Gripen','Sweden','EUGRIPEN'),
        ('Euro_Mistral','Cyprus','Euro_Milan'),('Euro_Reserve','Austria','Euro_Rifleman'),('Euro_ATGL','Bulgaria','Euro_Milan'),
        ('Euro_Paratrooper','Portugal','Euro_Rifleman'),('Euro_Ranger','Ireland','Euro_Commando'),('Euro_EOD','Malta','Euro_Rifleman'),
        ('Euro_Rescuer','Iceland','Euro_Rifleman'),('Euro_UpgradeMinimi','Belgium','Euro_Rifleman'),('Euro_UpgradeLynx','Hungary','Euro_Marksman'),
        ('Euro_UpgradeAhead','Switzerland','Euro_Skyranger'),('Euro_UpgradeOptics','Greece','Euro_PowerSpyDrone'),
        ('Euro_UpgradeCountermeasures','Denmark','Euro_Typhoon'),('Euro_PowerEngineering','Croatia','EUMV4'),
        ('Euro_PowerArtilleryBarrage','Slovakia','EUDANA'),('Euro_PowerCoalition','Latvia','EUBOXER'),
        ('Euro_PowerParadrop','Portugal','EUA400M'),('Euro_PowerEmergencyRepair','Iceland','EUPUMA'),
        ('Euro_PowerA10ThunderboltMissileStrike','Sweden','EUGRIPEN')]
    atlas=Image.new('RGB',(2048,2048));lines=['; Coalition portraits generated by coalition_icons.py.']
    gallery=Image.new('RGB',(1200,((len(rows)+5)//6)*182),(25,33,43));gd=ImageDraw.Draw(gallery)
    for i,(name,country,source) in enumerate(rows):
        im=model_portrait(source) if source.isupper() else existing(source)
        if name in ('Euro_EOD','Euro_Rescuer'):
            # Crop the reused face portrait above the rifle; identify noncombatants
            # with a role badge instead of showing an armed soldier.
            im=im.crop((15,0,135,96)).resize(CELL,Image.Resampling.LANCZOS)
            badge=ImageDraw.Draw(im);badge.rounded_rectangle((145,102,191,150),radius=5,fill=(226,232,229),outline=(30,56,65),width=2)
            if name=='Euro_Rescuer':
                badge.rectangle((162,110,174,142),fill=(25,107,87));badge.rectangle((152,120,184,132),fill=(25,107,87))
            else:
                badge.ellipse((157,114,177,134),fill=(50,58,68));badge.line((173,113,180,108,185,112),fill=(50,58,68),width=3)
        im.paste(flag(country),(7,7));d=ImageDraw.Draw(im);d.rectangle((6,6,37,27),outline=(30,44,58))
        x=i%10*200;y=i//10*160;atlas.paste(im,(x,y))
        aliases=[name,name+'_L']
        if name in ('Euro_PowerParadrop','Euro_PowerEmergencyRepair','Euro_PowerA10ThunderboltMissileStrike'):aliases += [name+'2',name+'3']
        for alias in aliases:
            lines += [f'MappedImage {alias}','  Texture = eu_coalition_icons.tga','  TextureWidth = 2048','  TextureHeight = 2048',
                      f'  Coords = Left:{x} Top:{y} Right:{x+200} Bottom:{y+160}','  Status = NONE','End','']
        gx=i%6*200;gy=i//6*182;gallery.paste(im,(gx,gy));gd.text((gx+7,gy+163),country+' / '+name.removeprefix('Euro_')[:16],fill='white')
    atlas.save(TEX/'eu_coalition_icons.tga')
    # Alphabetically after both legacy portrait files, to override selected images.
    (CLIENT/'EuropeRoster.ini').write_text('\n'.join(lines))
    out=ROOT/'build/coalition-roster';out.mkdir(exist_ok=True,parents=True);gallery.save(out/'roster-portraits.jpg')
    print('Wrote',len(rows),'coalition portraits')


if __name__=='__main__':main()
