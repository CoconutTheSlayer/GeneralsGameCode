"""The playable coalition: one clear battlefield role per production button.

Keep retired prototypes available to asset tools and old maps, but exclude them
from production, AI substitutions, promotions and reinforcement payloads.
National contingents can share a role; country coverage is not a unit quota.
"""
from stock_data import copied_record

CORE_UNITS = {
    'Euro_Dozer', 'Euro_NH90',
    'Euro_Rifleman', 'Euro_Milan', 'Euro_Marksman',
    'Euro_Leopard', 'Euro_Boxer', 'Euro_Skyranger', 'Euro_Dana', 'Euro_Ambulance',
    'Euro_Typhoon',
}
RETIRED_UNITS = {
    'Euro_Wiesel', 'Euro_Commando', 'Euro_Rafale', 'Euro_Tiger',
    'Euro_Leclerc', 'Euro_Puls', 'Euro_ReconDrone', 'Euro_Mistral', 'Euro_Tornado', 'Euro_Apache',
    'Euro_Patria', 'Euro_MV4', 'Euro_Reserve', 'Euro_ATGL', 'Euro_Ranger',
    'Euro_EOD', 'Euro_Rescuer', 'Euro_Paratrooper', 'Euro_Puma',
}


def apply(g):
    units = {o[0]: o for o in g['UNITS']}
    def describe(name, description):
        for i, o in enumerate(g['UNITS']):
            if o[0] == name:
                g['UNITS'][i] = (*o[:3], description, o[4])
                break

    for name in RETIRED_UNITS:
        units[name][4]['ai'] = False
        units[name][4].setdefault('fields', {})['Buildable'] = 'No'
    units['Euro_Dana'][4].update(ai=True, ai_parent='AmericaVehicleTomahawk')
    # USA scripts still request these source templates. Redirect them instead of
    # allowing either a retired prototype or an original USA vehicle to leak in.
    g['SKIRMISH_AI_ALIASES'] = [
        ('AmericaTankPaladin', 'Euro_Leopard'),
        ('AmericaVehicleSentryDrone', 'Euro_Boxer'),
        ('AmericaJetAurora', 'Euro_Rafale'),
    ]
    menus = g['COMMAND_SETS']
    for slots in menus.values():
        for slot, entry in list(slots.items()):
            if entry in RETIRED_UNITS or entry in {
                'Command_UpgradeAmericaSentryDroneGun', 'Euro_Command_Engineering',
            }:
                del slots[slot]
    menus['Euro_WarFactoryCommandSet'] = {
        1: 'Euro_Leopard', 2: 'Euro_Boxer', 3: 'Euro_Wiesel',
        4: 'Euro_Skyranger', 5: 'Euro_Dana', 6: 'Euro_Ambulance',
        9: 'Command_UpgradeAmericaTOWMissile', 10: 'Euro_Command_UpgradeAhead',
        13: 'Command_SetRallyPoint', 14: 'Command_Sell',
    }
    # The carrier supplies short-range scouting without another chassis or toggle.
    g['MODULES'].setdefault('Euro_Boxer', []).extend([
        'Behavior = StealthDetectorUpdate ModuleTag_Euro_CarrierRecon',
        '  DetectionRange = 140', '  DetectionRate = 1000', '  CanDetectWhileContained = No', 'End',
    ])
    describe('Euro_Boxer', 'Lithuania: five-seat infantry carrier with an autocannon and optional anti-tank missiles. '
             'Estonian sensors reveal nearby hidden enemies; Irish reconnaissance crews.')
    describe('Euro_Tiger', 'Spain: attack helicopter. Hunts infantry and light vehicles; rocket pods attack groups. Vulnerable to anti-aircraft fire.')
    describe('Euro_Dozer', 'Germany: builds and repairs the base and clears mines. Croatian and Maltese ordnance crews support the engineers.')
    describe('Euro_Milan', 'France: missile infantry against vehicles and aircraft. Laser designation concentrates fire on armour. '
             'Bulgarian and Cypriot crews serve alongside the French contingent.')
    describe('Euro_Ambulance', 'Slovenia: Austrian Pandur-derived Valuk ambulance. Heals nearby infantry and vehicles and removes toxins. '
             'Romanian and Icelandic rescue crews.')
    describe('Euro_Dana', 'Czechia: wheeled area artillery against infantry and bases. Needs protection at close range; Dutch fire-control crews.')
    # Reinforcements add familiar units to the army, not a second hidden roster.
    ocl = g['OBJECT_CREATION_LISTS']
    text = '\n'.join(ocl)
    for old, new in [
        ('Payload = Euro_Patria 2', 'Payload = Euro_Boxer 2'),
        ('Payload = Euro_Reserve 4', 'Payload = Euro_Rifleman 6'),
        ('Payload = Euro_ATGL 4', 'Payload = Euro_Milan 4'),
        ('    Payload = Euro_Ranger 2\n', ''),
        ('Payload = Euro_Paratrooper', 'Payload = Euro_Rifleman'),
    ]:
        text = text.replace(old, new)
    # Remove complete top-level OCL records, never fragments of nested modules.
    import re
    text = re.sub(r'^ObjectCreationList Euro_OCL_(?:Engineering|Repair[123])\n.*?^End\n?', '', text, flags=re.M|re.S)
    ocl[:] = text.splitlines()
    for rank in range(1, 4):
        ocl += copied_record('ObjectCreationList', f'SUPERWEAPON_RepairVehicles{rank}', f'Euro_OCL_Repair{rank}')
    cc = g['MODULES_COMMAND_CENTRE']
    start = cc.index('Behavior = OCLSpecialPower ModuleTag_Euro_Engineering')
    del cc[start:cc.index('End', start) + 1]
    g['POWERS'].update(
        Coalition=('Coalition Reinforcements', 'Latvian-led airlift brings two Vilkas carriers, six Legionnaires and four MILAN teams. Austrian reservists reinforce the same infantry units.'),
        Paradrop=('Portuguese Airborne', 'Portuguese airborne troops arrive aboard Luxembourg-crewed A400Ms. Uses the familiar Legionnaire equipment and controls.'),
        EmergencyRepair=('Field Rescue', 'Romanian and Icelandic rescue services repair allied vehicles in the target area immediately.'),
    )
    for key in g['PROMOTIONS']:
        for prefix in ('Paradrop', 'EmergencyRepair'):
            if key.startswith(prefix):
                title, desc = g['POWERS'][prefix]
                g['PROMOTIONS'][key] = (title + ' ' + key[-1], desc)
    # No promotion should unlock a hidden unit or advertise the retired robot team.
    g['PROMOTION_MENUS']['Euro_SCIENCE_CommandSetRank1'] = {1: 'SpyDrone', 2: 'StealthFighter'}
    for key in ('PaladinTank',):
        g['PROMOTIONS'].pop(key, None)
    g['SCIENCES'].pop('EuroEngineering', None)
    g['NEW_POWERS'].pop('Engineering', None)
    g['POWERS'].pop('Engineering', None)
    g['SPECIAL_POWERS'][:] = re.sub(
        r'^SpecialPower Euro_SuperweaponEngineering\n.*?^End\n?', '',
        '\n'.join(g['SPECIAL_POWERS']), flags=re.M|re.S).splitlines()
    g['SHORTCUTS'] = {i: p for i, p in g['SHORTCUTS'].items() if p != 'Engineering'}
    g['FACTION'].update(
        strategy='A European coalition built around durable tanks, infantry carriers and wheeled artillery. '
                 'Keep the army moving with field ambulances; use specialist aircraft and allied support to break resistance.',
        features='15 core units, mobile combined arms, 31 countries contributing crews and equipment',
    )

    from battlegroup_roster import apply as redesign
    redesign(g)
