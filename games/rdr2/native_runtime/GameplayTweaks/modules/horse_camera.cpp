// GameplayTweaks feature module: horse camera auto-centering toggle (#47).
//
// The previous implementation read and rewrote relative heading/pitch every
// idle frame.  That fought Rockstar's own mounted camera update and produced
// the reported jumping.  The referenced Riyusso mod instead changes four
// mounted-follow tuning values in cameras.ymt and never drives the orbit.
//
static void updateHorseCameraCentering(Ped ped) {
	(void)ped;
	// Deliberately inert until the four confirmed fields can be applied to a
	// project-owned vanilla extraction. Do not restore the old per-frame
	// heading/pitch setters: they caused the reported mounted-camera jumping.
}
