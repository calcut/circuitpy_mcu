"""
A Wrapper for the sparkfun LCD display library to help display datapoints.
"""

from sparkfun_serlcd import Sparkfun_SerLCD_I2C

class LCD_16x2(Sparkfun_SerLCD_I2C):
    def __init__(self, i2c):
        Sparkfun_SerLCD_I2C.__init__(self, i2c)

        self.set_fast_backlight_rgb(255, 255, 255)
        self.clear()

        # initialise variables for show_data_*() functions
        self.labels = ['','','','','','','','']
        self.values = ['','','','','','','','']
        self.page = False

    
    
    def show_text(self, text):
        self.clear()
        self.write(text)

    # ----------------------------------
    # show_data_16x2()
    # A helper function to display 8 strings, typically 4 labels and 4 data
    # points.
    # Intended for use with 16x2 LCD
    # Can toggle pages to show a different set of data
    

    def show_data(self, toggle=False):
        if toggle:
            self.page = not self.page
            
        l = self.labels
        v = self.values

        if not self.page:
            # prints labels and values, forcing 4 characters wide
            self.set_cursor(0,0)
            self.write(f'{l[0]:>4}'[:4])
            self.write(f'{v[0]:<4}'[:4])

            self.set_cursor(8,0)
            self.write(f'{l[1]:>4}'[:4])
            self.write(f'{v[1]:<4}'[:4])

            self.set_cursor(0,1)
            self.write(f'{l[2]:>4}'[:4])
            self.write(f'{v[2]:<4}'[:4])

            self.set_cursor(8,1)
            self.write(f'{l[3]:>4}'[:4])
            self.write(f'{v[3]:<4}'[:4])

        if self.page:
            self.set_cursor(0,0)
            self.write(f'{l[4]:>4}'[:4])
            self.write(f'{v[4]:<4}'[:4])

            self.set_cursor(8,0)
            self.write(f'{l[5]:>4}'[:4])
            self.write(f'{v[5]:<4}'[:4])

            self.set_cursor(0,1)
            self.write(f'{l[6]:>4}'[:4])
            self.write(f'{v[6]:<4}'[:4])

            self.set_cursor(8,1)
            self.write(f'{l[7]:>4}'[:4])
            self.write(f'{v[7]:<4}'[:4])

    

class LCD_20x4(Sparkfun_SerLCD_I2C):
    def __init__(self, i2c):
        Sparkfun_SerLCD_I2C.__init__(self, i2c)

        self.set_fast_backlight_rgb(255, 255, 255)
        self.clear()

        # initialise variables for show_data_*() functions
        self.labels = ['','','','','','','','']
        self.values = ['','','','','','','','']
        self.page = False

    def show_text(self, text):
        self.clear()
        self.write(text)

    def show_data_20x2(self, toggle=False):
        if toggle:
            self.page = not self.page
            
        l = self.labels
        v = self.values

        if not self.page:
            # prints labels and values, forcing 5 characters wide
            self.set_cursor(0,0)
            self.write(f'{l[0]:>5}'[:5])
            self.write(f'{v[0]:<5}'[:5])

            self.set_cursor(10,0)
            self.write(f'{l[1]:>5}'[:5])
            self.write(f'{v[1]:<5}'[:5])

            self.set_cursor(0,1)
            self.write(f'{l[2]:>5}'[:5])
            self.write(f'{v[2]:<5}'[:5])

            self.set_cursor(10,1)
            self.write(f'{l[3]:>5}'[:5])
            self.write(f'{v[3]:<5}'[:5])

        if self.page:
            self.set_cursor(0,0)
            self.write(f'{l[4]:>5}'[:5])
            self.write(f'{v[4]:<5}'[:5])

            self.set_cursor(10,0)
            self.write(f'{l[5]:>5}'[:5])
            self.write(f'{v[5]:<5}'[:5])

            self.set_cursor(0,1)
            self.write(f'{l[6]:>5}'[:5])
            self.write(f'{v[6]:<5}'[:5])

            self.set_cursor(10,1)
            self.write(f'{l[7]:>5}'[:5])
            self.write(f'{v[7]:<5}'[:5])

    def show_data_20x4(self):            
        l = self.labels
        v = self.values

        # prints labels and values, forcing 5 characters wide
        self.set_cursor(0,0)
        self.write(f'{l[0]:>5}'[:5])
        self.write(f'{v[0]:<5}'[:5])

        self.set_cursor(10,0)
        self.write(f'{l[1]:>5}'[:5])
        self.write(f'{v[1]:<5}'[:5])

        self.set_cursor(0,1)
        self.write(f'{l[2]:>5}'[:5])
        self.write(f'{v[2]:<5}'[:5])

        self.set_cursor(10,1)
        self.write(f'{l[3]:>5}'[:5])
        self.write(f'{v[3]:<5}'[:5])

        self.set_cursor(0,2)
        self.write(f'{l[4]:>5}'[:5])
        self.write(f'{v[4]:<5}'[:5])

        self.set_cursor(10,2)
        self.write(f'{l[5]:>5}'[:5])
        self.write(f'{v[5]:<5}'[:5])

        self.set_cursor(0,3)
        self.write(f'{l[6]:>5}'[:5])
        self.write(f'{v[6]:<5}'[:5])

        self.set_cursor(10,3)
        self.write(f'{l[7]:>5}'[:5])
        self.write(f'{v[7]:<5}'[:5])

    def show_data_long(self):            
        l = self.labels
        v = self.values

        # prints labels and values, forcing 10 characters wide
        self.set_cursor(0,0)
        self.write(f'{l[0]:>10}'[:10])
        self.write(f'{v[0]:<10}'[:10])

        self.set_cursor(0,1)
        self.write(f'{l[1]:>10}'[:10])
        self.write(f'{v[1]:<10}'[:10])

        self.set_cursor(0,2)
        self.write(f'{l[2]:>10}'[:10])
        self.write(f'{v[2]:<10}'[:10])

        self.set_cursor(0,3)
        self.write(f'{l[3]:>10}'[:10])
        self.write(f'{v[3]:<10}'[:10])

