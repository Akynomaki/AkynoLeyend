using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Shapes;
using System.Windows.Threading;
using Microsoft.Win32;
using Path = System.IO.Path;

namespace AkynoLeyendBuilder;

public partial class MainWindow : Window
{
    const long NeededBytes = 60L << 30;
    const string Manifest = "AkynoLeyend-build.json";
    static readonly (string Id, S Text)[] Stages = { ("read", S.Read), ("lift", S.Lift), ("compile", S.Compile), ("finish", S.Finish) };
    Language lang = Strings.All.First(language => language.Code == "pt-BR");
    string T(S text) => lang.Text[(int)text];
    string Local(string portuguese, string english) => lang.Code == "pt-BR" ? portuguese : english;

    readonly Dictionary<string, StageRow> rows = new();
    readonly DispatcherTimer clock = new() { Interval = TimeSpan.FromSeconds(1) };
    readonly DispatcherTimer checkDelay = new() { Interval = TimeSpan.FromMilliseconds(500) };
    readonly Stopwatch elapsed = new();
    readonly UiLogBuffer pendingLines = new();
    readonly DispatcherTimer logPump = new() { Interval = TimeSpan.FromMilliseconds(100) };
    CancellationTokenSource? checkCancellation;
    Runner? runner;
    string? current;
    string finished = "";
    int checkSerial;
    bool sourceOk;
    bool playing;
    GameGraphicsOptions? gameOptionsBeforePlay;
    string? operation;
    string? pendingUpdatePlan;
    string SettingsPath => Path.Combine(Tools.Find()?.Root ?? AppContext.BaseDirectory,"AkynoLeyend-launcher.json");

    public MainWindow()
    {
        InitializeComponent();
        BuilderVersion.Text = "Launcher " + LauncherVersion();
        logPump.Tick += (_, _) => FlushLines();
        logPump.Start();
        OutPath.Text = Path.Combine(Tools.Find()?.Root ?? AppContext.BaseDirectory, "jogo");
        foreach (var (id, text) in Stages)
        {
            rows[id] = new StageRow(T(text));
            StageList.Children.Add(rows[id].Root);
        }
        clock.Tick += (_, _) => ShowClock();
        checkDelay.Tick += (_, _) => { checkDelay.Stop(); CheckSource(); };
        Drop += Dropped;
        LanguageBox.ItemsSource = Strings.All;
        LanguageBox.SelectedItem = lang;
        ApplyLanguage();
        LoadSettings();
        _ = RefreshHardware();
        NavHome.Foreground=(Brush)FindResource("Accent");
        Refresh();
    }

    void LanguageChanged(object sender, SelectionChangedEventArgs e)
    {
        if (LanguageBox.SelectedItem is Language language) { lang = language; ApplyLanguage(); }
    }

    void ApplyLanguage()
    {
        if (BuildButton == null) return;
        Subtitle.Text = T(S.Subtitle);
        GameFilesLabel.Text = T(S.GameFiles);
        UseNup.Content = T(S.Nup);
        UseFolders.Content = T(S.Folders);
        BrowseA.Content = BrowseB.Content = BrowseC.Content = BrowseD.Content = T(S.Browse);
        SaveToLabel.Text = T(S.SaveTo);
        BuildButton.Content = T(S.Build);
        ExistingPlay.Content = T(S.Play);
        JobsLabel.Text = Local("Processos de compilação", "Build processes");
        AutoJobs.Content = Local("Automático (CPU e memória atuais)", "Automatic (current CPU and memory)");
        ProfileLabel.Text = Local("Perfil ao jogar", "Runtime profile");
        Profile8.Content=Local("8 GB (texturas reduzidas)","8 GB (reduced textures)");
        ShowLog.Content = T(ShowLog.IsChecked == true ? S.HideDetails : S.ShowDetails);
        CancelButton.Content = T(S.Cancel);
        BackButton.Content = T(S.Back);
        OpenButton.Content = T(S.OpenFolder);
        PlayButton.Content = T(S.Play);
        foreach (var (id, text) in Stages) rows[id].SetText(T(text));
        CheckSource();
        Refresh();
    }

    void SourceKindChanged(object sender, RoutedEventArgs e)
    {
        if (NupRow == null) return;
        NupRow.Visibility = UseNup.IsChecked == true ? Visibility.Visible : Visibility.Collapsed;
        FolderRows.Visibility = UseNup.IsChecked == true ? Visibility.Collapsed : Visibility.Visible;
        PathsChanged(sender, e);
    }

    void PathsChanged(object sender, RoutedEventArgs e)
    {
        if (BuildButton == null) return;
        ++checkSerial;
        checkCancellation?.Cancel();
        sourceOk = false;
        checkDelay.Stop();
        checkDelay.Start();
        Say(T(SourceGiven ? S.Checking : S.DropHint), "InkSoft");
        Refresh();
    }

    void OutputChanged(object sender, RoutedEventArgs e)
    {
        if (BuildButton != null) Refresh();
    }

    bool SourceGiven => UseNup.IsChecked == true ? File.Exists(NupPath.Text)
        : Directory.Exists(RomfsPath.Text) && File.Exists(Path.Combine(ExefsPath.Text, "main"));

