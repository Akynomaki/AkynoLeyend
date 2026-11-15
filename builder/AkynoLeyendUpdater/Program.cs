using System.IO;
using System.Text;
using System.Windows;

namespace AkynoLeyendUpdater;

static class Program
{
    /// Without arguments: the window for testers. With --pasta (used to test this same code path):
    /// --pasta <instalacao> --registro <arquivo>  updates without a window and writes the result.
    /// --pasta <instalacao> --somente-conferir --registro <arquivo>  inspects and verifies the package only.
    [STAThread]
    static int Main(string[] args)
    {
        var folder = Value(args, "--pasta");
        if (folder == null)
        {
            var app = new Application { ShutdownMode = ShutdownMode.OnMainWindowClose };
            return app.Run(new UpdaterWindow());
        }
        var log = Value(args, "--registro") ?? Path.Combine(Path.GetTempPath(), "AkynoLeyend-Atualizador.log");
        var text = new StringBuilder();
        int code;
        try
        {
            var found = Core.Inspect(folder);
            text.AppendLine($"instalacao={found.Root} versao={found.Version} jogo={found.GameVersion} saida={found.Output}");
            if (args.Contains("--somente-conferir"))
            {
                var preview = Core.Preview();
                text.AppendLine("pacote=" + preview.Version + " problema=" + (Core.Problem(found) ?? "nenhum"));
                code = 0;
            }
            else
            {
                var result = Core.Update(found, _ => { }).GetAwaiter().GetResult();
                text.AppendLine(result.Details);
                text.AppendLine((result.Success ? "SUCESSO: " : "FALHA: ") + result.Message);
                code = result.Success ? 0 : 1;
            }
        }
        catch (Exception e)
        {
            text.AppendLine("FALHA: " + e.Message);
            code = 2;
        }
        File.WriteAllText(log, text.ToString(), Encoding.UTF8);
        return code;
    }

    static string? Value(string[] args, string name)
    {
        var at = Array.IndexOf(args, name);
        return at >= 0 && at + 1 < args.Length ? args[at + 1] : null;
    }
}
