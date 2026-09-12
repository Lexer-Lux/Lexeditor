"""Exercise production RPF8 loading against small owned fixtures; no game data."""
from pathlib import Path
import os
import subprocess
import tempfile
from xml.sax.saxutils import escape

TEST=r'''
using System;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using RDR2_RPF_Tool.Core;
class Test {
 static void Check(bool value,string message){if(!value)throw new Exception(message);}
 static byte[] Fixture(ushort tag=255){var bytes=new byte[272];using(var s=new MemoryStream(bytes))using(var w=new BinaryWriter(s)){w.Write(0x52504638u);w.Write(0);w.Write(0);w.Write(tag);w.Write((ushort)121);}return bytes;}
 static string[] Owned(){var root=Path.Combine(Path.GetTempPath(),"Lexeditor-RpfCli");return Directory.Exists(root)?Directory.GetFileSystemEntries(root):Array.Empty<string>();}
 static void Main(string[] args){
  string fixture=Path.Combine(args[0],"source.rpf");var valid=Fixture();
  foreach(var data in new[]{Array.Empty<byte>(),new byte[272],Fixture(198)}){
   var before=Owned();bool threw=false;
   try{RPF8.Load("nested/script_rel.rpf",data);}catch{threw=true;}
   Check(threw,"bad nested archive accepted");Check(Owned().Order().SequenceEqual(before.Order()),"failed nested load leaked files");
   File.WriteAllBytes(fixture,data);threw=false;
   try{RPF8.Load(fixture);}catch{threw=true;}
   Check(threw,"bad disk archive accepted");
   // A thrown parse must not retain an open stream or delete the source.
   using(var stream=new FileStream(fixture,FileMode.Open,FileAccess.ReadWrite,FileShare.None))Check(stream.Length==data.Length,"source changed");
   Check(File.ReadAllBytes(fixture).SequenceEqual(data),"source bytes changed");
  }
  var baseline=Owned();
  var archives=Task.WhenAll(Enumerable.Range(0,8).Select(_=>Task.Run(()=>RPF8.Load("same/script_rel.rpf",valid)))).GetAwaiter().GetResult();
  var paths=archives.Select(x=>x.Rpf8StreamFile.Name).ToArray();
  Check(paths.Distinct().Count()==8,"concurrent nested loads collided");
  foreach(var archive in archives){Check(archive.FilePath=="same/script_rel.rpf","virtual identity lost");archive.Destroy();archive.Destroy();}
  Check(paths.All(x=>!File.Exists(x)&&!Directory.Exists(Path.GetDirectoryName(x))),"successful nested load leaked");
  Check(Owned().Order().SequenceEqual(baseline.Order()),"unrelated temp tree changed");
  // A virtual absolute/traversal name must never become a writable path.
  var odd=RPF8.Load(Path.Combine(args[0],"..","outside.rpf"),valid);
  Check(odd.Rpf8StreamFile.Name.StartsWith(Path.Combine(Path.GetTempPath(),"Lexeditor-RpfCli")),"virtual path escaped temp owner");odd.Destroy();
  File.WriteAllBytes(fixture,valid);var disk=RPF8.Load(fixture);disk.Destroy();Check(File.ReadAllBytes(fixture).SequenceEqual(valid),"normal archive deleted");
  Console.WriteLine("PASS: failed parse/decryption cleanup, source preservation, concurrent isolation, virtual-path isolation, repeated Destroy");
 }
}
'''
def run(cmd,**kwargs):
    p=subprocess.run(cmd,text=True,capture_output=True,**kwargs)
    if p.returncode:raise RuntimeError(p.stdout+p.stderr)
    return p.stdout

def main():
    root=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='lex-rpf8-lifetime-') as tmp:
        tmp=Path(tmp);binary=tmp/'bin';intermediate=tmp/'obj'
        run(['dotnet','build',str(root/'tools/rpf-cli/source/RpfCli/RpfCli.csproj'),'-o',str(binary),'-p:BaseIntermediateOutputPath='+str(intermediate)+os.sep,'--nologo','-v:q'])
        harness=tmp/'test';harness.mkdir();(harness/'Program.cs').write_text(TEST)
        assembly=escape(str(binary/'RpfCli.dll'))
        (harness/'Test.csproj').write_text('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net8.0-windows</TargetFramework></PropertyGroup><ItemGroup><Reference Include="RpfCli"><HintPath>'+assembly+'</HintPath></Reference></ItemGroup></Project>')
        env=dict(os.environ);owned=tmp/'temp';owned.mkdir();env['TEMP']=env['TMP']=str(owned)
        output=run(['dotnet','run','--project',str(harness/'Test.csproj'),'--',str(harness)],env=env)
        print('\n'.join(line for line in output.splitlines() if line.startswith('PASS:')))
if __name__=='__main__':main()
