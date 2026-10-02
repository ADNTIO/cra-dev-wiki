/*
 * Update over point-to-point LoRa, without a LoRaWAN network.
 *
 * The transport reuses Zephyr's TS004 decoder and its writes to the secondary slot,
 * exactly like a LoRaWAN FUOTA session. What is missing compared with LoRaWAN: the
 * network server, encryption, multicast and clock synchronisation. None of these
 * authenticates the firmware anyway: the signature, checked by MCUboot, decides.
 *
 * Frames (bytes, little-endian), all prefixed with "AD", type, session:
 *   SETUP (1) sender -> device: nb_frag u16, frag_size u8, padding u8
 *   READY (2) device -> sender: status u8 (0 = ready)
 *   FRAG  (3) sender -> device: index u16 (from 1), data
 *   DONE  (4) device -> sender: lost u16, rebuilt u16
 */

#ifndef P2P_H_
#define P2P_H_

#include <stdint.h>

/* Radio parameters shared by both boards. EU868, g3 sub-band
 * (869.4 - 869.65 MHz): 10% duty cycle, 27 dBm at most.
 */
#define P2P_FREQUENCY 869525000
#define P2P_TX_POWER  14 /* dBm */

/* Downlink (sender -> device), which carries the fragments: fast.
 * Uplink (device -> sender), a few bytes: robust, about 9 dB more sensitivity.
 * On our bench, the uplink arrived 40 dB weaker than the downlink, at the edge
 * of reception in SF7.
 */
#define P2P_DOWN_SF SF_7
#define P2P_DOWN_BW BW_250_KHZ
#define P2P_UP_SF   SF_10
#define P2P_UP_BW   BW_125_KHZ

/* Listens for update sessions. Returns 0 once a complete image is in the secondary
 * slot, a negative value on radio error. feed is called regularly to feed the
 * watchdog.
 */
int p2p_fuota_run(void (*feed)(void));

#endif
