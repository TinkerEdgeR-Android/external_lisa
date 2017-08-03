#!/usr/bin/env python

import logging

from conf import LisaLogging
LisaLogging.setup()
import json
import os
import devlib
from env import TestEnv
from android import Screen, Workload, System
from trace import Trace
import trappy
import pandas as pd
import sqlite3
import argparse
import shutil
from time import sleep

parser = argparse.ArgumentParser(description='CpuFrequency tests')

parser.add_argument('--out_prefix', dest='out_prefix', action='store',
                    default='default',
                    help='prefix for out directory')

parser.add_argument('--duration', dest='duration_s', action='store',
                    default=30, type=int,
                    help='Duration of test (default 30s)')

parser.add_argument('--serial', dest='serial', action='store',
                    help='Serial number of device to test')

args = parser.parse_args()

CRITICAL_TASKS = [
    "/system/bin/sh", "adbd", "/init"
]

def outfiles(on_cpus, freq):
    cpu_str = ''.join('{}-'.format(c) for c in on_cpus)
    samples = 'cpus{}freq{}-samples.csv'.format(cpu_str, freq)
    energy = 'cpus{}freq{}-energy.json'.format(cpu_str, freq)
    return energy, samples

def update_cpus(target, on_cpus, off_cpus):
    for cpu in on_cpus:
        target.hotplug.online(cpu)

    for cpu in off_cpus:
        target.hotplug.offline(cpu)

def experiment():
    # Check if the dhyrstone binary is on the device
    dhrystone = os.path.join(target.executables_directory, 'dhrystone')
    if not target.file_exists(dhrystone):
        raise RuntimeError('dhrystone could not be located here: {}'.format(
                dhrystone))

    # Create results directory
    outdir=te.res_dir + '_' + args.out_prefix
    try:
        shutil.rmtree(outdir)
    except:
        print "couldn't remove " + outdir
        pass
    os.makedirs(outdir)

    # Get clusters and cpus
    clusters = te.topology.get_level('cluster')
    cpus = [cpu for cluster in clusters for cpu in cluster]

    # Prevent screen from dozing
    Screen.set_doze_always_on(target, on=False)

    # Turn on airplane mode
    System.set_airplane_mode(target, on=True)

    # Turn off screen
    Screen.set_screen(target, on=False)

    # Store governors so they can be restored later
    governors = [ target.cpufreq.get_governor(cpu) for cpu in cpus]

    # Set the governer to userspace so the cpu frequencies can be set
    target.hotplug.online_all()
    target.cpufreq.set_all_governors('userspace')

    # Freeze all non critical tasks
    target.cgroups.freeze(exclude=CRITICAL_TASKS)

    # For each cluster
    for cluster in clusters:
        # Remove all userspace tasks from the cluster
        target_cg, _ = target.cgroups.isolate(cluster)

        # For each frequency on the cluster
        for freq in target.cpufreq.list_frequencies(cluster[0]):

            # Keep track of offline and online cpus
            off_cpus = cpus[:]
            on_cpus = []

            # For each cpu in the cluster
            for cpu in cluster:
                # Add the current cpu to the online list and remove it from the
                # offline list
                on_cpus.append(cpu)
                off_cpus.remove(cpu)

                # Bring the on_cpus online and take the off_cpus offline
                update_cpus(target, on_cpus, off_cpus)

                # Update the target cgroup in case hotplugging has introduced
                # any errors
                target_cg.set(cpus=on_cpus)

                # Switch the output file so the previous samples are not overwritten
                energy, samples = outfiles(on_cpus, freq)

                # Set cpu frequency for the newly add cpu
                target.cpufreq.set_frequency(cpu, freq)

                # Run dhrystone benchmark for longer than the requested time so
                # we have extra time to set up the measuring device
                target.execute('nohup {} -t {} -r {}  2>/dev/null 1>/dev/null'
                        ' &'.format(dhrystone, len(on_cpus), args.duration_s+60))

                # Start measuring
                te.emeter.reset()

                # Sleep for the required time
                sleep(args.duration_s)

                # Stop measuring
                te.emeter.report(outdir, out_energy=energy, out_samples=samples)

                # Kill dhrystone so it does not affect the next measurement
                pids = target.killall('dhyrstone')

    # Restore all the cpus
    target.hotplug.online_all()

    # Restore all governors
    for i, governor in enumerate(governors):
        target.cpufreq.set_governor(cpus[i], governor)

    # Restore non critical tasks
    target.cgroups.freeze(thaw=True)

    # Dump platform
    te.platform_dump(outdir)

    te._log.info('RESULTS are in out directory: {}'.format(outdir))

# Setup target configuration
my_conf = {

    # Target platform and board
    "platform"     : 'android',

    # Useful for reading names of little/big cluster
    # and energy model info, its device specific and use
    # only if needed for analysis
    # "board"        : 'pixel',

    # Device
    # By default the device connected is detected, but if more than 1
    # device, override the following to get a specific device.
    # "device"       : "HT6880200489",

    # Folder where all the results will be collected
    "results_dir" : "CpuFrequency",

    # Define devlib modules to load
    "modules"     : [
        'cpufreq',      # enable CPUFreq support
        'hotplug',      # enable hotplug support
        'cgroups',      # enable cgroups support
    ],

    "emeter" : {
        'instrument': 'monsoon',
        'conf': { }
    },

    # Tools required by the experiments
    "tools"     : [ ],

}

if args.serial:
    my_conf["device"] = args.serial

# Initialize a test environment using:
te = TestEnv(my_conf, wipe=False)
target = te.target

results = experiment()
