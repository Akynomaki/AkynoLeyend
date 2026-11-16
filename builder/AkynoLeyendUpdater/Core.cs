using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace AkynoLeyendUpdater;

/// An installation of a version this updater starts from (From), as found on disk (read only).
sealed record Installation(string Root, string Python, string Version, string Output, string? GameVersion);

sealed record UpdateResult(bool Success, string Message, string Details);

/// The bridge never replaces files itself: it hands the embedded package to the installation's own
/// verified updater (stage-update, then apply-update), which keeps backups and rolls back on failure.
static class Core
{
    /// (0.4.5-test.1) the versions it starts from: the Teste 4 of either branch, 0.4.4 and 0.4.5 (each accepted by the
    /// package's coherence.py by its exact sources)
    public static readonly string[] From = { "0.4.3-test.4", "0.4.4", "0.4.5", "0.4.5-test.1", "0.4.5-test.2", "0.4.5-test.3", "0.4.5-test.4", "0.4.5-test.5", "0.4.5-test.6", "0.4.5-test.7", "0.4.5-test.8", "0.4.6", "0.4.7", "0.4.8" };
    public const string To = "0.4.9";
    /// (0.4.4) how the installed version is named to the player, and this updater's log in atualizacoes/
    public const string FromName = "Teste 4, 0.4.4, 0.4.5, 0.4.5-test.1, 0.4.5-test.2, 0.4.5-test.3, 0.4.5-test.4, 0.4.5-test.5, 0.4.5-test.6, 0.4.5-test.7, 0.4.5-test.8, 0.4.6, 0.4.7 ou 0.4.8";
    public const string LogName = "atualizador-" + To + ".log";
    const string Resource = "AkynoLeyend-Atualizacao.zip";

    public static string ExpectedSha256 =>
        Assembly.GetExecutingAssembly().GetCustomAttributes<AssemblyMetadataAttribute>()
            .First(a => a.Key == "PackageSha256").Value!.ToLowerInvariant();

    public static Installation Inspect(string folder)
    {
        var root = Path.GetFullPath(folder.Trim().Trim('"'));
        string At(params string[] parts) => Path.Combine(new[] { root }.Concat(parts).ToArray());
        if (!File.Exists(At("manage.py")) || !File.Exists(At("AkynoLeyendBuilder.exe")) || !File.Exists(At("VERSION")))
            throw new InvalidOperationException("Esta pasta não é uma instalação do AkynoLeyend: escolha a pasta que contém AkynoLeyendBuilder.exe.");
        var python = At("ferramentas", "python", "python.exe");
        if (!File.Exists(python))
            throw new InvalidOperationException("Falta o Python do AkynoLeyend (ferramentas\\python). Nada foi alterado.");
        var version = File.ReadAllText(At("VERSION")).Trim();
        var output = At("jogo");
        try
        {
            using var settings = JsonDocument.Parse(File.ReadAllText(At("AkynoLeyend-launcher.json")));
            if (settings.RootElement.TryGetProperty("Output", out var chosen) && chosen.GetString() is { Length: > 0 } path
                && File.Exists(Path.Combine(path, "AkynoLeyend-build.json")))
                output = Path.GetFullPath(path);
        }
        catch (Exception e) when (e is IOException or JsonException or UnauthorizedAccessException or InvalidOperationException) { }
        string? game = null;
        try
        {
            using var manifest = JsonDocument.Parse(File.ReadAllText(Path.Combine(output, "AkynoLeyend-build.json")));
            game = manifest.RootElement.GetProperty("version").GetString();
        }
        catch (Exception e) when (e is IOException or JsonException or KeyNotFoundException or UnauthorizedAccessException or InvalidOperationException) { }
        return new(root, python, version, output, game);
    }

    /// Why this installation cannot be updated by this bridge, in plain words; null when it can.
    public static string? Problem(Installation found)
    {
        if (found.Version == To)
            return $"Esta instalação já está na versão {To}. Nada a fazer.";
        if (!From.Contains(found.Version))
            return $"Este atualizador é só para o {FromName} ({string.Join(" ou ", From)}). Versão encontrada: {found.Version}. Nada foi alterado.";
        if (found.GameVersion != null && !Directory.Exists(Path.Combine(found.Root, "work", "sa", "gen")))
            return "A pasta work desta instalação foi removida. Sem ela a atualização exigiria recompilar o jogo inteiro; nada foi alterado.";
        return null;
    }

