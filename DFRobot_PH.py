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

        if calibration_file:
            try:
                with open(calibration_file,'r') as f:
                    line = f.readline()
                    self.neutral_voltage = float(line.strip('neutral_voltage='))
                    line = f.readline()
                    self.acid_voltage = float(line.strip('acid_voltage='))

                    self.log.info(f'After calibration {self.neutral_voltage=} {self.acid_voltage=}')
            except OSError as e:
                if e.errno==2:
                    self.log.warning(f'Calibration file not found: {calibration_file}')
                    self.log.warning('Using default/uncalibrated settings')
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
        # print(f'voltage = {voltage} adc = {self.adc} ph = {ph}')

        return ph

    def calibrate(self):

        if not self.calibration_file:
            self.log.warning('No calibration file specified, calibration will not be saved!')

        voltage = self.adc.voltage
        
        self.log.info('These ranges may need adjusted:')
        self.log.info(f"Expected pH 7.0 range = 1.322 to 1.678 volts")
        self.log.info(f"Expected pH 4.0 range = 1.854 to 2.210 volts")

        if (voltage>1.322 and voltage<1.678):
            self.neutral_voltage = voltage
            self.log.info(f"Calibrated pH 7.0 = {voltage} volts")
            try:
                with open(self.calibration_file, 'r+') as f:
                    flist=f.readlines()
                    flist[0]=f'neutral_voltage={self.neutral_voltage}\n'
                    f.seek(0)
                    f.writelines(flist)
                    print(f"PH:7.0 Calibration saved, {flist[0]} -> {self.calibration_file}")
            except Exception as e:
                self.log.error(f'Could not save calibration data to {self.calibration_file}')
                self.log.error(str(e))

        elif (voltage>1.854 and voltage<2.210):
            self.acid_voltage = voltage
            self.log.info(f"Calibrated pH 4.0 = {voltage} volts")

            try:
                with open(self.calibration_file, 'r+') as f:
                    flist=f.readlines()
                    flist[1]=f'acid_voltage={self.acid_voltage}\n'
                    f.seek(0)
                    f.writelines(flist)
                    print(f"PH:4.0 Calibration saved, {flist[1]} -> {self.calibration_file}")
            except Exception as e:
                self.log.error(f'Could not save calibration data to {self.calibration_file}')
                self.log.error(str(e))
        else:
            self.log.error(f"Voltage={voltage}, out of range for PH4.0 or PH7.0")

    # def reset(self):
    #     '''!
    #       @brief   Reset the calibration data to default value.
    #     '''
        
    #     _acidVoltage    = 2032.44
    #     _neutralVoltage = 1500.0
    #     try:
    #         f=open('phdata.txt','r+')
    #         flist=f.readlines()
    #         flist[0]='neutralVoltage='+ str(_neutralVoltage) + '\n'
    #         flist[1]='acidVoltage='+ str(_acidVoltage) + '\n'
    #         f=open('phdata.txt','w+')
    #         f.writelines(flist)
    #         f.close()
    #         print(">>>Reset to default parameters<<<")
    #     except:
    #         f=open('phdata.txt','w')
    #         #flist=f.readlines()
    #         flist   ='neutralVoltage='+ str(_neutralVoltage) + '\n'
    #         flist  +='acidVoltage='+ str(_acidVoltage) + '\n'
    #         #f=open('data.txt','w+')
    #         f.writelines(flist)
    #         f.close()
    #         print(">>>Reset to default parameters<<<")