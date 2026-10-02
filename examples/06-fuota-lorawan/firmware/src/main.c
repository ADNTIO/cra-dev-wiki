/*
 * LoRaWAN FUOTA example for the "CRA & Dev" series, episode 6.
 *
 * The firmware joins the network, listens to the three FUOTA services, and applies
 * the rule from the article: a received image boots on trial, and is only confirmed
 * once it has proven itself. Each step is shown on the screen, if there is one.
 */

#include <app_version.h>
#include <zephyr/device.h>
#include <zephyr/dfu/mcuboot.h>
#include <zephyr/drivers/watchdog.h>
#include <zephyr/kernel.h>
#include <zephyr/logging/log.h>
#include <zephyr/logging/log_ctrl.h>
#include <zephyr/lorawan/lorawan.h>
#include <zephyr/sys/reboot.h>
#include <zephyr/sys/util.h>

#include "p2p.h"
#include "screen.h"

LOG_MODULE_REGISTER(fuota, LOG_LEVEL_INF);

#define WATCHDOG_TIMEOUT_MS 60000

/* Ports of the FUOTA services (LoRa Alliance specifications) */
#define PORT_MULTICAST_SETUP 200 /* TS005 */
#define PORT_FRAG_TRANSPORT  201 /* TS004 */
#define PORT_CLOCK_SYNC      202 /* TS003 */

static const struct device *const lora = DEVICE_DT_GET(DT_ALIAS(lora0));
static const struct device *const wdt = DEVICE_DT_GET(DT_ALIAS(watchdog0));
static int wdt_channel = -1;

/* What comes from the network. LoRaWAN callbacks run on the system workqueue and
 * must stay short: they post an event, the main loop handles it.
 */
struct event {
	enum { EVENT_DOWNLINK, EVENT_IMAGE_RECEIVED } type;
	uint8_t port;
	int16_t rssi;
	uint8_t len;
};

K_MSGQ_DEFINE(events, sizeof(struct event), 16, 4);

static void watchdog_start(void)
{
	const struct wdt_timeout_cfg cfg = {
		.window.max = WATCHDOG_TIMEOUT_MS,
		.flags = WDT_FLAG_RESET_SOC,
	};

	if (!device_is_ready(wdt)) {
		LOG_WRN("No watchdog");
		return;
	}
	wdt_channel = wdt_install_timeout(wdt, &cfg);
	if (wdt_channel < 0 || wdt_setup(wdt, WDT_OPT_PAUSE_HALTED_BY_DBG) < 0) {
		LOG_WRN("Watchdog not started");
		wdt_channel = -1;
	}
}

static void watchdog_feed(void)
{
	if (wdt_channel >= 0) {
		wdt_feed(wdt, wdt_channel);
	}
}

/* If the firmware hangs, the watchdog reboots the device, and MCUboot restores the
 * previous image as long as the new one is not confirmed.
 */
static FUNC_NORETURN void reboot(const char *reason)
{
	LOG_WRN("Rebooting: %s", reason);
	screen_step("Rebooting");
	LOG_PANIC(); /* flush the logs before cutting */
	sys_reboot(SYS_REBOOT_COLD);
}

/* Called by the fragmentation service once the image is complete in the secondary
 * slot. Zephyr has already asked MCUboot for a test boot.
 */
static void fuota_finished(void)
{
	struct event ev = {.type = EVENT_IMAGE_RECEIVED};

	k_msgq_put(&events, &ev, K_NO_WAIT);
}

/* Every downlink, including those of the FUOTA services, which Zephyr also handles
 * on its own.
 */
static void downlink_received(uint8_t port, uint8_t flags, int16_t rssi, int8_t snr,
			      uint8_t len, const uint8_t *data)
{
	struct event ev = {.type = EVENT_DOWNLINK, .port = port, .rssi = rssi, .len = len};

	ARG_UNUSED(flags);
	ARG_UNUSED(snr);
	ARG_UNUSED(data);
	k_msgq_put(&events, &ev, K_NO_WAIT);
}

static struct lorawan_downlink_cb downlink_cb = {
	.port = LW_RECV_PORT_ANY,
	.cb = downlink_received,
};

static void show_downlink(const struct event *ev)
{
	const char *service;

	switch (ev->port) {
	case 0:
		return; /* MAC acknowledgement, no data */
	case PORT_MULTICAST_SETUP:
		service = "mcast";
		break;
	case PORT_FRAG_TRANSPORT:
		service = "frag";
		break;
	case PORT_CLOCK_SYNC:
		service = "clock";
		break;
	default:
		service = "app";
		break;
	}
	LOG_INF("Downlink port %u (%s), %u bytes, RSSI %d dBm", ev->port, service, ev->len,
		ev->rssi);
	screen_step("DL %u %s", ev->port, service);
}

