/* Shared-mode Windows audio with engine-side format conversion. This avoids
   depending on a working legacy waveOut mapper or an exact endpoint format. */
#define WIN32_LEAN_AND_MEAN
#define COBJMACROS
#include <windows.h>
#include <initguid.h>
#include <mmdeviceapi.h>
#include <audioclient.h>
#include <audiosessiontypes.h>
#include <string.h>
#include "audio_wasapi.h"

void hos_log(const char *format, ...);

static IAudioClient *client;
static IAudioRenderClient *renderer;
static UINT32 capacity;
static unsigned frame_bytes;
static int com_owned, started;

void hos_wasapi_close(void) {
    if (client && started) IAudioClient_Stop(client);
    if (renderer) IAudioRenderClient_Release(renderer);
    if (client) IAudioClient_Release(client);
    renderer = NULL;
    client = NULL;
    capacity = 0;
    started = 0;
    if (com_owned) CoUninitialize();
    com_owned = 0;
}

int hos_wasapi_open(unsigned rate, unsigned channels) {
    hos_wasapi_close();
    HRESULT result = CoInitializeEx(NULL, COINIT_MULTITHREADED);
    if (FAILED(result) && result != RPC_E_CHANGED_MODE) {
        hos_log("audio: WASAPI COM initialization failed: %#lx", (unsigned long)result);
        return 0;
    }
    com_owned = SUCCEEDED(result);
    IMMDeviceEnumerator *enumerator = NULL;
    IMMDevice *device = NULL;
    result = CoCreateInstance(&CLSID_MMDeviceEnumerator, NULL, CLSCTX_INPROC_SERVER,
                              &IID_IMMDeviceEnumerator, (void **)&enumerator);
    if (SUCCEEDED(result)) {
        result = IMMDeviceEnumerator_GetDefaultAudioEndpoint(enumerator, eRender, eConsole, &device);
        if (FAILED(result))
            result = IMMDeviceEnumerator_GetDefaultAudioEndpoint(enumerator, eRender, eMultimedia, &device);
    }
    if (SUCCEEDED(result))
        result = IMMDevice_Activate(device, &IID_IAudioClient, CLSCTX_ALL, NULL, (void **)&client);
    WAVEFORMATEX format = {0};
    format.wFormatTag = WAVE_FORMAT_PCM;
    format.nChannels = (WORD)channels;
    format.nSamplesPerSec = rate;
    format.wBitsPerSample = 16;
    format.nBlockAlign = (WORD)(channels * sizeof(int16_t));
    format.nAvgBytesPerSec = rate * format.nBlockAlign;
    if (SUCCEEDED(result))
        result = IAudioClient_Initialize(client, AUDCLNT_SHAREMODE_SHARED,
                    AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM | AUDCLNT_STREAMFLAGS_SRC_DEFAULT_QUALITY,
                    500000, 0, &format, NULL); /* 50 ms requested; no exclusive mode */
    if (SUCCEEDED(result)) result = IAudioClient_GetBufferSize(client, &capacity);
    if (SUCCEEDED(result))
        result = IAudioClient_GetService(client, &IID_IAudioRenderClient, (void **)&renderer);
    if (device) IMMDevice_Release(device);
    if (enumerator) IMMDeviceEnumerator_Release(enumerator);
    if (FAILED(result) || !capacity) {
        hos_log("audio: WASAPI output unavailable: %#lx", (unsigned long)result);
        hos_wasapi_close();
        return 0;
    }
    frame_bytes = format.nBlockAlign;
    hos_log("audio: WASAPI shared output: %u Hz, %u channels, %u frames buffered", rate, channels, capacity);
    return 1;
}

int hos_wasapi_write(const int16_t *samples, unsigned frames) {
    if (!client || !renderer) return -1;
    UINT32 padding = 0;
    HRESULT result = IAudioClient_GetCurrentPadding(client, &padding);
    if (SUCCEEDED(result) && (padding > capacity || frames > capacity - padding)) return 0;
    BYTE *destination = NULL;
    if (SUCCEEDED(result)) result = IAudioRenderClient_GetBuffer(renderer, frames, &destination);
    if (SUCCEEDED(result)) {
        memcpy(destination, samples, (size_t)frames * frame_bytes);
        result = IAudioRenderClient_ReleaseBuffer(renderer, frames, 0);
    }
    if (SUCCEEDED(result) && !started) {
        unsigned prime = frames * 4;
        if (prime > capacity / 2) prime = capacity / 2;
        if (padding + frames >= prime) {
            result = IAudioClient_Start(client);
            if (SUCCEEDED(result)) started = 1;
        }
    }
    if (FAILED(result)) {
        hos_log("audio: WASAPI stream lost: %#lx; output will be retried", (unsigned long)result);
        hos_wasapi_close();
        return -1;
    }
    return 1;
}
