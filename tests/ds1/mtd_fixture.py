"""Synthetic DS1 material definitions, with no shipped shader data."""
import struct


def build_mtd(parameters=None):
    parameters = parameters or {'g_WaterColor': ('float4', [0.2, 0.3, 0.1, 0.4]),
        'g_WaterWaveHeight': ('float', [2]), 'g_SpecularPower': ('float', [100])}
    out = bytearray()
    def integer(value):
        out.extend(struct.pack('<i', value))
    def marker(value):
        out.append(value)
        out.extend(bytes(-len(out) % 4))
    def string(value, mark):
        raw = value.encode('shift_jis')
        integer(len(raw))
        out.extend(raw)
        marker(mark)
    def begin(kind, version, mark):
        integer(0)
        slot = len(out)
        integer(0)
        integer(kind)
        integer(version)
        marker(mark)
        return slot
    def end(slot):
        struct.pack_into('<I', out, slot, len(out)-slot-4)
    file = begin(0, 3, 1)
    header = begin(1, 2, 0xB0)
    string('MTD ', 0x34)
    integer(1000)
    end(header)
    marker(1)
    data = begin(2, 4, 0xA3)
    string('SyntheticWater.spx', 0xA3)
    string('Synthetic material', 3)
    integer(1)
    lists = begin(3, 4, 0xA3)
    integer(0)
    marker(3)
    integer(len(parameters))
    for name, (kind, values) in parameters.items():
        parameter = begin(4, 4, 0xA3)
        string(name, 0xA3)
        string(kind, 4)
        integer(1)
        basic = kind.rstrip('234')
        code, mark, fmt = {'float': (0x1002, 0xCA, 'f'),
            'int': (0x1001, 0xC5, 'i'), 'bool': (0x1000, 0xC0, '?')}[basic]
        value = begin(code, 1, mark)
        integer(len(values))
        out.extend(struct.pack('<'+fmt*len(values), *values))
        end(value)
        marker(4)
        integer(0)
        end(parameter)
    marker(3)
    integer(1)
    texture = begin(0x2000, 3, 0xA3)
    string('g_Bumpmap', 0x35)
    integer(0)
    marker(0x35)
    integer(0)
    end(texture)
    for slot in (lists, data, file):
        marker(4)
        integer(0)
        end(slot)
    return bytes(out)
