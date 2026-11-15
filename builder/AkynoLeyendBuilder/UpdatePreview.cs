using System.IO;
using System.Text.Json;

namespace AkynoLeyendBuilder;

/// Plain-text changes read only after Python has verified the selected package.
sealed record UpdatePreview(string Version, string Text)
{
    public static UpdatePreview Read(string path)
    {
        if (new FileInfo(path).Length > 4 * 1024 * 1024)
            throw new IOException("O resumo da atualização excede o limite.");
        using var doc = JsonDocument.Parse(File.ReadAllText(path));
        var root = doc.RootElement;
        var version = root.GetProperty("version").GetString();
        if (string.IsNullOrWhiteSpace(version) || version.Length > 120)
            throw new IOException("A versão do pacote é inválida.");
        var sections = new List<string>();
        if (root.TryGetProperty("notes", out var notes))
        {
            foreach (var (key, title) in new[] { ("new", "Novidades"), ("fixes", "Correções"),
                         ("experimental", "Experimental"), ("known_issues", "Limitações conhecidas") })
            {
                if (!notes.TryGetProperty(key, out var list)) continue;
                if (list.ValueKind != JsonValueKind.Array || list.GetArrayLength() > 40)
                    throw new IOException("As notas do pacote são inválidas.");
                var items = new List<string>();
                foreach (var item in list.EnumerateArray())
                {
                    var text = item.GetString();
                    if (string.IsNullOrWhiteSpace(text) || text.Length > 1000)
                        throw new IOException("Uma nota do pacote é inválida.");
                    items.Add("• " + text.Trim());
                }
                if (items.Count > 0) sections.Add(title + "\n" + string.Join("\n", items));
            }
        }
        return new(version, sections.Count > 0 ? string.Join("\n\n", sections)
            : "Este pacote não inclui uma lista de mudanças. A versão foi conferida; consulte as notas de quem o publicou.");
    }
}
