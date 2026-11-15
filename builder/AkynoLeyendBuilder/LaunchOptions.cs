using System.IO;
using System.Text.Json;
namespace AkynoLeyendBuilder;
sealed record GraphicsSettings {
 public string Backend{get;init;}="vulkan";
 public string Resolution{get;init;}="saved";
 public string OutputResolution{get;init;}="saved";
 public string Speed{get;init;}="saved";
 public string Upscaling{get;init;}="saved";
 public string Sharpness{get;init;}="saved";
 public string Framegen{get;init;}="saved";
 public string Pacing{get;init;}="saved";
 public string FpsCounter{get;init;}="saved";
 public string Handheld{get;init;}="saved";
 public string Cache{get;init;}="original";
 string LaunchResolution()=>Upscaling switch {
  "dlaa" or "fsr-native-aa" or "fsr4-native-aa"=>"100",
  "dlss" or "fsr-temporal" or "fsr4" when Resolution is not ("50" or "67" or "75")=>"50",
  _=>Resolution
 };
 public string[] Arguments(){
  if(Backend!="vulkan")throw new InvalidOperationException("OpenGL ainda não está disponível nesta versão.");
  var args=new List<string>{"--backend",Backend};
  // FSR 3.1, DLSS and DLAA take a fixed internal resolution: 100% for the native anti-aliasing modes (DLAA, FSR Native AA),
  // 50-75% for the others (the CLI refuses the rest: akynoleyend/graphics.py TEMPORAL)
  void Add(string option,string value,params string[] allowed){if(value=="saved")return;if(!allowed.Contains(value))throw new InvalidOperationException($"Opção inválida: {option}={value}");args.Add(option);args.Add(value);}
  Add("--resolution",LaunchResolution(),"auto","100","75","67","50","125","150","native-1440","native-4k");
  Add("--output-resolution",OutputResolution,"game","1440p","4k","1080p","720p","1600p");
  Add("--speed",Speed,"realtime","per-frame");
  Add("--upscaling",Upscaling,"off","catmull-rom","lanczos","fsr","fsr-temporal","fsr-native-aa","fsr4","fsr4-native-aa","dlss","dlaa");
  Add("--sharpness",Sharpness,"0","10","20","30");
  Add("--framegen",Framegen,"0","2","3","4","5","6","7","8","9");   // (9: Dinâmica, 0.4.5-test.1)
  Add("--pacing",Pacing,"on","off");
  Add("--fps-counter",FpsCounter,"on","off");
  var handheld=OutputResolution is "1440p" or "4k" or "1600p"?"off":Handheld;
  Add("--handheld",handheld,"on","off");
  Add("--cache-mode",Cache,"original","streaming","equilibrado");
  return args.ToArray();
 }
 public GraphicsSettings FollowGameOptions(GameGraphicsOptions? before, GameGraphicsOptions? after){
  if(after==null || after==before)return this;
  bool modeChanged=Upscaling!="saved" && after.Upscaling!=null && after.Upscaling!=Upscaling;
  return this with {
   Upscaling=modeChanged?"saved":Upscaling,
   Resolution=modeChanged || after.Resolution!=null && after.Resolution!=LaunchResolution()?"saved":Resolution,
   OutputResolution=after.OutputResolution!=null && after.OutputResolution!=OutputResolution?"saved":OutputResolution
  };
 }
 public static GraphicsSettings FsrPreset()=>Preset("smooth");
 public static GraphicsSettings Preset(string name)=>new(){
  Resolution=name=="amd-low"?"50":name=="quality"?"100":name=="balanced"?"75":"67",
  OutputResolution=name=="1600p"?"1600p":"1080p",Speed="realtime",Upscaling=name=="1600p"?"lanczos":"fsr",Sharpness="10",Framegen="0",
  Pacing="on",FpsCounter="on",Handheld=name=="amd-low"?"on":"off",Cache="equilibrado"};
 public GraphicsSettings NormalizeLegacyOutput()=>Resolution=="native-1440"||Resolution=="native-4k"?
  this with {Resolution="100",OutputResolution=Resolution=="native-1440"?"1440p":"4k"}:this;
}
// (0.4.6) launcher > Teste de desempenho is gone (0.4.5-test.2 to test.8); manage.py run --measure [--experiment] stays.
sealed record GameGraphicsOptions(DateTime Updated, string? OutputResolution, string? Resolution, string? Upscaling) {
 static readonly string[] Outputs={"game","1440p","4k","1080p","720p","1600p"};
 static readonly string[] Scales={"auto","100","75","67","50","125","150"};
 static readonly string[] Upscalers={"off","catmull-rom","lanczos","fsr","fsr-temporal","fsr-native-aa","fsr4","fsr4-native-aa","dlss","dlaa"};
 static string? Choice(string[] values, string text)=>int.TryParse(text,out var index) && (uint)index<values.Length?values[index]:null;
 public static GameGraphicsOptions? Read(string folder){
  try{
   var file=new FileInfo(Path.Combine(folder,"AkynoLeyend_opts.ini"));
   if(!file.Exists || file.Length>65536)return null;
   string? output=null,scale=null,mode=null;
   foreach(var line in File.ReadLines(file.FullName)){
    var fields=line.Split('=',2);
    if(fields.Length!=2)continue;
    switch(fields[0]){
     case "output_resolution": output=Choice(Outputs,fields[1]);break;
     case "resolution": scale=Choice(Scales,fields[1]);break;
     case "upscaler": mode=Upscalers.Contains(fields[1])?fields[1]:null;break;
    }
   }
   return new(file.LastWriteTimeUtc,output,scale,mode);
  }catch(IOException){return null;}
   catch(UnauthorizedAccessException){return null;}
 }
}
sealed record LauncherSettings {
 public int Schema{get;init;}=1;
 public string Output{get;init;}="";public string Nup{get;init;}="";public string Romfs{get;init;}="";public string Exefs{get;init;}="";
 public bool Folders{get;init;}public int Jobs{get;init;}public int Profile{get;init;}public string Language{get;init;}="pt-BR";
 public GraphicsSettings Graphics{get;init;}=new();
 public static LauncherSettings? Load(string path){if(!File.Exists(path))return null;if(new FileInfo(path).Length>65536)throw new IOException("Arquivo de ajustes excede 64 KiB.");var s=JsonSerializer.Deserialize<LauncherSettings>(File.ReadAllText(path));if(s?.Schema!=1||s.Graphics==null)throw new IOException("Formato de ajustes desconhecido.");s.Graphics.Arguments();return s;}
 public void Save(string path){Graphics.Arguments();var text=JsonSerializer.Serialize(this,new JsonSerializerOptions{WriteIndented=true});var temporary=path+"."+Guid.NewGuid().ToString("N")+".tmp";try{File.WriteAllText(temporary,text);File.Move(temporary,path,overwrite:true);}finally{if(File.Exists(temporary))File.Delete(temporary);}}
}
