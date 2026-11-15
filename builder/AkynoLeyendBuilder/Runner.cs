using System.Diagnostics;
using System.IO;
using System.Text;

namespace AkynoLeyendBuilder;

/// The frontend always uses the Python shipped with this project.
sealed record Tools(string Root, string Python)
{
    public static Tools? Find(string? start = null)
    {
        for (var directory = new DirectoryInfo(start ?? AppContext.BaseDirectory);
             directory != null; directory = directory.Parent)
        {
            var python = Path.Combine(directory.FullName, "ferramentas", "python", "python.exe");
            if (File.Exists(Path.Combine(directory.FullName, "manage.py")) && File.Exists(python))
                return new Tools(directory.FullName, python);
        }
        return null;
    }
}

/// One CLI process, with both pipes drained and cancellation of its whole process tree.
sealed class Runner
{
    readonly ProcessStartInfo info;
    readonly CancellationTokenSource cancellation = new();
    int started;

    public event Action<string>? Line;
    public event Action<string?>? Finished;

    public Runner(Tools tools, string command, IEnumerable<string> arguments) =>
        info = Info(tools, command, arguments);

    internal static ProcessStartInfo Info(Tools tools, string command, IEnumerable<string> arguments)
    {
        var info = new ProcessStartInfo(tools.Python)
        {
            WorkingDirectory = tools.Root,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
        };
        info.ArgumentList.Add("-I");
        // -I ignores PYTHON* environment variables, so select UTF-8 on the command line.
        info.ArgumentList.Add("-X");
        info.ArgumentList.Add("utf8");
        info.ArgumentList.Add("-u");
        info.ArgumentList.Add(Path.Combine(tools.Root, "manage.py"));
        info.ArgumentList.Add(command);
        foreach (var argument in arguments) info.ArgumentList.Add(argument);
        return info;
    }

    /// A child that outlives the launcher (the updater): its own console, nothing redirected.
    /// .NET refuses a start with an output encoding but no redirection, so the encodings are cleared too.
    internal static ProcessStartInfo Detached(Tools tools, string command, IEnumerable<string> arguments)
    {
        var info = Info(tools, command, arguments);
        info.CreateNoWindow = false;
        info.RedirectStandardOutput = false;
        info.RedirectStandardError = false;
        info.StandardOutputEncoding = null;
        info.StandardErrorEncoding = null;
        return info;
    }

    internal static async Task<int> Execute(ProcessStartInfo info, Action<string> report,
                                             CancellationToken cancellation)
    {
        cancellation.ThrowIfCancellationRequested();
        using var process = Process.Start(info) ?? throw new IOException("Processo não iniciado.");
        using var registration = cancellation.Register(() =>
        {
            try { process.Kill(entireProcessTree: true); }
            catch (InvalidOperationException) { }
            catch (System.ComponentModel.Win32Exception) { }
        });
        var gate = new object();
        async Task Drain(StreamReader stream)
        {
            while (await stream.ReadLineAsync() is { } line)
                lock (gate) report(line);
        }
        await Task.WhenAll(Drain(process.StandardOutput), Drain(process.StandardError), process.WaitForExitAsync());
        cancellation.ThrowIfCancellationRequested();
        return process.ExitCode;
    }

    public void Start()
    {
        if (Interlocked.Exchange(ref started, 1) != 0) throw new InvalidOperationException("Runner já iniciado.");
        _ = Task.Run(async () =>
        {
            string? failure = null;
            try
            {
                var status = await Execute(info, line =>
                {
                    if (line.StartsWith("@@error ")) failure = line[8..];
                    Line?.Invoke(line);
                }, cancellation.Token);
                if (status != 0) failure ??= $"O processo encerrou com código {status}. Consulte os detalhes.";
            }
            catch (OperationCanceledException) { failure = "cancelled"; }
            catch (Exception error) { failure = "Não foi possível executar as ferramentas: " + error.Message; }
            Finished?.Invoke(failure);
        });
    }

    public void Cancel() => cancellation.Cancel();

    public static async Task<(bool Ok, string Text)> Check(Tools tools, IEnumerable<string> arguments,
                                                          CancellationToken cancellation)
    {
        var result = (Ok: false, Text: "Não foi possível conferir a entrada.");
        try
        {
            var status = await Execute(Info(tools, "check", arguments), line =>
            {
                if (line.StartsWith("@@check ok ")) result = (true, line[11..]);
                else if (line.StartsWith("@@error ")) result = (false, line[8..]);
            }, cancellation);
            return status == 0 ? result : (false, result.Ok ? $"Verificação encerrou com código {status}." : result.Text);
        }
        catch (OperationCanceledException) { return (false, "A verificação foi cancelada ou excedeu o tempo limite."); }
        catch (Exception error) { return (false, "Não foi possível conferir a entrada: " + error.Message); }
    }
}
