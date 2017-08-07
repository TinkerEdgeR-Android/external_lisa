#!/usr/bin/env python

import os
from lxml import etree

from power_average import PowerAverage
from cpu_frequency_power_average import CpuFrequencyPowerAverage


class PowerProfile:
    def __init__(self):
        self.xml = etree.Element('device', name='Android')

    default_comments = {
        'none' : 'Nothing',

        'battery.capacity' : 'This is the battery capacity in mAh',

        'cpu.idle' : 'Power consumption when CPU is suspended',
        'cpu.awake' : 'Additional power consumption when CPU is in a kernel'
                ' idle loop',
        'cpu.clusters.cores' : 'Number of cores each CPU cluster contains',

        'screen.on' : 'Additional power used when screen is turned on at'
                ' minimum brightness',
        'screen.full' : 'Additional power used when screen is at maximum'
                ' brightness, compared to screen at minimum brightness',

        'bluetooth.controller.idle' : 'Average current draw (mA) of the'
                ' Bluetooth controller when idle.',
        'bluetooth.controller.rx' : 'Average current draw (mA) of the Bluetooth'
                ' controller when receiving.',
        'bluetooth.controller.tx' : 'Average current draw (mA) of the Bluetooth'
                ' controller when transmitting.',
        'bluetooth.controller.voltage' : 'Average operating voltage (mV) of the'
                ' Bluetooth controller.',

        'modem.controller.idle' : 'Average current draw (mA) of the modem'
                ' controller when idle.',
        'modem.controller.rx' : 'Average current draw (mA) of the modem'
                ' controller when receiving.',
        'modem.controller.tx' : 'Average current draw (mA) of the modem'
                ' controller when transmitting.',
        'modem.controller.voltage' : 'Average operating voltage (mV) of the'
                ' modem controller.',

        'wifi.controller.idle' : 'Average current draw (mA) of the Wi-Fi'
                ' controller when idle.',
        'wifi.controller.rx' : 'Average current draw (mA) of the Wi-Fi'
                ' controller when receiving.',
        'wifi.controller.tx' : 'Average current draw (mA) of the Wi-Fi'
                ' controller when transmitting.',
        'wifi.controller.voltage' : 'Average operating voltage (mV) of the'
                ' Wi-Fi controller.',
    }

    def _add_comment(self, item, name, comment):
        if (not comment) and (name in PowerProfile.default_comments):
            comment = PowerProfile.default_comments[name]
        if comment:
            self.xml.append(etree.Comment(comment))

    def add_item(self, name, value, comment=None):
        if self.get_item(name) is not None:
            raise RuntimeWarning('{} already added. Skipping.'.format(name))
            return

        item = etree.Element('item', name=name)
        item.text = str(value)
        self._add_comment(self.xml, name, comment)
        self.xml.append(item)

    def get_item(self, name):
        items = self.xml.findall(".//*[@name='{}']".format(name))
        if len(items) == 0:
            return None
        return float(items[0].text)

    def add_array(self, name, values, comment=None, subcomments=None):
        array = etree.Element('array', name=name)
        for i, value in enumerate(values):
            entry = etree.Element('value')
            entry.text = str(value)
            if subcomments:
                array.append(etree.Comment(subcomments[i]))
            array.append(entry)

        self._add_comment(self.xml, name, comment)
        self.xml.append(array)

    def __str__(self):
        return etree.tostring(self.xml, pretty_print=True)

