#!/usr/bin/python3
"""Run the installed Waydroid client with Android 16 Binder compatibility."""

import os
import sys

sys.path.insert(0, "/usr/lib/waydroid")

import tools
from tools import helpers
from tools.interfaces import IPlatform


_load_binder_nodes = helpers.drivers.loadBinderNodes


def _load_android_16_binder_nodes(args):
    _load_binder_nodes(args)
    args.SERVICE_MANAGER_PROTOCOL = "aidl6"


helpers.drivers.loadBinderNodes = _load_android_16_binder_nodes
IPlatform.INTERFACE = "id.waydro.waydroid.IPlatform"

if __name__ == "__main__":
    os.umask(0o0022)
    sys.exit(tools.main())
