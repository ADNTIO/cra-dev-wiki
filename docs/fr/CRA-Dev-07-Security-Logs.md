---
description: >-
  Le minimum que le CRA demande pour la journalisation (Annexe I, partie I, 2 l) : enregistrer qui a accédé à quoi et qui a modifié quoi, surveiller ces événements, laisser l'utilisateur désactiver. En Python, avec la seule bibliothèque standard.
---

# Qui a fait quoi, et quand ? Journaliser l'activité de sécurité

> **CRA & Dev #7** · [Série « CRA & Dev »](index.md) · Lecture : environ 5 min · Multiplateforme ·
> Exemple : Python (bibliothèque standard)

## Ce que demande le CRA

Le [Cyber Resilience Act][cra] demande, sur la base de l'évaluation des risques et le
cas échéant, de « fournir des informations relatives à la sécurité en enregistrant et
en surveillant les activités internes pertinentes, y compris l'accès ou la
modification des données, des services ou des fonctions, tout en laissant à
l'utilisateur la possibilité de désactiver le mécanisme » (Annexe I, partie I,
point 2, l).

Trois verbes : enregistrer, surveiller, désactiver. Pour ce point, le texte demande
ces trois actions.

## Le piège classique

Le journal existe, mais c'est celui du débogage : `connection reset`,
`value=15000`, des piles d'appels. Le jour où il faut savoir qui a changé une
consigne, la réponse n'y est pas. À l'inverse, tout journaliser y met des mots de
passe et des données personnelles, et noie l'événement utile.

## La technique : une liste fermée, une ligne par événement

D'abord, la liste des événements de sécurité. Elle est courte et fermée : tout ce qui
dit qui a accédé à quoi, ou qui a modifié quoi.

| Événement | Exemple |
| --- | --- |
| `login` | connexion réussie ou refusée |
| `access.denied` | commande refusée faute de droits |
| `config.change` | consigne ou réglage modifié |
| `firmware.update` | mise à jour installée |
| `logging.off`, `logging.on` | journalisation désactivée ou réactivée |

Ensuite, une ligne JSON par événement, avec toujours les mêmes champs : quand (en
UTC), quoi, qui, sur quoi, avec quel résultat. Le module `logging` de Python suffit
(extrait simplifié de `seclog/log.py`) :

```python
def record(self, event, actor, target, outcome="ok"):
    if event not in EVENTS:
        raise ValueError(f"unknown security event: {event}")
    if not self.enabled:
        return
    line = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "event": event, "actor": actor, "target": target, "outcome": outcome}
    self.logger.info(json.dumps(line))
```

Un `RotatingFileHandler` borne la taille sur le disque : un journal plein ne doit pas
remplir l'appareil. La rotation efface les fichiers les plus anciens : ce qui doit
être conservé plus longtemps doit être exporté avant (point 2 ci-dessous).

Surveiller, c'est faire quelque chose de ces lignes. Une règle simple suffit pour
commencer : cinq connexions refusées pour le même acteur déclenchent une alerte.

Désactiver, enfin. Le texte ne dit pas comment ; nous recommandons d'enregistrer la
désactivation elle-même, avec son auteur, comme dernière ligne. On sait alors quand
et par qui la journalisation a été coupée.

La [démonstration][example] fait les trois (sortie brute du programme, en anglais) :

```
1. The device records who accessed or changed what
   login            operator        hmi
   config.change    operator        spindle speed 12000 -> 15000 rpm
   firmware.update  update-service  1.0.0 -> 1.1.0
2. Monitoring: someone guesses the password
   ALERT: 5 failed logins from laptop-unknown
3. The user turns logging off
   last line: logging.off by admin, nothing recorded after it
```

## Sur l'embarqué

Les mêmes briques existent sur chaque cible :

| Cible | Enregistrer, en taille bornée | Exporter |
| --- | --- | --- |
| Microcontrôleur, C ou C++ | [journalisation Zephyr][zephyr-log] : backend fichier `CONFIG_LOG_BACKEND_FS`, taille et nombre de fichiers bornés | backend `CONFIG_LOG_BACKEND_NET` : syslog en UDP ou TCP, sans TLS |
| Microcontrôleur, Rust | façade [`log`][log-rs] (`no_std`) et file FIFO en flash [`sequential-storage`][seqstor], qui peut écraser la plus ancienne entrée | à écrire |
| Linux embarqué, C ou C++ | `syslog(3)` ou `sd_journal_send(3)` ; en C++, [spdlog][spdlog] (fichiers tournants, sortie syslog) | le démon système, par exemple [rsyslog en TLS][rsyslog-tls] |
| Linux embarqué, Rust | [`log`][log-rs] avec [`systemd-journal-logger`][sdjl] ou [`syslog`][syslog-rs] | idem |

## Trois choses à savoir

1. Ni secret ni donnée inutile dans le journal : un identifiant d'opérateur, pas son
   mot de passe ni son adresse. C'est aussi ce que demande le point 2, g)
   (minimisation des données).
2. Un attaquant qui prend la main sur l'appareil commence souvent par effacer les
   journaux. D'où une copie hors de l'appareil, vers un serveur de journaux, avec une
   durée de conservation définie. L'envoi doit être authentifié, chiffré (par exemple
   syslog sur TLS, [RFC 5425][rfc5425]) et résister aux coupures réseau. Le
   `SysLogHandler` de Python n'assure rien de tout cela ([documentation][syslogh]).
3. Le point 2, l) n'exige pas un journal infalsifiable. Si votre évaluation des
   risques le justifie, l'outil existe sur Linux : le
   [Forward Secure Sealing][journalctl] de systemd-journald.

## À retenir

Une liste fermée d'événements, une ligne structurée par événement, une règle de
surveillance, une désactivation qui laisse une trace : c'est le minimum que demande
le CRA pour ce point, et il tient dans quelques dizaines de lignes.

---

*Épisode précédent : [Mille fragments, une seule signature, mettre à jour un
firmware par LoRaWAN](CRA-Dev-06-FUOTA-LoRaWAN.md).*

*Code d'accompagnement, dans [`examples/07-security-logging`][example] : le journal,
la règle de surveillance, la démonstration et ses tests. Le README de l'exemple est
en anglais.*

[cra]: https://eur-lex.europa.eu/eli/reg/2024/2847/oj?locale=fr
[rfc5425]: https://www.rfc-editor.org/rfc/rfc5425
[syslogh]: https://docs.python.org/3/library/logging.handlers.html#sysloghandler
[zephyr-log]: https://docs.zephyrproject.org/latest/services/logging/index.html
[log-rs]: https://docs.rs/log/latest/log/
[seqstor]: https://docs.rs/sequential-storage/latest/sequential_storage/
[spdlog]: https://github.com/gabime/spdlog
[rsyslog-tls]: https://docs.rsyslog.com/doc/tutorials/tls_cert_summary.html
[sdjl]: https://docs.rs/systemd-journal-logger/latest/systemd_journal_logger/
[syslog-rs]: https://docs.rs/syslog/latest/syslog/
[journalctl]: https://www.freedesktop.org/software/systemd/man/latest/journalctl.html
[example]: https://github.com/ADNTIO/cra-dev-wiki/tree/main/examples/07-security-logging
