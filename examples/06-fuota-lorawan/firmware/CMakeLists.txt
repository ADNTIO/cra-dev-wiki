cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(fuota_lorawan)

target_sources(app PRIVATE src/main.c src/screen.c)
target_sources_ifdef(CONFIG_APP_TRANSPORT_P2P app PRIVATE src/p2p.c)
# p2p.c reuses the TS004 decoder and the flash writes of the fragmentation service
target_include_directories(app PRIVATE ${ZEPHYR_BASE}/subsys/lorawan/services)
