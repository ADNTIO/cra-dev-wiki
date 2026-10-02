/*
 * Device screen: the logo at boot, then the steps, one per line.
 * Without a screen declared in the devicetree, these functions do nothing.
 */

#ifndef SCREEN_H_
#define SCREEN_H_

/* Turns the screen on and shows the logo. */
void screen_init(void);

/* Adds a step at the bottom of the screen (ASCII, 12 characters at most). */
void screen_step(const char *fmt, ...);

#endif
