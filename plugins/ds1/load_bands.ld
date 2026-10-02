SECTIONS {
  .classifier 0x319B040 : { *(.text.classifier) }
  .recovery   0x319B0C0 : { *(.text.recovery) }
  .factor     0x356FEA : { *(.text.factor) }
  .fraction   0x2E1A7B : { *(.text.fraction) }
}
bands_count = 0x319B018;
special_enabled = 0x319B01C;
special_recovery = 0x319B020;
forced_rate = 0x319B024;
one = 0x319B028;
bands_table = 0x319B400;
maximum_load = 0x362340;
