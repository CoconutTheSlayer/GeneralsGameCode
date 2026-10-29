"""Ukraine-only finite drones, decoys and resource-costed local sapper mines."""
def support_logic(stock, post=False):
    out=[]
    def add(text):out.extend(text.strip().splitlines()+[''])
    for name,pre in [('Decoy','SCIENCE_AMERICA'),('DroneRaid1','SCIENCE_AMERICA SCIENCE_Rank3'),('DroneRaid2','SCIENCE_UkraineDroneRaid1 SCIENCE_Rank8')]:
        add(f'''Science SCIENCE_Ukraine{name}
  PrerequisiteSciences = {pre}
  SciencePurchasePointCost = 1
  IsGrantable = Yes
  DisplayName = SCIENCE:Ukraine{name}
  Description = CONTROLBAR:Ukraine{'Decoy' if name=='Decoy' else 'DroneRaid'}Description
End''')
    powers=[('SensorSweep','SPECIAL_RADAR_VAN_SCAN',45000,False,None,210),('Recon','SPECIAL_SPY_SATELLITE',60000,False,None,180),('DroneRaid','SPECIAL_A10_THUNDERBOLT_STRIKE',240000,False,'SCIENCE_UkraineDroneRaid1',65),('Decoy','SPECIAL_AMBUSH',120000,False,'SCIENCE_UkraineDecoy',45),('LongRangeRaid','SPECIAL_SCUD_STORM',300000,True,None,100),('LayMine','SPECIAL_CLUSTER_MINES',10000,False,None,12),('Demolition','SPECIAL_TIMED_CHARGES',10000,False,None,0)]
    for name,enum,reload,public,science,radius in powers:
        add(f'''SpecialPower Ukraine_{name}
  Enum = {enum}
  ReloadTime = {reload}
  PublicTimer = {'Yes' if public else 'No'}
  SharedSyncedTimer = {'No' if name in ('LayMine','Demolition','LongRangeRaid','SensorSweep') else 'Yes'}
  RadiusCursorRadius = {radius}
  ViewObjectDuration = {20000 if name=='Recon' else 0}
  ViewObjectRange = {180 if name=='Recon' else 0}
  ShortcutPower = {'No' if name in ('LayMine','Demolition','SensorSweep') else 'Yes'}
  {'RequiredScience = '+science if science else ''}
End''')
    loco='\n'.join(stock.record('Locomotor','A10ThunderboltLocomotor'))
    import re
    for key,val in [('Speed',135),('SpeedDamaged',115),('PreferredHeight',100)]:
        loco=re.sub(r'(?m)^(\s*'+key+r'\s*=).*$',r'\g<1> '+str(val),loco)
    add('Locomotor Ukraine_StrikeCarrierLocomotor\n'+loco+'\nEnd')
    # DeliverPayload supplies finite flights. Both visible carriers and drones
    # are ordinary vulnerable airborne targets, and leave no permanent units.
    add('''ChildObject Ukraine_StrikeCarrier AmericaJetA10Thunderbolt
  Side = Ukraine
  Buildable = No
  IsTrainable = No
  KindOf = PRELOAD CAN_CAST_REFLECTIONS VEHICLE AIRCRAFT DRONE SCORE IGNORED_IN_GUI
  RemoveModule ModuleTag_01
  AddModule
    Draw = W3DModelDraw ModuleTag_Ukraine_StrikeCarrierDraw
      OkToChangeModelColor = Yes
      ExtraPublicBone = MUZZLE01
      ExtraPublicBone = MUZZLE02
      DefaultConditionState
        Model = UATB2
        Animation = UATB2.UATB2
        AnimationMode = LOOP
      End
    End
  End
  ReplaceModule ModuleTag_02
    Body = ActiveBody ModuleTag_Ukraine_StrikeCarrierHealth
      MaxHealth = 240
      InitialHealth = 240
    End
  End
  RemoveModule ModuleTag_03
  RemoveModule ModuleTag_06
  RemoveModule ModuleTag_Armor01
  RemoveModule ModuleTag_10
  AddModule
    Behavior = SlowDeathBehavior ModuleTag_Ukraine_StrikeCarrierDeath
      DeathTypes = ALL
      DestructionDelay = 0
      FX = FINAL FX_GenericMissileDeath
      OCL = FINAL Ukraine_TB2_Wreck
    End
  End
  WeaponSet
    Conditions = None
    Weapon = PRIMARY None
  End
  RemoveModule ModuleTag_07
  AddModule
    Behavior = DeliverPayloadAIUpdate ModuleTag_Ukraine_CarrierAI
    End
  End
  Locomotor = SET_NORMAL Ukraine_StrikeCarrierLocomotor
  SoundAmbient = NoSound
End''')
    add('''ChildObject Ukraine_RaidDrone Ukraine_AttackDrone
  ReplaceModule ModuleTag_Ukraine_DroneHealth
    Body = ActiveBody ModuleTag_Ukraine_RaidDroneHealth
      MaxHealth = 25
      InitialHealth = 25
    End
  End
End
ChildWeapon Ukraine_RaidDroneDamage A10ThunderboltMissileWeapon
  PrimaryDamage = 160
  PrimaryDamageRadius = 26
  SecondaryDamage = 30
  SecondaryDamageRadius = 42
  RadiusDamageAffects = ENEMIES NEUTRALS ALLIES NOT_SIMILAR
  ProjectileDetonationFX = FX_TomahawkMissileDetonation
End''')
    for name,count in [('Raid1',1),('Raid2',2),('RaidSuper',4)]:
        add(f'''ObjectCreationList Ukraine_{name}
  DeliverPayload
    Transport = Ukraine_StrikeCarrier
    FormationSize = {count}
    FormationSpacing = 50
    StartAtPreferredHeight = Yes
    StartAtMaxSpeed = Yes
    MaxAttempts = 1
    DropDelay = 350
    DeliveryDistance = 250
    WeaponErrorRadius = {35 if count<4 else 65}
    WeaponConvergenceFactor = 0.5
    VisibleItemsDroppedPerInterval = 1
    VisibleDropBoneBaseName = MUZZLE
    VisibleSubObjectBaseName = NONE
    VisibleNumBones = 6
    VisiblePayloadTemplateName = Ukraine_RaidDrone
    VisiblePayloadWeaponTemplate = Ukraine_RaidDroneDamage
    InheritTransportVelocity = No
    ExitPitchRate = 30
    DeliveryDecalRadius = {65 if count<4 else 100}
    DeliveryDecal
      Texture = SCCA10Strike_USA
      Style = SHADOW_ALPHA_DECAL
      OpacityMin = 25%
      OpacityMax = 50%
      OpacityThrobTime = 500
      Color = R:255 G:180 B:50 A:255
      OnlyVisibleToOwningPlayer = No
    End
  End
End''')
    # Decoys use the owned BTR shell but have no weapon, cargo or utility.
    add('''ChildObject Ukraine_DecoyBTR Ukraine_BTR4
  Buildable = No
  BuildCost = 0
  CommandSet = Ukraine_VehicleCommandSet
  IsTrainable = No
  KindOf = PRELOAD SELECTABLE VEHICLE SCORE CAN_CAST_REFLECTIONS
  ExperienceValue = 0 0 0 0
  RemoveModule ModuleTag_Ukraine_Contain
  ReplaceModule ModuleTag_Ukraine_ModuleTag_02
    Body = ActiveBody ModuleTag_Ukraine_DecoyHealth
      MaxHealth = 45
      InitialHealth = 45
    End
  End
  WeaponSet
    Conditions = None
    Weapon = PRIMARY None
    Weapon = SECONDARY None
  End
  WeaponSet
    Conditions = PLAYER_UPGRADE
    Weapon = PRIMARY None
    Weapon = SECONDARY None
  End
  AddModule
    Behavior = LifetimeUpdate ModuleTag_Ukraine_DecoyLifetime
      MinLifetime = 35000
      MaxLifetime = 35000
    End
  End
End
ObjectCreationList Ukraine_CreateDecoys
  CreateObject
    ObjectNames = Ukraine_DecoyBTR
    Count = 2
    SpreadFormation = Yes
    MinDistanceAFormation = 15
    MinDistanceBFormation = 25
    MaxDistanceFormation = 65
  End
End
ChildWeapon Ukraine_MineDamage StructureMineWeapon
  PrimaryDamage = 160
  PrimaryDamageRadius = 16
End
ChildObject Ukraine_SapperMine ChinaStandardMine
  Side = Ukraine
  Buildable = No
  RemoveModule ModuleTag_01
  AddModule
    Draw = W3DModelDraw ModuleTag_Ukraine_MineDraw
      DefaultConditionState
        Model = UAMINE
      End
    End
  End
  ReplaceModule ModuleTag_02
    Body = ActiveBody ModuleTag_Ukraine_MineHealth
      MaxHealth = 50
      InitialHealth = 50
    End
  End
  ReplaceModule ModuleTag_03
    Behavior = StealthUpdate ModuleTag_Ukraine_MineStealth
      StealthDelay = 0
      StealthForbiddenConditions = NONE
      FriendlyOpacityMin = 50%
      FriendlyOpacityMax = 50%
      InnateStealth = Yes
      OrderIdleEnemiesToAttackMeUponReveal = No
    End
  End
  ReplaceModule ModuleTag_04
    Behavior = MinefieldBehavior ModuleTag_Ukraine_Minefield
      DetonationWeapon = Ukraine_MineDamage
      DetonatedBy = ENEMIES NEUTRAL
      NumVirtualMines = 1
      Regenerates = No
      StopsRegenAfterCreatorDies = No
      RepeatDetonateMoveThresh = 5
    End
  End
  RemoveModule ModuleTag_05
  GeometryMajorRadius = 12
End
; OCLUpdate resolves its OCL pointer while parsing: this must precede the helper.
ObjectCreationList Ukraine_CreateMine
  CreateObject
    ObjectNames = Ukraine_SapperMine
    Count = 1
    Disposition = LIKE_EXISTING
  End
End
Object Ukraine_ArmingMine
  Side = Ukraine
  KindOf = IMMOBILE IGNORED_IN_GUI NO_COLLIDE
  Body = ActiveBody ModuleTag_Ukraine_ArmingMineBody
    MaxHealth = 50
    InitialHealth = 50
  End
  Draw = W3DModelDraw ModuleTag_Ukraine_ArmingMineDraw
    DefaultConditionState
      Model = UAMINE
    End
  End
  Behavior = LifetimeUpdate ModuleTag_Ukraine_ArmingMineDelay
    MinLifetime = 3100
    MaxLifetime = 3100
  End
  Behavior = OCLUpdate ModuleTag_Ukraine_ArmedMine
    OCL = Ukraine_CreateMine
    MinDelay = 3000
    MaxDelay = 3000
  End
  Behavior = DestroyDie ModuleTag_Ukraine_ArmingMineDestroy
  End
  Geometry = SPHERE
  GeometryMajorRadius = 2
  GeometryIsSmall = Yes
End
ObjectCreationList Ukraine_CreateArmingMine
  CreateObject
    ObjectNames = Ukraine_ArmingMine
    Count = 1
    Disposition = LIKE_EXISTING
  End
End''')
    add("""Object Ukraine_SensorPulse
  Side = Ukraine
  KindOf = NO_COLLIDE IMMOBILE IGNORED_IN_GUI
  VisionRange = 210
  ShroudClearingRange = 210
  Body = ActiveBody ModuleTag_Ukraine_SensorBody
    MaxHealth = 1
    InitialHealth = 1
  End
  Behavior = StealthDetectorUpdate ModuleTag_Ukraine_SensorDetection
    DetectionRange = 210
    DetectionRate = 250
  End
  Behavior = LifetimeUpdate ModuleTag_Ukraine_SensorDuration
    MinLifetime = 8000
    MaxLifetime = 8000
  End
  Behavior = DestroyDie ModuleTag_Ukraine_SensorDestroy
  End
End
ObjectCreationList Ukraine_CreateSensorPulse
  CreateObject
    ObjectNames = Ukraine_SensorPulse
    Count = 1
  End
End""")
    text='\n'.join(out)
    decoy=re.search(r'^ChildObject Ukraine_DecoyBTR .*?^End\n',text,re.M|re.S).group(0)
    return (decoy if post else text.replace(decoy,'')).splitlines()+['']


def support_client():
    return '''CommandButton Ukraine_SensorSweep
  Command = SPECIAL_POWER
  SpecialPower = Ukraine_SensorSweep
  TextLabel = CONTROLBAR:UkraineSensorSweep
  DescriptLabel = CONTROLBAR:UkraineSensorSweepDescription
  ButtonImage = Ukraine_TB2
  ButtonBorderType = ACTION
End
ChildCommandButton Ukraine_Demolition Command_ColonelBurtonTimedDemoCharge
  SpecialPower = Ukraine_Demolition
  TextLabel = CONTROLBAR:UkraineDemolition
  DescriptLabel = CONTROLBAR:UkraineDemolitionDescription
  ButtonImage = Ukraine_Commando
End
CommandButton Ukraine_LayMine
  Command = SPECIAL_POWER
  SpecialPower = Ukraine_LayMine
  TextLabel = CONTROLBAR:UkraineLayMine
  DescriptLabel = CONTROLBAR:UkraineLayMineDescription
  ButtonImage = Ukraine_Commando
  ButtonBorderType = ACTION
End
'''.splitlines()
