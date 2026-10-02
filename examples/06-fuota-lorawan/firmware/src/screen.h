/*
 * Écran de l'appareil : le logo au démarrage, puis les étapes, une par ligne.
 * Sans écran déclaré dans le devicetree, ces fonctions ne font rien.
 */

#ifndef SCREEN_H_
#define SCREEN_H_

/* Allume l'écran et affiche le logo. */
void screen_init(void);

/* Ajoute une étape en bas de l'écran (ASCII, 12 caractères au plus). */
void screen_step(const char *fmt, ...);

#endif
