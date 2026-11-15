#pragma once
#include <stdint.h>

/* Called only by the audio renderer thread. Input is interleaved PCM16. */
int hos_wasapi_open(unsigned rate, unsigned channels);
int hos_wasapi_write(const int16_t *samples, unsigned frames); /* 1 queued, 0 full, -1 lost */
void hos_wasapi_close(void);
