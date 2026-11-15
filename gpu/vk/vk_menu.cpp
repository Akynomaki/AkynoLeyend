// AkynoLeyend's F1 panel. GDI redraws the bitmap on a change; presentation
// composites it after interpolation. The game does not receive menu input.
#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iterator>
#include <mutex>
#include <string>
#include <string_view>
#include <vector>

#include "vk_menu.h"
#include "menu_pointer.h"
#include "control_editor.h"
#include "vk_fsr_sdk.h"
#include "boot_options.h"
#include "menu_option_ids.h"
#include "hdr10_pixels.h"
#include "vk_antilag.h"
#include "vk_reflex.h"
#include "../../host/hos_paths.h"
#include "fg_dynamic.h"
#include "vk_framegen.h"
#include "vk_work.h"   // Count GPU work after other headers have declared the Vulkan calls.

namespace mkwvk {
HWND app_window();

Options opts;
extern std::vector<std::string> gpu_device_names;   // (vk_main.cpp: the Vulkan devices the GPU device row lists)

namespace {

struct Row {
    const char* name;
    const char* label;
    int* value;
    int lo, hi, step;
    const char* (*text)(int v);
    const char* help;   // (shown under the list while the row is selected)
};
const char* tx_framegen(int v) {
    static const char* t[] = {"Desligada", "", "2x", "3x", "4x", "5x", "6x", "7x", "8x", "Dinâmica"};
    return t[std::clamp(v, 0, 9)];
}
// (0.4.5-test.1) the Dinâmica rows
const char* tx_fg_max(int v) {
    static char b[16];
    snprintf(b, sizeof b, "%dx", std::clamp(v, 2, fgdyn::kMaxFrames));
    return b;
}
const char* tx_fg_target(int v) {
    static char b[48];
    if (const int fps = fgdyn::target_row_fps(v)) {
        snprintf(b, sizeof b, "%d FPS", fps);
    } else if (const int hz = framegen_refresh_hz()) {
        snprintf(b, sizeof b, "Monitor (%.0f FPS em %d Hz)", fgdyn::target_fps(0, hz), hz);
    } else {
        snprintf(b, sizeof b, "Monitor");
    }
    return b;
}
const char* tx_onoff(int v) { return v ? "Ligado" : "Desligado"; }
int selected_upscaler = 0;
int pending_render_scale = -1;
Upscaler started_upscaler = Upscaler::Off;
Upscaler displayed_upscaler = Upscaler::Off;
bool temporal_menu = false;
bool extended_outputs = false;
int boot_output = 0;

const char* upscaler_label(Upscaler mode) {
    // The pinned SDK 2.4 Vulkan binaries provide FSR 4.1.2 on supported GPUs.
    switch (mode) {
    case Upscaler::Off: return "Sem filtro";
    case Upscaler::Fsr31Native: return "FSR 3.1 · AA nativo";
    case Upscaler::Fsr4: return "AMD FSR 4.1";
    case Upscaler::Fsr4Native: return "FSR 4.1 · AA nativo";
    default: return upscalers[int(mode)].label;
    }
}
const char* unavailable(Upscaler mode) {
    if (!is_temporal(mode)) return nullptr;
    const bool nvidia = mode == Upscaler::Dlss || mode == Upscaler::Dlaa;
    if (is_fsr4(mode) && dev.props.vendorID != 0x1002) return "Requer Radeon compatível";
    if (nvidia && dev.props.vendorID != 0x10de) return "Requer NVIDIA RTX";
    if (!temporal_menu) return "Requer build com suporte temporal";
    if (is_fsr4(mode) && !fsr_sdk_fsr4_available()) return "FSR 4.1 indisponível neste SDK/driver";
    if (!nvidia && !getenv("AKYNO_FSR_SDK_DIR")) return "SDK AMD ausente";
    return nullptr;
}
Upscaler effective_upscaler() {
    return displayed_upscaler != Upscaler::Off ? displayed_upscaler : Upscaler(opts.upscale);
}
int selected_scale() {
    return upscaler_scale(Upscaler(selected_upscaler), pending_render_scale < 0 ? opts.resolution : pending_render_scale);
}
bool choose_upscaler(Upscaler mode) {
    if (int(mode) == selected_upscaler || unavailable(mode)) return false;
    opts.preset = 0;   // (the filter is one of the Quality preset's rows: Custom)
    selected_upscaler = int(mode);
    pending_render_scale = -1;
    if (!is_temporal(started_upscaler) && !is_temporal(mode)) {
        started_upscaler = mode;
        opts.upscale = int(mode);
    }
    return true;
}
const char* tx_percent(int v) {
    static char b[8];
    snprintf(b, sizeof b, "%d%%", v);
    return b;
}
const char* tx_resolution(int v) {
    static const char* t[] = {"Automática", "100%", "75%", "67%", "50%", "125% (exp.)", "150% (exp.)"};
    return t[v];
}
const char* tx_speed(int v) { return v ? "Tempo real" : "Por quadro"; }
const char* tx_output(int v) {
    static const char* t[] = {"2048 × 1152", "2560 × 1440", "3840 × 2160", "1920 × 1080", "1280 × 720", "2560 × 1600"};
    return t[std::clamp(v, 0, 5)];
}
const char* tx_ultrawide(int v) {
    return v ? "Formato do monitor" : boot_output == 5 ? "16:10 nativo" : "Proporção da imagem";
}

// (AkynoLeyend r9) Rows of Hookshot v2.1.0's menu (GPL-3.0), in this panel's words.
const char* tx_preset(int v) {
    static const char* t[] = {"Personalizado", "Mínimo (4 GB)", "Baixo (6 GB)", "Equilibrado (8 GB)", "Alto (12 GB)", "Ultra (16 GB+)"};
    return t[std::clamp(v, 0, 5)];
}
const char* tx_gpu(int v) {
    static char b[96];
    if (v <= 0) return "Automática";
    if (v - 1 < int(gpu_device_names.size())) snprintf(b, sizeof b, "%d: %s", v - 1, gpu_device_names[v - 1].c_str());
    else snprintf(b, sizeof b, "%d: ausente", v - 1);
    return b;
}
const char* tx_fps_cap(int v) {
    static const char* t[] = {"60", "90", "120", "144", "165", "240"};
    return t[std::clamp(v, 0, 5)];
}
const char* tx_anisotropy(int v) {
    static const char* t[] = {"Do jogo", "2x", "4x", "8x", "16x"};
    return t[std::clamp(v, 0, 4)];
}
const char* tx_robust(int v) {
    static const char* t[] = {"Automático", "Desligado", "Ligado"};
    return t[std::clamp(v, 0, 2)];
}
const char* tx_menu_size(int v) {
    static const char* t[] = {"Pequeno", "Médio", "Grande"};
    return t[std::clamp(v, 1, 3) - 1];
}
const char* tx_dead_zone(int v) {
    static const char* t[] = {"Padrão (24%)", "5%", "10%", "15%", "20%", "30%"};
    return t[std::clamp(v, 0, 5)];
}
const char* tx_rumble(int v) { return v ? tx_percent(v) : "Desligada"; }
// (AkynoLeyend r10) More rows of Hookshot v2.1.0's menu
const char* tx_dlss_model(int v) {
    static const char* t[] = {"Automático (K/M)", "K", "M", "L", "Padrão da NVIDIA"};
    return t[std::clamp(v, 0, 4)];
}
const char* tx_mouse_sens(int v) { return v > 0 ? tx_percent(akyno_mouse_sens_percent(v)) : "Teclas - e ="; }
const char* tx_menu_shortcut(int v) {
    static const char* t[] = {"F1, Insert ou Ctrl+M", "Só F1", "F1, Insert, Ctrl+M e Esc"};
    return t[std::clamp(v, 0, 2)];
}
// (AkynoLeyend r11) Hookshot v2.1.0's latency rows: offered only where the device has the extension
const char* tx_reflex(int v) {
    static const char* t[] = {"Desligado", "Ligado", "Ligado + Boost"};
    return reflex_available() ? t[std::clamp(v, 0, 2)] : "Indisponível nesta placa";
}
const char* tx_antilag(int v) { return antilag_available() ? (v ? "Ligado" : "Desligado") : "Indisponível nesta placa"; }
// (AkynoLeyend r12) Hookshot v2.1.0's Motion page
const char* tx_mic(int v) { return v ? "Padrão do sistema" : "Desligado"; }
const char* tx_gyro_deadzone(int v) {
    static const char* t[] = {"Baixa", "Padrão", "Alta"};
    return t[std::clamp(v, 0, 2)];
}
// (AkynoLeyend r13) Hookshot v2.1.0's Text speed, Text size and Mouse camera rows
const char* tx_text_speed(int v) {
    static const char* t[] = {"Normal", "2x", "4x", "Instantâneo"};
    return t[std::clamp(v, 0, 3)];
}
// (0.4.5-test.1, unified) the Render distance row: the game's own, then akyno_render_distance's metres
const char* tx_render_distance(int v) {
    static char b[32];
    const int m = akyno_render_distance(v);
    if (!m) return "Original";
    snprintf(b, sizeof b, "%d m", m);
    return b;
}
const char* tx_text_size(int v) {
    static const char* t[] = {"Original", "110%", "125%", "150%", "175%"};
    return t[std::clamp(v, 0, 4)];
}
const char* tx_mousecam(int v) { return v ? "Nativa" : "Como analógico direito"; }
// (AkynoLeyend r13) Hookshot v2.1.0's HDR rows. The value says so while the display lists no HDR10 surface (the picture then
// stays SDR: Windows' Use HDR is off, or the display has none)
const char* tx_hdr(int v) {
    static const char* t[] = {"Desligado", "Expandido", "Nativo (do jogo)"};
    static const char* unlisted[] = {"Desligado", "Expandido (tela sem HDR10)", "Nativo (tela sem HDR10)"};
    return (dev.hdr ? t : unlisted)[std::clamp(v, 0, 2)];
}
const char* tx_wide_menus(int v) {
    static const char* t[] = {"Largura total", "Centralizados, laterais desfocadas", "Centralizados, barras pretas"};
    return t[std::clamp(v, 0, 2)];
}
const char* tx_mesh_mode(int v) {   // (AkynoLeyend r13, Hookshot v2.1.0)
    static const char* t[] = {"Automático", "Nativos", "Compute"};
    return t[std::clamp(v, 0, 2)];
}
const char* tx_nits(int v) {
    static char b[24];
    snprintf(b, sizeof b, "%d nits", v);
    return b;
}

enum Setting { Fullscreen, Framegen, Pacing, Resolution, Output, Sharpness, Speed, Handheld, Ultrawide, Fps,
               Preset, Gpu, FpsCap, Aniso, Robust, Volume, MuteBg, MenuSize, PadBg, MouseInvert, InvertCamX, InvertCamY,
               DeadZone, Rumble, DlssModel, MouseSens, MenuKey, Reflex, AntiLag, Gyro, GyroSensX, GyroSensY, GyroInvX,
               GyroInvY, GyroDeadZone, Mic, TextSpeed, TextSize, MouseCam, CamNoCenter, Hdr, HdrWhite, HdrPeak, WideMenus, MeshMode,
               FgMax, FgTarget, RenderDistance, SettingCount };
Row rows[] = {
    {"Fullscreen", "Tela cheia", &opts.fullscreen, 0, 1, 1, tx_onoff,
     "Preenche o monitor com uma janela sem bordas. Também pode ser alternada pelo F11."},
    {"Frame generation", "Geração de quadros", &opts.framegen, 0, 9, 1, tx_framegen,
     "Insere quadros para suavizar o movimento. Dinâmica escolhe quantos a cada momento para chegar ao alvo abaixo. Desligue para medir os FPS reais do jogo."},
    {"Frame pacing", "Ritmo de quadros", &opts.pace, 0, 1, 1, tx_onoff,
     "Distribui a apresentação em intervalos mais regulares. Pode adicionar até um quadro de atraso."},
    {"Resolution", "Escala interna", &opts.resolution, 0, 6, 1, tx_resolution,
     "Reduz o trabalho da GPU antes da ampliação. Com saída 4K, 50% renderiza a cena em 1920 × 1080."},
    {"Output resolution", "Resolução de saída", &opts.output_res, 0, 5, 1, tx_output,
     "Tamanho da imagem final do jogo. Aplique ao reiniciar. Saídas maiores usam mais memória de vídeo."},
    {"Sharpness", "Nitidez", &opts.sharpness, 0, 100, 10, tx_percent,
     "Ajusta a nitidez da imagem. Arraste a barra ou use as setas. Valores altos podem criar halos."},
    {"Game speed", "Velocidade do jogo", &opts.realtime, 0, 1, 1, tx_speed,
     "Em tempo real, a velocidade acompanha o relógio. Por quadro, o jogo desacelera quando o FPS cai."},
    {"Handheld profile", "Perfil portátil", &opts.handheld, 0, 1, 1, tx_onoff,
     "Usa o perfil portátil do jogo, com resoluções menores. Aplique ao reiniciar."},
    {"Ultrawide", "Proporção da tela", &opts.ultrawide, 0, 1, 1, tx_ultrawide,
     "Adapta a câmera a monitores ultrawide. A interface do jogo fica em 16:9 no meio. Aplique ao reiniciar."},
    {"FPS counter", "Contador de FPS", &opts.show_fps, 0, 1, 1, tx_onoff,
     "Mostra o FPS de apresentação e, com geração ligada, a taxa de quadros reais do jogo."},
    {"Quality preset", "Predefinição", &opts.preset, 0, 5, 1, tx_preset,
     "Ajusta escala interna, filtro, nitidez e perfil para uma GPU com essa memória. Os limites de memória valem ao reiniciar."},
    {"GPU device", "Placa de vídeo", &opts.gpu_device, 0, 8, 1, tx_gpu,
     "Placa em que o jogo roda. Automática usa a melhor placa dedicada. Aplique ao reiniciar."},
    {"Frame rate cap", "Limite de FPS do jogo", &opts.fps_cap, 0, 5, 1, tx_fps_cap,
     "Limita os quadros que o jogo renderiza. Acima de 60 é experimental: cenas e chefes podem se comportar mal. Aplique ao reiniciar."},
    {"Anisotropic filtering", "Filtro anisotrópico", &opts.anisotropy, 0, 4, 1, tx_anisotropy,
     "Mantém nítidas as texturas vistas de lado, como o chão à frente. Do jogo usa 1x ou 2x. Aplique ao reiniciar."},
    {"Robust buffers", "Buffers robustos", &opts.robust, 0, 2, 1, tx_robust,
     "Leituras além do fim de um buffer são descartadas em vez de parar a GPU. Desligado pode ser mais rápido em algumas NVIDIA. Aplique ao reiniciar."},
    {"Volume", "Volume", &opts.volume, 0, 100, 5, tx_percent,
     "Volume do jogo. As opções de som do próprio jogo e o volume do Windows continuam valendo."},
    {"Mute in background", "Silenciar em segundo plano", &opts.mute_background, 0, 1, 1, tx_onoff,
     "Silencia o jogo enquanto outra janela está em foco. O som volta quando você retorna ao jogo."},
    {"Menu size", "Tamanho do menu", &opts.menu_size, 1, 3, 1, tx_menu_size,
     "Tamanho deste painel e do contador de FPS. Em janelas pequenas o painel já usa o menor tamanho."},
    {"Controller in background", "Controle em segundo plano", &opts.pad_background, 0, 1, 1, tx_onoff,
     "O controle continua jogando com outra janela em foco. Teclado e mouse ainda precisam da janela do jogo."},
    {"Invert mouse vertical", "Inverter mouse vertical", &opts.mouse_invert, 0, 1, 1, tx_onoff,
     "Troca cima e baixo do mouse capturado."},
    {"Invert camera X", "Inverter câmera X", &opts.invert_cam_x, 0, 1, 1, tx_onoff,
     "Inverte esquerda e direita do analógico direito."},
    {"Invert camera Y", "Inverter câmera Y", &opts.invert_cam_y, 0, 1, 1, tx_onoff,
     "Inverte cima e baixo do analógico direito."},
    {"Stick dead zone", "Zona morta do analógico", &opts.stick_dead_zone, 0, 5, 1, tx_dead_zone,
     "Quanto o analógico se move antes de o jogo perceber. Menor para precisão, maior para analógico com drift."},
    {"Rumble strength", "Força da vibração", &opts.rumble, 0, 150, 25, tx_rumble,
     "Força da vibração em relação à do jogo. Vale para controles lidos pelo SDL."},
    {"DLSS model", "Modelo do DLSS", &opts.dlss_model, 0, 4, 1, tx_dlss_model,
     "Rede da NVIDIA usada pelo DLSS e pelo DLAA. Automático usa K e, a 50% ou menos, M. Só vale com DLSS. Aplique ao reiniciar."},
    {"Mouse sensitivity", "Sensibilidade do mouse", &opts.mouse_sens, 0, 8, 1, tx_mouse_sens,
     "Quanto a câmera gira com o mouse capturado. Teclas - e = deixa as teclas - e = ajustarem no jogo, como antes."},
    {"Menu shortcut", "Atalho do menu", &opts.menu_shortcut, 0, 2, 1, tx_menu_shortcut,
     "Teclas que abrem este painel. Só F1 deixa o Insert livre para overlays. Com Esc, o Esc também abre o painel."},
    {"NVIDIA Reflex", "NVIDIA Reflex", &opts.reflex, 0, 2, 1, tx_reflex,
     "Placas NVIDIA: cada quadro começa o mais tarde possível, com menos atraso entre o controle e a tela. Não é usado com geração de quadros."},
    {"AMD Anti-Lag 2", "AMD Anti-Lag 2", &opts.antilag, 0, 1, 1, tx_antilag,
     "Placas AMD: o driver segura o início do quadro para ler o controle mais tarde. Não é usado com geração de quadros."},
    {"Motion controls", "Controles por movimento", &opts.gyro, 0, 1, 1, tx_onoff,
     "Mira com o giroscópio do controle onde o jogo usa movimento, como no Switch. Controle Pro, controles no modo Switch, DualSense e DualShock 4 (SDL)."},
    {"Motion sensitivity X", "Sensibilidade do movimento X", &opts.gyro_sens_x, 10, 600, 10, tx_percent,
     "Quanto a mira anda para os lados ao girar o controle. 100% é o do console."},
    {"Motion sensitivity Y", "Sensibilidade do movimento Y", &opts.gyro_sens_y, 10, 300, 10, tx_percent,
     "Quanto a mira sobe e desce ao inclinar o controle. 100% é o do console."},
    {"Invert motion X", "Inverter movimento X", &opts.gyro_inv_x, 0, 1, 1, tx_onoff, "Troca esquerda e direita da mira por movimento."},
    {"Invert motion Y", "Inverter movimento Y", &opts.gyro_inv_y, 0, 1, 1, tx_onoff, "Troca cima e baixo da mira por movimento."},
    {"Motion deadzone", "Zona morta do movimento", &opts.gyro_deadzone, 0, 2, 1, tx_gyro_deadzone,
     "Quanto um giro lento conta como parado. Alta firma um controle que treme parado; Baixa mantém os menores movimentos."},
    {"Microphone", "Microfone", &opts.mic, 0, 1, 1, tx_mic,
     "O que a ocarina ouve com a opção de microfone do jogo ligada (tocar um instrumento ou cantarolar). Usa o microfone padrão do Windows."},
    {"Text speed", "Velocidade do texto", &opts.text_speed, 0, 3, 1, tx_text_speed,
     "Rapidez com que as letras dos diálogos e mensagens aparecem. Normal é o ritmo do jogo, com as pausas; Instantâneo mostra a página de uma vez."},
    {"Text size", "Tamanho do texto", &opts.text_size, 0, 4, 1, tx_text_size,
     "Tamanho do texto dos diálogos, da Navi e das placas. Original é o do jogo."},
    {"Mouse camera", "Câmera do mouse", &opts.mouse_native, 0, 1, 1, tx_mousecam,
     "Como o mouse capturado gira a câmera. Nativa gira os ângulos da própria câmera, sem zona morta nem aceleração; a outra opção imita o analógico direito."},
    {"Disable camera centering", "Desativar centralização da câmera", &opts.disable_camera_centering, 0, 1, 1, tx_onoff,
     "A câmera deixa de voltar sozinha para trás do Link quando ele anda. Mira, travar no alvo e câmeras de cena continuam como no jogo."},
    {"HDR", "HDR", &opts.hdr, 0, 2, 1, tx_hdr,
     "Saída HDR10 em tela HDR (Windows: ligue Usar HDR nas configurações de tela). Expandido: a imagem SDR do jogo, com o branco no branco de papel e os realces até o pico. Nativo: o HDR do próprio jogo."},
    {"HDR paper white", "HDR: branco de papel", &opts.hdr_white, 80, 400, 10, tx_nits,
     "Brilho do branco da imagem com o HDR ligado. Cerca de 200 em uma sala comum; mais em sala clara."},
    {"HDR peak brightness", "HDR: brilho de pico", &opts.hdr_peak, 400, 4000, 100, tx_nits,
     "Os realces mais fortes com o HDR ligado: use o brilho de pico da sua tela."},
    {"Ultrawide menus", "Menus em ultrawide", &opts.wide_menus, 0, 2, 1, tx_wide_menus,
     "Com Proporção da tela no formato do monitor: os menus de pausa, itens e mapa e o que aparece ao lado deles. Telas de carregamento e filmes ganham as mesmas laterais. Vale na hora."},
    {"Mesh shaders", "Mesh shaders", &opts.mesh_mode, 0, 2, 1, tx_mesh_mode,
     "Como rodam os programas de mesh do jogo (boa parte do cenário). Automático usa os mesh shaders da placa e, sem eles, o caminho por compute. Compute usa esse caminho em qualquer placa: tente se faltarem objetos ou a placa travar. Aplique ao reiniciar."},
    {"Framegen maximum", "Geração dinâmica: máximo", &opts.fg_max, 2, 6, 1, tx_fg_max,
     "Com a geração Dinâmica: o máximo de quadros mostrados por quadro do jogo. Mais quadros usam mais memória de vídeo e mostram mais erros em movimentos rápidos."},
    {"Framegen target", "Geração dinâmica: alvo", &opts.fg_target, 0, 6, 1, tx_fg_target,
     "Com a geração Dinâmica: os FPS que ela procura mostrar. Monitor usa um pouco abaixo da taxa do monitor (138 em 144 Hz, 59 em 60 Hz). Quando o jogo sozinho chega ao alvo, nenhum quadro é inserido."},
    {"Render distance", "Distância de renderização", &opts.render_distance, 0, 8, 1, tx_render_distance,
     "Até onde as câmeras do jogo desenham o cenário. Original é o alcance do jogo. Valores menores cortam o que está além da distância: menos objetos por quadro, mais FPS em CPU e placa fracas. Vale na hora."},
};
static_assert(std::size(rows) == SettingCount);
constexpr Setting video_rows[] = {Preset, Output, Fullscreen, Gpu, Ultrawide, WideMenus, Handheld, Framegen, FgMax, FgTarget, Pacing, Hdr, HdrWhite, HdrPeak,
                                  FpsCap, Aniso, Robust, MeshMode, RenderDistance, DlssModel, Reflex, AntiLag};
constexpr Setting audio_rows[] = {Volume, MuteBg, Mic};
constexpr Setting game_rows[] = {Fps, MenuSize, Speed, TextSpeed, TextSize};
constexpr Setting pad_rows[] = {PadBg, MouseCam, MouseSens, MouseInvert, CamNoCenter, InvertCamX, InvertCamY, DeadZone, Rumble, MenuKey, Gyro,
                                GyroSensX, GyroSensY, GyroInvX, GyroInvY, GyroDeadZone};
// (rows read once, at the game's start: a change shows "reinicie" until the game is opened again)
constexpr Setting restart_rows[] = {Output, Handheld, Ultrawide, Gpu, FpsCap, Aniso, Robust, DlssModel, MeshMode};
int boot_values[SettingCount];
bool needs_restart(const int* value) {
    for (const Setting k : restart_rows)
        if (rows[k].value == value) return *value != boot_values[k];
    return false;
}
// (Hookshot v2.1.0 apply_preset: the scaling rows for a card with that much memory. The upscaler and frame generation stay the
// player's; a temporal upscaler keeps its own scale)
void apply_preset(int p) {
    static const int scale[] = {0, 4, 2, 1, 1, 1}, filter[] = {0, 2, 2, 1, 2, 2}, sharp[] = {0, 30, 30, 30, 40, 50};
    if (p < 1 || p > 5) return;
    if (!is_temporal(Upscaler(selected_upscaler))) {
        opts.resolution = scale[p];
        pending_render_scale = -1;
        if (!is_temporal(started_upscaler)) {
            opts.upscale = filter[p];
            selected_upscaler = filter[p];
            started_upscaler = Upscaler(filter[p]);
        }
    }
    opts.sharpness = sharp[p];
    opts.pace = 1;
    opts.realtime = 1;
    opts.handheld = p <= 2;
}
bool preset_row(const int* value) {
    return value == &opts.resolution || value == &opts.sharpness || value == &opts.pace || value == &opts.realtime ||
           value == &opts.handheld;
}
controls::Editor control_editor;
controls::Capture binding_capture;
const char* tx_prompts(int v) {
    static const char* t[]={"Automático", "Switch", "Xbox", "PlayStation 4", "PlayStation 5", "Steam Deck"};
    static char label[48];
    const int face=host && host->prompt_face?host->prompt_face():-1;
    const char* state=face<0?" (original)":v && v-1!=face?" (reinicia)":"";
    snprintf(label,sizeof label,"%s%s",t[std::clamp(v,0,5)],state);
    return label;
}
const char* tx_layout(int v) {return v==0?"Nintendo":v==1?"Xbox / PC":"Personalizado";}
const char* tx_action(int v) {return controls::actions[std::clamp(v,0,int(HOS_KEY_N)-1)];}
const char* pad_name(int p) {
    static const char* t[HOS_PROMPT_N + 1][HOS_PAD_N] = {   // (by place, then HOS_PROMPT_*)
        {"Bottom button", "Right button", "Left button", "Top button", "Select / Back", "Home", "Start", "Left stick press",
         "Right stick press", "L1 / LB", "R1 / RB", "D-pad up", "D-pad down", "D-pad left", "D-pad right", "L2 / LT", "R2 / RT"},
        {"B", "A", "Y", "X", "Minus", "Home", "Plus", "Left stick press", "Right stick press", "L", "R", "D-pad up",
         "D-pad down", "D-pad left", "D-pad right", "ZL", "ZR"},
        {"A", "B", "X", "Y", "View", "Xbox", "Menu", "Left stick press", "Right stick press", "LB", "RB", "D-pad up",
         "D-pad down", "D-pad left", "D-pad right", "LT", "RT"},
        {"Cross", "Circle", "Square", "Triangle", "Share", "PS", "Options", "L3", "R3", "L1", "R1", "D-pad up", "D-pad down",
         "D-pad left", "D-pad right", "L2", "R2"},
        {"Cross", "Circle", "Square", "Triangle", "Create", "PS", "Options", "L3", "R3", "L1", "R1", "D-pad up", "D-pad down",
         "D-pad left", "D-pad right", "L2", "R2"},
        {"A", "B", "X", "Y", "View", "Steam", "Menu", "L3", "R3", "L1", "R1", "D-pad up", "D-pad down", "D-pad left",
         "D-pad right", "L2", "R2"}};
    const int face = opts.prompts ? opts.prompts - 1 : host && host->prompt_face ? host->prompt_face() : -1;
    return p >= 0 && p < HOS_PAD_N ? t[face >= 0 && face < HOS_PROMPT_N ? face + 1 : 0][p] : "Nenhum";
}
const char* tx_pad(int v) { return control_editor.action>=HOS_SW_N?"Apenas teclado":pad_name(v); }
const char* tx_key(int v) {
    static char text[128];
    if(!v) return "Nenhuma";
    if(v>=1 && v<=6) {static const char* m[]={"","Mouse esquerdo","Mouse direito","","Mouse central","Mouse 4","Mouse 5"};if(m[v][0])return m[v];}
    LONG scan=LONG(MapVirtualKeyA((UINT)v,MAPVK_VK_TO_VSC))<<16;
    if(v==VK_LEFT || v==VK_RIGHT || v==VK_UP || v==VK_DOWN || v==VK_DELETE || v==VK_INSERT || v==VK_HOME || v==VK_END || v==VK_PRIOR || v==VK_NEXT) scan|=1<<24;
#ifdef _WIN32
    wchar_t name[40];
    if (GetKeyNameTextW(scan, name, int(std::size(name))) &&
        WideCharToMultiByte(CP_UTF8, 0, name, -1, text, sizeof text, nullptr, nullptr)) return text;
#else
    if (GetKeyNameTextA(scan, text, sizeof text)) return text;
#endif
    snprintf(text,sizeof text,"Tecla %d",v);
    return text;
}
Row control_rows[]={
    {"Button prompts", "Ícones dos botões", &opts.prompts, 0, 5, 1, tx_prompts,
     "O modo automático segue o controle conectado. Os ícones são aplicados ao reiniciar. Mods têm prioridade."},
    {"Layout preset", "Layout do controle", &control_editor.layout, 0, 1, 1, tx_layout,
     "Nintendo segue as posições originais. Xbox / PC troca A/B e X/Y e mantém o teclado."},
    {"Action", "Ação", &control_editor.action, 0, HOS_KEY_N-1, 1, tx_action,
     "Escolha a ação do jogo que deseja remapear, incluindo movimento e câmera."},
    {"Gamepad button", "Botão do controle", &control_editor.pad, -1, HOS_PAD_N-1, 1, tx_pad,
     "Enter ou clique para remapear. Solte o botão antes de pressionar. Delete limpa e Esc cancela."},
    {"Keyboard / mouse 1", "Tecla / mouse 1", &control_editor.key[0], 0, 255, 1, tx_key,
     "Enter ou clique para remapear. Delete limpa e Esc cancela. O jogo lê o mouse quando ele está capturado."},
    {"Keyboard / mouse 2", "Tecla / mouse 2", &control_editor.key[1], 0, 255, 1, tx_key,
     "Use uma segunda tecla ou botão para a mesma ação. Enter ou clique para remapear."},
};

enum Page { Video, Upscaling, Audio, Game, Controls, PageCount };
constexpr const char* page_labels[] = {"Tela", "Ampliação", "Áudio", "Jogo", "Controles"};
constexpr int kScaleRows = 2;
constexpr int kMenuWidth = 1120;   // at 720 lines
Page page = Video;
int item_count() {
    if (page == Upscaling) return kScaleRows + int(Upscaler::Count);
    if (page == Audio) return int(std::size(audio_rows));
    if (page == Game) return int(std::size(game_rows));
    return page == Controls ? int(std::size(control_rows) + std::size(pad_rows)) : int(std::size(video_rows));
}
bool mode_item(int i) { return page == Upscaling && i >= kScaleRows; }
Upscaler item_mode(int i) { return Upscaler(i - kScaleRows); }
const Row& menu_row(int i) {
    if (page == Controls)
        return i < int(std::size(control_rows)) ? control_rows[i] : rows[pad_rows[i - int(std::size(control_rows))]];
    if (page == Upscaling) return rows[i == 0 ? Resolution : Sharpness];
    if (page == Audio) return rows[audio_rows[i]];
    if (page == Game) return rows[game_rows[i]];
    return rows[video_rows[i]];
}

std::atomic<bool> open_now{false};
int selected = 0;
bool menu_refresh = false;
const char* ini_key(const Row& r) {
    static char k[32];
    size_t n = 0;
    for (const char* p = r.name; *p && n + 1 < sizeof k; p++) k[n++] = *p == ' ' ? '_' : (char)tolower(*p);
    k[n] = 0;
    return k;
}
void save() {
    if (FILE* f = hos_game_file("AkynoLeyend_opts.ini.part", "w")) {
        const auto mode = Upscaler(selected_upscaler);
        for (const Row& r : rows) {
            const int value = r.value == &opts.resolution ? selected_scale() : *r.value;
            fprintf(f, "%s=%d\n", ini_key(r), value);
        }
        fprintf(f, "upscaling=%d\n", window_filter(mode));  // older builds keep the spatial filter
        fprintf(f, "upscaler=%s\n", upscalers[selected_upscaler].key.data());
        fprintf(f,"button_prompts=%d\noptions_version=3\n",opts.prompts);
        if(host && host->binding) for(int i=0;i<HOS_KEY_N;++i) {
            if(i<HOS_SW_N) fprintf(f,"pad_%s=%d\n",controls::names[i],host->binding(HOS_BIND_PAD,i,0));
            fprintf(f,"key_%s=%d,%d\n",controls::names[i],host->binding(HOS_BIND_KEY,i,0),host->binding(HOS_BIND_KEY,i,1));
        }
        const bool bad=ferror(f)!=0;
        const bool closed=fclose(f)==0;
        if(bad || !closed || !hos_game_replace("AkynoLeyend_opts.ini.part","AkynoLeyend_opts.ini")) {
            hos_game_delete("AkynoLeyend_opts.ini.part");
            logf("menu: options were not saved; the previous file is preserved");
        }
    } else logf("menu: could not save options");
}

// ---- what is drawn: bitmaps of the menu and the counter, in the window's byte order ----
struct Bitmap {
    uint32_t w = 0, h = 0;
    std::vector<uint8_t> px;
    uint64_t version = 0;
    bool keyed = false;                   // (black is see-through: copied as the runs of pixels in between)
    std::vector<VkBufferImageCopy> runs;
};
Bitmap menu_bmp, fps_bmp;
std::mutex bmp_mu;
int scale_of(uint32_t h) { return std::max(1u, h / 720); }

void gdi_draw(Bitmap& out, uint32_t w, uint32_t h, void (*paint)(HDC, uint32_t, uint32_t, int), int scale) {
    BITMAPINFO bi{};
    bi.bmiHeader.biSize = sizeof bi.bmiHeader;
    bi.bmiHeader.biWidth = (LONG)w;
    bi.bmiHeader.biHeight = -(LONG)h;
    bi.bmiHeader.biPlanes = 1;
    bi.bmiHeader.biBitCount = 32;
    bi.bmiHeader.biCompression = BI_RGB;
    HDC dc = CreateCompatibleDC(nullptr);
    void* bits = nullptr;
    HBITMAP bmp = CreateDIBSection(dc, &bi, DIB_RGB_COLORS, &bits, nullptr, 0);
    if (!bmp) { DeleteDC(dc); return; }
    HGDIOBJ old = SelectObject(dc, bmp);
    paint(dc, w, h, scale);
    GdiFlush();
    const bool rgba = dev.swap_format == VK_FORMAT_R8G8B8A8_UNORM || dev.swap_format == VK_FORMAT_R8G8B8A8_SRGB;
    std::lock_guard lk(bmp_mu);
    out.w = w, out.h = h;
    out.px.assign((const uint8_t*)bits, (const uint8_t*)bits + (size_t)w * h * 4);
    if (out.keyed) {
        out.runs.clear();
        for (uint32_t y = 0; y < h; y++) {
            for (uint32_t x = 0; x < w;) {
                const uint8_t* p = out.px.data() + ((size_t)y * w + x) * 4;
                if (!(p[0] | p[1] | p[2])) { x++; continue; }
                uint32_t e = x + 1;
                for (; e < w; e++) {
                    const uint8_t* q = out.px.data() + ((size_t)y * w + e) * 4;
                    if (!(q[0] | q[1] | q[2])) break;
                }
                VkBufferImageCopy c{};
                c.bufferOffset = ((uint64_t)y * w + x) * 4;
                c.bufferRowLength = w;
                c.imageSubresource = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1};
                c.imageOffset = {(int32_t)x, (int32_t)y, 0};
                c.imageExtent = {e - x, 1, 1};
                out.runs.push_back(c);
                x = e;
            }
        }
    }
    if (dev.hdr) {
        // (AkynoLeyend r13: an HDR10 swapchain, 10:10:10:2 PQ words: hdr10_pixels.h. A panel has few colours: each is
        // encoded once and kept; one thread draws, the presenting one)
        static uint32_t keys[4096], words[4096], kept_for = 0;
        const bool red_low = dev.swap_format == VK_FORMAT_A2B10G10R10_UNORM_PACK32;
        const int white = akyno_hdr_white(opts.hdr_white);
        const uint32_t kind = (uint32_t)white << 1 | (red_low ? 1u : 0u);
        if (kept_for != kind) kept_for = kind, std::memset(keys, 0, sizeof keys);
        for (size_t i = 0; i < out.px.size(); i += 4) {
            uint8_t* p = out.px.data() + i;   // (GDI: blue, green, red)
            const uint32_t key = 1u << 24 | (uint32_t)p[2] << 16 | (uint32_t)p[1] << 8 | p[0];
            const uint32_t slot = (key * 2654435761u) >> 20;
            if (keys[slot] != key) keys[slot] = key, words[slot] = akyno_hdr10_pixel(p[2], p[1], p[0], (float)white, red_low);
            std::memcpy(p, &words[slot], 4);
        }
    } else
    for (size_t i = 0; i < out.px.size(); i += 4) {
        if (rgba) std::swap(out.px[i], out.px[i + 2]);
        out.px[i + 3] = 255;
    }
    out.version++;
    SelectObject(dc, old);
    DeleteObject(bmp);
    DeleteDC(dc);
}
HFONT font(int px, int weight, const char* family = "Segoe UI") {
    return CreateFontA(-px, 0, 0, 0, weight, 0, 0, 0, DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY,
                       DEFAULT_PITCH, family);
}
void fill(HDC dc, int x, int y, int w, int h, COLORREF c) {
    if (w <= 0 || h <= 0) return;
    RECT r{x, y, x + w, y + h};
    HBRUSH b = CreateSolidBrush(c);
    FillRect(dc, &r, b);
    DeleteObject(b);
}

#ifdef _WIN32
using MenuText = std::wstring;
MenuText gdi_text(std::string_view utf8) {
    if (utf8.empty()) return {};
    const int length = MultiByteToWideChar(CP_UTF8, 0, utf8.data(), int(utf8.size()), nullptr, 0);
    MenuText text(length, L'\0');
    if (length) MultiByteToWideChar(CP_UTF8, 0, utf8.data(), int(utf8.size()), text.data(), length);
    return text;
}
#else
// The POSIX GDI adapter accepts one byte per Latin-1 glyph.
using MenuText = std::string;
MenuText gdi_text(std::string_view utf8) {
    MenuText text;
    for (size_t i = 0; i < utf8.size();) {
        const auto first = static_cast<unsigned char>(utf8[i++]);
        if (first < 0x80) text += char(first);
        else if ((first == 0xc2 || first == 0xc3) && i < utf8.size())
            text += char(((first & 3) << 6) | (static_cast<unsigned char>(utf8[i++]) & 63));
        else {
            while (i < utf8.size() && (static_cast<unsigned char>(utf8[i]) & 0xc0) == 0x80) ++i;
            text += '?';
        }
    }
    return text;
}
#endif
SIZE text_size(HDC dc, const MenuText& text) {
    SIZE size{};
#ifdef _WIN32
    GetTextExtentPoint32W(dc, text.data(), int(text.size()), &size);
#else
    GetTextExtentPoint32A(dc, text.data(), int(text.size()), &size);
#endif
    return size;
}
void line_text(HDC dc, int x, int y, int width, std::string_view utf8, bool right = false) {
    if (width <= 0 || utf8.empty()) return;
    auto text = gdi_text(utf8);
    auto size = text_size(dc, text);
    if (size.cx > width) {
        const auto ellipsis = gdi_text("...");
        do {
            if (text.empty()) return;
            text.pop_back();
#ifdef _WIN32
            if (!text.empty() && text.back() >= 0xd800 && text.back() <= 0xdbff) text.pop_back();
#endif
            size = text_size(dc, text + ellipsis);
        } while (size.cx > width);
        text += ellipsis;
    }
    x += right ? width - size.cx : 0;
#ifdef _WIN32
    TextOutW(dc, x, y, text.data(), int(text.size()));
#else
    TextOutA(dc, x, y, text.data(), int(text.size()));
#endif
}
void wrap_help(HDC dc, std::string_view text, int width, int x, int y, int max_lines) {
    const int line_h = int(text_size(dc, gdi_text("Ag")).cy);
    for (int line = 0; line < max_lines && !text.empty(); ++line) {
        size_t count = text.size();
        if (line + 1 < max_lines) {
            size_t end = text.find(' ');
            while (end != text.npos && text_size(dc, gdi_text(text.substr(0, end))).cx <= width) {
                end = text.find(' ', end + 1);
            }
            if (text_size(dc, gdi_text(text.substr(0, end))).cx > width) {
                const auto previous = text.rfind(' ', (end == text.npos ? text.size() : end) - 1);
                count = previous == text.npos ? std::min(text.find(' '), text.size()) : previous;
            }
        }
        line_text(dc, x, y + line * line_h, width, text.substr(0, count));
        const auto next = text.find_first_not_of(' ', count);
        if (next == text.npos) break;
        text.remove_prefix(next);
    }
}

struct Rect {
    int x, y, w, h;
    bool contains(int px, int py) const {
        return px >= x && px < x + w && py >= y && py < y + h;
    }
    Rect inset(int n) const { return {x + n, y + n, w - 2 * n, h - 2 * n}; }
};

struct MenuLayout {
    int width, height, scale, header, side;
    int x, w, title_y, status_h, top, row_h, columns, first, visible, total, help_h;

