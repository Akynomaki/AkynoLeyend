using System.Diagnostics;
using AkynoLeyendBuilder;

if (args.Length != 1) throw new ArgumentException("Pass the Python executable as the only argument.");
var python = args[0];
var folder = Path.Combine(Path.GetTempPath(), "akynoleyend runner ç " + Guid.NewGuid());
Directory.CreateDirectory(folder);
var passed = 0;
void Require(bool condition, string message)
{
    if (!condition) throw new Exception(message);
}
async Task Check(string name, Func<Task> action)
{
    await action();
    Console.WriteLine("PASS " + name);
    passed++;
}
var tools = new Tools(folder, python);
try
{
    await Check("graphics settings roundtrip, exact arguments and corrupt settings rejection", () =>
    {
        var path = Path.Combine(folder, "settings.json");
        var graphics = new GraphicsSettings { Resolution = "100", Speed = "realtime", Upscaling = "lanczos", Sharpness = "10", Framegen = "0", Pacing = "on", Cache = "streaming" };
        var expected = new[] { "--backend", "vulkan", "--resolution", "100", "--speed", "realtime", "--upscaling", "lanczos", "--sharpness", "10", "--framegen", "0", "--pacing", "on", "--cache-mode", "streaming" };
        Require(graphics.Arguments().SequenceEqual(expected), "The renderer arguments changed.");
        // (0.4.5-test.1) Dinâmica goes out as --framegen 9, which akynoleyend/cli.py takes; any other value is still refused
        var dynamicArgs = (graphics with { Framegen = "9" }).Arguments();
        Require(dynamicArgs.SequenceEqual(expected.Select(a => a == "0" ? "9" : a)), "Dynamic frame generation did not go out as --framegen 9.");
        var unknown = false;
        try { (graphics with { Framegen = "10" }).Arguments(); }
        catch (InvalidOperationException) { unknown = true; }
        Require(unknown, "An unknown frame generation value was accepted.");
        // (0.4.6) the launcher's Teste de desempenho is gone: no measurement arguments to check
        var saved = new LauncherSettings { Output = "D:\\cópia com espaços", Profile = 3, Graphics = graphics };
        saved.Save(path);
        Require(LauncherSettings.Load(path) == saved, "The settings did not roundtrip.");
        Require(Directory.GetFiles(folder, "*.tmp").Length == 0, "An atomic staging file leaked.");
        var refused = false;
        try { (graphics with { Backend = "opengl" }).Arguments(); }
        catch (InvalidOperationException) { refused = true; }
        Require(refused, "Unsupported OpenGL must not start Vulkan silently.");
        File.WriteAllText(path, "{ broken JSON");
        refused = false;
        try { LauncherSettings.Load(path); }
        catch (System.Text.Json.JsonException) { refused = true; }
        Require(refused, "Corrupt settings were accepted.");
        File.Delete(path);
        return Task.CompletedTask;
    });
    await Check("experimental scales and balanced cache persist and reach the CLI", () =>
    {
        var path = Path.Combine(folder, "experimental.json");
        foreach (var scale in new[] { "125", "150" })
        {
            var graphics = new GraphicsSettings { Resolution = scale, Cache = "equilibrado" };
            var saved = new LauncherSettings { Graphics = graphics };
            saved.Save(path);
            var restored = LauncherSettings.Load(path);
            Require(restored == saved, "Experimental settings did not roundtrip.");
            Require(restored!.Graphics.Arguments().SequenceEqual(new[] {
                "--backend", "vulkan", "--resolution", scale, "--cache-mode", "equilibrado"
            }), "Experimental settings did not reach the CLI.");
        }
        File.Delete(path);
        return Task.CompletedTask;
    });
    await Check("native outputs and FSR persist and reach the CLI", () =>
    {
        var path = Path.Combine(folder, "native-fsr.json");
        foreach (var resolution in new[] { "native-1440", "native-4k" })
        {
            var graphics = new GraphicsSettings { Resolution = resolution, Upscaling = "fsr", Framegen = "0" };
            var arguments = graphics.Arguments();
            Require(arguments.Contains(resolution) && arguments.Contains("fsr"), "Output or FSR argument lost.");
            new LauncherSettings { Graphics = graphics }.Save(path);
            Require(LauncherSettings.Load(path)?.Graphics == graphics, "Native/FSR settings did not roundtrip.");
        }
        File.Delete(path);
        return Task.CompletedTask;
    });
    await Check("update preview separates additions, fixes and experimental changes", () =>
    {
        var path=Path.Combine(folder,"update-preview.json");
        File.WriteAllText(path,"{\"version\":\"0.4.3-test.4\",\"notes\":{\"new\":[\"Controles\"],\"fixes\":[\"FPS estável\"],\"experimental\":[\"Write-back em teste\"]}}");
        var preview=UpdatePreview.Read(path);
        Require(preview.Version=="0.4.3-test.4"&&preview.Text.Contains("Novidades")&&preview.Text.Contains("Correções")&&preview.Text.Contains("Experimental"),"Preview sections lost.");
        File.WriteAllText(path,"{\"version\":\"legacy\"}");
        Require(UpdatePreview.Read(path).Text.Contains("não inclui"),"Legacy package changes invented.");
        File.WriteAllText(path,"{\"version\":\"broken\",\"notes\":{\"new\":[12]}}");
        var refused=false;try{UpdatePreview.Read(path);}catch{refused=true;}
        Require(refused,"Malformed changes accepted.");
        File.Delete(path);return Task.CompletedTask;
    });
    await Check("every language contains all interface messages", () =>
    {
        Require(Strings.All.Select(language => language.Code).Distinct().Count() == Strings.All.Length, "Duplicate language code.");
        foreach (var language in Strings.All)
            Require(language.Text.Length == Enum.GetValues<S>().Length, "Incomplete language: " + language.Code);
        return Task.CompletedTask;
    });
    await Check("FSR preset separates output from internal scale and restores light settings", () =>
    {
        var g = GraphicsSettings.FsrPreset();
        var args = g.Arguments();
        Require(g.Resolution == "67" && g.OutputResolution == "1080p" && g.Upscaling == "fsr", "FSR preset mismatch.");
        Require(g.Sharpness == "10" && g.Framegen == "0" && g.Cache == "equilibrado", "Heavy previous options leaked.");
        Require(Array.IndexOf(args,"--output-resolution") >= 0 && args.Contains("1080p"), "Output did not reach CLI.");
        Require(g.FpsCounter=="on"&&args.Contains("--fps-counter"), "FPS counter missing from preset.");
        var path = Path.Combine(folder,"fsr-settings.json");
        new LauncherSettings { Graphics=g }.Save(path);
        Require(LauncherSettings.Load(path)?.Graphics == g, "Independent output did not roundtrip.");
        var legacy = new GraphicsSettings {Resolution="native-4k"}.NormalizeLegacyOutput();
        Require(legacy.Resolution=="100" && legacy.OutputResolution=="4k", "Legacy native output did not migrate.");
        return Task.CompletedTask;
    });
    await Check("AMD basic and three graphics presets retain Full HD, FSR and FPS", () => {
        foreach(var name in new[]{"amd-low","smooth","balanced","quality"}){
            var g=GraphicsSettings.Preset(name);
            Require(g.OutputResolution=="1080p"&&g.Upscaling=="fsr"&&g.FpsCounter=="on", "Preset defaults missing.");
            Require(g.Handheld==(name=="amd-low"?"on":"off"), "Handheld profile not explicit.");
            Require(g.Framegen=="0", "Frame generation should remain off in baseline presets.");
            Require(g.Arguments().Contains("--handheld"), "Handheld did not reach CLI.");
        }
        Require(GraphicsSettings.Preset("amd-low").Resolution=="50", "Weak-PC internal scale missing.");
        return Task.CompletedTask;
    });
    await Check("720p, 1600p and all selectable FSR modes reach the runtime", () =>
    {
        foreach (var output in new[] { "720p", "1600p" })
            foreach (var mode in new[] { "fsr", "fsr-temporal", "fsr-native-aa", "fsr4", "fsr4-native-aa" })
            {
                var graphics = new GraphicsSettings { OutputResolution=output, Upscaling=mode, Resolution="67", Handheld="on" };
                var argv = graphics.Arguments();
                Require(argv[Array.IndexOf(argv,"--output-resolution")+1]==output, "Output choice lost.");
                Require(argv[Array.IndexOf(argv,"--upscaling")+1]==mode, "FSR choice lost.");
                Require(argv[Array.IndexOf(argv,"--resolution")+1]==(mode.EndsWith("-native-aa")?"100":"67"), "Wrong render scale.");
                Require(argv[Array.IndexOf(argv,"--handheld")+1]==(output=="1600p"?"off":"on"), "Wrong portable mode.");
            }
        var preset=GraphicsSettings.Preset("1600p");
        Require(preset.OutputResolution=="1600p"&&preset.Resolution=="67"&&preset.Upscaling=="lanczos"&&preset.Framegen=="0",
            "1600p profile mismatch.");
        var dlss=GraphicsSettings.Preset("1600p-dlss");
        Require(dlss.Arguments().SequenceEqual(new[]{"--backend", "vulkan", "--resolution", "67", "--output-resolution", "1600p",
            "--speed", "realtime", "--upscaling", "dlss", "--sharpness", "10", "--framegen", "0", "--pacing", "on",
            "--fps-counter", "on", "--handheld", "off", "--cache-mode", "equilibrado"}), "The 1600p DLSS preset arguments changed.");
        var dlaa=dlss with {Upscaling="dlaa"};
        var dlaaArgs=dlaa.Arguments();
        Require(dlaaArgs[Array.IndexOf(dlaaArgs,"--resolution")+1]=="100", "Explicit DLAA lost native rendering.");
        return Task.CompletedTask;
    });
    await Check("a saved F1 change takes priority on the next play", () =>
    {
        var path=Path.Combine(folder,"AkynoLeyend_opts.ini");
        var graphics=new GraphicsSettings { OutputResolution="1440p", Upscaling="dlaa", Resolution="100" };
        File.WriteAllText(path,"output_resolution=1\r\nresolution=1\r\nupscaler=dlaa\r\n");
        var before=GameGraphicsOptions.Read(folder);
        Require(before?.Upscaling=="dlaa"&&graphics.FollowGameOptions(before,before)==graphics, "Existing choice changed.");
        File.WriteAllText(path,"output_resolution=5\r\nresolution=4\r\nupscaler=fsr-temporal\r\n");
        var after=GameGraphicsOptions.Read(folder);
        Require(after?.OutputResolution=="1600p"&&after.Resolution=="50", "F1 options unreadable.");
        var next=graphics.FollowGameOptions(before,after);
        Require(next.OutputResolution=="saved"&&next.Upscaling=="saved"&&next.Resolution=="saved", "Launcher would override F1.");
        File.Delete(path);
        return Task.CompletedTask;
    });
    await Check("UI log bursts remain bounded and keep completion and errors in order", () =>
    {
        var buffer = new UiLogBuffer();
        buffer.Add("@@stage compile Compiling");
        for (var i=0;i<50000;i++) buffer.Add("line "+i+new string('x',300));
        buffer.Add("@@error preserve this error");
        buffer.Add("@@done completed folder");
        var lines=buffer.Drain();
        Require(lines.Length <= UiLogBuffer.MaximumLines+3,"UI queue grew without a bound.");
        Require(lines.Sum(x=>x.Length) <= UiLogBuffer.MaximumCharacters+100,"UI character budget exceeded.");
        Require(lines[0].StartsWith("@@stage") && lines[^2].StartsWith("@@error") && lines[^1].StartsWith("@@done"),"Control order was lost.");
        Require(buffer.Drain().Length==0,"Drain did not clear the pending preview.");
        return Task.CompletedTask;
    });
    File.WriteAllText(Path.Combine(folder, "manage.py"), """
        import json, sys, time
        print('UTF8_MODE=' + str(sys.flags.utf8_mode), flush=True)
        if '--sleep' in sys.argv:
            print('ready', flush=True)
            time.sleep(30)
        elif sys.argv[1] == 'check':
            print('@@check ok e0f3ccfa', flush=True)
            sys.exit(23 if '--bad' in sys.argv else 0)
        else:
            print(json.dumps(sys.argv[2:], ensure_ascii=False), flush=True)
            for n in range(1200):
                print('output ' + str(n))
                print('error ' + str(n), file=sys.stderr)
            print('@@error failure from stderr', file=sys.stderr)
            sys.exit(23)
        """);
    await Check("local tool discovery from a nested folder", () =>
    {
        var nested = Path.Combine(folder, "app", "nested");
        Directory.CreateDirectory(nested);
        Require(Tools.Find(nested) == null, "Must not fall back to system Python.");
        var bundled = Path.Combine(folder, "ferramentas", "python");
        Directory.CreateDirectory(bundled);
        File.WriteAllText(Path.Combine(bundled, "python.exe"), "fixture");
        Require(Tools.Find(nested)?.Root == folder, "Package root was not found.");
        return Task.CompletedTask;
    });
    await Check("spaces and metacharacters remain one argument; both pipes drain", async () =>
    {
        const string argument = "D:\\cópia com espaços\\a & b;$literal.nup";
        var lines = new List<string>();
        var status = await Runner.Execute(Runner.Info(tools, "build", new[] { argument }), lines.Add, CancellationToken.None);
        Require(status == 23, "Exit code was lost.");
        Require(lines.Count == 2403, "A pipe was truncated or not drained.");
        Require(lines.Contains("UTF8_MODE=1"), "The Python child did not enable UTF-8.");
        Require(lines.Any(line => line.Contains("cópia com espaços")), "Unicode was changed in transit.");
        Require(lines.Any(line => line.Contains("a & b;$literal.nup")), "An argument was changed.");
        Require(lines.Contains("@@error failure from stderr"), "stderr error was lost.");
    });
    await Check("check success requires a zero exit code", async () =>
    {
        var good = await Runner.Check(tools, Array.Empty<string>(), CancellationToken.None);
        var bad = await Runner.Check(tools, new[] { "--bad" }, CancellationToken.None);
        Require(good.Ok && !bad.Ok, "A failing check was accepted.");
    });
    await Check("cancellation terminates an active process", async () =>
    {
        using var stop = new CancellationTokenSource(TimeSpan.FromSeconds(3));
        var elapsed = Stopwatch.StartNew();
        var cancelled = false;
        try
        {
            await Runner.Execute(Runner.Info(tools, "build", new[] { "--sleep" }),
                line => { if (line == "ready") stop.Cancel(); }, stop.Token);
        }
        catch (OperationCanceledException) { cancelled = true; }
        Require(cancelled && elapsed.Elapsed < TimeSpan.FromSeconds(5), "Cancellation did not stop the process.");
    });
    await Check("cancel before start does not spawn the child", async () =>
    {
        var process = new Runner(tools, "build", new[] { "--sleep" });
        var completion = new TaskCompletionSource<string?>(TaskCreationOptions.RunContinuationsAsynchronously);
        process.Finished += failure => completion.TrySetResult(failure);
        process.Cancel();
        process.Start();
        Require(await completion.Task.WaitAsync(TimeSpan.FromSeconds(3)) == "cancelled", "Early cancellation was lost.");
    });
    await Check("the detached updater really starts (no output encoding without redirection)", async () =>
    {
        var info = Runner.Detached(tools, "apply-update", new[] { "--plan", "nao-existe.json", "--wait-pid", "0" });
        Require(!info.RedirectStandardOutput && !info.RedirectStandardError, "The updater must not depend on the launcher's pipes.");
        info.CreateNoWindow = true;   // (only for this check: no console flashes while testing)
        using var child = Process.Start(info) ?? throw new Exception("The updater did not start.");
        await child.WaitForExitAsync().WaitAsync(TimeSpan.FromSeconds(30));
        Require(child.HasExited, "The detached updater did not finish.");
    });
    Console.WriteLine($"{passed} runner checks passed.");
}
finally { Directory.Delete(folder, recursive: true); }
