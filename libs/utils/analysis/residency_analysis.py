# SPDX-License-Identifier: Apache-2.0
#
# Copyright (C) 2015, Google, ARM Limited and contributors.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

""" Residency Analysis Module """

import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import pandas as pd
import pylab as pl
import operator
from trappy.utils import listify
from devlib.utils.misc import memoized
import numpy as np
import logging

from analysis_module import AnalysisModule
from trace import ResidencyTime, ResidencyData
from bart.common.Utils import area_under_curve

class Residency(object):
    def __init__(self, time):
        self.last_start_time = time
        self.total_time = np.float64(0.0)
        # Keep track of last seen start times
        self.start_time = -1
        # Keep track of maximum runtime seen
        self.end_time = -1
        self.max_runtime = -1
        # When Residency is created for the first time,
        # its running (switch in)
        self.running = 1

class PidResidency(Residency):
    def __init__(self, pid, comm, time):
        super(PidResidency, self).__init__(time)
        self.pid = pid
        self.comm = comm

class TgidResidency(Residency):
    def __init__(self, pid, name):
        super(PidResidency, self).__init__()
        # PID of the Task group main process
        self.pid = pid
        self.name = name

class CgroupResidency(Residency):
    def __init__(self, cgroup_name):
        super(CgroupResidency, self).__init__()
        self.name = cgroup_name

################################################################
# Callback and state machinery                                 #
################################################################
res_analysis_obj = None
debugg = False

def switch_cb(data):
    global res_analysis_obj, debugg

    log = res_analysis_obj._log
    prevpid = data['prev_pid']
    nextpid = data['next_pid']
    time = data['Index']
    cpu = data['__cpu']
    pid_res = res_analysis_obj.pid_residency[cpu]

    if debugg:
        print "{}: {} {} -> {} {}".format(time, prevpid, data['prev_comm'], \
                                          nextpid, data['next_comm'])

    # prev pid processing (switch out)
    if pid_res.has_key(prevpid):
        pr = pid_res[prevpid]
        if pr.running == 1:
            pr.running = 0
            runtime = time - pr.last_start_time
            if runtime > pr.max_runtime:
                pr.max_runtime = runtime
                pr.start_time = pr.last_start_time
                pr.end_time = time
            pr.total_time += runtime
            if debugg: log.info('adding to total time {}, new total {}'.format(runtime, pr.total_time))

        else:
            log.info('switch out seen while no switch in {}'.format(prevpid))
    else:
        log.info('switch out seen while no switch in {}'.format(prevpid))

    # nextpid processing for new pid (switch in)
    if not pid_res.has_key(nextpid):
        pr = PidResidency(nextpid, data['next_comm'], time)
        pid_res[nextpid] = pr
        return

    # nextpid processing for previously discovered pid (switch in)
    pr = pid_res[nextpid]
    if pr.running == 1:
        log.info('switch in seen for already running task {}'.format(nextpid))
        return
    pr.running = 1
    pr.last_start_time = time

class ResidencyAnalysis(AnalysisModule):
    """
    Support for calculating residencies

    :param trace: input Trace object
    :type trace: :mod:`libs.utils.Trace`
    """

    def __init__(self, trace):
        self.pid_list = []
        self.pid_tgid = {}
	# Array of entities (cores) to calculate residencies on
        # Each entries is a hashtable, for ex: pid_residency[0][123]
        # is the residency of PID 123 on core 0
        self.pid_residency = []
        self.tgid_residency = []
        self.cgroup_residency = []
        super(ResidencyAnalysis, self).__init__(trace)
	global res_analysis_obj
	res_analysis_obj = self

    def generate_residency_data(self):
        logging.info("Generating residency for {} PIDs!".format(len(self.pid_list)))
        for pid in self.pid_list:
            dict_ret = {}
            total = 0
            dict_ret['name'] = self._trace.getTaskByPid(pid)[0]
            dict_ret['tgid'] = -1 if not self.pid_tgid.has_key(pid) else self.pid_tgid[pid]
            for cpunr in range(0, self.ncpus):
                cpu_key = 'cpu_{}'.format(cpunr)
                try:
                    dict_ret[cpu_key] = self.pid_residency[cpunr][pid].total_time
                except:
                    dict_ret[cpu_key] = 0
                total += dict_ret[cpu_key]

            dict_ret['total'] = total
            yield dict_ret

    def _dfg_cpu_residencies(self):
        # Build a list of pids
        df = self._dfg_trace_event('sched_switch')
        df = df[['__pid']].drop_duplicates()
        for s in df.iterrows():
            self.pid_list.append(s[1]['__pid'])

        # Build the pid_tgid map (skip pids without tgid)
        df = self._dfg_trace_event('sched_switch')
        df = df[['__pid', '__tgid']].drop_duplicates()
        df_with_tgids = df[df['__tgid'] != -1]
        for s in df_with_tgids.iterrows():
            self.pid_tgid[s[1]['__pid']] = s[1]['__tgid']

	self.pid_tgid[0] = 0 # Record the idle thread as well (pid = tgid = 0)

        self.npids = len(df.index)                      # How many pids in total
        self.npids_tgid = len(self.pid_tgid.keys())     # How many pids with tgid
	self.ncpus = self._trace.ftrace._cpus		# How many total cpus

        logging.info("TOTAL number of CPUs: {}".format(self.ncpus))
        logging.info("TOTAL number of PIDs: {}".format(self.npids))
        logging.info("TOTAL number of TGIDs: {}".format(self.npids_tgid))

        # Create empty hash tables, 1 per CPU for each each residency
        for cpunr in range(0, self.ncpus):
            self.pid_residency.append({})
            self.tgid_residency.append({})
            self.cgroup_residency.append({})

        # Calculate residencies
        self._trace.ftrace.apply_callbacks({ "sched_switch": switch_cb })

        # Now build the final DF!
        pid_idx = pd.Index(self.pid_list, name="pid")
        df = pd.DataFrame(self.generate_residency_data(), index=pid_idx)
        df.sort_index(inplace=True)

        logging.info("total time spent by all pids across all cpus: {}".format(df['total'].sum()))
        logging.info("total real time range of events: {}".format(self._trace.time_range))
        return df

# vim :set tabstop=4 shiftwidth=4 expandtab
