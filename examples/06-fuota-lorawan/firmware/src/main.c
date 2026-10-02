/*
 * Exemple FUOTA LoRaWAN pour la série « CRA & Dev », épisode 6.
 *
 * Le firmware rejoint le réseau, écoute les trois services FUOTA, et applique la
 * règle de l'article : une image reçue démarre à l'essai, et n'est confirmée
 * qu'après avoir fait ses preuves. Chaque étape s'affiche sur l'écran, s'il y en a
 * un.
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

/* Ports des services FUOTA (spécifications LoRa Alliance) */
#define PORT_MULTICAST_SETUP 200 /* TS005 */
#define PORT_FRAG_TRANSPORT  201 /* TS004 */
#define PORT_CLOCK_SYNC      202 /* TS003 */

static const struct device *const lora = DEVICE_DT_GET(DT_ALIAS(lora0));
static const struct device *const wdt = DEVICE_DT_GET(DT_ALIAS(watchdog0));
static int wdt_channel = -1;

/* Ce qui arrive du réseau. Les rappels LoRaWAN tournent dans la workqueue
 * système et doivent rester courts : ils déposent un événement, la boucle
 * principale le traite.
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
		LOG_WRN("Pas de chien de garde");
		return;
	}
	wdt_channel = wdt_install_timeout(wdt, &cfg);
	if (wdt_channel < 0 || wdt_setup(wdt, WDT_OPT_PAUSE_HALTED_BY_DBG) < 0) {
		LOG_WRN("Chien de garde non démarré");
		wdt_channel = -1;
	}
}

static void watchdog_feed(void)
{
	if (wdt_channel >= 0) {
		wdt_feed(wdt, wdt_channel);
	}
}

/* Si le firmware se bloque, le chien de garde redémarre l'appareil, et MCUboot
 * restaure l'image précédente tant que la nouvelle n'est pas confirmée.
 */
static FUNC_NORETURN void reboot(const char *reason)
{
	LOG_WRN("Redémarrage : %s", reason);
	screen_step("Redemarrage");
	LOG_PANIC(); /* vider les journaux avant de couper */
	sys_reboot(SYS_REBOOT_COLD);
}

/* Appelé par le service de fragmentation quand l'image est complète dans le slot
 * secondaire. Zephyr a déjà demandé à MCUboot un démarrage à l'essai.
 */
static void fuota_finished(void)
{
	struct event ev = {.type = EVENT_IMAGE_RECEIVED};

	k_msgq_put(&events, &ev, K_NO_WAIT);
}

/* Tous les downlinks, y compris ceux des services FUOTA, qui ont en plus leur
 * propre traitement dans Zephyr.
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
		return; /* accusé de réception MAC, sans données */
	case PORT_MULTICAST_SETUP:
		service = "mcast";
		break;
	case PORT_FRAG_TRANSPORT:
		service = "frag";
		break;
	case PORT_CLOCK_SYNC:
		service = "heure";
		break;
	default:
		service = "appli";
		break;
	}
	LOG_INF("Downlink port %u (%s), %u octets, RSSI %d dBm", ev->port, service, ev->len,
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
		LOG_ERR("Identifiants LoRaWAN mal formés");
		return ret;
	}

	for (int i = 1; i <= CONFIG_APP_JOIN_ATTEMPTS; i++) {
		LOG_INF("Join OTAA, tentative %d/%d", i, CONFIG_APP_JOIN_ATTEMPTS);
		screen_step("Join %d/%d", i, CONFIG_APP_JOIN_ATTEMPTS);
		watchdog_feed();
		ret = lorawan_join(&cfg);
		if (ret == 0) {
			return 0;
		}
		LOG_WRN("Join refusé ou sans réponse (%d)", ret);
		k_sleep(K_SECONDS(5));
	}
	return ret;
}

/* Mise à jour par LoRa point à point. Le test de bon fonctionnement se limite à
 * « la radio répond » : il n'y a pas de réseau à rejoindre.
 */
