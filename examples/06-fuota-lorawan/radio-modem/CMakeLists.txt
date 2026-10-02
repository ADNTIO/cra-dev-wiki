cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(radio_modem)

# L'écran, le logo et les paramètres radio sont ceux du firmware FUOTA
target_sources(app PRIVATE src/main.c ../firmware/src/screen.c)
target_include_directories(app PRIVATE ../firmware/src)
