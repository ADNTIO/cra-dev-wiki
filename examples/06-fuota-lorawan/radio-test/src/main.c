/*
 * Point-to-point LoRa radio test, between two boards, without LoRaWAN.
 *
 * The "ping" board sends a numbered ping, the "pong" board answers and includes
 * the power at which it received it. Each successful exchange proves both
 * directions: ping -> pong (out), pong -> ping (back).
 */

#include <zephyr/device.h>
#include <zephyr/drivers/lora.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/sys/byteorder.h>

#include "screen.h"

LOG_MODULE_REGISTER(radio, LOG_LEVEL_INF);

#define PONG_TIMEOUT K_SECONDS(2)

enum { MSG_PING = 1, MSG_PONG = 2 };

struct __packed message {
	char magic[4]; /* "ADNT": ignore any other LoRa transmitter nearby */
	uint8_t type;
	uint32_t seq;
	int16_t rssi; /* pong: power at which the ping was received */
	int8_t snr;
};

static const struct device *const lora = DEVICE_DT_GET(DT_ALIAS(lora0));

static int radio_mode(bool tx)
{
	struct lora_modem_config cfg = {
		.frequency = CONFIG_APP_FREQUENCY,
		.bandwidth = BW_125_KHZ,
		.datarate = SF_7,
		.coding_rate = CR_4_5,
		.preamble_len = 8,
		.tx_power = CONFIG_APP_TX_POWER,
		.tx = tx,
	};

	return lora_config(lora, &cfg);
}

static int send(uint8_t type, uint32_t seq, int16_t rssi, int8_t snr)
{
	struct message msg = {.magic = "ADNT", .type = type, .rssi = rssi, .snr = snr};

	msg.seq = sys_cpu_to_le32(seq);
	msg.rssi = sys_cpu_to_le16(rssi);
	if (radio_mode(true) < 0) {
		return -EIO;
	}
	return lora_send(lora, (uint8_t *)&msg, sizeof(msg));
}

/* Waits for a message of the given type; ignores the rest. */
static int receive(uint8_t type, k_timeout_t timeout, struct message *msg, int16_t *rssi,
		   int8_t *snr)
{
	k_timepoint_t end = sys_timepoint_calc(timeout);

	if (radio_mode(false) < 0) {
		return -EIO;
	}
	while (!sys_timepoint_expired(end)) {
		int len = lora_recv(lora, (uint8_t *)msg, sizeof(*msg), sys_timepoint_timeout(end),
				    rssi, snr);

		if (len == sizeof(*msg) && memcmp(msg->magic, "ADNT", 4) == 0 &&
		    msg->type == type) {
			msg->seq = sys_le32_to_cpu(msg->seq);
			msg->rssi = sys_le16_to_cpu(msg->rssi);
			return 0;
		}
	}
	return -EAGAIN;
}

static void run_ping(void)
{
	uint32_t ok = 0;

	for (uint32_t seq = 1;; seq++) {
		struct message msg;
		int16_t rssi;
		int8_t snr;

		if (send(MSG_PING, seq, 0, 0) < 0) {
			LOG_ERR("PING_TX_ERR seq=%u", seq);
			screen_step("TX error");
		} else {
			LOG_INF("PING_TX seq=%u", seq);
			screen_step("> ping %u", seq);

			if (receive(MSG_PONG, PONG_TIMEOUT, &msg, &rssi, &snr) == 0 &&
			    msg.seq == seq) {
				ok++;
				LOG_INF("PONG_RX seq=%u out_rssi=%d out_snr=%d back_rssi=%d "
					"back_snr=%d ok=%u/%u",
					seq, msg.rssi, msg.snr, rssi, snr, ok, seq);
				screen_step("< pong %u", seq);
				screen_step("%d/%d dBm", msg.rssi, rssi);
			} else {
				LOG_WRN("PONG_TIMEOUT seq=%u ok=%u/%u", seq, ok, seq);
				screen_step("no pong");
			}
		}
		k_sleep(K_SECONDS(CONFIG_APP_PING_PERIOD));
	}
}

static void run_pong(void)
{
	for (;;) {
		struct message msg;
		int16_t rssi;
		int8_t snr;

		if (receive(MSG_PING, K_SECONDS(30), &msg, &rssi, &snr) < 0) {
			LOG_INF("Listening, no ping");
			continue;
		}
		LOG_INF("PING_RX seq=%u rssi=%d snr=%d", msg.seq, rssi, snr);
		screen_step("< ping %u", msg.seq);
		screen_step("%d dBm", rssi);

		if (send(MSG_PONG, msg.seq, rssi, snr) < 0) {
			LOG_ERR("PONG_TX_ERR seq=%u", msg.seq);
		} else {
			LOG_INF("PONG_TX seq=%u", msg.seq);
			screen_step("> pong %u", msg.seq);
		}
	}
}

int main(void)
{
	bool ping = IS_ENABLED(CONFIG_APP_ROLE_PING);

	screen_init();
	if (!device_is_ready(lora)) {
		LOG_ERR("LoRa radio unavailable");
		screen_step("Radio error");
		return 0;
	}
	LOG_INF("Radio test, role %s, %u Hz, %d dBm", ping ? "ping" : "pong",
		CONFIG_APP_FREQUENCY, CONFIG_APP_TX_POWER);
	screen_step("Radio test");
	screen_step("Role %s", ping ? "ping" : "pong");

	if (ping) {
		run_ping();
	} else {
		run_pong();
	}
	return 0;
}