    void Refresh()
    {
        BuildButton.IsEnabled = sourceOk && !string.IsNullOrWhiteSpace(OutPath.Text) && runner == null;
        RefreshUpdates();
        ExistingPlay.Visibility = (File.Exists(Path.Combine(OutPath.Text,Manifest)) || File.Exists(Path.Combine(OutPath.Text,"ocarina-build.json"))) ? Visibility.Visible : Visibility.Collapsed;
        try
        {
            // Intermediate files are in the project's work folder, even with another output drive.
            var root = Path.GetPathRoot(Tools.Find()?.Root ?? AppContext.BaseDirectory);
            var free = new DriveInfo(root!).AvailableFreeSpace;
            SpaceText.Text = T(S.Needs) + " " + string.Format(T(S.Free), root, free >> 30);
            SpaceText.Foreground = (Brush)FindResource(free >= NeededBytes ? "InkSoft" : "Bad");
        }
        catch (Exception) { SpaceText.Text = T(S.Needs); }
    }

    async void CheckSource()
    {
        var serial = ++checkSerial;
        checkCancellation?.Cancel();
        checkCancellation?.Dispose();
        checkCancellation = new CancellationTokenSource(TimeSpan.FromSeconds(60));
        sourceOk = false;
        if (!SourceGiven) { Say(T(S.DropHint), "InkSoft"); Refresh(); return; }
        var tools = Tools.Find();
        if (tools == null) { Say(T(S.ToolsMissing), "Bad"); Refresh(); return; }
        Say(T(S.Checking), "InkSoft");
        Refresh();
        var args = UseNup.IsChecked == true ? new[] { "--nup", NupPath.Text } : new[] { "--exefs", ExefsPath.Text };
        var (ok, text) = await Runner.Check(tools, args, checkCancellation.Token);
        if (serial != checkSerial) return;
        sourceOk = ok;
        Say(ok ? T(S.VersionOk) : text, ok ? "Accent" : "Bad");
        Refresh();
    }

    void Say(string text, string brush)
    {
        CheckText.Text = text;
        CheckText.Foreground = (Brush)FindResource(brush);
    }

    void Dropped(object sender, DragEventArgs e)
    {
        if (runner != null || e.Data.GetData(DataFormats.FileDrop) is not string[] { Length: > 0 } paths) return;
        foreach (var path in paths)
        {
            var name = Path.GetFileName(path).ToLowerInvariant();
            if (name.EndsWith(".nup")) { UseNup.IsChecked = true; NupPath.Text = path; }
            else if (name == "romfs") { UseFolders.IsChecked = true; RomfsPath.Text = path; }
            else if (name == "exefs") { UseFolders.IsChecked = true; ExefsPath.Text = path; }
            else if (Directory.Exists(Path.Combine(path, "romfs")) && Directory.Exists(Path.Combine(path, "exefs")))
            {
                UseFolders.IsChecked = true;
                RomfsPath.Text = Path.Combine(path, "romfs");
                ExefsPath.Text = Path.Combine(path, "exefs");
            }
        }
    }

    void BrowseNup(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFileDialog { Filter = "Arquivo .nup|*.nup", Title = T(S.GameFiles) };
        if (dialog.ShowDialog(this) == true) NupPath.Text = dialog.FileName;
    }

    string? PickFolder(string title)
    {
        var dialog = new OpenFolderDialog { Title = title };
        return dialog.ShowDialog(this) == true ? dialog.FolderName : null;
    }

    void BrowseRomfs(object sender, RoutedEventArgs e) => RomfsPath.Text = PickFolder("romfs") ?? RomfsPath.Text;
    void BrowseExefs(object sender, RoutedEventArgs e) => ExefsPath.Text = PickFolder("exefs") ?? ExefsPath.Text;
    void BrowseOut(object sender, RoutedEventArgs e) => OutPath.Text = PickFolder(T(S.SaveTo)) ?? OutPath.Text;

    void StartBuild(object sender, RoutedEventArgs e)
    {
        var tools = Tools.Find();
        if (tools == null) { Say(T(S.ToolsMissing), "Bad"); return; }
        if (!sourceOk || runner != null) return;
        SaveSettings();
        operation=null;
        checkDelay.Stop();
        checkCancellation?.Cancel();
        var args = new List<string>();
        if (UseNup.IsChecked == true) args.AddRange(new[] { "--nup", NupPath.Text });
        else args.AddRange(new[] { "--romfs", RomfsPath.Text, "--exefs", ExefsPath.Text });
        args.AddRange(new[] { "--out", OutPath.Text, "--language", lang.Code,
                             "--tools", Path.Combine(tools.Root, "ferramentas") });
        if (JobsBox.SelectedIndex > 0) args.AddRange(new[] { "--jobs", JobsBox.SelectedIndex.ToString() });
        foreach (var row in rows.Values) row.Reset();
        StageList.Visibility = Visibility.Visible;
        pendingLines.Clear();
        Log.Clear();
        current = null;
        finished = "";
        playing = false;
        BuildTitle.Text = T(S.Building);
        BuildNote.Foreground = (Brush)FindResource("InkSoft");
        ShowPage(building: true);
        SetButtons(cancel: true);
        elapsed.Restart();
        runner = new Runner(tools, "build", args);
        runner.Line += pendingLines.Add;
        runner.Finished += failure => Queue(() => Ended(failure));
        clock.Start();
        ShowClock();
        runner.Start();
    }

    void Queue(Action action)
    {
        if (!Dispatcher.HasShutdownStarted) Dispatcher.BeginInvoke(action);
    }

