/*
 * Mise à jour par LoRa point à point, sans réseau LoRaWAN.
 *
 * Le transport réutilise le décodeur TS004 et l'écriture dans le slot secondaire
 * de Zephyr, exactement comme une session FUOTA LoRaWAN. Ce qui manque par
 * rapport à LoRaWAN : le serveur réseau, le chiffrement, le multicast et la
 * synchronisation d'horloge. Rien de tout cela n'authentifie le firmware de toute
 * façon : c'est la signature, vérifiée par MCUboot, qui décide.
 *
 * Trames (octets, petit-boutiste), toutes préfixées par « AD », type, session :
 *   SETUP (1) émetteur -> appareil : nb_frag u16, frag_size u8, padding u8
 *   READY (2) appareil -> émetteur : statut u8 (0 = prêt)
 *   FRAG  (3) émetteur -> appareil : index u16 (à partir de 1), données
 *   DONE  (4) appareil -> émetteur : perdus u16, reconstruits u16
 */

#ifndef P2P_H_
#define P2P_H_

#include <stdint.h>

/* Paramètres radio communs aux deux cartes. EU868, sous-bande g3
 * (869,4 - 869,65 MHz) : 10 % de temps d'émission, 27 dBm au plus.
 */
#define P2P_FREQUENCY 869525000
#define P2P_TX_POWER  14 /* dBm */

/* Sens descendant (émetteur -> appareil), qui porte les fragments : rapide.
 * Sens montant (appareil -> émetteur), quelques octets : robuste, environ 9 dB
 * de sensibilité en plus. Sur notre banc, le sens montant arrivait 40 dB plus
 * faible que le descendant, à la limite de réception en SF7.
 */
#define P2P_DOWN_SF SF_7
#define P2P_DOWN_BW BW_250_KHZ
#define P2P_UP_SF   SF_10
#define P2P_UP_BW   BW_125_KHZ

/* Écoute les sessions de mise à jour ; ne rend la main qu'en cas d'erreur radio.
 * feed est appelé régulièrement pour nourrir le chien de garde.
 */
int p2p_fuota_run(void (*feed)(void));

#endif