    int row_of(int i) const { return mode_item(i) ? kScaleRows + (i - kScaleRows) / columns : i; }
    Rect item(int i) const {
        const int y = top + (row_of(i) - first) * row_h;
        if (!mode_item(i)) return {x, y, w, row_h - 5 * scale};
        const int col = (i - kScaleRows) % columns;
        const int gap = 8 * scale, cell = (w - (columns - 1) * gap) / columns;
        return {x + col * (cell + gap), y, cell, row_h - 5 * scale};
    }
    Rect tab(int i) const {
        const bool inline_tabs = header == 61 * scale;
        const int left = (inline_tabs ? 232 : 10) * scale;
        const int gap = 6 * scale, cell = (width - left - 18 * scale - (PageCount - 1) * gap) / PageCount;
        return {left + i * (cell + gap), (inline_tabs ? 12 : 43) * scale, cell, 36 * scale};
    }
    Rect footer_key(int i) const {
        const bool labeled = width >= 700 * scale;
        const int key = 29 * scale, gap = 4 * scale;
        const int group = (width - 36 * scale) / 4;
        const int x = 18 * scale + group * (i / 2) + (labeled ? 94 : 0) * scale + (i % 2) * (key + gap);
        return {x, height - 37 * scale, i == 6 ? 40 * scale : key, 27 * scale};
    }
    Rect slider(int i) const {
        const Rect cell = item(i);
        const int left = cell.x + cell.w / 2;
        return {left, cell.y + 17 * scale, cell.x + cell.w - left - 68 * scale, 3 * scale};
    }
    int hit(int px, int py) const {
        for (int i = 0; i < item_count(); ++i) {
            const int row = row_of(i);
            if (row >= first && row < first + visible && item(i).contains(px, py)) return i;
        }
        return -1;
    }
};

int first_visible_row = 0;
Page painted_page = Video;
MenuLayout painted{};

void soft_rect(HDC dc, Rect r, int radius, COLORREF colour) {
    if (r.w <= 0 || r.h <= 0) return;
    const int cut = std::min(radius, std::min(r.w, r.h) / 2);
    fill(dc, r.x, r.y + cut, r.w, r.h - 2 * cut, colour);
    for (int i = 0; i < cut; ++i) {
        const int pad = cut - i;
        fill(dc, r.x + pad, r.y + i, r.w - 2 * pad, 1, colour);
        fill(dc, r.x + pad, r.y + r.h - 1 - i, r.w - 2 * pad, 1, colour);
    }
}
void card(HDC dc, Rect r, int scale, COLORREF background, COLORREF border) {
    soft_rect(dc, r, 5 * scale, border);
    soft_rect(dc, r.inset(scale), 4 * scale, background);
}
void mark(HDC dc, int x, int y, int s, COLORREF gold) {
    for (int i = 0; i < 3; ++i) {
        const int centre = x + (i == 0 ? 17 : i == 1 ? 8 : 26) * s;
        const int top = y + (i == 0 ? 0 : 15) * s;
        for (int row = 0; row < 14 * s; ++row) {
            const int span = (row * 8) / 14;
            fill(dc, centre - span, top + row, 2 * span + 1, 1, gold);
        }
    }
}

const char* mode_help(Upscaler mode) {
    if (is_fsr4(mode) && dev.props.vendorID != 0x1002)
        return "O SDK da AMD oferece este modo em Radeons compatíveis. Em uma RTX, DLSS e DLAA são as opções da NVIDIA.";
    if (const char* reason = unavailable(mode)) return reason;
    if (mode == Upscaler::Dlss || mode == Upscaler::Dlaa) {
        if (mode == started_upscaler && !getenv("AKYNO_DLSS_DIR"))
            return "Runtime ausente. Use Baixar DLSS da NVIDIA no launcher.";
    }
    if (mode == started_upscaler && is_temporal(mode) && effective_upscaler() != mode)
        return "O modo solicitado ainda não foi aplicado à cena. O log do jogo registra o motivo se o filtro alternativo persistir.";
    if (is_native_aa(mode)) return "Suaviza bordas em resolução interna de 100%. Usa mais GPU e memória em 4K.";
    if (is_temporal(mode)) return "Reconstrói a imagem a partir de uma escala interna menor. Selecione e reinicie pelo launcher.";
    if (mode == Upscaler::Off) return "Usa a ampliação padrão do jogo.";
    return "Filtro aplicado na apresentação da imagem. Se você usa um modo temporal, reinicie para trocar.";
}

void paint_menu(HDC dc, uint32_t w, uint32_t h, int s) {
    const auto& m = painted;
    const COLORREF page_bg = RGB(9, 9, 9), rail_bg = RGB(16, 15, 12);
    const COLORREF raised = RGB(20, 19, 16), focus = RGB(37, 32, 21);
    const COLORREF line = RGB(50, 43, 29), strong = RGB(103, 81, 43);
    const COLORREF ink = RGB(241, 237, 228), quiet = RGB(180, 173, 160);
    const COLORREF gold = RGB(214, 173, 81), light_gold = RGB(240, 204, 121);

    fill(dc, 0, 0, int(w), int(h), page_bg);
    fill(dc, 0, 0, int(w), m.header, rail_bg);
    fill(dc, 0, 0, int(w), 2 * s, gold);
    fill(dc, 0, m.header - s, int(w), s, line);
    fill(dc, 0, int(h) - s, int(w), s, line);

    SetBkMode(dc, TRANSPARENT);
    const bool inline_tabs = m.header == 61 * s;
    HFONT brand = font((inline_tabs ? 22 : 17) * s, FW_NORMAL, "Georgia");
    HFONT body = font(16 * s, FW_SEMIBOLD);
    HFONT detail = font(14 * s, FW_NORMAL);
    HGDIOBJ old = SelectObject(dc, brand);
    if (inline_tabs) mark(dc, 16 * s, 16 * s, s, gold);
    SetTextColor(dc, gold);
    line_text(dc, (inline_tabs ? 59 : 12) * s, (inline_tabs ? 17 : 10) * s,
              inline_tabs ? 166 * s : int(w) - 24 * s, "AkynoLeyend");
    SelectObject(dc, body);
    for (int i = 0; i < PageCount; ++i) {
        const Rect button = m.tab(i);
        const bool active = i == page;
        card(dc, button, s, active ? focus : raised, active ? strong : line);
        if (active) fill(dc, button.x + 9 * s, button.y + button.h - 3 * s, button.w - 18 * s, 2 * s, gold);
        SetTextColor(dc, active ? light_gold : quiet);
        line_text(dc, button.x + 13 * s, button.y + 8 * s, button.w - 26 * s, page_labels[i]);
    }

    const auto active = effective_upscaler();
    const bool pending = Upscaler(selected_upscaler) != started_upscaler;
    const bool fallback = is_temporal(started_upscaler) && active != started_upscaler;
    if (m.status_h) {
        const Rect status{m.x, m.top - m.status_h, m.w, m.status_h - 9 * s};
        card(dc, status, s, raised, strong);
        SelectObject(dc, detail);
        SetTextColor(dc, quiet);
        line_text(dc, status.x + 12 * s, status.y + 5 * s, status.w - 24 * s, fallback ? "Filtro alternativo em uso" : "Modo em uso");
        SelectObject(dc, body);
        SetTextColor(dc, light_gold);
        line_text(dc, status.x + 12 * s, status.y + 20 * s, status.w - 24 * s, upscaler_label(active));
        if (pending || fallback) {
            const bool narrow = status.w < 410 * s;
            SelectObject(dc, detail);
            SetTextColor(dc, quiet);
            const char* note = pending ? "Reinicie para aplicar" : "Solicitado ao abrir";
            if (!narrow) line_text(dc, status.x + status.w / 2, status.y + 5 * s, status.w / 2 - 12 * s, note, true);
            line_text(dc, status.x + status.w / 2, status.y + 21 * s, status.w / 2 - 12 * s,
                      narrow ? note : upscaler_label(pending ? Upscaler(selected_upscaler) : started_upscaler), true);
        }
    }

    for (int i = 0; i < item_count(); ++i) {
        const int row = m.row_of(i);
        if (row < m.first || row >= m.first + m.visible) continue;
        const Rect r = m.item(i);
        const bool focused = i == selected;
        const bool is_mode = mode_item(i);
        const Upscaler mode = is_mode ? item_mode(i) : Upscaler::Off;
        const bool in_use = is_mode && mode == active;
        card(dc, r, s, focused ? focus : raised, in_use ? gold : focused ? strong : line);
        if (focused) fill(dc, r.x + 3 * s, r.y + 6 * s, 2 * s, r.h - 12 * s, gold);
        SelectObject(dc, body);
        if (is_mode) {
            const char* locked = unavailable(mode);
            SetTextColor(dc, in_use ? light_gold : locked ? quiet : ink);
            line_text(dc, r.x + 12 * s, r.y + 3 * s, r.w - 24 * s, upscaler_label(mode));
            SelectObject(dc, detail);
            SetTextColor(dc, in_use ? light_gold : quiet);
            const char* note = in_use ? "Em uso" : locked ? locked :
                mode == Upscaler(selected_upscaler) ? "Salvo · reinicie" :
                is_temporal(mode) ? "Temporal · reinicia" : "Espacial";
            line_text(dc, r.x + 12 * s, r.y + 21 * s, r.w - 24 * s, note);
            continue;
        }

        const Row& option = menu_row(i);
        const int mid = r.x + r.w * 52 / 100, baseline = r.y + (r.h - 18 * s) / 2;
        SetTextColor(dc, ink);
        line_text(dc, r.x + 12 * s, baseline, mid - r.x - 20 * s, option.label);
        SetTextColor(dc, focused ? light_gold : quiet);
        if (option.value == &opts.sharpness) {
            const Rect bar = m.slider(i);
            fill(dc, bar.x, bar.y, bar.w, bar.h, strong);
            fill(dc, bar.x, bar.y, bar.w * opts.sharpness / 100, bar.h, gold);
            if (bar.w > 0) soft_rect(dc, {bar.x + bar.w * opts.sharpness / 100 - 3 * s, bar.y - 3 * s, 6 * s, 9 * s}, 2 * s, light_gold);
            line_text(dc, r.x + r.w - 58 * s, baseline, 44 * s, tx_percent(opts.sharpness), true);
        } else {
            const int value = option.value == &opts.resolution ? selected_scale() : *option.value;
            if (needs_restart(option.value)) {
                SetTextColor(dc, gold);
                char pending[128];
                snprintf(pending, sizeof pending, "%s · reinicie", option.text(value));
                line_text(dc, mid, baseline, r.x + r.w - mid - 13 * s, pending, true);
            } else line_text(dc, mid, baseline, r.x + r.w - mid - 13 * s, option.text(value), true);
        }
    }
    if (m.visible < m.total) {
        const int track = m.visible * m.row_h - 5 * s;
        fill(dc, m.x + m.w + 6 * s, m.top, 2 * s, track, line);
        fill(dc, m.x + m.w + 6 * s, m.top + track * m.first / m.total, 2 * s, track * m.visible / m.total, gold);
    }
    if (m.side || m.help_h) {
        const int footer_y = m.height - 47 * s;
        const Rect help_box = m.side
            ? Rect{m.x + m.w + 18 * s, m.title_y, m.side, footer_y - m.title_y - 10 * s}
            : Rect{m.x, m.top + m.visible * m.row_h + 4 * s, m.w, m.help_h};
        const bool is_mode = mode_item(selected);
        const auto mode = is_mode ? item_mode(selected) : Upscaler::Off;
        const Row* option = is_mode ? nullptr : &menu_row(selected);
        const char* label = is_mode ? upscaler_label(mode) : option->label;
        const char* help = is_mode ? mode_help(mode) : option->help;
        if (is_mode && pending && mode == Upscaler(selected_upscaler) && !unavailable(mode))
            help = "No launcher, escolha Gráficos > Ampliação > Usar opção salva e abra o jogo novamente.";
        if (option && option->value == &opts.resolution && is_native_aa(Upscaler(selected_upscaler)))
            help = "DLAA e AA nativo renderizam em 100%. Selecione um modo de ampliação para reduzir a escala.";
        if (option && option->value == &opts.output_res && opts.output_res == 5 && opts.handheld)
            help = "2560 × 1600 usa o perfil de mesa. Desligue o perfil portátil e reinicie.";
        card(dc, help_box, s, rail_bg, strong);
        const int inset = 13 * s, inner = help_box.w - 2 * inset;
        SelectObject(dc, body);
        SetTextColor(dc, light_gold);
        line_text(dc, help_box.x + inset, help_box.y + 8 * s, inner, label);
        SelectObject(dc, detail);
        SetTextColor(dc, quiet);
        wrap_help(dc, help, inner, help_box.x + inset, help_box.y + 31 * s, m.side ? 5 : 2);
        if (m.side && page != Controls && help_box.h >= 192 * s) {
            const int y = help_box.y + help_box.h - 77 * s;
            fill(dc, help_box.x + inset, y, inner, s, line);
            char window[52];
            snprintf(window, sizeof window, "Janela Vulkan  %u × %u", dev.swap_extent.width, dev.swap_extent.height);
            char output[72];
            snprintf(output, sizeof output, "Saída em uso  %s", tx_output(boot_output));
            line_text(dc, help_box.x + inset, y + 10 * s, inner, window);
            line_text(dc, help_box.x + inset, y + 31 * s, inner, output);
            if (opts.output_res != boot_output) {
                SetTextColor(dc, gold);
                line_text(dc, help_box.x + inset, y + 52 * s, inner, "Reinicie para aplicar a saída");
            }
        }
    }

    const int foot = m.height - 47 * s;
    fill(dc, 0, foot, int(w), 47 * s, rail_bg);
    fill(dc, 0, foot, int(w), s, line);
    SelectObject(dc, detail);
    if (binding_capture.active) {
        SetTextColor(dc, light_gold);
        line_text(dc, 16 * s, foot + 15 * s, int(w) - 32 * s, "Pressione o botão ou a tecla · Esc cancela · Delete limpa");
    } else {
        static const char* labels[] = {"Navegar", "Ajustar", "Seções", "Fechar"};
        for (int i = 0; i < 7; ++i) {
            const Rect key = m.footer_key(i);
            if (m.width >= 700 * s && i % 2 == 0) {
                SetTextColor(dc, quiet);
                line_text(dc, key.x - 94 * s, key.y + 5 * s, 86 * s, labels[i / 2]);
            }
            card(dc, key, s, raised, strong);
            if (i >= 4) {
                SetTextColor(dc, light_gold);
                line_text(dc, key.x + 7 * s, key.y + 4 * s, key.w - 10 * s, i == 4 ? "Q" : i == 5 ? "E" : "Esc");
            } else {
                const int x = key.x + key.w / 2, y = key.y + key.h / 2;
                for (int n = 0; n < 5 * s; ++n) {
                    const int span = n / 2;
                    if (i < 2) fill(dc, x - span, y + (i ? 2 * s - n : n - 2 * s), 2 * span + 1, 1, light_gold);
                    else fill(dc, x + (i == 3 ? 2 * s - n : n - 2 * s), y - span, 1, 2 * span + 1, light_gold);
                }
            }
        }
    }
    SelectObject(dc, old);
    DeleteObject(brand);
    DeleteObject(body);
    DeleteObject(detail);
}

char fps_text[48] = "";
char fps_sub[32] = "";
/// The FPS overlay: a gold number with a dark edge, nothing behind it. Hard-edged letters: see-through pixels are copied or not.
void outlined(HDC dc, int x, int y, const char* text, COLORREF colour, int edge) {
    SetTextColor(dc, RGB(6, 8, 6));
    const int n = (int)strlen(text);
    for (int dy = -edge; dy <= edge; dy++)
        for (int dx = -edge; dx <= edge; dx++)
            if (dx || dy) TextOutA(dc, x + dx, y + dy, text, n);
    SetTextColor(dc, colour);
    TextOutA(dc, x, y, text, n);
}
HFONT hard_font(int px, int weight) {
    return CreateFontA(-px, 0, 0, 0, weight, 0, 0, 0, DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, NONANTIALIASED_QUALITY,
                       DEFAULT_PITCH, "Segoe UI");
}
void paint_fps(HDC dc, uint32_t w, uint32_t h, int s) {
    fill(dc, 0, 0, (int)w, (int)h, RGB(0, 0, 0));
    SetBkMode(dc, TRANSPARENT);
    SetTextAlign(dc, TA_RIGHT | TA_TOP);
    const COLORREF gold = RGB(240, 204, 121);
    const int right = (int)w - 2 * s;
    HFONT label = hard_font(13 * s, FW_BOLD), big = hard_font(28 * s, FW_BOLD);
    HGDIOBJ old = SelectObject(dc, label);
    outlined(dc, right, 14 * s, "FPS", gold, s);
    SelectObject(dc, big);
    outlined(dc, right - 30 * s, 0, fps_text, gold, s);
    if (fps_sub[0]) {
        SelectObject(dc, label);
        outlined(dc, right, 32 * s, fps_sub, RGB(226, 232, 226), s);
    }
    SelectObject(dc, old);
    DeleteObject(label);
    DeleteObject(big);
}
void redraw_menu_at(int s) {
    const int width = s == 1 ? std::min(kMenuWidth, std::max(1, int(dev.swap_extent.width))) : kMenuWidth * s;
    const int window_h = std::max(1, int(dev.swap_extent.height));
    const int header = (width >= 620 * s ? 61 : 90) * s;
    const int side = width >= 920 * s ? width / 3 : 0;
    const int pad = 18 * s, x = pad, w = width - 2 * pad - (side ? side + pad : 0);
    const int title_y = header + 14 * s;
    const int status_h = page == Upscaling && window_h >= 275 * s ? 55 * s : 0;
    const int top = title_y + status_h;
    const int columns = page == Upscaling && w >= 390 * s ? 2 : 1;
    const int row_h = (page == Upscaling ? 44 : 38) * s;
    const int total = page == Upscaling ? kScaleRows + (int(Upscaler::Count) + columns - 1) / columns : item_count();
    const int help_h = !side && window_h >= 350 * s ? 68 * s : 0;
    const int fixed = top + help_h + 58 * s;
    const int visible = s == 1 ? std::clamp((window_h - fixed) / row_h, 1, total) : total;
    const int height = s == 1 ? std::min(window_h, fixed + visible * row_h) : fixed + visible * row_h;
    painted = {width, height, s, header, side, x, w, title_y, status_h, top, row_h, columns, 0, visible, total, help_h};
    first_visible_row = menu_pointer::first_row(first_visible_row, painted.row_of(selected), visible, total);
    painted.first = first_visible_row;
    painted_page = page;
    gdi_draw(menu_bmp, uint32_t(width), uint32_t(height), paint_menu, s);
}

std::atomic<int64_t> game_frames{0}, shown_frames{0};
int cur_scale = 1;
// Hookshot v2.0.13: reduce whole-size steps until the overlay fits. The fitted
// scale is shared by rendering and pointer input and reset when the window changes.
int menu_fit = 1 << 20;
uint32_t menu_fit_w = 0, menu_fit_h = 0;
int menu_scale_for(uint32_t w, uint32_t h) {
    if (w != menu_fit_w || h != menu_fit_h) {
        menu_fit_w = w, menu_fit_h = h, menu_fit = 1 << 20;
    }
    // (Menu size: a whole step smaller or larger, where the window has the room: redraw_menu fits it)
    return std::min(std::max(1, scale_of(h) + opts.menu_size - 2), menu_fit);
}
void redraw_menu(int s) {
    for (;;) {
        redraw_menu_at(s);
        uint32_t w, h;
        { std::lock_guard lk(bmp_mu); w = menu_bmp.w, h = menu_bmp.h; }
        if (s <= 1 || (w <= dev.swap_extent.width && h <= dev.swap_extent.height)) return;
        menu_fit = cur_scale = --s;
    }
}

struct Upload {
    VkBuffer buf = VK_NULL_HANDLE;
    VmaAllocation alloc = nullptr;
    void* map = nullptr;
    uint64_t size = 0, version = 0;
};
Upload ups[2][3];   // (the menu's, the counter's; a frame in flight's each)

void copy_over(VkCommandBuffer cmd, VkImage dst, Bitmap& b, Upload& u, int x, int y, uint32_t w, uint32_t h) {
    std::lock_guard lk(bmp_mu);
    if (!b.w) return;
    // Keyed FPS runs stay whole. The smallest menu may exceed a small window;
    // copy its visible area instead of dropping the complete overlay.
    if (b.keyed && (x < 0 || y < 0 || uint64_t(x) + b.w > w || uint64_t(y) + b.h > h)) return;
    const auto area = menu_pointer::clip(x, y, b.w, b.h, w, h);
    if (!area.width || !area.height) return;
    const uint64_t size = (uint64_t)b.w * b.h * 4;
    if (u.size < size) {
        if (!create_buffer(size, VK_BUFFER_USAGE_TRANSFER_SRC_BIT, true, u.buf, u.alloc, &u.map)) return;
        u.size = size, u.version = 0;
    }
    if (u.version != b.version) std::memcpy(u.map, b.px.data(), size), u.version = b.version;
    if (b.keyed) {
        static thread_local std::vector<VkBufferImageCopy> at;
        at = b.runs;
        for (auto& r : at) r.imageOffset.x += x, r.imageOffset.y += y;
        if (!at.empty()) vkCmdCopyBufferToImage(cmd, u.buf, dst, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, (uint32_t)at.size(), at.data());
        return;
    }
    VkBufferImageCopy c{};
    c.bufferOffset = area.offset;
    c.bufferRowLength = b.w;
    c.imageSubresource = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1};
    c.imageOffset = {area.x, area.y, 0};
    c.imageExtent = {area.width, area.height, 1};
    vkCmdCopyBufferToImage(cmd, u.buf, dst, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, 1, &c);
}

} // namespace

