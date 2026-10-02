/*
 * Écran de l'appareil, par le framebuffer texte de Zephyr (CFB).
 */

#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#include <zephyr/device.h>
#include <zephyr/display/cfb.h>
#include <zephyr/drivers/display.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>

#include "screen.h"

LOG_MODULE_REGISTER(screen, LOG_LEVEL_INF);

#if DT_HAS_CHOSEN(zephyr_display) && defined(CONFIG_CHARACTER_FRAMEBUFFER)

#include "logo.h"

#define LOGO_DURATION K_SECONDS(3)
#define LINE_LEN      13 /* 12 caractères de 10 pixels, plus le zéro final */
#define MAX_LINES     4  /* 4 lignes de 16 pixels */

static const struct device *const display = DEVICE_DT_GET(DT_CHOSEN(zephyr_display));
static bool ready;
static K_MUTEX_DEFINE(lock);
static char lines[MAX_LINES][LINE_LEN];
static int nb_lines;

static void draw_logo(void)
{
	for (int y = 0; y < LOGO_HEIGHT; y++) {
		for (int x = 0; x < LOGO_WIDTH; x++) {
			if (logo_bitmap[y * LOGO_WIDTH / 8 + x / 8] & (0x80 >> (x % 8))) {
				struct cfb_position pos = {.x = x, .y = y};

				cfb_draw_point(display, &pos);
			}
		}
	}
}

void screen_init(void)
{
	if (!device_is_ready(display) || cfb_framebuffer_init(display) < 0) {
		LOG_WRN("Écran indisponible");
		return;
	}
	cfb_framebuffer_set_font(display, 0); /* 10 x 16 pixels */
	cfb_framebuffer_clear(display, true);
	display_blanking_off(display);

	draw_logo();
	cfb_framebuffer_finalize(display);
	k_sleep(LOGO_DURATION);
	ready = true;
}

void screen_step(const char *fmt, ...)
{
	va_list args;

	if (!ready) {
		return;
	}
	k_mutex_lock(&lock, K_FOREVER);

	/* Les étapes défilent : la plus récente en bas */
	if (nb_lines == MAX_LINES) {
		memmove(lines[0], lines[1], sizeof(lines[0]) * (MAX_LINES - 1));
		nb_lines--;
	}
	va_start(args, fmt);
	vsnprintf(lines[nb_lines++], LINE_LEN, fmt, args);
	va_end(args);

	cfb_framebuffer_clear(display, false);
	for (int i = 0; i < nb_lines; i++) {
		cfb_print(display, lines[i], 0, i * 16);
	}
	cfb_framebuffer_finalize(display);

	k_mutex_unlock(&lock);
}

#else

void screen_init(void)
{
}

void screen_step(const char *fmt, ...)
{
	ARG_UNUSED(fmt);
}

#endif
