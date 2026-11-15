using System.ComponentModel;
using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using Microsoft.Win32;

namespace AkynoLeyendUpdater;

/// One window: find or choose the installation, read the notes, update, follow the progress.
sealed class UpdaterWindow : Window
{
    static Brush Hex(string color) => (Brush)new BrushConverter().ConvertFromString(color)!;
    static readonly Brush Page = Hex("#090909"), Raised = Hex("#141310"), Line = Hex("#322B1D"), Ink = Hex("#F1EDE4"),
        InkSoft = Hex("#B4ADA0"), InkFaint = Hex("#7E776A"), Accent = Hex("#D6AD51"), AccentInk = Hex("#171208"),
        Bad = Hex("#E2776B"), Good = Hex("#9CCB7A");

    readonly ComboBox installations = new() { MinHeight = 34, FontSize = 13, Padding = new Thickness(8, 4, 8, 4) };
    readonly TextBlock info = new() { TextWrapping = TextWrapping.Wrap, FontSize = 13, Margin = new Thickness(0, 10, 0, 0) };
    readonly TextBox notes = Reader(13, 220);
    readonly TextBox log = Reader(11.5, 150);
    readonly TextBlock status = new() { TextWrapping = TextWrapping.Wrap, FontSize = 14, Margin = new Thickness(0, 14, 0, 0) };
    readonly ProgressBar progress = new() { Height = 4, IsIndeterminate = true, Visibility = Visibility.Collapsed, Margin = new Thickness(0, 12, 0, 0),
                                           Foreground = Accent, Background = Raised, BorderThickness = new Thickness(0) };
    readonly Button update, choose, close;
    Installation? selected;
    bool running;