void menu_init() {
    static bool done;
    if (done) return;
    done = true;
    Upscaler saved_upscaler = Upscaler::Count;
    if (FILE* f = hos_game_file("AkynoLeyend_opts.ini", "r")) {
        char line[80];
        bool has_resolution = false;
        bool v2 = false;
        int old_dynres = -1;   // (the row before Resolution: 0, the full scale, is its 100%; 1 is Auto)
        while (fgets(line, sizeof line, f)) {
            char* eq = strchr(line, '=');
            if (!eq) continue;
            *eq = 0;
            for (Row& r : rows)
                if (r.value != &selected_upscaler && !strcmp(line, ini_key(r)))
                    *r.value = std::clamp(atoi(eq + 1), r.lo, r.hi);
            if (!strcmp(line, "upscaling")) opts.upscale = std::clamp(atoi(eq + 1), 0, int(Upscaler::Fsr1));
            if (!strcmp(line, "upscaler")) {
                std::string_view value(eq + 1);
                saved_upscaler = parse_upscaler(value.substr(0, value.find_first_of("\r\n")), Upscaler::Count);
            }
            if (!strcmp(line,"button_prompts")) opts.prompts=std::clamp(atoi(eq+1),0,5);
            has_resolution |= !strcmp(line, "resolution");
            v2 |= !strcmp(line, "options_version");
            if (!strcmp(line, "dynamic_resolution")) old_dynres = atoi(eq + 1);
        }
        fclose(f);
        if (!has_resolution && old_dynres >= 0) opts.resolution = old_dynres ? 0 : 1;
        // (Game speed is Real time by default now: Per frame played at half speed at 30 fps, the "slow motion" players
        // reported. An options file from before kept the old default whether chosen or not: Real time for it too)
        if (!v2) opts.realtime = 1;
    }
    if (opts.framegen == 1) opts.framegen = 2;
    if (const char* e = getenv("RX_VK_FRAMEGEN_MULT")) opts.framegen = std::min(std::max(atoi(e), 2), 8);
    if (const char* e = getenv("RX_VK_PACE")) opts.pace = atoi(e) != 0;
    if (const char* e = getenv("RX_VK_UPSCALE")) opts.upscale = std::clamp(atoi(e), 0, int(Upscaler::Fsr1));
    if (const char* e = getenv("HOS_OUTPUT_RES")) opts.output_res = atoi(e);
    if (const char* e = getenv("HOS_REALTIME_STEP")) opts.realtime = atoi(e) != 0;
    if (const char* e = getenv("HOS_DYNRES")) opts.resolution = atoi(e) != 0 ? 0 : 1;
    if (const char* e = getenv("AKYNO_RESOLUTION")) opts.resolution = std::clamp(atoi(e), 0, 6);
    if (const char* e = getenv("AKYNO_FRAMEGEN")) { opts.framegen = std::clamp(atoi(e), 0, 9); if (opts.framegen == 1) opts.framegen = 0; }
    if (const char* e = getenv("AKYNO_SHARPNESS")) opts.sharpness = std::clamp(atoi(e), 0, 100);
    if (const char* e = getenv("AKYNO_FPS_COUNTER")) opts.show_fps = atoi(e) != 0;
    if (const char* e = getenv("HOS_HANDHELD")) opts.handheld = atoi(e) != 0;
    extended_outputs = getenv("AKYNO_EXTENDED_OUTPUTS") != nullptr;
    if (opts.output_res < 0 || opts.output_res > (extended_outputs ? 5 : 3)) opts.output_res = 0;
    boot_output = opts.handheld && opts.output_res != 3 && opts.output_res != 4 ? 0 : opts.output_res;
    started_upscaler = Upscaler(opts.upscale);
    const char* engine = getenv("AKYNO_TEMPORAL_ENGINE");
    const char* fsr = getenv("AKYNO_FSR_TEMPORAL");
    if (engine && !strcmp(engine, "dlss")) started_upscaler = opts.resolution == 1 ? Upscaler::Dlaa : Upscaler::Dlss;
    else if (fsr && !strcmp(fsr, "1")) {
        if (engine && !strcmp(engine, "fsr4"))
            started_upscaler = opts.resolution == 1 ? Upscaler::Fsr4Native : Upscaler::Fsr4;
        else started_upscaler = opts.resolution == 1 ? Upscaler::Fsr31Native : Upscaler::Fsr31;
    }
    if (const char* e = getenv("AKYNO_UPSCALER")) started_upscaler = parse_upscaler(e, started_upscaler);
    selected_upscaler = int(started_upscaler);
    if (!getenv("AKYNO_UPSCALER") && !is_temporal(started_upscaler) &&
        saved_upscaler != Upscaler::Count && is_temporal(saved_upscaler))
        selected_upscaler = int(saved_upscaler);
    temporal_menu = getenv("AKYNO_TEMPORAL_MENU") != nullptr;
}

