#!/usr/bin/python
# -*- coding: utf-8 -*-

import time
import xbmc

from default import Cleaner
from settings import *
from utils import debug


def autostart():
    """
    Starts the cleaning service based on the user's settings.
    """
    if get_setting(service_enabled):  # TODO: Make this into a while to account for enabling of service
        cleaner = Cleaner()

        service_sleep = 10
        ticker = 0
        delayed_completed = False

        while not xbmc.abortRequested:
            scan_interval_ticker = get_setting(scan_interval) * 60 / service_sleep
            delayed_start_ticker = get_setting(delayed_start) * 60 / service_sleep

            if delayed_completed and ticker >= scan_interval_ticker:
                cleaner.cleanup()
                ticker = 0
            elif not delayed_completed and ticker >= delayed_start_ticker:
                delayed_completed = True
                cleaner.cleanup()
                ticker = 0

            time.sleep(service_sleep)
            ticker += 1

        debug("Abort requested. Terminating.")
    else:
        debug("Service not enabled.")


if __name__ == "__main__":
    autostart()
