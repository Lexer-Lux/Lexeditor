#pragma once

// Release is the safe default. Development builds opt in from the compiler
// command line, so distributing a normal build cannot accidentally retain a
// runtime INI switch that re-enables development-only behavior.
#ifndef GAMEPLAYTWEAKS_DEV_MODE
#define GAMEPLAYTWEAKS_DEV_MODE 0
#endif

#if GAMEPLAYTWEAKS_DEV_MODE != 0 && GAMEPLAYTWEAKS_DEV_MODE != 1
#error GAMEPLAYTWEAKS_DEV_MODE must be either 0 or 1.
#endif

namespace GameplayTweaksBuild
{
	static constexpr bool Development = GAMEPLAYTWEAKS_DEV_MODE == 1;
}

