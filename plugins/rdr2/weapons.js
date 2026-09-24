// ----- Weapons and ammunition -----

// What each weapon field actually DOES, keyed by its leaf name. A "?" appears
// only for fields listed here — a hover that just says "constrained to N
// values" wastes the reader's time, so a field we cannot honestly explain gets
// no hover at all.
const WEAPON_FIELD_HELP={
  // Damage modes (one per ammo type)
  Damage:"Base damage this weapon does with this ammo type, before every modifier below.",
  DamageType:"What kind of damage the hit registers as: BULLET, ARROW, EXPLOSIVE, MELEE. Drives reactions, dismemberment and immunities, not the number.",
  Penetration:"How readily the shot passes through a body or cover to keep travelling.",
  ImpulseMultiplier:"Scales the physical shove a hit puts on the target's ragdoll. Visual knockback, not damage.",
  AmmoInfo:"Which ammo record this damage mode belongs to. This is the link that makes a mode ammo-specific.",
  MeleeExecutionDismemberment:"Whether a melee execution with this mode can sever limbs.",
  DamageFallOffInfo:"Named distance/damage CURVE this mode uses. Edit the referenced falloff record's points, not a number here.",
  AccuracyInfo:"Named accuracy record this mode uses — the spread cone, not a single number.",
  // Headshots and hit regions
  HeadShotDamageModifierPlayer:"Multiplier applied to YOUR headshots.",
  HeadShotDamageModifierAI:"Multiplier applied to headshots the AI lands.",
  MinHeadShotDistancePlayer:"Below this distance your headshot multiplier is at its floor; it scales up to the Max distance.",
  MaxHeadShotDistancePlayer:"Distance at which your headshot multiplier reaches full strength.",
  MinHeadShotDistanceAI:"Same distance ramp, for headshots the AI lands on you.",
  MaxHeadShotDistanceAI:"Distance at which the AI's headshot multiplier reaches full strength.",
  MaxHeadShotDistanceToPlayerWithScope:"Headshot distance ceiling when the shooter is scoped.",
  NonRegionLimbDamageModifier:"Multiplier for hits on limbs with no dedicated damage region.",
  LightlyArmouredDamageModifier:"Multiplier against lightly armoured targets.",
  CriticalHitChanceModifier:"Scales the chance of a critical hit.",
  VehicleDamageModifier:"Multiplier when the hit lands on a vehicle rather than a ped.",
  PlayerDamagedByAIModifier:"Scales damage the AI does TO YOU with this weapon.",
  PlayerDamagedByPlayerModifier:"Scales damage you do to another player. Story Mode has no other player.",
  AIDamagedByPlayerModifier:"Scales damage YOU do to AI with this weapon. The main difficulty dial.",
  DismembermentPercent:"How likely a qualifying hit severs the bone region.",
  DismembermentIncrement:"How much each hit adds toward the dismemberment threshold.",
  // Rate of fire and reloading
  TimeBetweenShotsMin:"Seconds between shots at the fastest. Lower is faster — this is the fire-rate dial.",
  TimeBetweenShotsMax:"Seconds between shots at the slowest, for weapons whose cadence varies.",
  ReloadTime:"Reload duration in seconds.",
  VehicleReloadTime:"Reload duration while mounted or in a vehicle.",
  AnimReloadRate:"Playback rate of the reload animation. Higher is faster; this is what actually shortens the reload you see.",
  SpinUpTime:"Seconds of spin-up before the weapon can fire.",
  SpinTime:"Seconds the mechanism keeps spinning while held.",
  SpinDownTime:"Seconds to spin back down after firing stops.",
  AlternateWaitTime:"Delay before the alternate (secondary) fire mode is available again.",
  FireType:"How the trigger behaves: single shot, delayed hit, instant hit, projectile.",
  BatchSpread:"Spread across the pellets of one shot. Shotgun choke.",
  // Ranges
  WeaponRange:"Maximum distance this weapon is effective at.",
  WeaponRangeInVehicle:"Effective range while mounted or in a vehicle.",
  MaxRange:"Hard distance cap for this record's projectile or effect.",
  DesiredRange:"Range the AI tries to hold when fighting with this weapon.",
  LockOnRange:"Distance at which soft/auto aim will acquire a target.",
  LockOnRangeInVehicle:"Auto-aim acquisition distance while mounted or in a vehicle.",
  IdleLockOnRangeModifier:"Scales lock-on range while you are not actively aiming.",
  SoftLockDurationOverride:"How long soft lock holds a target before releasing it.",
  ProjectileRangeMin:"Shortest distance the projectile is thrown or launched.",
  ProjectileRangeMax:"Longest distance the projectile is thrown or launched.",
  AiSoundRange:"How far away NPCs can HEAR this weapon fire. A stealth dial.",
  AiPotentialBlastEventRange:"Radius in which NPCs react to this weapon as a potential blast threat.",
  MeleeWeaponRangeMin:"Closest distance a melee swing connects.",
  MeleeWeaponRangeMax:"Furthest distance a melee swing connects.",
  MeleeWeaponRangeMaxRun:"Melee reach while running.",
  MeleeWeaponRangeMinToRun:"Distance beyond which the AI runs in rather than swinging.",
  Speed:"Projectile muzzle velocity. Low values are what make shots look laggy at distance.",
  // Force / physics
  Force:"Base physical force a hit imparts.",
  ForceHitPed:"Force applied when the hit lands on a person or animal.",
  ForceHitVehicle:"Force applied when the hit lands on a vehicle.",
  ForceMaxStrengthMult:"Ceiling multiplier on applied force.",
  ForceFalloffRangeStart:"Distance at which applied force begins to drop off.",
  ForceFalloffRangeEnd:"Distance at which applied force reaches its minimum.",
  ForceFalloffMin:"Floor the applied force falls off to.",
  ProjectileForce:"Force carried by the projectile itself on impact.",
  FragImpulse:"Impulse applied to breakable (fragment) objects hit.",
  VerticalLaunchAdjustment:"Upward bias added when the projectile is launched.",
  DropForwardVelocity:"Forward speed given to the weapon when it is dropped.",
  // Aim, sway, recoil, camera
  BulletBendingNearRadius:"Close-range auto-aim assist radius: how far a shot is silently bent toward the target.",
  BulletBendingFarRadius:"Long-range auto-aim assist radius.",
  BulletBendingZoomedRadius:"Auto-aim assist radius while zoomed.",
  FirstPersonBulletBendingNearRadius:"Close-range auto-aim assist radius in first person.",
  FirstPersonBulletBendingFarRadius:"Long-range auto-aim assist radius in first person.",
  FirstPersonBulletBendingZoomedRadius:"Auto-aim assist radius while zoomed in first person.",
  BulletDirectionOffsetInDegrees:"Fixed angular offset applied to the shot direction.",
  RecoilShakeAmplitude:"How hard the camera kicks on firing.",
  RecoilShakeAmplitudeFirstPerson:"Camera kick on firing in first person.",
  MinTimeBetweenRecoilShakes:"Floor on how often the recoil shake can retrigger.",
  ExplosionShakeAmplitude:"Camera shake strength from this weapon's explosion.",
  ReticleSwaySettleDuration:"Seconds of holding aim before the reticle sway settles.",
  ReticleSwayPostSettleRestartTime:"How long a settled reticle stays settled before sway restarts.",
  ReticleSwayAmplitudeModifierNear:"Sway strength at close range.",
  ReticleSwayAmplitudeModifierFar:"Sway strength at long range.",
  ReticleSwayRangeNear:"Distance treated as 'near' for the sway modifiers.",
  ReticleSwayRangeFar:"Distance treated as 'far' for the sway modifiers.",
  ReticuleStyleHash:"Which reticle graphic this weapon uses.",
  CameraFov:"Field of view while aiming this weapon. Lower is more zoomed in.",
  FirstPersonAimFovMin:"Most zoomed-in first-person aim FOV.",
  FirstPersonAimFovMax:"Least zoomed-in first-person aim FOV.",
  ZoomFactorForAccurateMode:"Extra zoom applied in the game's steadied/accurate aim mode.",
  // Classification and misc
  WeaponType:"The weapon's category. Drives holstering, wheel slot and animation set.",
  SwapWeaponType:"Category used when swapping this weapon in and out.",
  Score:"Ranking value the AI and the shop UI use to compare weapons.",
  IsSpecialWeapon:"Marks the weapon as special-cased by script.",
  IsOutlawWeapon:"Marks the weapon as an outlaw/unique item.",
  AttachBone:"Bone the weapon model attaches to when holstered or held.",
  BoneTag:"Which body region this damage/force entry applies to.",
  EffectGroup:"Impact effect family: decides sparks, dust and surface reactions.",
  DamageTime:"Seconds of damage-over-time applied by a hit.",
  DamageTimeInVehicle:"Damage-over-time duration when the target is in a vehicle.",
  DamageTimeInVehicleHeadShot:"Damage-over-time duration for a headshot on a target in a vehicle.",
  Distance:"Distance for this point on the falloff curve.",
  AccuracyFalloffMin:"Lowest accuracy multiplier after distance falloff has finished.",
  AccuracyFalloffRangeStart:"Distance where accuracy starts to fall from its full value.",
  AccuracyFalloffRangeEnd:"Distance where accuracy reaches its falloff minimum.",
  AccuracySpread:"Base angular spread of shots that use this accuracy record.",
  AccurateModeAccuracyModifier:"Accuracy multiplier while the weapon is in accurate or steadied aim mode.",
  HipFireAccuracySpread:"Angular spread when firing without aiming down the weapon.",
  RecoilAccuracyMin:"Best accuracy value allowed while recoil is active.",
  RecoilAccuracyMax:"Worst accuracy value allowed while recoil is active.",
  RecoilAccuracyToAllowHeadShotAI:"Recoil-accuracy threshold below which AI headshots are allowed.",
  RecoilAccuracyToAllowHeadShotPlayer:"Recoil-accuracy threshold below which player headshots are allowed.",
  RecoilErrorTime:"Time that recoil error remains before recovery takes over.",
  RecoilPenalty:"Accuracy penalty added by each shot's recoil.",
  RecoilRecoveryRate:"Rate at which recoil accuracy returns toward its resting value.",
  RunAndGunAccuracyMaxModifier:"Maximum accuracy multiplier while moving and firing.",
  RunAndGunAccuracyMinOverride:"Minimum run-and-gun accuracy. A negative value leaves the normal minimum in use.",
  RunAndGunAccuracyModifier:"General accuracy multiplier while moving and firing.",
  PairedWithPistolAccuracyModifier:"Accuracy multiplier when this weapon is dual-wielded with a pistol.",
  PairedWithRevolverAccuracyModifier:"Accuracy multiplier when this weapon is dual-wielded with a revolver.",
  PairedWithShotgunAccuracyModifier:"Accuracy multiplier when this weapon is dual-wielded with a sawn-off shotgun.",
  AimProbeLengthMin:"Shortest obstruction probe used to keep first-person weapon aiming clear of nearby geometry.",
  AimProbeLengthMax:"Longest obstruction probe used to keep first-person weapon aiming clear of nearby geometry.",
  AimProbeRadiusOverrideFPSIdle:"First-person aim obstruction-probe radius while idle.",
  AimProbeRadiusOverrideFPSIdleStealth:"First-person aim obstruction-probe radius while idle in stealth.",
  AimProbeRadiusOverrideFPSLT:"First-person aim obstruction-probe radius for the left-trigger aim state.",
  AimProbeRadiusOverrideFPSRNG:"First-person aim obstruction-probe radius for ranged aiming.",
  AimProbeRadiusOverrideFPSScope:"First-person aim obstruction-probe radius while using a scope.",
  IkRecoilDisplacement:"Distance the weapon-hand IK rig moves for recoil.",
  IkRecoilDisplacementScope:"Weapon-hand IK recoil displacement while scoped.",
  IkRecoilDisplacementScaleBackward:"Backward scale applied to the IK recoil movement.",
  IkRecoilDisplacementScaleVertical:"Vertical scale applied to the IK recoil movement.",
  UpperArmTranslationBias:"Bias applied to upper-arm IK translation while holding this weapon.",
  FirstPersonDofSubjectMagnificationPowerFactorNear:"Near-subject magnification used by first-person depth of field.",
  FirstPersonDofMaxNearInFocusDistance:"Farthest near distance that remains in focus in first person.",
  FirstPersonDofMaxNearInFocusDistanceBlendLevel:"Blend amount used at the first-person near-focus distance limit.",
  FirstPersonReticuleStyleHash:"Reticle graphic used in first person.",
  BulletsInBatch:"Number of projectiles emitted by one shot. This is normally the pellet count.",
  BulletsPerAnimLoop:"Number of rounds handled during one reload-animation loop.",
  MaxDrawingMBR:"Maximum draw value used by bows and other drawn weapons. A negative value disables the override.",
  LaunchPitchCorrectionMax:"Maximum pitch correction applied when launching a thrown or arcing projectile.",
  SkinPenetration:"How deeply the projectile can pass into a target before it stops.",
  BleedOutTimeMultiplier:"Multiplier on how long a qualifying wounded target takes to bleed out.",
  HeadOnCloseRangePedModifier:"Damage multiplier for a close-range hit on a ped facing the attack.",
  KnockdownCount:"NaturalMotion hit count used before the weapon forces a knockdown reaction.",
  KillshotImpulseScale:"Physical impulse multiplier for a killing shot's body reaction.",
  NumDamageRegionsThatCanBeBypassed:"Number of protected damage regions that this ammunition can bypass.",
  NumPedImpacts:"Maximum number of ped impacts the projectile can register while penetrating targets.",
  ExpandPedCapsuleRadius:"Extra target-capsule radius used when testing this weapon's hits.",
  TimeLeftBetweenShotsWhereShouldFireIsCached:"Remaining shot delay within which the trigger decision stays cached.",
  SectionedReloadInfo:"Reload sequence used for weapons that load rounds in separate animation sections.",
  SectionedReloadInfoDual:"Sectioned reload sequence used while dual-wielding.",
  CockingInfo:"Cocking animation and timing preset used between shots.",
  IkRecoilInfo:"Hand-and-weapon recoil animation preset.",
  AimingInfo:"Aiming behavior preset used by this weapon.",
  DegradationInfo:"Condition-loss preset that controls dirt, rust, wear and performance decay.",
  FamiliarityInfo:"Weapon-familiarity preset used for skill growth and handling changes.",
  RumbleInfo:"Controller-rumble preset used when the weapon fires or strikes.",
  Audio:"Weapon audio preset. It selects the report and handling sound family; it does not change damage.",
  Slot:"Inventory and weapon-wheel slot identifier for this weapon.",
  Group:"Weapon group used for shared behavior, inventory grouping and animation selection.",
  Caliber:"Caliber identifier used to associate the weapon with matching ballistic and effect data.",
  AmmoFlags:"Behavior flags for this ammunition, such as penetration, incendiary or projectile handling rules.",
  WeaponFlags:"Behavior flags that enable weapon capabilities and restrictions. Known names are safe to interpret; hexadecimal tokens are unresolved flags and should be left alone.",
  DefaultAIAttackMode:"Attack mode AI uses first with this weapon, such as Shoot or Melee.",
  AIAttackModes:"Attack modes AI is allowed to use with this weapon.",
  FiringPatternAliases:"AI firing-pattern family used to choose burst length and pauses.",
  FiringDistractionTime:"Time after firing during which the shot continues to affect AI distraction behavior.",
  DistractionDecayModifier:"Multiplier on how fast the weapon's distraction effect fades.",
  MotivationImpactMultiplier:"Multiplier on the morale or motivation effect caused by a hit.",
  DeadeyeDrainModifier:"Multiplier on Dead Eye drain while this weapon is active.",
  MaxDeadeyeTaggedTargets:"Maximum targets or hit points that Dead Eye can tag for this weapon. A negative value uses the normal limit.",
  PickupHash:"World pickup definition created when this weapon is dropped in Story Mode.",
  MPPickupHash:"Multiplayer pickup definition for this weapon.",
  UnlockWeaponHash:"Weapon identifier used by unlock and ownership checks.",
  RewardHash:"Reward identifier granted when this ammo or weapon pickup is collected.",
  StatName:"Stat-system identifier used for weapon familiarity and recorded use.",
  SkillStatName:"Stat-system identifier used for this weapon's skill progression.",
  PermanentDegradationHumanName:"Text label used for the permanently worn version of the weapon.",
  AnimationLookupHash:"Animation lookup set used to resolve the weapon's actions.",
  PrimaryHandBlackboardString:"Animation blackboard slot assigned to the primary hand.",
  SecondaryHandBlackboardString:"Animation blackboard slot assigned to the secondary hand.",
  SupportingHandBlackboardString:"Animation blackboard slot assigned to the supporting hand.",
  HolsterAttachPoint:"Body attachment point used by the normal holster position.",
  AlternateHolsterAttachPoint:"Body attachment point used by the alternate holster position.",
  MutuallyExclusiveHolsterAttachPoint:"Attachment point that cannot be occupied at the same time as the normal holster.",
  MutuallyExclusiveAlternateHolsterAttachPoint:"Attachment point that cannot be occupied at the same time as the alternate holster.",
  ArmpitAttachPoint:"Attachment point used when the weapon is tucked under the arm.",
  TemporaryAttachPoint:"Temporary body attachment point used during transitions or scripted handling.",
  ShortArmHolsterDOF:"Depth-of-field override used during a short-arm holster animation.",
  TorsoIKAngleLimit:"Maximum torso IK turn angle while aiming this weapon. A negative value uses the normal limit.",
  AimingBreathingAdditiveWeight:"Breathing-animation weight while aiming.",
  FiringBreathingAdditiveWeight:"Breathing-animation weight while firing.",
  StealthAimingBreathingAdditiveWeight:"Breathing-animation weight while aiming in stealth.",
  StealthFiringBreathingAdditiveWeight:"Breathing-animation weight while firing in stealth.",
  AimingLeanAdditiveWeight:"Body-lean animation weight while aiming.",
  FiringLeanAdditiveWeight:"Body-lean animation weight while firing.",
  StealthAimingLeanAdditiveWeight:"Body-lean animation weight while aiming in stealth.",
  StealthFiringLeanAdditiveWeight:"Body-lean animation weight while firing in stealth.",
  FireProbeBone:"Skeleton bone used as the origin for the weapon's fire or muzzle probe.",
  LightRadiusMult:"Multiplier on the radius of light emitted by this weapon.",
  LightRadiusMultLerpTime:"Seconds used to blend changes to the weapon-light radius.",
  VehicleAttackAngle:"Maximum attack angle allowed while using the weapon from a vehicle or mount.",
  AirborneAircraftLockOnMultiplier:"Lock-on range multiplier against aircraft that are in the air.",
  VehicleWeaponHash:"Weapon definition used by the vehicle-mounted weapon entry.",
  CoverTypeHash:"Cover-handling category used to choose compatible cover animations.",
  CameraDictionaryHash:"Camera dictionary that contains this weapon's camera presets.",
  DefaultCameraHash:"Normal third-person aiming camera preset.",
  InteractionLockonCameraHash:"Camera preset used when locked onto an interaction target.",
  HorseCameraHash:"Aiming camera preset used while mounted.",
  CoverCameraHash:"Camera preset used while aiming from cover.",
  CoverReadyToFireCameraHash:"Camera preset used in cover when the weapon is ready to fire.",
  CoverHipFireCameraHash:"Camera preset used when hip-firing from cover.",
  RunAndGunCameraHash:"Camera preset used while moving and firing.",
  GrappleCameraHash:"Camera preset used when the weapon is involved in a grapple.",
  RecoilShakeHash:"Third-person camera-shake preset used for recoil.",
  RecoilShakeHashFirstPerson:"First-person camera-shake preset used for recoil.",
  LookingGlassDefaultScopeInfo:"Scope-view preset used by binocular or looking-glass behavior.",
  DismembermentSetting:"Dismemberment rule set used by this ammunition or weapon.",
  NmTuningSet:"Default NaturalMotion body-reaction preset for hits from this weapon.",
  NmShotTuningSet:"NaturalMotion body-reaction preset for a normal shot.",
  NmHeadShotTuningSet:"NaturalMotion body-reaction preset for a head shot.",
  NmNeckShotTuningSet:"NaturalMotion body-reaction preset for a neck shot.",
  NmBackShotTuningSet:"NaturalMotion body-reaction preset for a back shot.",
  NmArmShotTuningSet:"NaturalMotion body-reaction preset for an arm shot.",
  NmLegShotTuningSet:"NaturalMotion body-reaction preset for a leg shot.",
  MeleeRightFistTargetHealthDamageScaler:"Damage multiplier applied to the target by the right-fist melee action.",
  TintSpecValues:"Available material tint set for weapon customization.",
  VertData:"Weapon geometry tuning record used for its first-person and handling offsets.",
};
function weaponFieldHelp(field){
  const path=String(field||"");
  // Linked ammo rows read "WEAPON_BOW / Performance / Damage", so trim.
  const leaf=path.split("/").pop().trim();
  if(WEAPON_FIELD_HELP[leaf])return WEAPON_FIELD_HELP[leaf];
  if(/\/Explosion\//.test(path)){
    const target={Default:"the normal impact",HitCar:"cars",HitTruck:"trucks",HitBike:"bikes",HitBoat:"boats",HitPlane:"aircraft"}[leaf];
    if(target)return `Explosion-effect tag used when this damage mode hits ${target}. It selects the reaction/effect class, not blast damage.`;
  }
  if(/\/Components\//.test(path)&&leaf==="Name")return "Component identifier fitted at this attachment point.";
  if(/\/Components\//.test(path)&&leaf==="Default")return "Whether this component is fitted to the base weapon by default.";
  if(/DamageModes\//.test(path)&&leaf==="Name")return "Damage-mode identifier. Each mode joins the weapon to one ammunition type and its damage settings.";
  if(/^Vfx.*HashName$/.test(leaf))return "Visual-effect preset used for this specific muzzle, tracer, smoke, blood or impact effect. It changes presentation, not damage.";
  if(/^WindDisturbance.*HashName$/.test(leaf))return "Wind-disturbance effect preset produced by the muzzle blast or passing projectile.";
  // Opaque UNK_MEMBER fields and bare unnamed list items get no help icon.
  return "";
}

function weaponFieldDomain(data,section,row,current){
  const path=row.path.join(".");
  const values=[];
  for(const source of [data,state.weaponData.vanilla])for(const record of source?.[section]||[]){
    const match=record.fields.find(field=>field.path.join(".")===path&&
      (field.targetType||"")===(row.targetType||"")&&(field.targetName||"")===(row.targetName||""));
    if(match?.value!==undefined&&!values.includes(String(match.value)))values.push(String(match.value));
  }
  if(!values.includes(String(current)))values.push(String(current));
  return values.sort((a,b)=>a.localeCompare(b,undefined,{numeric:true}));
}

function weaponValueControl(data,section,row,current,edited,onChange){
  const values=weaponFieldDomain(data,section,row,current);
  const numeric=values.every(value=>/^-?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?$/i.test(value));
  // No title on any of these: a hover that only restates the widget you are
  // already looking at is noise. Field meaning lives on the "?" instead.
  const attrs={class:`weapon-value${edited?" edited":""}`};
  if(numeric){
    Object.assign(attrs,{type:"number",step:"any",value:current,onchange:ev=>onChange(ev.target.value)});
    if(isRO())attrs.readonly="readonly";
    return el("input",attrs);
  }
  if(values.length<=100){
    attrs.onchange=ev=>onChange(ev.target.value);
    if(isRO())attrs.disabled="disabled";
    return el("select",attrs,...values.map(value=>{const option=el("option",{value},value);if(value===String(current))option.selected=true;return option;}));
  }
  Object.assign(attrs,{type:"text",value:current,onchange:ev=>onChange(ev.target.value)});
  if(isRO())attrs.readonly="readonly";
  return el("input",attrs);
}

async function renderWeapons() {
  const f=state.filters, section=f.weaponSection||"weapons";f.weaponSection=section;
  const current=renderScope("renderWeapons");
  if(!state.weaponData[state.ds])state.weaponData[state.ds]=await api("/api/weapons");
  if(state.ds==="mine"&&!state.weaponData.vanilla)state.weaponData.vanilla=await api("/api/weapons",undefined,"vanilla");
  if(!state.weaponReference)state.weaponReference=await api("/api/weapons-reference");
  if(!current())return;
  const d=state.weaponData[state.ds],tb=$("#toolbar");tb.innerHTML="";
  if(!d.available)return noData("This dataset has no weapons.ymt.");
  const sectionLabels={weapons:"Weapons",ammo:"Ammo types",velocity:"Projectile speed"};
  const sectionTabs=LexeditorUI.subtabBar({tabs:Object.entries(sectionLabels).map(([id,label])=>({id,label})),active:section,
    change:key=>{f.weaponSection=key;f.weapon="";f.weaponPage=0;renderWeapons();}});
  if(section==="velocity"){
    if(!state.projectileSpeeds[state.ds])state.projectileSpeeds[state.ds]=await api("/api/weapons/projectile-speeds");
    if(!current())return;
    return renderProjectileSpeeds(state.projectileSpeeds[state.ds],sectionTabs);
  }
  const records=d[section],names=records.map(x=>x.name).sort();if(!f.weapon||!names.includes(f.weapon))f.weapon=names[0];
  const sv=d.shellVfx;
  const shellBox=sv&&sv.available?el("label",{style:"display:flex;align-items:center;gap:6px;margin:4px 0;cursor:pointer",
    title:`Blank every weapon's shell-eject VFX so vanilla shells stop duplicating the physical collectible casings. Currently ${sv.blank}/${sv.total} fields blank across ${(sv.files||[]).length} weapon files${sv.mixed?" (mixed)":""}.`},
    el("input",{type:"checkbox",checked:(state.weaponShellVfxEdit??sv.blanked)===true,
      onchange:ev=>{state.weaponShellVfxEdit=ev.target.checked;renderToolbarOnly();}}),
    "Blank vanilla shell VFX (collectible casings)"):sv?el("span",{class:"hint"},"Shell comparison unavailable: a weapon layer or its vanilla reference is missing."):null;
  tb.append(sectionTabs);
  const weaponFilters=[...(shellBox?[shellBox]:[]),savebar(saveWeapons)];
  const m=$("#main");m.innerHTML="";
  // Left list of weapons (loot-tables master/detail pattern), filtered by name.
  const q=(f.weaponQ||"").toUpperCase();
  const listNames=names.filter(n=>!q||n.includes(q)||(localizedValue(n)||"").toUpperCase().includes(q));
  if(!Number.isFinite(f.weaponPage))f.weaponPage=0;if(!Number.isFinite(f.weaponPageSize))f.weaponPageSize=20;
  m.append(LexeditorUI.pagedListDetail({modOnly:(()=>{const touched=touchedRecords(Object.values(state.weaponEdits||{}),[],1);
      return {available:!isRO(),value:state.modOnly===true,changed:name=>touched.has(String(name)),
        change:value=>{state.modOnly=value;f.weaponPage=0;renderWeapons();}};})(),
    rows:listNames,key:n=>n,slots:false,page:f.weaponPage,pageSize:f.weaponPageSize,selected:f.weapon,noun:"records",splitKey:`rdr2-weapons-${section}`,defaultSplit:44,
    search:{key:`rdr2-weapons-${section}`,value:f.weaponQ||"",placeholder:`Search ${section}…`,change:value=>{f.weaponQ=value;f.weaponPage=0;renderWeapons();}},filters:weaponFilters,
    master:({rows,selected,select})=>LexeditorUI.columnList({rows,key:n=>n,selected,select,columns:[
      {key:"name",label:section==="weapons"?"Weapon":"Ammo type",render:n=>originDisplayName(localizedValue(n)?.trim()||n,records.find(row=>row.name===n))},
      {key:"id",label:"ID",render:n=>n}]}),
    detail:name=>weaponDetail(d,section,records.find(row=>row.name===name),f),sync:next=>{f.weaponPage=next.page;f.weaponPageSize=next.pageSize;f.weapon=next.selected||"";},change:next=>{f.weaponPage=next.page;f.weaponPageSize=next.pageSize;f.weapon=next.selected||"";renderWeapons();}}));
}

function renderProjectileSpeeds(data,sectionTabs){
  const tb=$("#toolbar"),m=$("#main");tb.innerHTML="";m.innerHTML="";
  if(!data.available){tb.append(sectionTabs);return noData("Projectile-speed data is unavailable.");}
  const edits=state.projectileSpeedEdits;
  const toolbar=LexeditorUI.toolbar(
    el("input",{type:"text",placeholder:"Filter cartridges or weapons…",value:state.filters.velocityQ||"",oninput:ev=>{state.filters.velocityQ=ev.target.value;filterRerender(ev,renderWeapons);}}),
    el("span",{class:"count"},`${data.cartridges.length} cartridges`));
  // The issue explicitly forbids editable/displayed per-cartridge values when
  // there is no real runtime switch. Keep the proven mapping visible, but do
  // not offer a save action for settings the game would ignore.
  if(data.runtimeSwitching)toolbar.append(savebar(saveProjectileSpeeds));
  tb.append(sectionTabs,toolbar);
  const status=LexeditorUI.stack({fill:false,className:"lex-notice"},
    el("b",{},`Global base: ${data.baseSpeed} game-speed units. `),
    data.runtimeSwitching?"The ASI applies the selected cartridge multiplier at runtime.":data.runtimeStatus);
  const q=(state.filters.velocityQ||"").toUpperCase();
  const rows=data.cartridges.filter(row=>!q||row.ammo.includes(q)||row.uses.some(use=>use.weapon.includes(q)||use.damageMode.includes(q)));
  const speedOf=row=>{
    const value=edits[row.ammo]??row.multiplier;
    return data.runtimeSwitching?Number(data.baseSpeed)*Number(value):Number(data.baseSpeed);
  };
  const table=columnList({class:"velocity-table",align:"start",headerAlign:"start","aria-label":"Cartridge speeds",
    rows,key:row=>row.ammo,editable:true,
    template:"minmax(160px,1fr) 120px 150px minmax(0,2fr)",
    columns:[{key:"ammo",label:"Cartridge",cellClass:"key",render:row=>weaponRecordLink("ammo",row.ammo)},
      {key:"multiplier",label:data.runtimeSwitching?"Multiplier":"Multiplier (inactive)",
        sortValue:row=>Number(edits[row.ammo]??row.multiplier),
        render:row=>el("input",{class:`weapon-value${row.ammo in edits?" edited":""}`,type:"number",min:"0.05",max:"10",step:"0.01",
          value:edits[row.ammo]??row.multiplier,"aria-label":`Speed multiplier for ${row.ammo}`,
          disabled:(!data.runtimeSwitching||isRO())?true:undefined,
          onchange:ev=>{const n=Number(ev.target.value);if(Number.isFinite(n)&&n>=0.05&&n<=10)edits[row.ammo]=n;renderToolbarOnly();}})},
      {key:"speed",label:data.runtimeSwitching?"Effective speed":"Current runtime speed",
        sortValue:row=>speedOf(row),
        render:row=>Number.isFinite(speedOf(row))?speedOf(row).toFixed(2):"—"},
      {key:"uses",label:"Real weapon / damage-mode mappings",
        sortValue:row=>row.uses.map(use=>use.weapon).join("|"),
        render:row=>el("span",{},...row.uses.map(use=>el("div",{class:"n"},weaponRecordLink("weapons",use.weapon),` / ${use.damageMode}`)))}]});
  m.append(status,el("div",{class:"weapon-fieldscroll"},table));
}

async function saveProjectileSpeeds(){
  const data=state.projectileSpeeds.mine;
  if(!data?.runtimeSwitching)throw new Error("Per-cartridge projectile speed is not active in the runtime");
  const entries=data.cartridges.map(row=>({ammo:row.ammo,multiplier:state.projectileSpeedEdits[row.ammo]??row.multiplier}));
  const r=await api("/api/weapons/projectile-speeds/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({entries})});
  state.projectileSpeedEdits={};delete state.projectileSpeeds.mine;toast(`Saved ${r.saved} cartridge multipliers`);renderWeapons();
}

// The six stats the game shows in-game. Only Damage and Fire Rate exist as
// clean single numbers; the rest are curves, sub-records, or in another file,
// so they are shown honestly (a value where there is one, a note where there
// is not) rather than faked. Clicking a tile filters the field list to it.
function weaponBig6(record, fv){
  const strip=LexeditorUI.tileGrid([]);
  const num=v=>{const n=+v;return Number.isFinite(n)?(n%1?n.toFixed(2).replace(/0+$/,"").replace(/\.$/,""):String(n)):null;};
  const tile=(label,value,note,filterField)=>{
    const control=filterField?el("button",{type:"button",title:note||"",onclick:()=>{state.filters.weaponFieldQ=filterField;renderWeapons();}},value??"—"):LexeditorUI.readonlyField(value??"—");
    const t=LexeditorUI.detailField({label,control,help:note?fieldHelp(note):null});
    return t;
  };
  // Damage modes are named per ammo type (DM_ARROW, DM_AMMO_EXPRESS, ...), so
  // the strip shows the FIRST one — Rockstar's default load for that weapon.
  const firstMode=suffix=>{const hit=Object.keys(fv).find(k=>k.startsWith("DamageModes/")&&k.endsWith("/"+suffix));return hit?fv[hit]:undefined;};
  const damage=num(firstMode("Damage"));
  const fireRate=num(fv["WeaponTimeBetweenShots/TimeBetweenShotsMin"]);
  const reload=num(fv["WeaponReload/AnimReloadRate"]);
  const falloff=fv["DamageFallOffInfo"]||firstMode("DamageFallOffInfo");
  strip.append(
    tile("Damage",damage,"Damage of this weapon's FIRST damage mode (its default ammo). Each ammo type has its own mode — click to see them all.","Damage"),
    tile("Fire rate",fireRate,"Seconds between shots (lower = faster). WeaponTimeBetweenShots/TimeBetweenShotsMin","TimeBetweenShots"),
    tile("Reload",reload,"Reload anim rate multiplier (higher = faster). WeaponReload/AnimReloadRate","Reload"),
    tile("Range",falloff?String(falloff).replace(/^DAMAGE_FALLOFF_/,""):null,"Range is a named falloff CURVE, not a number — edit the referenced CWeaponDamageFallOffInfo record's distances.","Falloff"),
    tile("Accuracy",null,"Driven by CWeaponAccuracyInfo (a sub-record) + spread — no single displayed number is stored.","Accuracy"),
    tile("Mag size",null,"Magazine capacity is defined in weaponcomponents.meta (the clip/cylinder component), not in weapons.ymt.",null));
  return strip;
}

const WEAPON_FIELD_CATEGORIES=[
  {key:"damage",label:"Damage & hit effects",description:"Damage, body-region modifiers, headshots, penetration, bleed-out and dismemberment.",
    match:path=>/DamageModes|WeaponDamage|HeadShot|Dismember|BleedOut|SkinPenetration|CriticalHit|NonRegionLimb|LightlyArmoured|Killshot/i.test(path)},
  {key:"fire",label:"Firing & reloading",description:"Trigger behavior, shot timing, reloads, cocking, pellet count and weapon cadence.",
    match:path=>/WeaponReload|WeaponTimeBetweenShots|FireType|CockingInfo|SectionedReload|BulletsInBatch|BulletsPerAnimLoop|Spin(?:Up|Down|Time)|AlternateWait|BatchSpread|MaxDrawingMBR/i.test(path)},
  {key:"accuracy",label:"Accuracy, recoil & camera",description:"Spread, recoil, aim assistance, reticle sway, camera presets, field of view and first-person IK.",
    match:path=>/Accuracy|Recoil|Retic|BulletBending|WeaponAimOffsets|WeaponCamera|Camera|CameraFov|AimFov|Dof|ZoomFactor|AimProbe|IkRecoil|TorsoIK|BulletDirection/i.test(path)},
  {key:"range",label:"Range & targeting",description:"Effective ranges, lock-on distances, AI engagement distance and projectile reach.",
    match:path=>/WeaponRanges|LockOnRange|DesiredRange|Range(?:Min|Max|InVehicle)?|AiSoundRange|AiPotentialBlastEventRange|DistanceFromTarget/i.test(path)},
  {key:"physics",label:"Force & projectile physics",description:"Impact force, ragdoll impulse, projectile speed, launch correction and physical hit behavior.",
    match:path=>/WeaponForce|Force|Impulse|Projectile|Launch|DropForward|\bSpeed\b|FragImpulse|NumPedImpacts/i.test(path)},
  {key:"melee",label:"Melee & body reactions",description:"Melee reach and damage plus NaturalMotion hit, knockdown and body-reaction presets.",
    match:path=>/Melee|WeaponNM|Nm(?:Tuning|Shot|Head|Neck|Back|Arm|Leg)|Knockdown/i.test(path)},
  {key:"ai",label:"AI & Dead Eye",description:"AI attack selection, combat preference, distraction, motivation and Dead Eye limits.",
    match:path=>/\bAI|AIAttack|FiringPattern|Familiarity|Distraction|Motivation|Deadeye|DeadEye/i.test(path)},
  {key:"handling",label:"Animation, handling & holsters",description:"Animation sets, hand assignments, attachment points, holsters, additive pose weights and components.",
    match:path=>/AttachPoints|AttachBone|AttachPoint|Holster|Blackboard|Animation|AdditiveWeight|Breathing|LeanAdditive|Armpit|TemporaryAttach|UpperArm|ShortArm|FireProbeBone/i.test(path)},
  {key:"effects",label:"Audio, visuals & feedback",description:"Sound, visual effects, wind effects, rumble and weapon-generated light.",
    match:path=>/Audio|Vfx|EffectGroup|WindDisturbance|Rumble|LightRadius/i.test(path)},
  {key:"condition",label:"Condition & degradation",description:"Condition loss, dirt, rust, permanent wear and their displayed labels.",
    match:path=>/Degrad|DurationWet|DurationDirty|Soot|Rust|Dirt/i.test(path)},
  {key:"vehicle",label:"Mounted & vehicle use",description:"Vehicle-specific damage, reload, camera, range, lock-on and attack limits.",
    match:path=>/Vehicle|Horse|Aircraft|HitCar|HitTruck|HitBike|HitBoat|HitPlane/i.test(path)},
  {key:"identity",label:"Identity, inventory & flags",description:"Record identity, inventory placement, unlock links, stats, weapon class and behavior flags.",
    match:path=>/WeaponType|SwapWeaponType|WeaponFlags|AmmoFlags|\bSlot\b|\bGroup\b|\bScore\b|SpecialWeapon|OutlawWeapon|PickupHash|UnlockWeaponHash|RewardHash|StatName|SkillStatName|Caliber|TintSpec|VertData|\bType\b|\bSize\b|\bDefault\b/i.test(path)},
];

function weaponFieldCategory(row){
  const parts=String(row.field||"").split("/").map(part=>part.trim());
  const marker=parts.findIndex(part=>part==="Performance"||part==="Range curve"||part==="Accuracy curve");
  let path=parts.join("/");
  if(marker>=0){
    const prefix=parts[marker]==="Range curve"?"DamageFallOffInfo":parts[marker]==="Accuracy curve"?"AccuracyInfo":"DamageModes";
    path=[prefix,...parts.slice(marker+1)].join("/");
  }
  const leaf=parts[parts.length-1]||"";
  if(/^UNK_MEMBER_/i.test(leaf)||/^Item \d+$/i.test(leaf))
    return {key:"unidentified",label:"Unidentified fields",description:"The extracted schema has no reliable name for these values. They remain editable, but Lexeditor does not guess what they do."};
  return WEAPON_FIELD_CATEGORIES.find(group=>group.match(path))||
    {key:"identity",label:"Identity, inventory & flags",description:"Record identity, inventory placement, unlock links, stats, weapon class and behavior flags."};
}

function weaponDetail(d,section,record,f){
  const body=LexeditorUI.stack({fill:false}),pane=LexeditorUI.detailPanel({title:record?LexeditorUI.detailField({label:"Name",control:localizationInput(record.name)}):"Weapon",meta:record?.name,body});
  if(!record)return pane.appendChild(LexeditorUI.stack({fill:false,className:"lex-notice"},"Select a weapon."))&&pane;
  const vanilla=state.weaponData.vanilla?.[section]?.find(x=>x.name===record.name);
  const wr=state.weaponReference?.[section]?.find(x=>x.name===record.name);
  const byField=(r)=>Object.fromEntries((r?.fields||[]).map(x=>[x.field,x.value]));const vv=byField(vanilla),wv=byField(wr);
  const fv=Object.fromEntries((record.fields||[]).map(x=>[x.field,x.value]));
  const editKey=`${section}|${record.name}`,edits=state.weaponEdits[editKey]||(state.weaponEdits[editKey]={});
  body.append(LexeditorUI.detailField({label:"Source",control:LexeditorUI.readonlyField(record.sourceFile||d.file)}));
  if(section==="weapons")body.append(weaponBig6(record,fv));
  body.append(LexeditorUI.actionRow(el("input",{id:"weapon-field-filter",type:"text",placeholder:"Filter fields…",value:f.weaponFieldQ||"",
    oninput:ev=>{f.weaponFieldQ=ev.target.value;filterRerender(ev,renderWeapons);}}),
    f.weaponFieldQ?closeButton({title:"Clear field filter",onclick:()=>{f.weaponFieldQ="";renderWeapons();}}):""));
  const q=(f.weaponFieldQ||"").toUpperCase();
  const rows=sortedRows("weapons",record.fields.filter(x=>x.field!=="Name"&&(!q||x.field.toUpperCase().includes(q))),{field:x=>x.field,value:x=>x.value,references:x=>vv[x.field]??wv[x.field]??""});
  const grouped=new Map();
  rows.forEach(row=>{const group=weaponFieldCategory(row);if(!grouped.has(group.key))grouped.set(group.key,{...group,rows:[]});grouped.get(group.key).rows.push(row);});
  const order=[...WEAPON_FIELD_CATEGORIES.map(group=>group.key),"unidentified"];
  const groups=LexeditorUI.stack({fill:false});
  [...grouped.values()].sort((a,b)=>order.indexOf(a.key)-order.indexOf(b.key)).forEach(group=>{
    const editKey=row=>`${row.targetType||section}|${row.targetName||record.name}|${row.path.join(".")}`;
    const table=columnList({class:"weapon-field-table",align:"start",headerAlign:"start","aria-label":`${group.label} fields`,
      rows:group.rows,key:editKey,editable:true,localSort:false,
      template:"minmax(180px,1fr) minmax(0,1.6fr)",
      columns:[{key:"field",label:"Field",cellClass:"key",
          render:row=>{const help=weaponFieldHelp(row.field);
            return LexeditorUI.inlineLabel(el("span",{},row.field),help?fieldHelp(help):null);}},
        {key:"value",label:()=>el("span",{},"My value",fieldHelp("Value with V / WR references beside the control (shared refField layout).")),
          render:row=>{const key=editKey(row),cur=edits[key]?.value??row.value;
            const setValue=value=>{edits[key]={path:row.path,kind:row.kind,value,targetType:row.targetType,targetName:row.targetName};renderToolbarOnly();};
            const control=weaponValueControl(d,section,row,cur,key in edits,setValue);
            return refField(control,[["V","vtag",vv[row.field]],["WR","ucotag",wv[row.field]]],cur,
              (value,ev)=>{const target=ev.currentTarget.closest('[role="row"]').querySelector(".weapon-value");
                if(target){target.value=value;target.dispatchEvent(new Event("change",{bubbles:true}));}},String);}}]});
    const details=LexeditorUI.detailSection({title:`${group.label} (${group.rows.length})`,
      collapsible:true,open:!!q,attrs:{"data-group":group.key},
      help:fieldHelp(group.description),body:table});
    groups.append(details);
  });
  if(!rows.length)groups.append(LexeditorUI.stack({fill:false,className:"lex-notice"},"No fields match."));
  body.append(groups);
  return pane;
}

async function saveWeapons(){
  const section=state.filters.weaponSection||"weapons",name=state.filters.weapon,key=`${section}|${name}`,edits=Object.values(state.weaponEdits[key]||{});
  const record=state.weaponData.mine?.[section]?.find(row=>row.name===name);
  const localizedSaved=await saveLocalization();const r=await api("/api/weapons/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({section,name,sourceFile:record?.sourceFile,edits})});
  delete state.weaponEdits[key];delete state.weaponData.mine;toast(`Saved ${r.saved} weapon + ${localizedSaved} in-game text field(s)`);renderWeapons();
}

async function saveWeaponShellVfx(){
  if(state.weaponShellVfxEdit===null)return 0;
  const r=await api("/api/weapons/shell-vfx/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({blanked:state.weaponShellVfxEdit})});
  state.weaponShellVfxEdit=null;delete state.weaponData.mine;return r.saved;
}