    void Line(string line)
    {
        if (line.StartsWith("@@update_plan ")) pendingUpdatePlan = line[14..];
        else if (line.StartsWith("@@shader_progress ")) {
            var parts=line.Split(' ',StringSplitOptions.RemoveEmptyEntries);
            if(parts.Length==3&&long.TryParse(parts[1],out var done)&&long.TryParse(parts[2],out var total)&&total>0){
                BuildTitle.Text="Preparando shaders";BuildNote.Text=$"{done:N0} de {total:N0} · {done*100/total}%";
                ShaderProgress.Visibility=Visibility.Visible;ShaderProgress.IsIndeterminate=false;
                ShaderProgress.Value=Math.Clamp(done/(double)total,0,1);
            }
        }
        else if (line=="@@shader_ready") {ShaderProgress.Visibility=Visibility.Collapsed;BuildTitle.Text="Executando o jogo";BuildNote.Text="Shaders preparados. O jogo está iniciando.";}
        else if (line.StartsWith("@@stage "))
        {
            var id = line.Split(' ')[1];
            if(id=="shaders"){BuildTitle.Text="Conferindo shaders";BuildNote.Text="Preparação automática antes da partida.";ShaderProgress.Visibility=Visibility.Visible;ShaderProgress.IsIndeterminate=true;}
            if (current != null && rows.TryGetValue(current, out var previous)) previous.Done();
            current = id;
            if (rows.TryGetValue(id, out var row)) row.Begin();
        }
        else if (line.StartsWith("@@progress "))
        {
            if (current != null && rows.TryGetValue(current, out var row) &&
                double.TryParse(line[11..], System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out var fraction))
                row.Progress(fraction);
        }
        else if (line.StartsWith("@@done ")) finished = line[7..];
    }

    void FlushLines()
    {
        var lines = pendingLines.Drain();
        if (lines.Length == 0) return;
        var text = new StringBuilder();
        foreach (var line in lines)
        {
            Line(line);
            if (!line.StartsWith("@@progress")) text.AppendLine(line);
        }
        if (text.Length == 0) return;
        Log.AppendText(text.ToString());
        if (Log.Text.Length > 256000) Log.Text = Log.Text[^128000..];
        if (ShowLog.IsChecked == true) Log.ScrollToEnd();
    }

    async Task RefreshHardware()
    {
        try
        {
            var tools = Tools.Find();
            if (tools == null) { HardwareText.Text = "Extraia a pasta ferramentas completa."; return; }
            string? payload = null;
            using var stop = new CancellationTokenSource(TimeSpan.FromSeconds(15));
            var code = await Runner.Execute(Runner.Info(tools, "hardware", Array.Empty<string>()),
                line => { if (line.StartsWith("@@hardware ")) payload = line[11..]; }, stop.Token);
            if (code != 0 || payload == null) throw new IOException("Detecção indisponível.");
            using var json = JsonDocument.Parse(payload);
            var h = json.RootElement;
            HardwareText.Text = $"{h.GetProperty("logical_cpus").GetInt32()} threads · " +
                $"{h.GetProperty("ram_total").GetInt64() / (double)(1L << 30):F1} GiB RAM · " +
                $"{h.GetProperty("ram_available").GetInt64() / (double)(1L << 30):F1} GiB disponíveis. " +
                $"Automático sugere {h.GetProperty("jobs").GetInt32()} processos agora; confere novamente ao compilar.";
        }
        catch { HardwareText.Text = "O modo automático consulta CPU e memória antes de compilar."; }
    }

    void Ended(string? failure)
    {
        FlushLines();
        clock.Stop();
        elapsed.Stop();
        runner = null;
        ShaderProgress.Visibility=Visibility.Collapsed;
        if(operation=="stage-update"&&failure==null&&pendingUpdatePlan!=null){
            try{
                var preview=UpdatePreview.Read(pendingUpdatePlan);
                UpdateVersion.Text="Atualização " + preview.Version;
                UpdateChanges.Text=preview.Text;
                UpdatesNote.Text="Pacote conferido. Confira as mudanças e clique em Instalar atualização.";
                UpdatesNote.Foreground=(Brush)FindResource("InkSoft");
                operation=null;ShowPage(false);SetupPage.Visibility=Visibility.Collapsed;UpdatesPage.Visibility=Visibility.Visible;
                foreach(var nav in new[]{NavHome,NavGraphics,NavUpdates,NavTools,NavCredits})
                    nav.Foreground=(Brush)FindResource(nav==NavUpdates?"Accent":"InkSoft");
                Refresh();return;
            }catch(Exception ex){pendingUpdatePlan=null;failure="Não foi possível ler as notas: "+ex.Message;}
        }
        Navigation.IsEnabled=true;
        if(operation!=null){
            BuildTitle.Text=failure==null?"Operação concluída":"Operação interrompida";
            BuildNote.Text=failure??"Consulte o resultado nos detalhes abaixo.";
            BuildNote.Foreground=(Brush)FindResource(failure==null?"Accent":"Bad");
            operation=null;ShowLog.IsChecked=true;
            SetButtons(done:File.Exists(Path.Combine(finished,Manifest)),back:true);
        }
        else if (playing)
        {
            playing = false;
            var currentGraphics = CaptureGraphics();
            var gameGraphics = currentGraphics.FollowGameOptions(gameOptionsBeforePlay, GameGraphicsOptions.Read(finished));
            gameOptionsBeforePlay = null;
            if (gameGraphics != currentGraphics)
            {
                ApplyGraphics(gameGraphics);
                if (SaveSettings()) GraphicsNote.Text = "O launcher vai usar as mudanças salvas no F1.";
            }
            BuildTitle.Text = Local("Jogo encerrado", "Game closed");
            BuildNote.Text = failure == "cancelled" ? T(S.Cancelled) : failure ?? Local("Os registros estão na pasta diagnosticos do jogo.", "Logs are in the game's diagnosticos folder.");
            BuildNote.Foreground = (Brush)FindResource(failure == null || failure == "cancelled" ? "InkSoft" : "Bad");
            if (failure != null) ShowLog.IsChecked = true;
            SetButtons(done: true, back: true);
        }
        else if (failure == null && finished.Length > 0 && File.Exists(Path.Combine(finished, Manifest)))
        {
            foreach (var row in rows.Values) row.Done();
            BuildTitle.Text = T(S.Ready);
            BuildNote.Text = $"{finished}  ·  {T(S.BuiltIn)} {Span(elapsed.Elapsed)}";
            SetButtons(done: true, back: true);
        }
        else
        {
            BuildTitle.Text = T(failure == "cancelled" ? S.Cancelled : S.Stopped);
            BuildNote.Text = failure == "cancelled" ? T(S.CancelledNote) : failure ?? Local("O manifesto final não foi produzido. Consulte os detalhes.", "The final manifest was not produced. See details.");
            BuildNote.Foreground = (Brush)FindResource(failure == "cancelled" ? "InkSoft" : "Bad");
            if (current != null && rows.TryGetValue(current, out var row)) row.Stopped();
            ShowLog.IsChecked = true;
            SetButtons(back: true);
        }
        Refresh();
    }

