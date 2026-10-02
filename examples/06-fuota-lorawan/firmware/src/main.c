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

/* Join retries on a confirmed image: 1 minute, then doubling, up to 1 hour */
#define JOIN_RETRY_MIN_S 60
#define JOIN_RETRY_MAX_S 3600

/* Before rebooting a confirmed image on a radio failure: avoids a reboot loop */
#define RADIO_FAILURE_WAIT_S 600

/* Ports of the FUOTA services (LoRa Alliance specifications) */
#define PORT_MULTICAST_SETUP 200 /* TS005 */
#define PORT_FRAG_TRANSPORT  201 /* TS004 */
#define PORT_CLOCK_SYNC      202 /* TS003 */

static const struct device *const lora = DEVICE_DT_GET(DT_ALIAS(lora0));
static const struct device *const wdt = DEVICE_DT_GET(DT_ALIAS(watchdog0));
static int wdt_channel = -1;

/* Downlinks seen by the application. LoRaWAN callbacks run on the system
 * workqueue and must stay short: they post an event, the main loop handles it.
 * Losing one only loses a line on the screen.
 */
struct downlink {
	uint8_t port;
	int16_t rssi;
	uint8_t len;
};

K_MSGQ_DEFINE(downlinks, sizeof(struct downlink), 16, 4);

/* The end of a transfer must never be lost: a semaphore, not a queue slot. */
static K_SEM_DEFINE(image_received, 0, 1);

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

