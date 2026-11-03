/* Lexeditor adapter for the pinned PvP Overhaul anti-ban source.
 * SPDX-License-Identifier: AGPL-3.0-only */
#pragma once
#include <windows.h>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include "../lexeditor_ds1_loader.h"
namespace Game { inline constexpr uint64_t ds1_base = 0x140000000; }
void ConsoleWrite(const char *format, ...);
[[noreturn]] void FATALERROR(const char *format, ...);