    void ShowClock()
    {
        if (runner != null) BuildNote.Text = $"{(playing ? Local("Registros em diagnosticos.", "Logs in diagnosticos.") : T(S.Patience))}  {T(S.Elapsed)}: {Span(elapsed.Elapsed)}";
    }

    static string Span(TimeSpan time) => time.TotalHours >= 1 ? $"{(int)time.TotalHours} h {time.Minutes} min" : time.TotalMinutes >= 1 ? $"{time.Minutes} min" : $"{time.Seconds} s";

    void ShowPage(bool building)
    {
        Navigation.IsEnabled=!building;
        GraphicsPage.Visibility=UpdatesPage.Visibility=ToolsPage.Visibility=CreditsPage.Visibility=Visibility.Collapsed;
        SetupPage.Visibility = building ? Visibility.Collapsed : Visibility.Visible;
        BuildPage.Visibility = building ? Visibility.Visible : Visibility.Collapsed;
    }

    void SetButtons(bool cancel = false, bool done = false, bool back = false)
    {
        CancelButton.Visibility = cancel ? Visibility.Visible : Visibility.Collapsed;
        PlayButton.Visibility = OpenButton.Visibility = done ? Visibility.Visible : Visibility.Collapsed;
        BackButton.Visibility = back ? Visibility.Visible : Visibility.Collapsed;
    }

    void CancelBuild(object sender, RoutedEventArgs e) => runner?.Cancel();
    void Back(object sender, RoutedEventArgs e) { ShowPage(building: false); foreach(var nav in new[]{NavHome,NavGraphics,NavUpdates,NavTools,NavCredits})nav.Foreground=(Brush)FindResource(nav==NavHome?"Accent":"InkSoft"); Refresh(); }

    void LogToggled(object sender, RoutedEventArgs e)
    {
        var show = ShowLog.IsChecked == true;
        Log.Visibility = show ? Visibility.Visible : Visibility.Collapsed;
        ShowLog.Content = T(show ? S.HideDetails : S.ShowDetails);
        if (show) Log.ScrollToEnd();
    }

    void OpenFolder(object sender, RoutedEventArgs e)
    {
        try { Process.Start(new ProcessStartInfo(finished) { UseShellExecute = true }); }
        catch (Exception error) { BuildNote.Text = error.Message; }
    }

    void PlayExisting(object sender, RoutedEventArgs e) { finished = Path.GetFullPath(OutPath.Text); Play(sender, e); }

    void Play(object sender, RoutedEventArgs e)
    {
        var tools = Tools.Find();
        if (tools == null) { Say(T(S.ToolsMissing), "Bad"); return; }
        if (runner != null) return;
        if (!SaveSettings()) return;
        gameOptionsBeforePlay = GameGraphicsOptions.Read(finished);
        operation=null;
        playing=true;
        StageList.Visibility = Visibility.Collapsed;
        pendingLines.Clear();
        Log.Clear();
        BuildTitle.Text = Local("Executando o jogo", "Running the game");
        BuildNote.Foreground = (Brush)FindResource("InkSoft");
        ShowPage(building: true);
        SetButtons(cancel: true);
        var args=new List<string>{"--require-current-build","--out",finished,"--profile",ProfileBox.SelectedIndex switch{1=>"8gb",2=>"nitido",3=>"compatibilidade",4=>"desempenho-1600",_=>"original"}};
        try{args.AddRange(CaptureGraphics().Arguments());}   // (0.4.6) no Teste de desempenho
        catch(Exception error){playing=false;BuildNote.Text=error.Message;SetButtons(back:true);return;}
        runner=new Runner(tools,"run",args);
        runner.Line += pendingLines.Add;
        runner.Finished += failure => Queue(() => Ended(failure));
        elapsed.Restart();
        clock.Start();
        ShowClock();
        runner.Start();
    }