    /// Quick look only (the launcher if open, this file's folder, a few personal folders, 3 levels, a few seconds).
    /// Anything else is chosen by the tester through a normal file window.
    public static List<string> Discover(TimeSpan budget)
    {
        var found = new List<string>();
        void Consider(string? folder)
        {
            if (folder == null) return;
            try
            {
                var full = Path.GetFullPath(folder);
                if (File.Exists(Path.Combine(full, "AkynoLeyendBuilder.exe")) && File.Exists(Path.Combine(full, "manage.py"))
                    && !found.Contains(full, StringComparer.OrdinalIgnoreCase))
                    found.Add(full);
            }
            catch (Exception e) when (e is IOException or UnauthorizedAccessException or ArgumentException or NotSupportedException) { }
        }
        foreach (var process in Process.GetProcessesByName("AkynoLeyendBuilder"))
        {
            try { Consider(Path.GetDirectoryName(process.MainModule?.FileName)); } catch (Exception) { }
            process.Dispose();
        }
        for (var directory = new DirectoryInfo(AppContext.BaseDirectory); directory != null; directory = directory.Parent)
            Consider(directory.FullName);
        var clock = Stopwatch.StartNew();
        var skip = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
            { "work", "jogo", "ferramentas", "atualizacoes", "node_modules", ".git", "AppData" };
        var profile = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        var starts = new[] { Path.Combine(profile, "Downloads"), Environment.GetFolderPath(Environment.SpecialFolder.Desktop),
            Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments) };
        var options = new EnumerationOptions { IgnoreInaccessible = true, RecurseSubdirectories = false, AttributesToSkip = FileAttributes.ReparsePoint };
        foreach (var start in starts.Where(Directory.Exists))
        {
            var queue = new Queue<(string, int)>();
            queue.Enqueue((start, 0));
            while (queue.Count > 0 && clock.Elapsed < budget)
            {
                var (folder, depth) = queue.Dequeue();
                Consider(folder);
                if (depth >= 3) continue;
                try
                {
                    foreach (var child in Directory.EnumerateDirectories(folder, "*", options))
                        if (!skip.Contains(Path.GetFileName(child))) queue.Enqueue((child, depth + 1));
                }
                catch (Exception e) when (e is IOException or UnauthorizedAccessException) { }
            }
        }
        return found;
    }

    /// Launcher or game of this installation still open (they hold files the update replaces).
    public static List<string> Blocking(Installation found)
    {
        var open = new List<string>();
        foreach (var name in new[] { "AkynoLeyendBuilder", "AkynoLeyend" })
            foreach (var process in Process.GetProcessesByName(name))
            {
                try
                {
                    var path = process.MainModule?.FileName;
                    if (path != null && path.StartsWith(found.Root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
                        open.Add(name == "AkynoLeyend" ? "o jogo" : "o launcher");
                }
                catch (Exception) { }
                process.Dispose();
            }
        return open.Distinct().ToList();
    }

    public static Stream OpenPackage() =>
        Assembly.GetExecutingAssembly().GetManifestResourceStream(Resource)
        ?? throw new InvalidOperationException("O pacote de atualização não está dentro deste executável.");

    /// Release notes read from the embedded package index (plain text, bounded).
    public static AkynoLeyendBuilder.UpdatePreview Preview()
    {
        var temporary = Path.Combine(Path.GetTempPath(), "AkynoLeyend-indice-" + Guid.NewGuid().ToString("N") + ".json");
        try
        {
            using (var archive = new ZipArchive(OpenPackage(), ZipArchiveMode.Read))
            using (var index = (archive.GetEntry("update-package.json") ?? throw new InvalidDataException("Pacote sem índice.")).Open())
            using (var file = File.Create(temporary))
                index.CopyTo(file);
            return AkynoLeyendBuilder.UpdatePreview.Read(temporary);
        }
        finally { File.Delete(temporary); }
    }

    /// Every file of the package against its index (names, count and SHA-256), before the installation sees it.
    static void VerifyIndex(string archivePath)
    {
        using var archive = ZipFile.OpenRead(archivePath);
        var indexEntry = archive.GetEntry("update-package.json") ?? throw new InvalidDataException("Pacote sem índice.");
        using var index = JsonDocument.Parse(indexEntry.Open());
        if (index.RootElement.GetProperty("version").GetString() != To)
            throw new InvalidDataException("O pacote embutido não é da versão " + To + ".");
        var expected = index.RootElement.GetProperty("files").EnumerateObject().ToDictionary(f => f.Name, f => f.Value.GetString());
        var entries = archive.Entries.Where(e => e.FullName != "update-package.json").ToList();
        if (entries.Count != expected.Count)
            throw new InvalidDataException("O pacote tem arquivos fora do índice.");
        foreach (var entry in entries)
        {
            if (!expected.TryGetValue(entry.FullName, out var digest))
                throw new InvalidDataException("Arquivo fora do índice: " + entry.FullName);
            using var stream = entry.Open();
            if (Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant() != digest)
                throw new InvalidDataException("Arquivo danificado no pacote: " + entry.FullName);
        }
    }

    /// Normal user permissions are enough; explain instead of asking for administrator rights.
    static string? WriteProblem(Installation found)
    {
        foreach (var folder in new[] { found.Root, Path.Combine(found.Root, "ferramentas", "prebuilt"), found.Output,
                                       Path.Combine(found.Root, "work", "sa", "build") })
        {
            if (!Directory.Exists(folder)) continue;
            var probe = Path.Combine(folder, ".akynoleyend-gravacao-" + Guid.NewGuid().ToString("N"));
            try { File.WriteAllText(probe, "ok"); File.Delete(probe); }
            catch (Exception e) when (e is IOException or UnauthorizedAccessException)
            {
                return "Sem permissão para gravar em \"" + folder + "\". Não mova a pasta: feche programas que a usem " +
                       "ou ajuste a permissão dela para o seu usuário. Nada foi alterado.";
            }
        }
        return null;
    }

    static async Task<string> ExtractPackage(string folder)
    {
        Directory.CreateDirectory(folder);
        var path = Path.Combine(folder, "AkynoLeyend-Atualizacao-" + To + ".zip");
        using var hash = SHA256.Create();
        await using (var source = OpenPackage())
        await using (var target = File.Create(path))
        await using (var crypto = new CryptoStream(target, hash, CryptoStreamMode.Write))
            await source.CopyToAsync(crypto);
        var actual = Convert.ToHexString(hash.Hash!).ToLowerInvariant();
        if (actual != ExpectedSha256)
            throw new InvalidOperationException("O pacote dentro do atualizador está danificado (SHA-256 diferente). Baixe o atualizador de novo; nada foi alterado.");
        return path;
    }

    /// Runs the installation's own manage.py with both pipes drained. The exit is awaited without waiting
    /// for EOF: apply-update restarts the launcher, which must not keep this call open.
    static async Task<int> Run(Installation found, IEnumerable<string> arguments, Action<string> line)
    {
        var info = new ProcessStartInfo(found.Python)
        {
            WorkingDirectory = found.Root, UseShellExecute = false, CreateNoWindow = true,
            RedirectStandardOutput = true, RedirectStandardError = true,
            StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8,
        };
        foreach (var argument in new[] { "-I", "-X", "utf8", "-u", Path.Combine(found.Root, "manage.py") }.Concat(arguments))
            info.ArgumentList.Add(argument);
        using var process = Process.Start(info) ?? throw new InvalidOperationException("O Python do AkynoLeyend não iniciou.");
        async Task Drain(StreamReader reader)
        {
            try { for (string? text; (text = await reader.ReadLineAsync()) != null;) line(text); }
            catch (Exception e) when (e is IOException or ObjectDisposedException) { }
        }
        var readers = Task.WhenAll(Drain(process.StandardOutput), Drain(process.StandardError));
        await Task.Run(() => process.WaitForExit(int.MaxValue));
        await Task.WhenAny(readers, Task.Delay(TimeSpan.FromSeconds(5)));
        return process.ExitCode;
    }

    public static async Task<UpdateResult> Update(Installation found, Action<string> report)
    {
        var problem = Problem(found);
        if (problem != null) return new(false, problem, "");
        var open = Blocking(found);
        if (open.Count > 0) return new(false, "Feche " + string.Join(" e ", open) + " desta instalação e tente de novo. Nada foi alterado.", "");
        var unwritable = WriteProblem(found);
        if (unwritable != null) return new(false, unwritable, "");
        var drive = new DriveInfo(Path.GetPathRoot(found.Root)!);
        if (drive.AvailableFreeSpace < 1L << 30)
            return new(false, "Espaço livre insuficiente: são necessários pelo menos 1 GB no disco da instalação. Nada foi alterado.", "");
        var details = new StringBuilder();
        var clock = Stopwatch.StartNew();
        void Log(string text)
        {
            var stamped = $"{clock.Elapsed.TotalSeconds,7:0.0}s  {text}";
            details.AppendLine(stamped);
            report(stamped);
        }
        var temporary = Path.Combine(Path.GetTempPath(), "AkynoLeyend-Atualizador-" + Guid.NewGuid().ToString("N"));
        try
        {
            Log($"Instalação: {found.Root} ({found.Version}; jogo {found.GameVersion ?? "não criado"})");
            Log("Conferindo o pacote embutido...");
            var archive = await ExtractPackage(temporary);
            VerifyIndex(archive);
            Log("Pacote íntegro (SHA-256 " + ExpectedSha256 + "); todos os arquivos conferem com o índice.");
            string? plan = null;
            var staged = await Run(found, new[] { "stage-update", "--archive", archive, "--out", found.Output }, text =>
            {
                if (text.StartsWith("@@update_plan ")) plan = text["@@update_plan ".Length..].Trim();
                Log(text);
            });
            if (staged != 0 || plan == null || !File.Exists(plan))
                return new(false, "A instalação recusou o pacote antes de alterar qualquer arquivo. Consulte os detalhes.", details.ToString());
            Log("Aplicando (o próprio atualizador da instalação guarda cópia dos arquivos e reverte em caso de falha)...");
            string? error = null;
            var applied = await Run(found, new[] { "apply-update", "--plan", plan, "--wait-pid", "0" }, text =>
            {
                if (text.StartsWith("@@error ")) error = text["@@error ".Length..];
                Log(text);
            });
            var after = Inspect(found.Root);
            if (applied != 0 || after.Version != To || (found.GameVersion != null && after.GameVersion != To))
            {
                var reverted = after.Version == found.Version ? "Os arquivos anteriores foram restaurados." : "Verifique a instalação: a versão ficou " + after.Version + ".";
                return new(false, "A atualização foi interrompida. " + reverted + (error != null ? " Motivo: " + error : "")
                    + " Registro: " + Path.Combine(found.Root, "atualizacoes", LogName), details.ToString());
            }
            var verified = new StringBuilder();
            var check = await Run(found, new[] { "run", "--out", found.Output, "--dry-run" }, text => { verified.AppendLine(text); Log(text); });
            var dll = Path.Combine(found.Output, "AkynoLeyend.dll");
            var prebuilt = Path.Combine(found.Root, "ferramentas", "prebuilt", "AkynoLeyend.dll");
            if (found.GameVersion != null && (check != 0 || !verified.ToString().Contains("Verificacao concluida")
                || !File.Exists(dll) || Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(dll))) != Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(prebuilt)))))
                return new(false, "A atualização foi aplicada, mas a conferência final do jogo (hashes e par EXE/DLL) falhou. Consulte o registro: "
                    + Path.Combine(found.Root, "atualizacoes", LogName), details.ToString());
            var summary = "";
            try
            {
                using var compiled = JsonDocument.Parse(File.ReadAllText(Path.Combine(found.Root, "work", "logs", "compile-summary.json")));
                var r = compiled.RootElement;
                summary = $" Componentes recompilados: {r.GetProperty("compiled").GetInt32()}; reaproveitados: {r.GetProperty("local_hits").GetInt32() + r.GetProperty("shared_hits").GetInt32()}; renderizador pronto: {(r.GetProperty("renderer_prebuilt").GetBoolean() ? "sim" : "não")}.";
            }
            catch (Exception e) when (e is IOException or JsonException or KeyNotFoundException or InvalidOperationException) { }
            Log("Concluído em " + clock.Elapsed.TotalSeconds.ToString("0") + " s.");
            return new(true, $"Atualizado para {To} em {clock.Elapsed.TotalSeconds:0} s. O jogo não foi recompilado; saves e configurações preservados.{summary} O launcher novo foi aberto.", details.ToString());
        }
        catch (Exception e) when (e is IOException or UnauthorizedAccessException or InvalidOperationException or InvalidDataException
                                       or JsonException or KeyNotFoundException or System.ComponentModel.Win32Exception)
        {
            Log("Erro: " + e.Message);
            var now = Inspect(found.Root);
            return new(false, e.Message + (now.Version == found.Version ? " A instalação continua na versão " + found.Version + "." : ""), details.ToString());
        }
        finally
        {
            try { Directory.Delete(temporary, true); } catch (Exception) { }
            try
            {
                var logs = Path.Combine(found.Root, "atualizacoes");
                Directory.CreateDirectory(logs);
                File.WriteAllText(Path.Combine(logs, LogName), details.ToString(), Encoding.UTF8);
            }
            catch (Exception) { }
        }
    }
}
