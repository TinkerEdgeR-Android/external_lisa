#!/usr/bin/env python

import os
from lxml import etree

from power_average import PowerAverage

class PowerProfile:
    def __init__(self):
        self.xml = etree.Element('device', name='Android')

    default_comments = {
        'cpu.idle' : 'Power consumption when CPU is suspended',
        'cpu.awake' : 'Additional power consumption when CPU is in a kernel'
                ' idle loop',

        'screen.on' : 'Additional power used when screen is turned on at'
                ' minimum brightness',
        'screen.full' : 'Additional power used when screen is at maximum'
                ' brightness, compared to screen at minimum brightness',
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

    def __str__(self):
        return etree.tostring(self.xml, pretty_print=True)

class PowerProfileGenerator:

    @staticmethod
    def get(emeter):
        power_profile = PowerProfile()
        PowerProfileGenerator._compute_measurements(power_profile, emeter)
        return power_profile

    @staticmethod
    def _run_experiment(filename, duration, out_prefix, args=''):
        os.system('python {} --collect energy --duration {} --out_prefix {} {} '.format(
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
                'cpu_idle')
        power = PowerProfileGenerator._power_average(emeter,
                'SuspendResume_cpu_idle', start=duration*0.25,
                remove_outliers=True)

        power_profile.add_item('cpu.idle', power)

    # The power profile defines cpu.awake as an idle cpu
    @staticmethod
    def _measure_cpu_awake(power_profile, emeter):
        duration = 120
        PowerProfileGenerator._run_experiment('run_idle_resume.py', duration,
                'cpu_awake')
        power = PowerProfileGenerator._power_average(emeter,
                'IdleResume_cpu_awake', start=duration*0.25,
                remove_outliers=True)
        cpu_idle_power = power_profile.get_item('cpu.idle')

        power_profile.add_item('cpu.awake', power - cpu_idle_power)

    @staticmethod
    def _measure_screen_on(power_profile, emeter):
        duration = 120
        PowerProfileGenerator._run_experiment('run_display_image.py', duration,
                'screen_on', '--brightness 0')
        power = PowerProfileGenerator._power_average(emeter,
                'DisplayImage_screen_on')
        cpu_idle_power = power_profile.get_item('cpu.idle')

        power_profile.add_item('screen.on', power - cpu_idle_power)

    @staticmethod
    def _measure_screen_full(power_profile, emeter):
        duration = 120
        PowerProfileGenerator._run_experiment('run_display_image.py', duration,
                'screen_full', '--brightness 100')
        power = PowerProfileGenerator._power_average(emeter,
                'DisplayImage_screen_full')
        cpu_idle_power = power_profile.get_item('cpu.idle')

        power_profile.add_item('screen.full', power - cpu_idle_power)

    @staticmethod
    def _compute_measurements(power_profile, emeter):
        PowerProfileGenerator._measure_cpu_idle(power_profile, emeter)
        PowerProfileGenerator._measure_cpu_awake(power_profile, emeter)
        PowerProfileGenerator._measure_screen_on(power_profile, emeter)
        PowerProfileGenerator._measure_screen_full(power_profile, emeter)

my_emeter = {
    'power_column'      : 'output_power',
    'sample_rate_hz'    : 500,
}

print PowerProfileGenerator.get(my_emeter)
