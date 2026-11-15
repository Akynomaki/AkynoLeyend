"""0.4.7: the launcher's new look (black and gold theme, side navigation, abstract banners, maximize/restore, the save
picker with its own title bar, blur behind it and Cancelar fixed at the bottom), taken from a redesign made over 0.4.5 and
merged by hunk over 0.4.6; "EXPORTAR SAVES" reads "Exportar Save". Nothing else changes: host, renderer and Python as in
0.4.6. Read from the sources: no window is opened here."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def source(name):
    return (ROOT / name).read_text(encoding="utf-8")


LAUNCHER = "builder/AkynoLeyendBuilder/"


class Look(unittest.TestCase):
    def test_the_new_look_is_in(self):
        xaml = source(LAUNCHER + "MainWindow.xaml")
        code = source(LAUNCHER + "MainWindow.xaml.cs")
        for title in ("Sua próxima jornada", "A imagem do seu jeito", "Tudo pronto para jogar"):
            self.assertIn(title, xaml)
        self.assertNotIn("Seu destino. Sua jornada.", xaml)   # the character card stays out
        self.assertIn("void ToggleMaximize(object sender, RoutedEventArgs e)", code)
        self.assertIn('Click="ToggleMaximize"', xaml)
        # the save picker: blur behind it, put back in finally
        picker = code[code.index("string? ChooseSaveEmulator()"):code.index("void ExportSaves(")]
        self.assertIn("backdrop.Effect=new System.Windows.Media.Effects.BlurEffect{Radius=9};", picker)
        self.assertIn("}finally{\n            backdrop.Effect=previousEffect;", picker)
        self.assertIn('IsCancel=true', picker)
        self.assertNotIn("Assets", source(LAUNCHER + "AkynoLeyendBuilder.csproj"))

    def test_the_button_text(self):
        xaml = source(LAUNCHER + "MainWindow.xaml")
        self.assertIn('<Button Content="Exportar Save" Click="ExportSaves"', xaml)
        self.assertNotIn("EXPORTAR SAVES", xaml)


class Kept(unittest.TestCase):
    def test_0_4_6_stays(self):
        xaml = source(LAUNCHER + "MainWindow.xaml")
        code = source(LAUNCHER + "MainWindow.xaml.cs")
        self.assertNotIn("MeasureBox", xaml + code)   # no Teste de desempenho (0.4.6)
        self.assertIn("try{args.AddRange(CaptureGraphics().Arguments());}", code)
        for name in ("fritz", "mdias", "pokedinner", "lichii"):
            self.assertIn('"%s"' % name, code)
        self.assertIn('new Runner(tools,"export-saves",', code)


class Version(unittest.TestCase):
    def test_0_4_6_installs_update_in_place(self):
        from akynoleyend import __version__
        from akynoleyend.coherence import PREVIOUS_HOST_SOURCES
        # (0.4.8: the version itself is test_048_preload's)
        self.assertIn(__version__, ("0.4.7", "0.4.8"))
        self.assertEqual(source("VERSION").strip(), __version__)
        self.assertIn("01dd7fee3d40dc2feee1e74d81ee26c9ed6364d9b4ceab5d904ad0cc6ccb7ddb", PREVIOUS_HOST_SOURCES["0.4.6"])
        self.assertIn('"0.4.6"', source("builder/AkynoLeyendUpdater/Core.cs"))
        self.assertIn("<Version>%s</Version>" % __version__, source(LAUNCHER + "AkynoLeyendBuilder.csproj"))
        renderer = json.loads(source("ferramentas/prebuilt/renderer.json"))
        self.assertEqual(renderer["release"], __version__)
        self.assertEqual(renderer["shader_stamp"], "4cdbb0029868040b")


if __name__ == "__main__":
    unittest.main()