    void Navigate(object sender,RoutedEventArgs e){
        if(runner!=null||sender is not Button b)return;
        ShowPage(false);SetupPage.Visibility=Visibility.Collapsed;
        UIElement page=b.Tag?.ToString() switch{"graphics"=>GraphicsPage,"updates"=>UpdatesPage,"tools"=>ToolsPage,"credits"=>CreditsPage,_=>SetupPage};
        page.Visibility=Visibility.Visible;
        RefreshUpdates();
        foreach(var nav in new[]{NavHome,NavGraphics,NavUpdates,NavTools,NavCredits})nav.Foreground=(Brush)FindResource(nav==b?"Accent":"InkSoft");
    }
    static string Choice(ComboBox b)=>(b.SelectedItem as ComboBoxItem)?.Tag?.ToString()??"saved";
    static void Select(ComboBox b,string value){b.SelectedIndex=0;for(int i=0;i<b.Items.Count;i++)if(b.Items[i] is ComboBoxItem x&&x.IsEnabled&&x.Tag?.ToString()==value){b.SelectedIndex=i;break;}}
    GraphicsSettings CaptureGraphics()=>new(){Backend=Choice(BackendBox),Resolution=Choice(ResolutionBox),OutputResolution=Choice(OutputBox),Speed=Choice(SpeedBox),Upscaling=Choice(UpscaleBox),Sharpness=Choice(SharpnessBox),Framegen=Choice(FramegenBox),Pacing=Choice(PacingBox),Cache=Choice(CacheBox),FpsCounter=Choice(FpsBox),Handheld=Choice(HandheldBox)};
    void ApplyGraphics(GraphicsSettings g){g=g.NormalizeLegacyOutput();Select(BackendBox,g.Backend);Select(ResolutionBox,g.Resolution);Select(OutputBox,g.OutputResolution);Select(SpeedBox,g.Speed);Select(UpscaleBox,g.Upscaling);Select(SharpnessBox,g.Sharpness);Select(FramegenBox,g.Framegen);Select(PacingBox,g.Pacing);Select(CacheBox,g.Cache);Select(FpsBox,g.FpsCounter);Select(HandheldBox,g.Handheld);}
    void LoadSettings(){try{var s=LauncherSettings.Load(SettingsPath);if(s==null)return;if(!string.IsNullOrWhiteSpace(s.Output))OutPath.Text=s.Output;NupPath.Text=s.Nup;RomfsPath.Text=s.Romfs;ExefsPath.Text=s.Exefs;UseFolders.IsChecked=s.Folders;UseNup.IsChecked=!s.Folders;JobsBox.SelectedIndex=Math.Clamp(s.Jobs,0,8);ProfileBox.SelectedIndex=Math.Clamp(s.Profile,0,ProfileBox.Items.Count-1);LanguageBox.SelectedItem=Strings.All.FirstOrDefault(x=>x.Code==s.Language)??lang;ApplyGraphics(s.Graphics);}catch(Exception e){GraphicsNote.Text="Não foi possível ler ajustes anteriores; usando padrões: "+e.Message;}}
    bool SaveSettings(){try{new LauncherSettings{Output=OutPath.Text,Nup=NupPath.Text,Romfs=RomfsPath.Text,Exefs=ExefsPath.Text,Folders=UseFolders.IsChecked==true,Jobs=JobsBox.SelectedIndex,Profile=ProfileBox.SelectedIndex,Language=lang.Code,Graphics=CaptureGraphics()}.Save(SettingsPath);return true;}catch(Exception e){GraphicsNote.Text="Não foi possível salvar: "+e.Message;return false;}}
    void SaveGraphics(object sender,RoutedEventArgs e){if(SaveSettings())GraphicsNote.Text="Ajustes salvos. Serão aplicados ao jogar.";}
    void Preset(object sender,RoutedEventArgs e)
    {
        var p=(sender as Button)?.Tag?.ToString();
        ApplyGraphics(p=="saved"?new GraphicsSettings():GraphicsSettings.Preset(p??"smooth"));
        ProfileBox.SelectedIndex=p=="1600p"?4:0;
        GraphicsNote.Text=p=="saved"?"Os ajustes seguem as opções salvas no jogo.":
            p=="1600p"?"Saída 2560×1600, escala interna de 67% e geração de quadros desligada.":
            p=="amd-low"?"AMD básico: Full HD, escala 50%, FSR 1, portátil ligado e FPS visível. Reinicie o jogo.":
            "Perfil aplicado: Full HD, FSR 1 e FPS visível. A escala interna pode ser ajustada separadamente.";
        SaveSettings();
    }

