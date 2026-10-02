cmake_minimum_required(VERSION 3.20.0)

find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(radio_modem)

# The screen, the logo and the radio parameters are those of the FUOTA firmware
target_sources(app PRIVATE src/main.c ../firmware/src/screen.c)
target_include_directories(app PRIVATE ../firmware/src)