bool menu_is_open() { return open_now.load(std::memory_order_relaxed); }

void menu_note_frame(bool game_frame) {
    shown_frames.fetch_add(1, std::memory_order_relaxed);
    if (game_frame) game_frames.fetch_add(1, std::memory_order_relaxed);
}

// The Fullscreen row and F11 are one setting: the row asks the window's thread (host/display.c), F11 shows in the row
void fullscreen_tick() {
    static int applied = 0, settle = 0;
    const HWND main_window = app_window();
    if (!main_window) return;
    static const bool env = getenv("HOS_FULLSCREEN") != nullptr;   // (a test's own choice: the row is left alone)
    if (env) return;
    if (opts.fullscreen != applied) {
        applied = opts.fullscreen;
        settle = 60;
        PostMessageA(main_window, WM_APP + 7, (WPARAM)applied, 0);
        return;
    }
    if (settle > 0) { settle--; return; }
    const int now = !(GetWindowLongA(main_window, GWL_STYLE) & WS_CAPTION);
    if (now != applied) {
        opts.fullscreen = applied = now;
        menu_refresh = true;
        save();
    }
}

/// A rate over the half-second that just ended. The first call only starts that interval: the frames since launch,
/// divided by one second, were shown as the rate the moment the counter was turned on.
bool fps_take(int64_t now, int64_t shown, int64_t game, int64_t* next, int64_t* last_shown, int64_t* last_game,
              double* shown_rate, double* game_rate) {
    if (now < *next) return false;
    const bool have = *next != 0;
    if (have) {
        const double secs = (now - *next + 500000000) / 1e9;
        *shown_rate = (shown - *last_shown) / secs;
        *game_rate = (game - *last_game) / secs;
    }
    *last_shown = shown;
    *last_game = game;
    *next = now + 500000000;
    return have;
}