    void RunTool(object sender,RoutedEventArgs e){
        if(runner!=null||sender is not Button{Tag:string command})return;
        var tools=Tools.Find();if(tools==null){ToolNote.Text=UpdatesNote.Text=T(S.ToolsMissing);return;}
        if(string.IsNullOrWhiteSpace(OutPath.Text))return;
        try{finished=Path.GetFullPath(OutPath.Text);}catch(Exception ex){ToolNote.Text=UpdatesNote.Text=ex.Message;return;}
        if(command=="dlss-runtime"&&MessageBox.Show(this,
            "O AkynoLeyend não inclui o runtime do NVIDIA DLSS. Este botão baixa nvngx_dlss.dll (DLSS 310.9.16) do repositório oficial "+
            "github.com/NVIDIA/DLSS, confere o SHA-256 e o guarda em %LOCALAPPDATA%\\AkynoLeyend\\ngx.\n\n"+
            "O arquivo é da NVIDIA e segue a licença NVIDIA RTX SDKs (salva como LICENSE.txt ao lado):\n"+
            "https://github.com/NVIDIA/DLSS/blob/9981c6350dc58c0ce21f024fd65e31e851c31689/LICENSE.txt\n\n"+
            "Você leu e aceita a licença da NVIDIA?","NVIDIA DLSS",MessageBoxButton.YesNo,MessageBoxImage.Question,MessageBoxResult.No)!=MessageBoxResult.Yes)return;
        if(!SaveSettings())return;operation=command;playing=false;StageList.Visibility=Visibility.Collapsed;pendingLines.Clear();Log.Clear();
        BuildTitle.Text=command=="prepare-shaders"?"Preparando shaders":command=="maintain-build"?"Atualizando build":command=="dlss-runtime"?"Baixando DLSS da NVIDIA":"Verificando e coletando";
        BuildNote.Foreground=(Brush)FindResource("InkSoft");ShowPage(true);SetButtons(cancel:true);ShowLog.IsChecked=true;
        var args=command=="doctor"?Array.Empty<string>():command=="dlss-runtime"?new[]{"--accept-nvidia-license"}:new[]{"--out",finished};
        runner=new Runner(tools,command,args);runner.Line+=pendingLines.Add;runner.Finished+=failure=>Queue(()=>Ended(failure));elapsed.Restart();clock.Start();ShowClock();runner.Start();
    }
    // Ferramentas > Exportar Save (EXPORTAR SAVES before 0.4.7): a compatible emulator save into this port's save folder (manage.py export-saves,
    // akynoleyend/saves.py). The emulator's folder is only read; the port's save goes to jogo\user\save-backups first.
    static readonly (string Name,string Label,string Where)[] SaveEmulators={
        ("fritz","Fritz (Fritchii)","%APPDATA%\\eden"),
        ("mdias","MDias (fork do Lichii)","%APPDATA%\\lichii ou %APPDATA%\\eden"),
        ("pokedinner","PokeDinner","%APPDATA%\\eden"),
        ("lichii","Lichii","%APPDATA%\\lichii ou %APPDATA%\\eden"),
    };
    string? ChooseSaveEmulator(){
        string? chosen=null;
        var dialog=new Window{Title="Exportar saves",Owner=this,WindowStartupLocation=WindowStartupLocation.CenterOwner,
            Width=Math.Min(760,SystemParameters.WorkArea.Width-32),Height=Math.Min(720,SystemParameters.WorkArea.Height-32),MinWidth=560,MinHeight=440,ResizeMode=ResizeMode.CanResize,ShowInTaskbar=false,
            WindowStyle=WindowStyle.None,UseLayoutRounding=true,SnapsToDevicePixels=true,
            Background=(Brush)FindResource("Page"),Foreground=(Brush)FindResource("Ink"),FontSize=16,FontFamily=new FontFamily("Segoe UI")};
        System.Windows.Shell.WindowChrome.SetWindowChrome(dialog,new System.Windows.Shell.WindowChrome{
            CaptionHeight=50,ResizeBorderThickness=new Thickness(6),GlassFrameThickness=new Thickness(0),CornerRadius=new CornerRadius(0),UseAeroCaptionButtons=false});
        var panel=new StackPanel{Margin=new Thickness(28,22,28,22)};
        panel.Children.Add(new TextBlock{Text="De qual emulador vem o save?",FontFamily=new FontFamily("Georgia"),FontSize=32,
            Foreground=(Brush)FindResource("AccentHover"),TextWrapping=TextWrapping.Wrap,TextAlignment=TextAlignment.Center,Margin=new Thickness(0,0,0,18)});
        panel.Children.Add(new TextBlock{Text="Escolha a origem do seu save compatível.",Style=(Style)FindResource("Note"),TextAlignment=TextAlignment.Center,Margin=new Thickness(0,0,0,22)});
        panel.Children.Add(new Border{Background=(Brush)FindResource("RaisedHover"),BorderBrush=(Brush)FindResource("Accent"),BorderThickness=new Thickness(1),CornerRadius=new CornerRadius(8),Padding=new Thickness(18),
            Child=new TextBlock{Text="Seu save atual será salvo em um backup antes da cópia.",TextWrapping=TextWrapping.Wrap,TextAlignment=TextAlignment.Center}});
        panel.Children.Add(new TextBlock{Text="Feche o jogo e o emulador antes de continuar.",Style=(Style)FindResource("Note"),TextAlignment=TextAlignment.Center,Margin=new Thickness(0,16,0,26)});
        foreach(var emulator in SaveEmulators){
            var button=new Button{Content=emulator.Label,HorizontalContentAlignment=HorizontalAlignment.Stretch,Tag=emulator.Name,Style=(Style)FindResource("Quiet"),Height=58,FontSize=19,Margin=new Thickness(0,0,0,12),
                ToolTip="Procura em "+emulator.Where+"\\nand\\user\\save"};
            var row=new Grid();row.ColumnDefinitions.Add(new ColumnDefinition{Width=new GridLength(46)});row.ColumnDefinitions.Add(new ColumnDefinition());row.ColumnDefinitions.Add(new ColumnDefinition{Width=new GridLength(24)});
            var folder=new System.Windows.Shapes.Path{Data=Geometry.Parse("M1,7 L1,2 L11,2 L15,6 L29,6 L29,23 L1,23 Z M1,7 L29,7"),Stroke=(Brush)FindResource("Accent"),StrokeThickness=1.8,Width=30,Height=26,HorizontalAlignment=HorizontalAlignment.Left,VerticalAlignment=VerticalAlignment.Center};
            var label=new TextBlock{Text=emulator.Label,FontSize=20,VerticalAlignment=VerticalAlignment.Center};Grid.SetColumn(label,1);
            var arrow=new TextBlock{Text="›",FontSize=30,Foreground=(Brush)FindResource("Accent"),VerticalAlignment=VerticalAlignment.Center};Grid.SetColumn(arrow,2);
            row.Children.Add(folder);row.Children.Add(label);row.Children.Add(arrow);button.Content=row;
            button.Click+=(_,_)=>{chosen=(string)button.Tag;dialog.DialogResult=true;};
            panel.Children.Add(button);
        }
        var cancel=new Button{Content="Cancelar",IsCancel=true,MinWidth=160,HorizontalAlignment=HorizontalAlignment.Right,Style=(Style)FindResource("Quiet"),Margin=new Thickness(0,16,0,0)};
        cancel.Click+=(_,_)=>dialog.DialogResult=false;
        var layout=new Grid();layout.RowDefinitions.Add(new RowDefinition{Height=new GridLength(50)});layout.RowDefinitions.Add(new RowDefinition());layout.RowDefinitions.Add(new RowDefinition{Height=GridLength.Auto});
        var titlebar=new Grid{Background=(Brush)FindResource("Raised"),Margin=new Thickness(0,0,0,1)};
        var title=new TextBlock{Text="Exportar saves",FontSize=18,Margin=new Thickness(24,0,64,0),VerticalAlignment=VerticalAlignment.Center};titlebar.Children.Add(title);
        var close=new Button{Content="×",Style=(Style)FindResource("Caption"),FontSize=26,HorizontalAlignment=HorizontalAlignment.Right,VerticalAlignment=VerticalAlignment.Center,ToolTip="Fechar"};
        System.Windows.Shell.WindowChrome.SetIsHitTestVisibleInChrome(close,true);close.Click+=(_,_)=>dialog.DialogResult=false;titlebar.Children.Add(close);layout.Children.Add(titlebar);
        var scroll=new ScrollViewer{VerticalScrollBarVisibility=ScrollBarVisibility.Auto,HorizontalScrollBarVisibility=ScrollBarVisibility.Disabled,Content=panel,Margin=new Thickness(0,0,8,0)};Grid.SetRow(scroll,1);layout.Children.Add(scroll);
        cancel.Margin=new Thickness(0);cancel.Height=42;
        var footer=new Border{BorderBrush=(Brush)FindResource("Line"),BorderThickness=new Thickness(0,1,0,0),Padding=new Thickness(24,14,24,14),Child=cancel};Grid.SetRow(footer,2);layout.Children.Add(footer);
        dialog.Content=new Border{BorderBrush=(Brush)FindResource("Accent"),BorderThickness=new Thickness(1),Margin=new Thickness(0),Child=layout};
        var backdrop=(UIElement)Content;
        var previousEffect=backdrop.Effect;
        try{
            backdrop.Effect=new System.Windows.Media.Effects.BlurEffect{Radius=9};
            return dialog.ShowDialog()==true?chosen:null;
        }finally{
            backdrop.Effect=previousEffect;
        }
    }
    void ExportSaves(object sender,RoutedEventArgs e){
        if(runner!=null)return;
        var tools=Tools.Find();if(tools==null){ToolNote.Text=UpdatesNote.Text=T(S.ToolsMissing);return;}
        if(string.IsNullOrWhiteSpace(OutPath.Text))return;
        try{finished=Path.GetFullPath(OutPath.Text);}catch(Exception ex){ToolNote.Text=ex.Message;return;}
        var emulator=ChooseSaveEmulator();if(emulator==null)return;
        var label=SaveEmulators.First(x=>x.Name==emulator).Label;
        if(!SaveSettings())return;operation="export-saves";playing=false;StageList.Visibility=Visibility.Collapsed;pendingLines.Clear();Log.Clear();
        BuildTitle.Text="Exportando saves do "+label;
        BuildNote.Text="Procurando o save compatível no "+label+" e copiando para "+Path.Combine(finished,"user","save")+".";
        BuildNote.Foreground=(Brush)FindResource("InkSoft");ShowPage(true);SetButtons(cancel:true);ShowLog.IsChecked=true;
        runner=new Runner(tools,"export-saves",new[]{"--emulator",emulator,"--out",finished});
        runner.Line+=pendingLines.Add;runner.Finished+=failure=>Queue(()=>Ended(failure));elapsed.Restart();clock.Start();ShowClock();runner.Start();
    }
    void UpdateBuild(object sender,RoutedEventArgs e){
        if(runner!=null)return;
        var tools=Tools.Find();if(tools==null){MessageBox.Show(this,T(S.ToolsMissing),"AkynoLeyend");return;}
        var dialog=new OpenFileDialog{Filter="Atualização AkynoLeyend (.zip)|*.zip",Title="Selecionar pacote de atualização"};
        if(dialog.ShowDialog(this)!=true)return;
        if(!SaveSettings())return;
        try{finished=Path.GetFullPath(OutPath.Text);}catch(Exception ex){UpdatesNote.Text=ex.Message;return;}
        pendingUpdatePlan=null;operation="stage-update";playing=false;
        StageList.Visibility=Visibility.Collapsed;pendingLines.Clear();Log.Clear();ShowPage(true);SetButtons(cancel:true);
        BuildTitle.Text="Conferindo atualização";BuildNote.Text="Conferindo arquivos para mostrar as novidades e correções antes de instalar.";
        var args=new List<string>{"--archive",dialog.FileName,"--out",finished};
        if(JobsBox.SelectedIndex>0)args.AddRange(new[]{"--jobs",JobsBox.SelectedIndex.ToString()});
        runner=new Runner(tools,"stage-update",args);runner.Line+=pendingLines.Add;runner.Finished+=failure=>Queue(()=>Ended(failure));
        elapsed.Restart();clock.Start();runner.Start();
    }
    // The Builder's own version (its assembly metadata), never a fixed label: the installed game is shown apart.
    static string LauncherVersion(){
        var info=(System.Reflection.Assembly.GetExecutingAssembly().GetCustomAttributes(typeof(System.Reflection.AssemblyInformationalVersionAttribute),false)
            .FirstOrDefault() as System.Reflection.AssemblyInformationalVersionAttribute)?.InformationalVersion;
        if(string.IsNullOrWhiteSpace(info))return "versão desconhecida";
        var plus=info.IndexOf('+');
        return plus>0?info[..plus]:info;
    }
    void RefreshUpdates(){
        if(ChooseUpdateButton==null)return;
        var manifest=Path.Combine(OutPath.Text,Manifest);
        var installed=File.Exists(manifest);
        InstalledVersion.Text="Jogo instalado: versão não identificada";
        if(installed)try{
            using var doc=JsonDocument.Parse(File.ReadAllText(manifest));
            if(doc.RootElement.TryGetProperty("version",out var v))InstalledVersion.Text="Jogo instalado: "+v.GetString()+"   ·   Launcher: "+LauncherVersion();
        }catch{InstalledVersion.Text="Não foi possível ler a versão do jogo instalado.";}
        ChooseUpdateButton.IsEnabled=runner==null;
        MaintainUpdateButton.IsEnabled=runner==null&&installed;
        ApplyUpdateButton.IsEnabled=runner==null&&pendingUpdatePlan!=null&&File.Exists(pendingUpdatePlan);
    }
    void ApplySelectedUpdate(object sender,RoutedEventArgs e){
        if(runner!=null||pendingUpdatePlan==null)return;
        try{
            var tools=Tools.Find()??throw new IOException(T(S.ToolsMissing));
            var info=Runner.Detached(tools,"apply-update",new[]{"--plan",pendingUpdatePlan,"--wait-pid",Environment.ProcessId.ToString()});
            if(Process.Start(info)==null)throw new IOException("O atualizador não iniciou.");
            Application.Current.Shutdown();
        }catch(Exception ex){UpdatesNote.Text="Não foi possível iniciar a atualização: "+ex.Message;UpdatesNote.Foreground=(Brush)FindResource("Bad");}
    }
    void OpenGameFolder(object sender,RoutedEventArgs e){try{Process.Start(new ProcessStartInfo(Path.GetFullPath(OutPath.Text)){UseShellExecute=true});}catch(Exception ex){ToolNote.Text=ex.Message;}}
    void OpenCredits(object sender,RoutedEventArgs e){try{Process.Start(new ProcessStartInfo(Path.Combine(Tools.Find()?.Root??AppContext.BaseDirectory,"creditos")){UseShellExecute=true});}catch(Exception ex){MessageBox.Show(this,ex.Message,"AkynoLeyend");}}

