/*
 * Mise à jour par LoRa point à point : voir p2p.h.
 */

#include <string.h>

#include <zephyr/device.h>
#include <zephyr/drivers/lora.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/byteorder.h>
#include <zephyr/sys/reboot.h>

/* API internes du service de fragmentation de Zephyr (subsys/lorawan/services) */
#include "frag_decoder_lowmem.h"
#include "frag_flash.h"

#include "p2p.h"
#include "screen.h"

LOG_MODULE_REGISTER(p2p, LOG_LEVEL_INF);

enum { P2P_SETUP = 1, P2P_READY = 2, P2P_FRAG = 3, P2P_DONE = 4 };

#define HEADER_LEN   4 /* « AD », type, session */
#define PROGRESS_STEP 100

static const struct device *const lora = DEVICE_DT_GET(DT_ALIAS(lora0));

static struct {
	bool active;
	uint8_t session;
	uint16_t nb_frag;
	uint8_t frag_size;
	uint16_t received;
	struct frag_decoder decoder;
} ctx;

/* L'appareil reçoit sur le sens descendant et répond sur le sens montant. */
static int radio_mode(bool tx)
{
	struct lora_modem_config cfg = {
		.frequency = P2P_FREQUENCY,
		.bandwidth = tx ? P2P_UP_BW : P2P_DOWN_BW,
		.datarate = tx ? P2P_UP_SF : P2P_DOWN_SF,
		.coding_rate = CR_4_5,
		.preamble_len = 8,
		.tx_power = P2P_TX_POWER,
		.tx = tx,
	};

	return lora_config(lora, &cfg);
}

static void send(uint8_t type, const uint8_t *payload, size_t len)
{
	uint8_t buf[HEADER_LEN + 8] = {'A', 'D', type, ctx.session};

	memcpy(&buf[HEADER_LEN], payload, len);
	if (radio_mode(true) < 0 || lora_send(lora, buf, HEADER_LEN + len) < 0) {
		LOG_ERR("Émission impossible (type %u)", type);
	}
	radio_mode(false);
}

static void on_setup(uint8_t session, const uint8_t *p, size_t len)
{
	uint8_t status = 0;

	if (len < 4) {
		return;
	}
	if (ctx.active && session == ctx.session) {
		send(P2P_READY, &status, 1); /* l'émetteur n'a pas reçu notre READY */
		return;
	}

	ctx.session = session;
	ctx.nb_frag = sys_get_le16(p);
	ctx.frag_size = p[2];
	ctx.received = 0;
	LOG_INF("Session %u : %u fragments de %u octets", session, ctx.nb_frag, ctx.frag_size);

	if (ctx.nb_frag == 0 || ctx.nb_frag > FRAG_MAX_NB || ctx.frag_size > FRAG_MAX_SIZE) {
		LOG_ERR("Session refusée : dépasse les capacités du décodeur");
		screen_step("Session KO");
		ctx.active = false;
		status = 1;
		send(P2P_READY, &status, 1);
		return;
	}

	screen_step("Session %u", session);
	screen_step("%u frag.", ctx.nb_frag);
	if (frag_flash_init(ctx.frag_size) < 0) { /* efface le slot secondaire */
		LOG_ERR("Effacement du slot secondaire impossible");
		status = 2;
		send(P2P_READY, &status, 1);
		return;
	}
	frag_dec_init(&ctx.decoder, ctx.nb_frag, ctx.frag_size);
	ctx.active = true;
	send(P2P_READY, &status, 1);
}

/* Rend true quand l'image est complète dans le slot secondaire. */
static bool on_fragment(uint8_t session, const uint8_t *p, size_t len)
{
	uint16_t index;
	int ret;

	/* Longueur vérifiée avant toute lecture : c'est ce contrôle qui manquait
	 * dans le décodeur TS004 de Zephyr avant la 4.4.2 (CVE-2026-13480).
	 */
	if (!ctx.active || session != ctx.session || len != 2U + ctx.frag_size) {
		return false;
	}
	index = sys_get_le16(p);
	if (index == 0) {
		return false;
	}
	if (index > ctx.nb_frag) {
		frag_flash_use_cache(); /* fragments de redondance : en RAM */
	}

	ret = frag_dec(&ctx.decoder, index, &p[2], ctx.frag_size);
	ctx.received++;
	if (ctx.received % PROGRESS_STEP == 0) {
		LOG_INF("Fragment %u, %u reçus", index, ctx.received);
		screen_step("Frag %u/%u", MIN(index, ctx.nb_frag), ctx.nb_frag);
	}

	if (ret == FRAG_DEC_ERR_TOO_MANY_FRAMES_LOST || ret == FRAG_DEC_ERR) {
		LOG_ERR("Trop de fragments perdus, session abandonnée (%d)", ret);
		screen_step("Trop de perte");
		ctx.active = false;
		return false;
	}
	if (ret < 0) {
		return false;
	}

	/* Écrit le cache et demande à MCUboot un démarrage à l'essai */
	frag_flash_finish();
	LOG_INF("Image complète : %u fragments reçus, %u perdus, %u reconstruits", ctx.received,
		ctx.decoder.lost_frame_count, ctx.decoder.filled_lost_frame_count);
	screen_step("Image recue");
	return true;
}

int p2p_fuota_run(void (*feed)(void))
{
	static uint8_t buf[255];

	if (radio_mode(false) < 0) {
		return -EIO;
	}
	LOG_INF("En écoute : %u Hz, %d dBm", P2P_FREQUENCY, P2P_TX_POWER);
	screen_step("Ecoute LoRa");

	for (;;) {
		int16_t rssi;
		int8_t snr;
		int len;

		feed();
		len = lora_recv(lora, buf, sizeof(buf), K_SECONDS(10), &rssi, &snr);
		if (len < HEADER_LEN || buf[0] != 'A' || buf[1] != 'D') {
			continue;
		}

		switch (buf[2]) {
		case P2P_SETUP:
			on_setup(buf[3], &buf[HEADER_LEN], len - HEADER_LEN);
			break;
		case P2P_FRAG:
			if (on_fragment(buf[3], &buf[HEADER_LEN], len - HEADER_LEN)) {
				uint8_t stats[4];

				sys_put_le16(ctx.decoder.lost_frame_count, &stats[0]);
				sys_put_le16(ctx.decoder.filled_lost_frame_count, &stats[2]);
				/* L'émetteur écoute entre deux fragments : quelques
				 * répétitions suffisent.
				 */
				for (int i = 0; i < 3; i++) {
					send(P2P_DONE, stats, sizeof(stats));
					k_sleep(K_MSEC(700));
				}
				return 0;
			}
			break;
		default:
			break;
		}
	}
}
