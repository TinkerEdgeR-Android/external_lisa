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
    def __init__(self, pid, tgid, name):
        super(PidResidency, self).__init__()
        self.tgid = tgid
        self.pid = pid
        self.name = name

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

class ResidencyAnalysis(AnalysisModule):
    """
    Support for calculating residencies

    :param trace: input Trace object
    :type trace: :mod:`libs.utils.Trace`
    """

    def __init__(self, trace):
        pid_tgid = None
        pid_residency = None
        tgid_residency = None
        cgroup_residency = None
        core_residency = None
        super(ResidencyAnalysis, self).__init__(trace)

    def _dfg_get_cpu_residencies(self):
        # Build the pid_tgid map
        self.pid_tgid = {}
        df = self._dfg_trace_event('sched_switch')
        df = df[['__pid', '__tgid']].drop_duplicates()
        df_with_tgids = df[df['__tgid'] != -1]
        for s in df_with_tgids.iterrows():
            self.pid_tgid[s[1]['__pid']] = s[1]['__tgid']

        # How many pids in total
        self.npids = len(df.index)
        # How many pids with tgid
        self.npids_tgid = len(self.pid_tgid.keys())

        print self.npids
        print self.npids_tgid
        print self.pid_tgid

# vim :set tabstop=4 shiftwidth=4 expandtab
