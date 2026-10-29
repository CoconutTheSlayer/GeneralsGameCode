"""Structural checks for the playable coalition, including assets and menu reachability."""
import json
import math
from pathlib import Path
import re
import struct
import build_europe as b
from curated_roster import CORE_UNITS, RETIRED_UNITS
from coalition_infantry import chunks, cstr

ROOT=Path(b.ROOT);DATA=Path(b.DATA)


def check_model(path):
    meshes=set();refs=[];hierarchies=[];triangles=0
    for cid,body,_ in chunks(path.read_bytes()):
        if cid==0x740:meshes.add(cstr(body[8:40]).upper())
        if cid==0:
            parts={c:d for c,d,_ in chunks(body)}
            h=parts[31];mesh=cstr(h[24:40])+'.'+cstr(h[8:24]);meshes.add(mesh.upper())
            ntri,nvert=struct.unpack_from('<II',h,40)
            assert len(parts[2])==nvert*12,(path,'vertex count')
            assert len(parts[32])==ntri*32,(path,'triangle count')
            assert all(math.isfinite(v) for v in struct.unpack('<'+'f'*(len(parts[2])//4),parts[2])),(path,'nonfinite geometry')
            for i in range(ntri):assert max(struct.unpack_from('<3I',parts[32],i*32))<nvert,(path,'bad triangle')
            triangles+=ntri
        if cid==0x100:
            for c,d,_ in chunks(body):
                if c==0x102:
                    names=[cstr(d[i:i+16]).upper() for i in range(0,len(d),60)]
                    assert len(names)==len(set(names)),(path,'duplicate bone')
                    for i in range(len(names)):
                        parent=struct.unpack_from('<i',d,i*60+16)[0]
                        assert parent<i,(path,'invalid bone hierarchy')
                    hierarchies=names
        if cid==0x700:
            for c,d,_ in chunks(body):
                if c==0x702:
                    for cc,dd,_ in chunks(d):
                        if cc==0x704:refs.append((struct.unpack_from('<I',dd)[0],cstr(dd[4:]).upper()))
    for bone,mesh in refs:
        assert mesh in meshes,(path,'missing mesh',mesh)
        if hierarchies:assert bone<len(hierarchies),(path,'missing bone')
    assert triangles>0,(path,'empty model')
    return triangles


def main():
    countries=json.loads((Path(__file__).parent/'coalition_countries.json').read_text())
    assert len(countries)==31 and len({c['country'] for c in countries})==31
    ids={o[0] for o in b.UNITS+b.BUILDINGS};upgrades={u[0] for u in b.UPGRADES}
    text='\n'.join((DATA/'Data/INI/Addon/Logic/Europe.ini').read_text().splitlines())
    production={x for slots in b.COMMAND_SETS.values() for x in slots.values() if x in ids}
    core={o[0] for o in b.UNITS}&production
    assert core==CORE_UNITS,(core-CORE_UNITS,CORE_UNITS-core)
    assert 'Euro_Outpost' not in production
    accessible_buttons={x for slots in b.COMMAND_SETS.values() for x in slots.values()}
    payloads=set(re.findall(r'\b(?:Payload|Transport)\s*=\s*(Euro_\w+)', '\n'.join(b.OBJECT_CREATION_LISTS)))
    for c in countries:
        assert c['reference'] not in RETIRED_UNITS,c
        assert c['reference'] in production|payloads|upgrades|accessible_buttons or c['reference']=='Euro_SuperweaponArtilleryBarrage',c
    assert not payloads&RETIRED_UNITS,('retired payload',payloads&RETIRED_UNITS)
    mappings=[(o[4].get('ai_parent',o[1]),o[0]) for o in b.UNITS+b.BUILDINGS if o[4].get('ai',True)]+b.SKIRMISH_AI_ALIASES
    parents=[p for p,_ in mappings]
    assert len(parents)==len(set(parents)),'ambiguous AI substitution'
    assert all(target not in RETIRED_UNITS for _,target in mappings)
    assert dict(mappings)['AmericaVehicleTomahawk']=='Euro_Dana'
    assert dict(mappings)['AmericaVehicleSentryDrone']=='Euro_Boxer'
    for o in b.UNITS:
        if o[0] in RETIRED_UNITS:assert o[4]['fields']['Buildable']=='No',o[0]
    assert 'PaladinTank' not in {x for s in b.PROMOTION_MENUS.values() for x in s.values()}
    assert 'Engineering' not in b.SHORTCUTS.values()
    for menu,slots in b.COMMAND_SETS.items():assert all(1<=i<=14 for i in slots),(menu,slots)
    for menu,slots in b.PROMOTION_MENUS.items():assert max(slots)<=(15 if menu.endswith('Rank3') else 4),menu
    for o in b.UNITS+b.BUILDINGS:
        for alternatives in o[4].get('pre',[]):assert all(x in ids for x in alternatives),(o[0],alternatives)
    models={m.upper() for m in re.findall(r'^\s*Model\s*=\s*(EU\w+)',text,re.M)}
    paths={p.stem.upper():p for p in (DATA/'Art/W3D').glob('EU*.w3d')}
    counts={}
    for name in sorted(models):
        assert name in paths,('missing model',name)
        counts[name]=check_model(paths[name])
    assert 'WeaponBonus = PLAYER_UPGRADE DAMAGE 125%' in text
    assert 'ConditionState = USER_1' in text
    assert 'RemoveModule ModuleTag_Laser_One' in text
    # Role contracts catch accidental inheritance of USA all-purpose weapons.
    weapons={w[0]:w[2] for w in b.WEAPONS}
    objects={o[0]:o[4] for o in b.UNITS+b.BUILDINGS}
    assert len(CORE_UNITS)==11
    assert weapons['Euro_TyphoonMissile']['AntiGround']=='No'
    milan=objects['Euro_Milan'];milan_extra='\n'.join(milan['extra'])
    assert weapons['Euro_MilanMissile']['AntiAirborneVehicle']=='No'
    assert weapons['Euro_MilanMissile']['AttackRange']==225
    assert 'Euro_MilanGuidedMissile' not in weapons
    assert milan['weapons']=={'MissileDefenderMissileWeapon':'Euro_MilanMissile'}
    assert 'Weapon = PRIMARY Euro_MilanMissile' in milan_extra
    assert not any('Weapon = SECONDARY' in l for l in milan['extra'])
    assert all('RemoveModule '+tag in milan_extra for tag in ('ModuleTag_08','ModuleTag_09','ModuleTag_CBHunt'))
    assert milan['command']=='Euro_InfantryCommandSet'
    assert not any('Laser' in x for x in b.COMMAND_SETS[milan['command']].values())
    assert not any('Weapon = TERTIARY' in l for l in objects['Euro_Boxer']['extra'])
    assert not any('Euro_GM6' in l for l in b.MODULES['Euro_Marksman'])
    marksman=objects['Euro_Marksman'];marksman_extra='\n'.join(marksman['extra'])
    assert all('RemoveModule '+tag in marksman_extra for tag in ('ModuleTag_08','ModuleTag_09'))
    assert 'AutoAcquireEnemiesWhenIdle = Yes Stealthed' not in marksman_extra
    assert 'AutoAcquireEnemiesWhenIdle = Yes' in marksman_extra
    assert not {'STEALTH_GARRISON','CANNOT_RETALIATE'}&set(marksman['fields']['KindOf'].split())
    assert weapons['Euro_MarksmanRifle']['PrimaryDamage']==40
    assert weapons['Euro_MarksmanRifle']['DelayBetweenShots']==1200
    assert weapons['Euro_MarksmanRifle']['AttackRange']==240
    assert objects['Euro_Rifleman']['cost']==250
    assert weapons['Euro_OerlikonAir']['AttackRange']==weapons['Euro_SkyrangerDummy']['AttackRange']==240
    assert 'Upgrade_EuroLynx' not in upgrades
    assert 'Upgrade_EuroGreenDeal' not in upgrades
    assert weapons['Euro_DanaGun']['PreAttackDelay']==1200
    recovery='\n'.join(b.MODULES['Euro_Ambulance'])
    assert 'DamageCooldown = 8000' in recovery and 'ForbiddenKindOf = AIRCRAFT' in recovery
    assert 'RemoveModule ModuleTag_22' in objects['Euro_Ambulance']['extra']
    assert 'RemoveModule ModuleTag_23' in objects['Euro_Ambulance']['extra']
    assert 'RemoveModule ModuleTag_12' in objects['Euro_ParticleCannonUplink']['extra']
    assert 'OCL = Euro_OCL_ConventionalStrike' in '\n'.join(objects['Euro_ParticleCannonUplink']['extra'])
    assert 'OnlyVisibleToOwningPlayer = No' in '\n'.join(b.OBJECT_CREATION_LISTS)
    assert 'BonusConditionType = SMOKE_SCREEN' in '\n'.join(b.SPECIAL_POWERS)
    report=dict(countries=len(countries),buildable_units=len(core),buildable_buildings=len(production-core),
                model_variants=len(counts),triangles=sum(counts.values()),ai_substitutions=len(parents),
                core=sorted(core),retired_prototypes=sorted(RETIRED_UNITS),status='passed')
    out=ROOT/'build/coalition-roster';out.mkdir(parents=True,exist_ok=True)
    (out/'validation.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