    public UpdaterWindow()
    {
        Title = "AkynoLeyend — Atualizador " + Core.FromName + " → " + Core.To;
        Width = 820; Height = 860; MinWidth = 640; MinHeight = 640;
        Background = Page; Foreground = Ink; FontFamily = new FontFamily("Segoe UI");
        WindowStartupLocation = WindowStartupLocation.CenterScreen;
        update = ButtonFor("Atualizar", primary: true);
        choose = ButtonFor("Escolher AkynoLeyendBuilder.exe…", primary: false);
        close = ButtonFor("Fechar", primary: false);
        update.IsEnabled = false;

        var body = new StackPanel { Margin = new Thickness(36, 28, 36, 28) };
        body.Children.Add(new TextBlock { Text = "AkynoLeyend", FontFamily = new FontFamily("Georgia"), FontSize = 30, Foreground = Accent });
        body.Children.Add(new TextBlock { Text = "Atualização do " + Core.FromName + " para " + Core.To, FontSize = 20, Margin = new Thickness(0, 10, 0, 6) });
        body.Children.Add(new TextBlock
        {
            Text = "Atualiza a sua instalação sem recompilar o jogo e sem internet. Saves, configurações e a pasta work são preservados; " +
                   "se algo falhar, os arquivos anteriores são restaurados.",
            TextWrapping = TextWrapping.Wrap, Foreground = InkSoft, FontSize = 13, Margin = new Thickness(0, 0, 0, 20)
        });
        body.Children.Add(Label("Instalação"));
        var row = new DockPanel();
        DockPanel.SetDock(choose, Dock.Right);
        choose.Margin = new Thickness(10, 0, 0, 0);
        row.Children.Add(choose);
        row.Children.Add(installations);
        body.Children.Add(row);
        body.Children.Add(info);
        body.Children.Add(Label("O que muda", 20));
        body.Children.Add(notes);
        var buttons = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 18, 0, 0) };
        buttons.Children.Add(update);
        close.Margin = new Thickness(10, 0, 0, 0);
        buttons.Children.Add(close);
        body.Children.Add(buttons);
        body.Children.Add(progress);
        body.Children.Add(status);
        body.Children.Add(Label("Detalhes", 14));
        body.Children.Add(log);
        Content = new ScrollViewer { Content = body, VerticalScrollBarVisibility = ScrollBarVisibility.Auto };

        installations.SelectionChanged += (_, _) => Select(installations.SelectedItem as string);
        choose.Click += (_, _) => Choose();
        close.Click += (_, _) => Close();
        update.Click += async (_, _) => await Update();
        Loaded += async (_, _) => await Startup();
    }

    static TextBox Reader(double size, double height) => new()
    {
        IsReadOnly = true, TextWrapping = TextWrapping.Wrap, VerticalScrollBarVisibility = ScrollBarVisibility.Auto,
        Height = height, FontSize = size, Background = Raised, Foreground = Ink, BorderBrush = Line,
        Padding = new Thickness(10), FontFamily = size < 13 ? new FontFamily("Consolas") : new FontFamily("Segoe UI")
    };

    static TextBlock Label(string text, double top = 0) =>
        new() { Text = text, FontSize = 14, FontWeight = FontWeights.SemiBold, Margin = new Thickness(0, top, 0, 8) };

    static Button ButtonFor(string text, bool primary) => new()
    {
        Content = text, FontSize = 14, Padding = new Thickness(18, 8, 18, 8), Cursor = System.Windows.Input.Cursors.Hand,
        Background = primary ? Accent : Raised, Foreground = primary ? AccentInk : Ink, BorderBrush = primary ? Accent : Line
    };

    async Task Startup()
    {
        try { notes.Text = Core.Preview().Text; }
        catch (Exception e) { notes.Text = "Não foi possível ler as notas do pacote: " + e.Message; }
        info.Text = "Procurando a instalação…";
        info.Foreground = InkFaint;
        var found = await Task.Run(() => Core.Discover(TimeSpan.FromSeconds(4)));
        foreach (var folder in found) installations.Items.Add(folder);
        if (installations.Items.Count > 0) installations.SelectedIndex = 0;
        else
        {
            info.Text = "Nenhuma instalação encontrada automaticamente. Clique em \"Escolher AkynoLeyendBuilder.exe…\" e selecione o " +
                        "AkynoLeyendBuilder.exe da pasta onde você instalou o AkynoLeyend.";
            info.Foreground = InkSoft;
        }
    }

    void Choose()
    {
        var dialog = new OpenFileDialog
        {
            Title = "Selecione o AkynoLeyendBuilder.exe da sua instalação",
            Filter = "Launcher do AkynoLeyend|AkynoLeyendBuilder.exe", CheckFileExists = true
        };
        if (dialog.ShowDialog(this) != true) return;
        var folder = Path.GetDirectoryName(dialog.FileName)!;
        if (!installations.Items.Contains(folder)) installations.Items.Insert(0, folder);
        installations.SelectedItem = folder;
    }

    void Select(string? folder)
    {
        selected = null;
        update.IsEnabled = false;
        if (folder == null) return;
        try
        {
            var found = Core.Inspect(folder);
            var problem = Core.Problem(found);
            info.Text = $"Pasta: {found.Root}\nInstalado: {found.Version} (jogo: {found.GameVersion ?? "ainda não criado"})   →   Pacote: {Core.To}" +
                        (problem != null ? "\n" + problem : "");
            info.Foreground = problem == null ? Ink : Bad;
            if (problem == null) { selected = found; update.IsEnabled = !running; }
        }
        catch (Exception e) when (e is InvalidOperationException or IOException or UnauthorizedAccessException)
        {
            info.Text = e.Message;
            info.Foreground = Bad;
        }
    }

    async Task Update()
    {
        if (selected == null || running) return;
        var open = Core.Blocking(selected);
        while (open.Count > 0)
        {
            var answer = MessageBox.Show(this, $"Feche {string.Join(" e ", open)} do AkynoLeyend desta instalação e clique em OK.\n\n{selected.Root}",
                "Fechar o AkynoLeyend", MessageBoxButton.OKCancel, MessageBoxImage.Information);
            if (answer != MessageBoxResult.OK) return;
            open = Core.Blocking(selected);
        }
        if (MessageBox.Show(this, $"Atualizar a instalação abaixo para {Core.To}?\n\n{selected.Root}\n\nO jogo não será recompilado. " +
                "Saves, configurações e a pasta work são preservados.", "Confirmar atualização", MessageBoxButton.YesNo,
                MessageBoxImage.Question) != MessageBoxResult.Yes) return;
        running = true;
        update.IsEnabled = choose.IsEnabled = close.IsEnabled = installations.IsEnabled = false;
        progress.Visibility = Visibility.Visible;
        status.Text = "Atualizando… Não feche esta janela.";
        status.Foreground = InkSoft;
        log.Clear();
        var result = await Core.Update(selected, line => Dispatcher.BeginInvoke(() => { log.AppendText(line + "\n"); log.ScrollToEnd(); }));
        running = false;
        progress.Visibility = Visibility.Collapsed;
        close.IsEnabled = choose.IsEnabled = installations.IsEnabled = true;
        status.Text = result.Message;
        status.Foreground = result.Success ? Good : Bad;
        Select(selected.Root);
    }

    protected override void OnClosing(CancelEventArgs e)
    {
        if (running)
        {
            e.Cancel = true;
            MessageBox.Show(this, "Aguarde o fim da atualização. Fechar agora deixaria a instalação no meio da troca.",
                "Atualização em andamento", MessageBoxButton.OK, MessageBoxImage.Warning);
        }
        base.OnClosing(e);
    }
}