static FUNC_NORETURN void run_p2p(bool confirmed)
{
	LOG_INF("Radio LoRa prête (point à point)");
	screen_step("Radio OK");
	if (!confirmed) {
		if (boot_write_img_confirmed() < 0) {
			reboot("confirmation de l'image impossible");
		}
		LOG_INF("Image confirmée");
		screen_step("Confirmee");
	}
	if (p2p_fuota_run(watchdog_feed) == 0) {
		reboot("nouvelle image reçue, MCUboot va la vérifier");
	}
	reboot("radio LoRa en erreur");
	CODE_UNREACHABLE;
}

int main(void)
{
	bool confirmed = boot_is_img_confirmed();
	bool joined;

	screen_init(); /* le logo, quelques secondes */
	LOG_INF("Firmware %s, image %s", APP_VERSION_STRING,
		confirmed ? "confirmée" : "à l'essai");
	screen_step("v%s %s", APP_VERSION_STRING, confirmed ? "ok" : "essai");
	watchdog_start();

	if (!device_is_ready(lora)) {
		reboot("radio LoRa indisponible");
	}

	if (IS_ENABLED(CONFIG_APP_TRANSPORT_P2P)) {
		run_p2p(confirmed);
	}

	if (lorawan_start() < 0) {
		reboot("pile LoRaWAN indisponible");
	}
	lorawan_register_downlink_callback(&downlink_cb);
	LOG_INF("Radio LoRa prête");
	screen_step("Radio OK");

	if (CONFIG_APP_JOIN_ATTEMPTS == 0) {
		screen_step("Join desact.");
	}
	joined = join() == 0;
	if (CONFIG_APP_JOIN_ATTEMPTS > 0) {
		screen_step(joined ? "Join OK" : "Join echec");
	}

	/* Le test de bon fonctionnement. Une image à l'essai qui le rate redémarre
	 * sans se confirmer : MCUboot remet l'ancienne.
	 */
	if (!confirmed) {
		if (!joined && IS_ENABLED(CONFIG_APP_SELFTEST_REQUIRES_JOIN)) {
			reboot("image à l'essai incapable de rejoindre le réseau");
		}
		if (boot_write_img_confirmed() < 0) {
			reboot("confirmation de l'image impossible");
		}
		LOG_INF("Image confirmée");
		screen_step("Confirmee");
	}

	if (joined) {
		lorawan_enable_adr(true);
		lorawan_clock_sync_run();                   /* TS003 */
		lorawan_frag_transport_run(fuota_finished); /* TS004 */
		/* TS005 démarre seul, en arrière-plan */
		screen_step("FUOTA pret");
	}

	int64_t next_uplink = k_uptime_get();

	for (;;) {
		struct event ev;

		watchdog_feed();
		if (k_msgq_get(&events, &ev, K_SECONDS(10)) == 0) {
			if (ev.type == EVENT_IMAGE_RECEIVED) {
				screen_step("Image recue");
				reboot("nouvelle image reçue, MCUboot va la vérifier");
			}
			show_downlink(&ev);
		}
		if (!joined || k_uptime_get() < next_uplink) {
			continue;
		}
		/* En classe A, ce sont les uplinks qui ouvrent les fenêtres de
		 * réception dont le serveur a besoin pour préparer la session.
		 */
		next_uplink += CONFIG_APP_UPLINK_PERIOD * MSEC_PER_SEC;
		uint8_t payload[] = {APP_VERSION_MAJOR, APP_VERSION_MINOR, APP_PATCHLEVEL};

		if (lorawan_send(2, payload, sizeof(payload), LORAWAN_MSG_UNCONFIRMED) < 0) {
			LOG_WRN("Uplink non envoyé");
			screen_step("Uplink echec");
		} else {
			screen_step("Uplink OK");
		}
	}
	return 0;
}