static int join(void)
{
	static uint8_t dev_eui[8], join_eui[8], app_key[16];
	struct lorawan_join_config cfg = {
		.mode = LORAWAN_ACT_OTAA,
		.dev_eui = dev_eui,
		.otaa = {.join_eui = join_eui, .app_key = app_key, .nwk_key = app_key},
	};
	int ret = -EINVAL;

	if (hex2bin(CONFIG_APP_LORAWAN_DEV_EUI, strlen(CONFIG_APP_LORAWAN_DEV_EUI),
		    dev_eui, sizeof(dev_eui)) != sizeof(dev_eui) ||
	    hex2bin(CONFIG_APP_LORAWAN_JOIN_EUI, strlen(CONFIG_APP_LORAWAN_JOIN_EUI),
		    join_eui, sizeof(join_eui)) != sizeof(join_eui) ||
	    hex2bin(CONFIG_APP_LORAWAN_APP_KEY, strlen(CONFIG_APP_LORAWAN_APP_KEY),
		    app_key, sizeof(app_key)) != sizeof(app_key)) {
		LOG_ERR("Malformed LoRaWAN credentials");
		return ret;
	}

	for (int i = 1; i <= CONFIG_APP_JOIN_ATTEMPTS; i++) {
		LOG_INF("OTAA join, attempt %d/%d", i, CONFIG_APP_JOIN_ATTEMPTS);
		screen_step("Join %d/%d", i, CONFIG_APP_JOIN_ATTEMPTS);
		watchdog_feed();
		ret = lorawan_join(&cfg);
		if (ret == 0) {
			return 0;
		}
		LOG_WRN("Join rejected or no answer (%d)", ret);
		k_sleep(K_SECONDS(5));
	}
	return ret;
}

/* Update over point-to-point LoRa. The health check is just "the radio answers":
 * there is no network to join.
 */
static FUNC_NORETURN void run_p2p(bool confirmed)
{
	LOG_INF("LoRa radio ready (point to point)");
	screen_step("Radio OK");
	if (!confirmed) {
		if (boot_write_img_confirmed() < 0) {
			reboot("cannot confirm the image");
		}
		LOG_INF("Image confirmed");
		screen_step("Confirmed");
	}
	if (p2p_fuota_run(watchdog_feed) == 0) {
		reboot("new image received, MCUboot will verify it");
	}
	reboot("LoRa radio error");
	CODE_UNREACHABLE;
}

int main(void)
{
	bool confirmed = boot_is_img_confirmed();
	bool joined;

	screen_init(); /* the logo, for a few seconds */
	LOG_INF("Firmware %s, image %s", APP_VERSION_STRING, confirmed ? "confirmed" : "on trial");
	screen_step("v%s %s", APP_VERSION_STRING, confirmed ? "ok" : "trial");
	watchdog_start();

	if (!device_is_ready(lora)) {
		reboot("LoRa radio unavailable");
	}

	if (IS_ENABLED(CONFIG_APP_TRANSPORT_P2P)) {
		run_p2p(confirmed);
	}

	if (lorawan_start() < 0) {
		reboot("LoRaWAN stack unavailable");
	}
	lorawan_register_downlink_callback(&downlink_cb);
	LOG_INF("LoRa radio ready");
	screen_step("Radio OK");

	if (CONFIG_APP_JOIN_ATTEMPTS == 0) {
		screen_step("Join off");
	}
	joined = join() == 0;
	if (CONFIG_APP_JOIN_ATTEMPTS > 0) {
		screen_step(joined ? "Join OK" : "Join failed");
	}

	/* The health check. A test image that fails it reboots without confirming
	 * itself: MCUboot puts the old one back.
	 */
	if (!confirmed) {
		if (!joined && IS_ENABLED(CONFIG_APP_SELFTEST_REQUIRES_JOIN)) {
			reboot("test image unable to join the network");
		}
		if (boot_write_img_confirmed() < 0) {
			reboot("cannot confirm the image");
		}
		LOG_INF("Image confirmed");
		screen_step("Confirmed");
	}

	if (joined) {
		lorawan_enable_adr(true);
		lorawan_clock_sync_run();                   /* TS003 */
		lorawan_frag_transport_run(fuota_finished); /* TS004 */
		/* TS005 starts on its own, in the background */
		screen_step("FUOTA ready");
	}

	int64_t next_uplink = k_uptime_get();

	for (;;) {
		struct event ev;

		watchdog_feed();
		if (k_msgq_get(&events, &ev, K_SECONDS(10)) == 0) {
			if (ev.type == EVENT_IMAGE_RECEIVED) {
				screen_step("Image rcvd");
				reboot("new image received, MCUboot will verify it");
			}
			show_downlink(&ev);
		}
		if (!joined || k_uptime_get() < next_uplink) {
			continue;
		}
		/* In class A, uplinks are what opens the receive windows the server
		 * needs to set up the session.
		 */
		next_uplink += CONFIG_APP_UPLINK_PERIOD * MSEC_PER_SEC;
		uint8_t payload[] = {APP_VERSION_MAJOR, APP_VERSION_MINOR, APP_PATCHLEVEL};

		if (lorawan_send(2, payload, sizeof(payload), LORAWAN_MSG_UNCONFIRMED) < 0) {
			LOG_WRN("Uplink not sent");
			screen_step("Uplink fail");
		} else {
			screen_step("Uplink OK");
		}
	}
	return 0;
}