/* Sleeps while keeping the watchdog fed. */
static void wait(int seconds)
{
	for (int i = 0; i < seconds; i += 10) {
		watchdog_feed();
		k_sleep(K_SECONDS(MIN(10, seconds - i)));
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

/* A test image reboots at once, so MCUboot rolls it back. A confirmed image has no
 * older image to go back to: it waits before retrying, rather than reboot-looping.
 */
static FUNC_NORETURN void radio_failure(bool confirmed, const char *reason)
{
	LOG_ERR("%s", reason);
	screen_step("Radio error");
	if (confirmed) {
		wait(RADIO_FAILURE_WAIT_S);
	}
	reboot(reason);
}

/* Called by the fragmentation service once the image is complete in the secondary
 * slot. Zephyr has already asked MCUboot for a test boot.
 */
static void fuota_finished(void)
{
	k_sem_give(&image_received);
}

/* Every downlink, including those of the FUOTA services, which Zephyr also handles
 * on its own.
 */
static void downlink_received(uint8_t port, uint8_t flags, int16_t rssi, int8_t snr,
			      uint8_t len, const uint8_t *data)
{
	struct downlink dl = {.port = port, .rssi = rssi, .len = len};

	ARG_UNUSED(flags);
	ARG_UNUSED(snr);
	ARG_UNUSED(data);
	k_msgq_put(&downlinks, &dl, K_NO_WAIT);
}

static struct lorawan_downlink_cb downlink_cb = {
	.port = LW_RECV_PORT_ANY,
	.cb = downlink_received,
};

static void show_downlink(const struct downlink *dl)
{
	const char *service;

	switch (dl->port) {
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
	LOG_INF("Downlink port %u (%s), %u bytes, RSSI %d dBm", dl->port, service, dl->len,
		dl->rssi);
	screen_step("DL %u %s", dl->port, service);
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
			screen_step("Join OK");
			return 0;
		}
		LOG_WRN("Join rejected or no answer (%d)", ret);
		k_sleep(K_SECONDS(5));
	}
	screen_step("Join failed");
	return ret;
}

/* Starts the FUOTA services; returns true if all of them started. */
static bool start_services(void)
{
	int clock, frag;

	lorawan_enable_adr(true);
	clock = lorawan_clock_sync_run();                   /* TS003 */
	frag = lorawan_frag_transport_run(fuota_finished); /* TS004 */
	/* TS005 starts on its own, in the background */
	if (clock < 0 || frag < 0) {
		LOG_ERR("FUOTA services not started (clock sync %d, frag transport %d)", clock,
			frag);
		screen_step("FUOTA error");
		return false;
	}
	screen_step("FUOTA ready");
	return true;
}

static void confirm(void)
{
	if (boot_write_img_confirmed() < 0) {
		reboot("cannot confirm the image");
	}
	LOG_INF("Image confirmed");
	screen_step("Confirmed");
}

/* Update over point-to-point LoRa. The health check is just "the radio answers":
 * there is no network to join.
 */
static FUNC_NORETURN void run_p2p(bool confirmed)
{
	LOG_INF("LoRa radio ready (point to point)");
	screen_step("Radio OK");
	if (!confirmed) {
		confirm();
		confirmed = true;
	}
	if (p2p_fuota_run(watchdog_feed) == 0) {
		reboot("new image received, MCUboot will verify it");
	}
	radio_failure(confirmed, "LoRa radio error");
}

int main(void)
{
	bool confirmed = boot_is_img_confirmed();
	bool joined = false, services = false;
	int join_retry_s = JOIN_RETRY_MIN_S;
	int64_t next_join, next_uplink;

	screen_init(); /* the logo, for a few seconds */
	LOG_INF("Firmware %s, image %s", APP_VERSION_STRING, confirmed ? "confirmed" : "on trial");
	screen_step("v%s %s", APP_VERSION_STRING, confirmed ? "ok" : "trial");
	watchdog_start();

	if (!device_is_ready(lora)) {
		radio_failure(confirmed, "LoRa radio unavailable");
	}

	if (IS_ENABLED(CONFIG_APP_TRANSPORT_P2P)) {
		run_p2p(confirmed);
	}

	if (lorawan_start() < 0) {
		radio_failure(confirmed, "LoRaWAN stack unavailable");
	}
	lorawan_register_downlink_callback(&downlink_cb);
	LOG_INF("LoRa radio ready");
	screen_step("Radio OK");

	if (CONFIG_APP_JOIN_ATTEMPTS == 0) {
		screen_step("Join off");
	} else {
		joined = join() == 0;
	}
	if (joined) {
		services = start_services();
	}

	/* The health check. A test image that fails it reboots without confirming
	 * itself: MCUboot puts the old one back. A product would check more here:
	 * storage migration, critical peripherals, a first exchange with the backend.
	 */
	if (!confirmed) {
		if (IS_ENABLED(CONFIG_APP_SELFTEST_REQUIRES_JOIN) && !(joined && services)) {
			reboot(joined ? "test image unable to start the FUOTA services"
				      : "test image unable to join the network");
		}
		confirm();
	}

	next_join = k_uptime_get() + join_retry_s * MSEC_PER_SEC;
	next_uplink = k_uptime_get();

	for (;;) {
		struct downlink dl;

		watchdog_feed();
		if (k_sem_take(&image_received, K_NO_WAIT) == 0) {
			screen_step("Image rcvd");
			reboot("new image received, MCUboot will verify it");
		}
		if (k_msgq_get(&downlinks, &dl, K_SECONDS(1)) == 0) {
			show_downlink(&dl);
		}

		/* Offline, the device cannot receive the update that would fix it:
		 * keep trying to join, ever more slowly.
		 */
		if (!joined && CONFIG_APP_JOIN_ATTEMPTS > 0 && k_uptime_get() >= next_join) {
			joined = join() == 0;
			if (joined) {
				services = start_services();
			} else {
				join_retry_s = MIN(join_retry_s * 2, JOIN_RETRY_MAX_S);
				next_join = k_uptime_get() + join_retry_s * MSEC_PER_SEC;
			}
		}

		if (!joined || k_uptime_get() < next_uplink) {
			continue;
		}
		/* In class A, uplinks are what opens the receive windows the server
		 * needs to set up the session.
		 */
		next_uplink = k_uptime_get() + CONFIG_APP_UPLINK_PERIOD * MSEC_PER_SEC;
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