    void ToggleMaximize(object sender, RoutedEventArgs e) => WindowState = WindowState == WindowState.Maximized ? WindowState.Normal : WindowState.Maximized;
    void Minimize(object sender, RoutedEventArgs e) => WindowState = WindowState.Minimized;
    void CloseWindow(object sender, RoutedEventArgs e) => Close();

    protected override void OnClosing(CancelEventArgs e)
    {
        if (runner != null && MessageBox.Show(this,
                playing ? Local("Encerrar o jogo e fechar?", "Stop the game and close?") : T(S.CloseQuestion),
                "AkynoLeyend", MessageBoxButton.YesNo) != MessageBoxResult.Yes)
        {
            e.Cancel = true;
            return;
        }
        SaveSettings();
        ++checkSerial;
        checkDelay.Stop();
        clock.Stop();
        logPump.Stop();
        checkCancellation?.Cancel();
        runner?.Cancel();
        base.OnClosing(e);
    }
}

sealed class StageRow
{
    public readonly Grid Root = new() { Margin = new Thickness(0, 0, 0, 14) };
    readonly Ellipse dot = new() { Width = 8, Height = 8, VerticalAlignment = VerticalAlignment.Center };
    readonly TextBlock name = new();
    readonly TextBlock percent = new() { HorizontalAlignment = HorizontalAlignment.Right };
    readonly ProgressBar bar = new() { Margin = new Thickness(20, 6, 0, 0), Visibility = Visibility.Collapsed };

