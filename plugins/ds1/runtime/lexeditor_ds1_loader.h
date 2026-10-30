#pragma once
#include <stddef.h>
#include <wchar.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Apply a lexeditor-ds1-patch.bin to the image at `image`. Returns 1 when
 * every record was applied; 0 when nothing was changed, with the reason in
 * `message`. Every check runs before the first change. */
int lx_apply(unsigned char *image, const unsigned char *data, size_t size, char *message, size_t capacity);

/* Make every connection and host lookup in this process fail, for good.
 * 1 when every way online is blocked. */
int lx_block_network(void);
void lx_debug_log(const char *text);
void lx_online_preflight(void);
void lx_online_start(void);
int lx_save_install(unsigned char *image);
int lx_save_path(const wchar_t *input, wchar_t *output, size_t capacity);
#ifdef __cplusplus
}
#endif