// (once, at the first tick, after menu_init has read the file and the environment: what the rows read only at the start
// were, for their "reinicie" mark)
static void note_boot_values() {
    static bool done;
    if (done) return;
    done = true;
    if (opts.gpu_device > int(gpu_device_names.size())) opts.gpu_device = 0;   // (a card that is gone: Auto)
    for (int i = 0; i < SettingCount; ++i) boot_values[i] = *rows[i].value;
    boot_values[Output] = boot_output;
}

void menu_tick() {
    note_boot_values();
    fullscreen_tick();
    static const int keys[] = {VK_INSERT, VK_UP, VK_DOWN, VK_LEFT, VK_RIGHT, VK_ESCAPE, VK_F1,
                               'W', 'S', 'A', 'D', 'M', VK_LBUTTON, 'Q', 'E'};
    static bool held[std::size(keys)]{};
    HWND fg = GetForegroundWindow();
    DWORD pid = 0;
    if (fg) GetWindowThreadProcessId(fg, &pid);
    const bool mine = pid == GetCurrentProcessId();
    bool press[std::size(keys)]{};
    for (size_t i = 0; i < std::size(keys); i++) {
        const bool down = mine && (GetAsyncKeyState(keys[i]) & 0x8000) != 0;
        press[i] = down && !held[i];
        held[i] = down;
    }
    const bool resized = dev.swap_extent.width != menu_fit_w || dev.swap_extent.height != menu_fit_h;
    const int scale = menu_scale_for(dev.swap_extent.width, dev.swap_extent.height);
    bool changed = resized || scale != cur_scale || menu_refresh;
    {   // (AkynoLeyend r13: the window's image changed its pixels, HDR10 on or off or its paper white: the panel is drawn
        // again in them, and the counter is left out until its next count, both being bytes copied over that image)
        static uint32_t pixels_were = 0;
        const uint32_t pixels_now = (uint32_t)dev.swap_format << 12 ^ (dev.hdr ? 1u << 11 | (uint32_t)akyno_hdr_white(opts.hdr_white) : 0u);
        if (pixels_now != pixels_were) {
            if (pixels_were) {
                std::lock_guard lk(bmp_mu);
                fps_bmp.w = fps_bmp.h = 0;
            }
            pixels_were = pixels_now, changed = true;
        }
    }
    menu_refresh = false;
    cur_scale = scale;
    const bool chord = press[11] && (GetAsyncKeyState(VK_CONTROL) & 0x8000);
    // (r10: the Menu shortcut row. Esc, with it, only opens: an open panel takes Esc as before, back a page or closed)
    const bool was_open = open_now.load();
    const bool esc_opens = !was_open && press[5] && akyno_menu_opens(opts.menu_shortcut, 0, 0, 0, 1);
    if (akyno_menu_opens(opts.menu_shortcut, press[6], press[0], chord, 0) || esc_opens)
        open_now = !was_open, changed = true;
    static bool special_held[2]{};
    const bool tab = mine && (GetAsyncKeyState(VK_TAB) & 0x8000);
    const bool enter = mine && (GetAsyncKeyState(VK_RETURN) & 0x8000);
    const bool tab_press = tab && !special_held[0];
    bool activate = enter && !special_held[1];
    special_held[0] = tab;
    special_held[1] = enter;

    static bool was_mouse = false, dragging = false;
    static POINT previous{};
    if (!open_now.load()) {
        binding_capture.active = false;
        was_mouse = false;
        if (dragging) {
            dragging = false;
            save();
        }
    } else {
        const Upscaler actual = fsr_sdk_active();
        changed |= actual != displayed_upscaler;
        displayed_upscaler = actual;

        const auto read_input = [&](bool (&keys_now)[256]) {
            for (int i = 0; i < 256; ++i) keys_now[i] = mine && (GetAsyncKeyState(i) & 0x8000);
        };
        if (binding_capture.active) {
            bool keys_now[256];
            read_input(keys_now);
            int code = 0;
            const int result = binding_capture.poll(keys_now, host && host->pad_raw ? host->pad_raw() : 0, mine, code);
            if (result == 1) {
                control_editor.bind(host, binding_capture.set, binding_capture.slot, code);
                save();
            }
            changed |= result != 0;
        } else {
            const auto switch_page = [&](Page next) {
                if (page == next) return;
                if (dragging) save();
                dragging = false;
                page = next;
                selected = 0;
                first_visible_row = 0;
                if (page == Controls) control_editor.refresh(host);
                menu_fit = 1 << 20;
                changed = true;
            };
            const auto step_page = [&](int direction) {
                switch_page(Page((int(page) + direction + PageCount) % PageCount));
            };
            if (tab_press || press[14]) step_page(1);
            else if (press[13]) step_page(-1);

            press[1] |= press[7];
            press[2] |= press[8];
            press[3] |= press[9];
            press[4] |= press[10];
            POINT cursor{};
            RECT client{};
            const HWND window = app_window();
            const bool current_layout = !resized && painted.width && painted_page == page;
            if (mine && window && current_layout && GetCursorPos(&cursor) &&
                ScreenToClient(window, &cursor) && GetClientRect(window, &client)) {
                const auto origin = menu_pointer::origin(int(dev.swap_extent.width), int(dev.swap_extent.height),
                                                         painted.width, painted.height);
                const int mx = menu_pointer::image_coordinate(cursor.x, client.right, int(dev.swap_extent.width)) - origin.x;
                const int my = menu_pointer::image_coordinate(cursor.y, client.bottom, int(dev.swap_extent.height)) - origin.y;
                const bool moved = was_mouse && (cursor.x != previous.x || cursor.y != previous.y);
                if (press[12]) {
                    for (int i = 0; i < PageCount; ++i)
                        if (painted.tab(i).contains(mx, my)) switch_page(Page(i));
                    for (int i = 0; i < 7; ++i) {
                        if (!painted.footer_key(i).contains(mx, my)) continue;
                        if (i < 4) press[i + 1] = true;
                        else if (i < 6) step_page(i == 4 ? -1 : 1);
                        else open_now = false;
                        break;
                    }
                }
                const int hover = painted_page == page ? painted.hit(mx, my) : -1;
                if (hover >= 0 && (moved || press[12]) && !dragging && hover != selected) {
                    selected = hover;
                    changed = true;
                }
                if (press[12] && hover >= 0) {
                    const Rect bar = painted.slider(hover);
                    if (page == Upscaling && hover == 1 && mx >= bar.x && bar.w > 0)
                        dragging = true;
                    else activate = true;
                }
                if (dragging) {
                    if (!held[12]) {
                        dragging = false;
                        save();
                    } else {
                        const Rect bar = painted.slider(1);
                        if (bar.w > 0) {
                            const int v = std::clamp((mx - bar.x) * 100 / bar.w, 0, 100) / 10 * 10;
                            changed |= v != opts.sharpness;
                            opts.sharpness = v;
                        }
                    }
                }
                previous = cursor;
                was_mouse = true;
            } else {
                if (dragging) save();
                dragging = false;
                was_mouse = false;
            }

            if (press[5] && !esc_opens) open_now = false;
            if (open_now.load() && !dragging) {
                const int columns = painted_page == page ? painted.columns : 1;
                const int direction = int(press[2]) - int(press[1]);
                if (direction) {
                    int next = selected + (mode_item(selected) ? columns : 1) * direction;
                    if (mode_item(selected) && next < kScaleRows) next = kScaleRows - 1;
                    if (page == Upscaling && columns == 2 && next < 0) next = item_count() - columns;
                    selected = (next + item_count()) % item_count();
                    changed = true;
                }

                if (mode_item(selected)) {
                    if (columns == 2 && press[3] != press[4]) {
                        selected = kScaleRows + (selected - kScaleRows) / columns * columns + int(press[4]);
                        changed = true;
                    }
                    if (activate && choose_upscaler(item_mode(selected))) {
                        changed = true;
                        save();
                    }
                } else if (press[3] || press[4] || activate) {
                    const Row& r = menu_row(selected);
                    const bool pad = r.value == &control_editor.pad;
                    if (pad || r.value == &control_editor.key[0] || r.value == &control_editor.key[1]) {
                        if (!pad || control_editor.action < HOS_SW_N) {
                            bool keys_now[256];
                            read_input(keys_now);
                            binding_capture.begin(pad ? HOS_BIND_PAD : HOS_BIND_KEY,
                                                  r.value == &control_editor.key[1] ? 1 : 0, keys_now,
                                                  host && host->pad_raw ? host->pad_raw() : 0);
                            changed = true;
                        }
                    } else {
                        const bool forward = press[4] || activate;
                        const bool scale_setting = r.value == &opts.resolution;
                        int lo = r.lo, hi = r.hi;
                        if (r.value == &opts.output_res && !extended_outputs) hi = 3;
                        if (r.value == &opts.gpu_device) hi = int(gpu_device_names.size());
                        const auto mode = Upscaler(selected_upscaler);
                        if (scale_setting && is_temporal(mode)) {
                            lo = is_native_aa(mode) ? 1 : 2;
                            hi = is_native_aa(mode) ? 1 : 4;
                        }
                        int v = (scale_setting ? selected_scale() : *r.value) + (forward ? r.step : -r.step);
                        if (r.value == &opts.framegen && v == 1) v = forward ? 2 : 0;
                        v = v > hi ? lo : v < lo ? hi : v;
                        if (scale_setting && mode != started_upscaler) pending_render_scale = v;
                        else *r.value = v;
                        if (r.value == &opts.preset) apply_preset(v);
                        else if (preset_row(r.value)) opts.preset = 0;   // (a row of the preset set by hand: Custom)
                        if (r.value == &opts.menu_size) menu_fit = 1 << 20;
                        if (r.value == &control_editor.layout) control_editor.preset(host, v);
                        else if (r.value == &control_editor.action) control_editor.refresh(host);
                        changed = true;
                        save();
                    }
                }
            }
        }
        if (changed && open_now.load()) redraw_menu(menu_scale_for(dev.swap_extent.width, dev.swap_extent.height));
    }
    {
        static bool told = false;
        const bool now_open = open_now.load();
        if (now_open != told && app_window()) {
            told = now_open;
            PostMessageA(app_window(), WM_APP + 8, (WPARAM)now_open, 0);
        }
    }
    if (opts.show_fps) {
        static int64_t next = 0, last_game = 0, last_shown = 0;
        const int64_t now = prof_now();
        double shown = 0, game = 0;
        if (fps_take(now, shown_frames.load(), game_frames.load(), &next, &last_shown, &last_game, &shown, &game)) {
            snprintf(fps_text, sizeof fps_text, "%.0f", shown);
            if (opts.framegen >= 2) snprintf(fps_sub, sizeof fps_sub, "base %.0f", game);
            else fps_sub[0] = 0;
            fps_bmp.keyed = true;
            const int fps_scale = std::max(1, scale_of(dev.swap_extent.height) + opts.menu_size - 2);
            gdi_draw(fps_bmp, 120u * fps_scale, 54u * fps_scale, paint_fps, fps_scale);
        }
    }
}