    public StageRow(string text)
    {
        Root.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(20) });
        Root.ColumnDefinitions.Add(new ColumnDefinition());
        Root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        Root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        name.Text = text;
        bar.Style = (Style)Application.Current.FindResource("Thin");
        percent.Foreground = Brush("InkSoft");
        Grid.SetColumn(name, 1);
        Grid.SetColumn(percent, 1);
        Grid.SetRow(bar, 1);
        Grid.SetColumnSpan(bar, 2);
        Root.Children.Add(dot);
        Root.Children.Add(name);
        Root.Children.Add(percent);
        Root.Children.Add(bar);
        Reset();
    }

    static Brush Brush(string key) => (Brush)Application.Current.FindResource(key);
    public void SetText(string text) => name.Text = text;
    public void Reset()
    {
        dot.Fill = Brush("Line"); name.Foreground = Brush("InkFaint");
        percent.Text = ""; bar.Visibility = Visibility.Collapsed; bar.IsIndeterminate = false; bar.Value = 0;
    }
    public void Begin()
    {
        dot.Fill = Brush("Ink"); name.Foreground = Brush("Ink");
        bar.Visibility = Visibility.Visible; bar.IsIndeterminate = true;
    }
    public void Progress(double fraction)
    {
        if (!double.IsFinite(fraction)) return;
        fraction = Math.Clamp(fraction, 0, 1);
        bar.Visibility = Visibility.Visible; bar.IsIndeterminate = false; bar.Value = fraction;
        percent.Text = $"{(int)(fraction * 100)}%";
    }
    public void Done()
    {
        dot.Fill = Brush("Accent"); name.Foreground = Brush("InkSoft");
        percent.Text = ""; bar.IsIndeterminate = false; bar.Visibility = Visibility.Collapsed;
    }
    public void Stopped()
    {
        dot.Fill = Brush("Bad"); name.Foreground = Brush("Ink"); bar.IsIndeterminate = false;
    }
}
