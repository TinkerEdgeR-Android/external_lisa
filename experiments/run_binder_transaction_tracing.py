#!/usr/bin/env python

from time import sleep
import os
import argparse
from android import System
from env import TestEnv

# Setup target configuration
conf = {
    # Target platform and board
    "platform"     : 'android',
    # Useful for reading names of little/big cluster
    # and energy model info, its device specific and use
    # only if needed for analysis
    # "board"        : 'pixel',
    # Device
    # By default the device connected is detected, but if more than 1
    # device, override the following to get a specific device.
    # "device"       : "HT66N0300080",
    # Folder where all the results will be collected
    "results_dir" : "BinderTransactionTracing",
    # Define devlib modules to load
    "modules"     : [
        'cpufreq',      # enable CPUFreq support
        'cpuidle',      # enable cpuidle support
        # 'cgroups'     # Enable for cgroup support
    ],
    "emeter" : {
        'instrument': 'monsoon',
        'conf': { }
    },
    "systrace": {
        'extra_categories': ['binder_driver'],
        "extra_events": ["binder_transaction_alloc_buf"],
    },
    # Tools required by the experiments
    "tools"   : [ 'taskset'],

    "skip_nrg_model" : True,
}

te = TestEnv(conf, wipe=False)
target = te.target

def experiment(duration_s, cmd):
    """
    Starts systrace and run a command on target if specified. If
    no command is given, collect the trace for duration_s seconds.

    :param duration_s: duration to collect systrace
    :type duration_s: int

    :param cmd: command to execute on the target
    :type cmd: string
    """
    systrace_output = System.systrace_start(
        te, os.path.join(te.res_dir, 'trace.html'), conf=conf)
    if cmd:
        target.execute(cmd)
    else:
        sleep(duration_s)
    systrace_output.sendline("")
    System.systrace_wait(te, systrace_output)
    te.platform_dump(te.res_dir)

parser = argparse.ArgumentParser(
    description="Collect systrace for binder events while executing"
    "a command on the target or wait for duration_s seconds")

parser.add_argument("--duration", "-d", type=int, default=0,
                    help="How long to collect the trace in seconds.")
parser.add_argument("--command", "-c", type=str, default="",
                    help="Command to execute on the target.")

if __name__ == "__main__":
    args = parser.parse_args()
    experiment(args.duration, args.command)