void menu_record(VkCommandBuffer cmd, VkImage dst, int slot, uint32_t w, uint32_t h) {
    if (opts.show_fps) {
        std::unique_lock lk(bmp_mu);
        const uint32_t fw = fps_bmp.w;
        lk.unlock();
        const int fps_scale = std::max(1, scale_of(dev.swap_extent.height) + opts.menu_size - 2);
        if (fw) copy_over(cmd, dst, fps_bmp, ups[1][slot], (int)w - (int)fw - (int)(12 * fps_scale), (int)(10 * fps_scale), w, h);
    }
    if (open_now.load(std::memory_order_relaxed)) {
        std::unique_lock lk(bmp_mu);
        const uint32_t mw = menu_bmp.w, mh = menu_bmp.h;
        lk.unlock();
        // (one copy finished before the next: on a Radeon the menu came out with its top torn away beside the FPS counter)
        VkMemoryBarrier2 mb{VK_STRUCTURE_TYPE_MEMORY_BARRIER_2};
        mb.srcStageMask = mb.dstStageMask = VK_PIPELINE_STAGE_2_ALL_TRANSFER_BIT;
        mb.srcAccessMask = mb.dstAccessMask = VK_ACCESS_2_TRANSFER_WRITE_BIT;
        VkDependencyInfo di{VK_STRUCTURE_TYPE_DEPENDENCY_INFO};
        di.memoryBarrierCount = 1, di.pMemoryBarriers = &mb;
        vkCmdPipelineBarrier2(cmd, &di);
        const auto origin = menu_pointer::origin((int)w, (int)h, (int)mw, (int)mh);
        if (mw) copy_over(cmd, dst, menu_bmp, ups[0][slot], origin.x, origin.y, w, h);
    }
}

} // namespace mkwvk