class PowerProfileGenerator:

    @staticmethod
    def get(emeter, datasheet):
        power_profile = PowerProfile()

        PowerProfileGenerator._compute_measurements(power_profile, emeter)
        PowerProfileGenerator._import_datasheet(power_profile, datasheet)

        return power_profile

    @staticmethod
    def _run_experiment(filename, duration, out_prefix, args=''):
        os.system('python {} --duration {} --out_prefix {} {} '.format(
                os.path.join(os.environ['LISA_HOME'], 'experiments', filename),
                duration, out_prefix, args))

    @staticmethod
    def _power_average(emeter, results_dir, start=None, remove_outliers=False):
        column = emeter['power_column']
        sample_rate_hz = emeter['sample_rate_hz']

        return PowerAverage.get(os.path.join(os.environ['LISA_HOME'], 'results',
                results_dir, 'samples.csv'), column, sample_rate_hz,
                start=start, remove_outliers=remove_outliers) * 1000

    # The power profile defines cpu.idle as a suspended cpu
    @staticmethod
    def _measure_cpu_idle(power_profile, emeter):
        duration = 120
        PowerProfileGenerator._run_experiment('run_suspend_resume.py', duration,
                'cpu_idle', args='--collect energy')
        power = PowerProfileGenerator._power_average(emeter,
                'SuspendResume_cpu_idle', start=duration*0.25,
                remove_outliers=True)

        power_profile.add_item('cpu.idle', power)

    # The power profile defines cpu.awake as an idle cpu
    @staticmethod
    def _measure_cpu_awake(power_profile, emeter):
        duration = 120
        PowerProfileGenerator._run_experiment('run_idle_resume.py', duration,
                'cpu_awake', args='--collect energy')
        power = PowerProfileGenerator._power_average(emeter,
                'IdleResume_cpu_awake', start=duration*0.25,
                remove_outliers=True)
        cpu_idle_power = power_profile.get_item('cpu.idle')

        power_profile.add_item('cpu.awake', power - cpu_idle_power)

    @staticmethod
    def _measure_screen_on(power_profile, emeter):
        duration = 120
        PowerProfileGenerator._run_experiment('run_display_image.py', duration,
                'screen_on', args='--collect energy --brightness 0')
        power = PowerProfileGenerator._power_average(emeter,
                'DisplayImage_screen_on')
        cpu_idle_power = power_profile.get_item('cpu.idle')

        power_profile.add_item('screen.on', power - cpu_idle_power)

    @staticmethod
    def _measure_screen_full(power_profile, emeter):
        duration = 120
        PowerProfileGenerator._run_experiment('run_display_image.py', duration,
                'screen_full', args='--collect energy --brightness 100')
        power = PowerProfileGenerator._power_average(emeter,
                'DisplayImage_screen_full')
        cpu_idle_power = power_profile.get_item('cpu.idle')

        power_profile.add_item('screen.full', power - cpu_idle_power)

    @staticmethod
    def _measure_clusters(power_profile, emeter):
        duration = 120
        # Run experiment
        PowerProfileGenerator._run_experiment('run_cpu_frequency.py', duration,
                'cpu_freq')

        # Get clusters
        clusters = CpuFrequencyPowerAverage.get(
                os.path.join(os.environ['LISA_HOME'], 'results',
                'CpuFrequency_cpu_freq'), os.path.join(os.environ['LISA_HOME'],
                'results', 'CpuFrequency', 'platform.json'),
                emeter['power_column'])

        # Add cpu.clusters.cores
        cpu_cluster_cores = [ len(cluster.get_cpus()) for cluster in clusters ]
        power_profile.add_array('cpu.clusters.cores', cpu_cluster_cores)

        # Add cpu.base.cluster
        for i, cluster in enumerate(clusters):
            comment = 'Additional power used when any cpu core is turned on'\
                    ' in cluster{}. Does not include the power used by the cpu'\
                    ' core(s).'.format(i)
            power_profile.add_item('cpu.base.cluster{}'.format(i),
                    cluster.get_cluster_cost()*1000, comment)

        # Add cpu.speeds.cluster
        for i, cluster in enumerate(clusters):
            comment = 'Different CPU speeds as reported in /sys/devices/system/'\
                    'cpu/cpu{}/cpufreq/scaling_available_frequencies'.format(
                    cluster.get_cpus()[0])
            freqs = cluster.get_cpu_freqs()
            power_profile.add_array('cpu.speeds.cluster{}'.format(i),
                    freqs, comment)

        # Add cpu.active.cluster
        for i, cluster in enumerate(clusters):
            freqs = cluster.get_cpu_freqs()
            cpu_active = [ cluster.get_cpu_cost(freq)*1000 for freq in freqs ]
            comment = 'Additional power used by a CPU from cluster {} when'\
                    ' running at different speeds. Currently this measurement'\
                    ' also includes cluster cost.'.format(i)
            subcomments = [ '{} MHz CPU speed'.format(freq * 0.001) for freq in freqs ]
            power_profile.add_array('cpu.active.cluster{}'.format(i),
                    cpu_active, comment, subcomments)

    @staticmethod
    def _compute_measurements(power_profile, emeter):
        PowerProfileGenerator._measure_cpu_idle(power_profile, emeter)
        PowerProfileGenerator._measure_cpu_awake(power_profile, emeter)
        PowerProfileGenerator._measure_screen_on(power_profile, emeter)
        PowerProfileGenerator._measure_screen_full(power_profile, emeter)
        PowerProfileGenerator._measure_clusters(power_profile, emeter)

    @staticmethod
    def _import_datasheet(power_profile, datasheet):
        for item in sorted(datasheet.keys()):
            power_profile.add_item(item, datasheet[item])

my_emeter = {
    'power_column'      : 'output_power',
    'sample_rate_hz'    : 500,
}

my_datasheet = {

# Add datasheet values in the following format:
#
#    'none'  : 0,
#
#    'battery.capacity'  : 0,
#
#    'bluetooth.controller.idle'     : 0,
#    'bluetooth.controller.rx'       : 0,
#    'bluetooth.controller.tx'       : 0,
#    'bluetooth.controller.voltage'  : 0,
#
#    'modem.controller.idle'     : 0,
#    'modem.controller.rx'       : 0,
#    'modem.controller.tx'       : 0,
#    'modem.controller.voltage'  : 0,
#
#    'wifi.controller.idle'      : 0,
#    'wifi.controller.rx'        : 0,
#    'wifi.controller.tx'        : 0,
#    'wifi.controller.voltage'   : 0,
}

print PowerProfileGenerator.get(my_emeter, my_datasheet)
