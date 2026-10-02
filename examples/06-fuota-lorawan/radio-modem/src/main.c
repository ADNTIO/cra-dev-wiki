/*
 * Modem LoRa piloté par le PC, ligne par ligne, sur la console série.
 *
 * La carte ne connaît rien à la mise à jour : le PC fabrique les trames
 * (tools/p2p_send.py) et la carte se contente de les émettre, puis de remonter
 * ce qu'elle entend. Mêmes paramètres radio que la carte à mettre à jour (p2p.h).
 *
 *   PC -> carte : « DATA <hex> »  ajoute des octets à la trame en cours, « OK »
 *                 « TX <hex> »    ajoute les derniers octets et émet la trame,
 *                                 répond « OK <durée en ms> »
 *                 « SHOW <texte> » affiche une ligne à l'écran, répond « OK »
 *   carte -> PC : « RX <hex> <rssi> <snr> » pour chaque trame reçue
 *
 * Une ligne de console ne dépasse pas 255 caractères (le pilote UART de Zephyr
 * compte sur 8 bits) : une trame de plus de 125 octets arrive en plusieurs lignes.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <zephyr/console/console.h>
#include <zephyr/device.h>
#include <zephyr/drivers/lora.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/printk.h>
#include <zephyr/sys/util.h>

#include "p2p.h"
#include "screen.h"

static const struct device *const lora = DEVICE_DT_GET(DT_ALIAS(lora0));

/* Le modem émet sur le sens descendant et écoute le sens montant (voir p2p.h). */
static int radio_mode(bool tx)
{
	struct lora_modem_config cfg = {
		.frequency = P2P_FREQUENCY,
		.bandwidth = tx ? P2P_DOWN_BW : P2P_UP_BW,
		.datarate = tx ? P2P_DOWN_SF : P2P_UP_SF,
		.coding_rate = CR_4_5,
		.preamble_len = 8,
		.tx_power = P2P_TX_POWER,
		.tx = tx,
	};

	return lora_config(lora, &cfg);
}

static void received(const struct device *dev, uint8_t *data, uint16_t size, int16_t rssi,
		     int8_t snr, void *user_data)
{
	/* Statique : ce rappel tourne sur une pile trop petite pour 511 octets */
	static char hex[2 * 255 + 1];

	ARG_UNUSED(dev);
	ARG_UNUSED(user_data);
	bin2hex(data, size, hex, sizeof(hex));
	printk("RX %s %d %d\n", hex, rssi, snr);
}

static int listen(void)
{
	if (radio_mode(false) < 0) {
		return -EIO;
	}
	return lora_recv_async(lora, received, NULL);
}

static uint8_t frame[255];
static size_t frame_len;

static int append(const char *hex)
{
	size_t len = hex2bin(hex, strlen(hex), &frame[frame_len], sizeof(frame) - frame_len);

	if (len == 0 || len * 2 != strlen(hex)) {
		frame_len = 0;
		printk("ERR trame invalide\n");
		return -EINVAL;
	}
	frame_len += len;
	return 0;
}

static void transmit(const char *hex)
{
	size_t len;
	int64_t start;
	int ret;

	if (append(hex) < 0) {
		return;
	}
	len = frame_len;
	frame_len = 0;
	lora_recv_async(lora, NULL, NULL); /* arrête l'écoute */
	start = k_uptime_get();
	ret = radio_mode(true);
	if (ret == 0) {
		ret = lora_send(lora, frame, len);
	}
	if (ret < 0) {
		printk("ERR emission %d\n", ret);
	} else {
		printk("OK %lld\n", k_uptime_get() - start);
	}
	listen();
}

int main(void)
{
	screen_init();
	if (!device_is_ready(lora) || listen() < 0) {
		screen_step("Radio KO");
		printk("ERR radio\n");
		return 0;
	}
	screen_step("Modem LoRa");
	screen_step("Pret");
	console_getline_init();
	printk("READY\n");

	for (;;) {
		char *line = console_getline();

		if (strncmp(line, "DATA ", 5) == 0) {
			if (append(line + 5) == 0) {
				printk("OK\n");
			}
		} else if (strncmp(line, "TX ", 3) == 0) {
			transmit(line + 3);
		} else if (strncmp(line, "SHOW ", 5) == 0) {
			screen_step("%s", line + 5);
			printk("OK\n");
		} else if (strcmp(line, "HELLO") == 0) {
			printk("READY\n");
		} else {
			printk("ERR commande inconnue\n");
		}
	}
	return 0;
}
