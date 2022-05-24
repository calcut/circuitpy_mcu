'''!
  Heavily modified from:
  @file DFRobot_PH.py
  @copyright   Copyright (c) 2010 DFRobot Co.Ltd (http://www.dfrobot.com)
  @license     The MIT License (MIT)
  @author [Jiawei Zhang](jiawei.zhang@dfrobot.com)
  @version  V1.0
  @date  2018-11-06
  @url https://github.com/DFRobot/DFRobot_PH
'''

import adafruit_logging as logging
import time
import sys

class DFRobot_PH():

    def __init__(self, analog_in, calibration_file=None, log_handler=None):

        if log_handler:
            self.log = logging.getLogger('pH_log')
            self.log.setLevel(logging.INFO)
        else:
            self.log = logging.NullLogger()

        self.adc = analog_in # Should be an AnalogIn object
        self.calibration_file = calibration_file

        # defaults
        self.acid_voltage      = 2.03244
        self.neutral_voltage   = 1.50
        self.calibration_temp  = 25

        if calibration_file:
            try:
                with open(calibration_file,'r') as f:
                    line = f.readline()
                    self.neutral_voltage = float(line.strip('neutral_voltage='))
                    line = f.readline()
                    self.acid_voltage = float(line.strip('acid_voltage='))
                    line = f.readline()
                    self.calibration_temp = float(line.strip('calibration_temp='))

                    self.log.info(f'After calibration {self.neutral_voltage=}  {self.acid_voltage=} {self.calibration_temp=}')
            except OSError as e:
                if e.errno==2:
                    self.log.warning(f'Calibration file not found: {calibration_file}')
                    self.log.warning('Writing new file with default/uncalibrated settings')
                    self.write_calibration_file()
                else:
                    self.log.error(f'Could not read calibration data from {calibration_file}')
                    self.log.error(str(e))

    def read_PH(self, temperature=None):

        voltage = self.adc.voltage

        # modified from the original be simplified to a y=mx+c line
        slope     = (7.0-4.0)/(self.neutral_voltage - self.acid_voltage)
        intercept = 7.0 - slope*self.neutral_voltage
        ph        = slope*voltage+intercept
        round(ph,2)

        return ph

    def read_PH(self, temperature=None):

        voltage = self.adc.voltage

        if not temperature:
            temperature = self.calibration_temp

        # Our probe's calibrated slope
        slope = (7-4) / (self.neutral_voltage - self.acid_voltage) #pH/V

        # Derivation of temperature effects is shown here, but value is hard coded as a temperature coefficent
            # # Theoretical/ideal slopes according to Nernst Equation.
            # # Using this so we don't have to calibrate our probe at 2 different temperatures.
            # slope_00c = -54.20 #mV/pH at 0 degC
            # slope_25c = -59.16 #mV/pH at 25 degC

            # # Calculate how much the slope should be modified as we move away from 25C
            # temperature_modifier = (slope_25c-slope_00c)/25 # mV/pH/degC

            # # Our probe has a different range (all positive volts), convert to a ratio
            # temperature_coeff = temperature_modifier/slope_25c # /degC

        # slope changes (from calibration) by this much per degC
        temperature_coeff = 0.00335 # /degC

        # apply the temperature coeff to our slope    
        slope = slope + (slope * temperature_coeff*(self.calibration_temp-temperature))

        # To calculate pH, take the difference between voltage and neutral voltage
        # This means the offset is exactly 7
        # Necessary becuase neutral pH is the isopotential point 
        # where temperature does not affect the measurement.
        # http://tools.thermofisher.com/content/sfs/brochures/Log-86-Tip-pH-Temperature-Compensation-Simplified-EN.pdf

        ph = (voltage - self.neutral_voltage) * slope + 7
        ph = round(ph,2)

        return ph

    def calibrate(self, temperature=None):

        if not self.calibration_file:
            self.log.warning('No calibration file specified, calibration will not be saved!')

        voltage = self.adc.voltage
        if temperature:
            self.calibration_temp = temperature
        
        self.log.info('These ranges may need adjusted:')
        vmin_ph7 = 1.2
        # vmin_ph7 = 1.322 # Often getting lower than this for PH7
        vmax_ph7 = 1.678
        vmin_ph4 = 1.854
        vmax_ph4 = 2.210
        self.log.info(f"Expected pH 7.0 range = {vmin_ph7} to {vmax_ph7} volts")
        self.log.info(f"Expected pH 4.0 range = {vmin_ph4} to {vmax_ph4} volts")

        if (voltage>vmin_ph7 and voltage<vmax_ph7):
            self.neutral_voltage = voltage
            self.log.info(f"Calibrated pH 7.0 = {voltage} volts")
            self.write_calibration_file()

        elif (voltage>vmin_ph4 and voltage<vmax_ph4):
            self.acid_voltage = voltage
            self.log.info(f"Calibrated pH 4.0 = {voltage} volts")
            self.write_calibration_file()

        else:
            self.log.warning(f"Voltage={voltage}, out of expected range for PH4.0 or PH7.0")


    def write_calibration_file(self):
        if self.calibration_file:
            try:
                with open(self.calibration_file,'w+') as f:
                    f.write(f'neutral_voltage={self.neutral_voltage}\n')
                    f.write(f'acid_voltage={self.acid_voltage}\n')
                    f.write(f'calibration_temp={self.calibration_temp}\n')
                    self.log.info(f'Writing to calibration file --> {self.calibration_file}:\n'
                        + f'neutral_voltage={self.neutral_voltage}\n'
                        + f'acid_voltage={self.acid_voltage}\n'
                        + f'calibration_temp={self.calibration_temp}\n')
            except Exception as e:
                self.log.error(f'Could not write calibration data to {self.calibration_file}')
                self.log.error(str(e)) 