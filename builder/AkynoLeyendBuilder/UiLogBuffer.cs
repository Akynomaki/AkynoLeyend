namespace AkynoLeyendBuilder;

// Keep complete logs in Python's run files; bound only the live UI preview.
sealed class UiLogBuffer
{
    readonly object gate = new();
    readonly Queue<(long Sequence, string Text)> messages = new();
    readonly Queue<(long Sequence, string Text)> controls = new();
    long sequence;
    int characters;
    public const int MaximumCharacters = 128000;
    public const int MaximumLines = 512;

    public void Add(string line)
    {
        lock (gate)
        {
            if (line.Length > 16000) line = line[..16000];
            var item = (++sequence, line);
            if (line.StartsWith("@@")) controls.Enqueue(item);
            else
            {
                messages.Enqueue(item);
                characters += line.Length;
                while (messages.Count > MaximumLines || characters > MaximumCharacters)
                    characters -= messages.Dequeue().Text.Length;
            }
        }
    }

    public string[] Drain()
    {
        lock (gate)
        {
            var result = controls.Concat(messages).OrderBy(x => x.Sequence).Select(x => x.Text).ToArray();
            controls.Clear(); messages.Clear(); characters = 0;
            return result;
        }
    }

    public void Clear()
    {
        lock (gate) { controls.Clear(); messages.Clear(); characters = 0; }
    }
}
