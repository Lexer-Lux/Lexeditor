#pragma once
void lexeditor_ff8_flare_tick();
void lexeditor_ff8_flare_service_stationary_field();
// -1 means no request: run the normal native encounter check.
int lexeditor_ff8_flare_world_gate(unsigned short *encounter, bool allowed);
int lexeditor_ff8_flare_field_gate(bool allowed);
int lexeditor_ff8_flare_owner_install();
