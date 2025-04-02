#!/bin/bash

sudo insmod led_kernal/rp1_ws281x_pwm.ko pwm_channel=2
sudo dtoverlay rp1_ws281x_pwm
sudo pinctrl set 18 a3 pn
