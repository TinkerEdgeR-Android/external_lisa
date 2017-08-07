#!/usr/bin/env python

from __future__ import division
import os
import re
import json
import argparse
import pandas as pd
import numpy as np

from power_average import PowerAverage

# This script computes the cluster power cost and cpu power costs at each
# frequency for each cluster. The output can be used in power models or power
# profiles.

def average(values):
    return sum(values) / len(values)

class Cluster:
    def __init__(self, cpus, freqs):
        # Cpus in the cluster
        self.cpus = cpus
        # Frequencies supported by the cluster
        self.freqs = freqs
        # The average cluster cost of this cluster
        self.cluster_cost = 0.0
        # The average cpu costs by frequency
        self.cpu_costs = {}
        # Samples is a dict whose keys are tuples of cpus. Its values are dicts
        # whose keys are frequencies and values are sample averages.
        # For example: to access the sample averages for cpus 0, 1, 2 at frequency
        # 595200. avg = samples[(0, 1, 2)][595200]
        self.samples = {}

    def contains(self, cpus):
        return set(self.cpus).issuperset(set(cpus))

    def add_sample(self, cpus, freq, cost):
        # Convert the cpus to a tuple because mutable lists cannot be used as
        # keys to dicts.
        cpus_tuple = tuple(cpus)

        if cpus_tuple not in self.samples:
            self.samples[cpus_tuple] = {}

        self.samples[cpus_tuple][freq] = cost

    def get_sample(self, cpus, freq):
        return self.samples[tuple(cpus)][freq]

    def compute_costs(self):
        # At any given frequency, the total power usage of the cluster is
        # total_power = cluster_cost + cpu_cost * n_cpus
        #
        # Given this formula we can compute the cluster cost and cpu cost at
        # each frequency.
        #
        # While the computed cluster_cost can vary based on frequency, we need
        # to get one cluster_cost. To do this, we will
        # take the average cluster_cost.
        #
        # Once we have an average cluster_cost, we can go back and compute the
        # cost of an additional cpu at each frequency relative to the average
        # cluster_cost.

        # Compute cluster cost
        cluster_costs = []

        for freq in self.freqs:
            for n in range(1, len(self.cpus)):
                # cluster_cost + cpu_cost * n
                n_cost = self.get_sample(self.cpus[:n], freq)
                # cluster_cost + cpu_cost * (n + 1)
                n_plus_one_cost = self.get_sample(self.cpus[:n+1], freq)

                # (cluster_cost + cpu_cost * (n + 1)) - (cluster_cost + cpu_cost * n)
                cpu_cost = n_plus_one_cost - n_cost

                # cpu_cost * n
                n_cpu_cost = cpu_cost * n

                # (cluster_cost + cpu_cost * n) - (cpu_cost * n)
                cluster_costs.append(n_cost - n_cpu_cost)

        self.cluster_cost = average(cluster_costs)

        # Compute cpu costs
        for freq in self.freqs:
            cpu_costs = []

            for n in range(1, len(self.cpus) + 1):
                # cluster_cost + cpu_cost * n
                total_cost = self.get_sample(self.cpus[:n], freq)

                # ((cluster_cost + cpu_cost * n) - cluster_cost) / n
                cpu_costs.append((total_cost - self.cluster_cost) / n)

            self.cpu_costs[freq] = average(cpu_costs)

    def get_cpus(self):
        return self.cpus

    def get_cluster_cost(self):
        return self.cluster_cost

    def get_cpu_freqs(self):
        return sorted(list(self.cpu_costs.keys()))

    def get_cpu_cost(self, freq):
        return self.cpu_costs[freq]

    def __str__(self):
        cpu_cost_str = "".join("\tfreq: %s \tcost: %s\n" % (f, self.cpu_costs[f])
                for f in sorted(self.cpu_costs))
        return "Cluster: {}\nCluster cost: {}\nCpu cost:\n{}".format(self.cpus,
                self.cluster_cost, cpu_cost_str)

    __repr__ = __str__


class CpuFrequencyPowerAverage:
    @staticmethod
    def get(results_dir, platform_file, column):
        clusters = []

        CpuFrequencyPowerAverage._populate_clusters(clusters, platform_file)
        CpuFrequencyPowerAverage._parse_samples(clusters, results_dir, column)
        CpuFrequencyPowerAverage._compute_costs(clusters)

        return clusters

    @staticmethod
    def _populate_clusters(clusters, platform_file):
        with open(platform_file, 'r') as f:
            platform = json.load(f)

        for i in sorted(platform["clusters"]):
            clusters.append(Cluster(platform["clusters"][i], platform["freqs"][i]))

    @staticmethod
    def _parse_samples(clusters, results_dir, column):
        for filename in os.listdir(results_dir):
            if filename.endswith(".csv"):

                # Extract the cpu and frequency information from the file name
                m = re.match('cpus(?P<cpus>(\d-)+)freq(?P<freq>\d*)-samples.csv',
                    filename)

                # Get the cpus running during the sample in an int tuple
                cpus = tuple(map(int, m.group('cpus')[:-1].split('-')))
                freq = int(m.group('freq'))

                # Add the cost to the correct cluster
                cost = PowerAverage.get(os.path.join(results_dir, filename),
                        column)

                for cluster in clusters:
                    if cluster.contains(cpus):
                        cluster.add_sample(cpus, freq, cost)
                        break;

    @staticmethod
    def _compute_costs(clusters):
        for cluster in clusters:
            cluster.compute_costs()


parser = argparse.ArgumentParser(
        description="Get the cluster cost and cpu cost per frequency. Optionally"
                    " specify a time interval over which to calculate the sample.")

parser.add_argument("--column", "-c", type=str, required=True,
                    help="The name of the column in the sample.csv's that"
                    " contain the power values to average.")

parser.add_argument("--results_dir", "-d", type=str,
                    default=os.path.join(os.environ["LISA_HOME"],
                    "results/CpuFrequency_default"),
                    help="The results directory to read from. (default"
                    " LISA_HOME/results/CpuFrequency_default)")

parser.add_argument("--platform_file", "-p", type=str,
                    default=os.path.join(os.environ["LISA_HOME"],
                    "results/CpuFrequency/platform.json"),
                    help="The results directory to read from. (default"
                    " LISA_HOME/results/CpuFrequency/platform.json)")

if __name__ == "__main__":
    args = parser.parse_args()

    print CpuFrequencyPowerAverage.get(args.results_dir, args.platform_file,
            args.column)
