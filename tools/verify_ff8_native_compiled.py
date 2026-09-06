"""Compile the production FF8 native modules against instrumented native I/O.

Linux/g++ test harness, no game or external headers required. Native memory
semantics are also tested separately with --exe by the Unicorn test. This
checks production C++ logic, not a rewritten Python model or live rendering.
"""
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
FIXTURES=ROOT/'tools/fixtures/ff8_native'


def party_source():
    source=(ROOT/'games/ff8/ffnx_party_switch/ffnx-src/lexeditor_ff8_party_switch.cpp').read_text()
    source='\n'.join(line for line in source.splitlines() if not line.startswith('#include'))
    start=source.index('template<class T> T &mem(')
    end=source.index('constexpr std::uintptr_t kController',start)
    source=source[:start]+'''template<class T> T &mem(std::uintptr_t a) { return test_mem<T>(a); }
template<class R,class... A> R native(std::uintptr_t a,A... args) { return test_native<R>(a,args...); }
'''+source[end:]
    return (FIXTURES/'party_harness.cpp').read_text()+source+'\n'+(FIXTURES/'party_cases.cpp').read_text()


def compile_and_run(text: str, name: str):
    with tempfile.TemporaryDirectory(prefix='ff8-native-') as folder:
        source=Path(folder)/f'{name}.cpp'; binary=Path(folder)/name
        source.write_text(text)
        subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Wno-unused-function','-Wno-unused-parameter','-O1','-g',str(source),'-o',str(binary)],check=True)
        subprocess.run([str(binary)],check=True,timeout=15)


def bars_source():
    source=(ROOT/'games/ff8/ffnx_status_bars/ffnx-src/lexeditor_ff8_bars.cpp').read_text()
    source='\n'.join(line for line in source.splitlines() if not line.startswith('#include'))
    return (FIXTURES/'bars_harness.cpp').read_text()+source+'\n'+(FIXTURES/'bars_cases.cpp').read_text()


if __name__=='__main__':
    compile_and_run(party_source(),'party')
    compile_and_run(bars_source(),'bars')
