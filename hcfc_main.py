# -*- coding: utf-8 -*-
"""
Created on Tue Oct  8 09:24:50 2019
branch gentry (06 April 2020)
@author: hcfc_ms
 
"""


from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QMessageBox, QTableWidget, QTableWidgetItem
from PyQt5.QtCore import QTime, Qt, QTimer
from hcfc import Ui_MainWindow
import sys
import random
import lj
from repeat_timer import RepeatTimer
from time import gmtime, strftime 
import time
import csv

class main(QtWidgets.QMainWindow):
          
    def __init__(self):
        '''Create an instance of main.
        Written by A. Clarke.
        Commented by M. Gentry on 02Apr2020'''
        
        super(main, self).__init__() # inherit __init__() of the parent class
        self.ui = Ui_MainWindow() # the only class defined in hcfc.py
        self.ui.setupUi(self) # method of Ui_MainWindow(), sets up UI
        
        self.tm = strftime("%Y-%m-%d %H:%M:%S", gmtime()) # str formated GMT 
        self.timers=[] # empty list to hold timers later (RepeatTimers?)
        self.auxilary_hardware() #method defined here. detect and connect to hardware
        self.list_entries=[] # for updating the UI status list
        
        self.timer_sequence_idle() # method defined here. Starts the system in idle mode
        self.start_time = 540 # start time in seconds
        # I assume start_time is a delay time
        self.start_time_min=self.start_time/60.0 # start time in minutes
        
        # These methods interface with the GUI defined in hcfc.py
        self.ui.pushStartStop.setEnabled(False)
        self.ui.exitButton.clicked.connect(self.appQuit)
        self.ui.createTableButton.clicked.connect(self.fillTable)
        self.ui.tableChangeButton.clicked.connect(self.editTable)
        #self.ui.pfpCheckBox.clicked.connect(self.start_sequence)
        self.sequence = [] # list for holding the injection sequence

        
    def fillTable(self):
        '''Create and populate the sequence table in the GUI from sequence.txt, 
        a comma-delimited text file in the working directory.
        Written by A. Clarke. 
        Commented and edited by M. Gentry on 03Apr2020.'''
        
        # Could use "with" for opening this file
        with open('sequence.txt') as seq_file:
            reader = csv.reader(seq_file) # reads the .txt file 
            for row in reader:
                self.sequence.append(row) # fills the empty list with the rows of the sequence file
        #below is the code to poplulate the sequence table.
        rowCount = len(self.sequence) # number of rows in the sequence file
        colCount = max([len(p) for p in self.sequence]) # legnth of longest row in sequence.txt
        # possibly should return debugging info 
        # instead of assuming all rows are of max length? e.g.
        min_colCount = min([len(p) for p in self.sequence])
        if colCount == min_colCount: # checks that the min and max row lengths are equal
            pass # continue executing the program
        else:
            raise ValueError('Rows of sequence.txt are of unequal length')
            # raising an error stops the code and prevents the table from populating
            # alternatively, print('Rows of sequence.txt are of unequal length')
            # will attempt to build the table anyway
        
        # Build the GUI table 
        self.ui.sequenceTable.setRowCount(rowCount) 
        self.tableWidget = QTableWidget()
        self.tableWidget.setRowCount(rowCount)
        self.tableWidget.setColumnCount(colCount)

        #populate the table 
        for row, sample in enumerate(self.sequence):
            for column, value in enumerate(sample):
               newItem = QTableWidgetItem(value) # make an editable GUI-object from value?
               self.ui.sequenceTable.setItem(row, column, newItem) # place newItem at (row,column)
        
        self.ui.pushStartStop.setEnabled(True) # un-grey the Start button
        self.ui.createTableButton.setEnabled(False) # Grey out the create table button
        
        # print to the Spyder console
        print(self.sequence)
        print(rowCount)
        print(colCount)
        
    
               
       
            
        
        #####self.timer_sequence_idle()
        #self.t=threading.Timer(10.0, self.sol0_on) 
        #self.t.start() 
        #self.t.cancel
       # self.t2=threading.Timer(15.0, self.sol0_off)
        #self.t2.start() 
        #self.handle =lj.t7_labjack.connect_labjack(self)
    #def startup(self):
        
        
    #def check_mode(self):
        
        #self.ui.idleCheckBox.stateChanged.connect(self.state_changed)
        #if self.ui.idleCheckBox.isChecked():
            #self.ui.pushStartStop.clicked.connect(self.timer_sequence_idle()
        #elif self.ui.normalCheckBox.isChecked():
            #self.ui.pushStartStop.clicked.connect(self.timer_sequence_normal()
       # elif self.ui.pfpCheckBox.isChecked():
            #pass
        #else:
            #self.timer_sequence_idle()
            
    def waitForStart(self):
        '''Written by A. Clarke
        Comented by M. Gentry on 03Apr2020
        self.timer and self.timer1 are defined in method timer_sequence_idle(),
        which passes waitForStart() as an argument as:
            'self.ui.normalCheckBox.stateChanged.connect(self.waitForStart)'
        '''
        
        # Stop the timers 
        self.timer.stop() 
        self.timer1.stop()
        
        # pass self.start_sequence() to another fuction
        self.ui.pushStartStop.clicked.connect(self.start_sequence)   
        
        
    def start_sequence(self):
        '''
        Presumably starts the sequence that is checked off on the GUI.
        Written by A. Clarke
        Commented by M. Gentry on 03Apr2020'''
        
        if self.ui.normalCheckBox.isChecked(): # Returns True if 'normal' is checked
            self.tm = strftime("%Y-%m-%d %H:%M:%S", gmtime()) # get GMT as a string
            self.list_entries.append(f'{self.tm} Status: normal')
            # self.list_entries is defined in __init__() 
            # it is the list of strings reported to the GUI as a sequence runs
            self.timer_sequence_normal()
            
        elif self.ui.pfpCheckBox.isChecked(): # if pfp is checked
            self.timer_sequence_pfp() # start pfp 
        else: # otherwise idle
            self.timer_sequence_idle()
        self.ui.pushStartStop.setEnabled(False) # Grey-out the start button
        
    def auxilary_hardware(self):
        """ Autodetect and make communication connections to hardware (Valco,
            valves, Omega temp controllers, Labjack, etc.)
        I believe G. Dutton wrote something like this. There are likely examples
         in the LJM folders as well.
            - M. Gentry """
        #self.valves()  #need to write this class
        # which class? -M. Gentry
        self.t7 = lj.t7_labjack()
       # self.omegas = omega.Omega_iseries() #need to write this class
        
    #def timers(self):
        #self.tmr =repeat_timer.RepeatTimer()
        
    def update_idle(self):
        '''Updates the UI in idle mode. 
        Referenced as 'self.timer.timeout.connect(self.update_normal)'
        in timer_sequence_idle() and timer_sequence_pfp().
        Written by A. Clarke
        Commented by M. Gentry on 09Apr20
        '''
        
        self.ui.timeEdit.setTime(QTime.currentTime()) # sets the UI time to the current time
    
        self.address=0 # perhaps to be used as an analog I/O address 
        ain0_data = self.t7.analog(0) # store output of LJ channel 0
        ain1_data = self.t7.analog(1) # store output of LJ channel 1
    
        # Set UI objects' text using the LJ output
        self.ui.ain0.setText(f'{ain0_data:.1f} ain0')
        self.ui.ain1.setText(f'{ain1_data:.1f} ain1')
    
        # add an 'Idle' entry to the status list
        self.list_entries=[f'{self.tm} Status: Idle']
        model = QtGui.QStandardItemModel()
        self.ui.listView.setModel(model)
        
        # put the list entries into the UI
        for i in self.list_entries:
            item = QtGui.QStandardItem(i)
            model.appendRow(item)
                
    def update_normal(self):
        '''Updates the UI in normal mode.
        Referenced as 'self.timer.timeout.connect(self.update_normal)'
        in timer_sequence_idle() and timer_sequence_pfp().
        Written by A. Clarke
        Commented by M. Gentry on 09Apr20
        '''
        self.ui.timeEdit.setTime(QTime.currentTime()) # sets the UI time to the current time 
        
        # LJ address access, store in variables
        self.address=0
        ain0_data = self.t7.analog(0)
        ain1_data = self.t7.analog(1)
        
        # Update text in the UI
        self.ui.ain0.setText(f'{ain0_data:.1f}')
        self.ui.ain1.setText(f'{ain1_data:.1f}')
        
        # don't add anything extra to the status list
        model = QtGui.QStandardItemModel() # new UI object
        self.ui.listView.setModel(model) # use it for the list graphics
        
        # update the UI according to the status list 'list_entries'
        for i in self.list_entries:
            item = QtGui.QStandardItem(i)
            model.appendRow(item)
    
        
    def timer_sequence_idle(self):
        '''Sequence of timers for the idle mode of operation.
        Written by A. Clarke
        Commented by M. Gentry on 10Apr20'''
        self.sol0_off() # defined below, turns a solenoid off
        self.timer = QtCore.QTimer()  # some other kind of timer
        self.timer.timeout.connect(self.update_idle) 
        self.timer.start(1000)
    
        self.timer1 = QtCore.QTimer()
        self.timer1.timeout.connect(self.dataOut)
        self.timer1.start(1000)
        
        # checking if the the "normal" box has been selected in the GUI?
        self.ui.normalCheckBox.stateChanged.connect(self.waitForStart) 
        
        
    def timer_sequence_normal(self):
        '''
        Timer sequence for running normal flasks.
        In Idle mode, we only need the Qtimer timers to update the GUI. 
        To operate valves we use RepeatTimer from repeat_timer.py. 
        This is why normal mode has RepeatTimer but Idle does not?
        Written by A. Clarke
        Commented by M. Gentry on 10Apr20
        '''
        timers=[] # will hold timers I assume
        
        # add a timer that turns sol0 on
        t = RepeatTimer(30, 60, self.sol0_on) # class defined in repeat_timer.py
        self.timers.append(t) # add that timer to the list
        
        # add a timer 30 seconds out of phase that turns sol1 off
        t = RepeatTimer(0, 60, self.sol0_off)
        self.timers.append(t)

        # start all the timers
        for t in self.timers:
            t.setDaemon(True) # make the timers stop if the main code finishes.
            t.start()
        
        # timers for updating the GUI as in timer_sequence_idle()
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_normal)
        self.timer.start(1000)
        
        self.timer1 = QtCore.QTimer()
        self.timer1.timeout.connect(self.dataOut)
        self.timer1.start(1000)
        
        # but we have a third GUI timer for a new function
        # display_counters()
        self.timer2 = QtCore.QTimer()
        self.timer2.timeout.connect(self.display_counters)
        self.timer2.start(1000)
        
    def timer_sequence_pfp(self):  
        '''Timer sequence for running pfps.
        Written by A. Clarke
        Commented by M. Gentry on 10Apr20'''
        timers=[]
        t = RepeatTimer(0, 10, self.sol0_on)
        timers.append(t)
        
        t = RepeatTimer(5, 10, self.sol0_off)
        timers.append(t)
        input(self.timers)
        for t in self.timers:
            t.setDaemon(True)
            t.start()
        
        # as in idle mode, no display counters for PFP mode...?
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_idle)
        self.timer.start(1000)
        
        self.timer1 = QtCore.QTimer()
        self.timer1.timeout.connect(self.dataOut)
        self.timer1.start(1000) 
        
    def display_counters(self):
        '''
        Updates the time until next start reported in the GUI.
        I'm note sure exactly which value this is.
        Written by A. Clarke
        Commented by M. Gentry on 10Apr20
        '''
        # looks like restarting a counter when it gets close to zero
        if self.start_time <1:
            self.start_time=540
        
        # update the text in the GUI
        self.ui.cryoSecCounter.setText(f'{self.start_time:}')
        self.ui.cryoMinCounter.setText(f'{self.start_time_min:.1f}')
        
        #decrement start time
        self.start_time =self.start_time-1
        self.start_time_min = self.start_time /60.0
        
    def function1():
        '''
        Thanks a bunch for this name.
        Prints out the current GMT
        Looks like a test functions
        Written by A. Clarke
        Commented by M. Gentry on 10Apr20
        '''
        tm = strftime("%Y-%m-%d %H:%M:%S", gmtime())
        print(f'{tm} Hi')
        
    def sol0_on(self):
        '''
        Turns solennoid 0 on. 
        Written by A. Clarke
        Commented by M. Gentry on 09Apr20
        '''
        self.t7.dio_write(0,1) # activates LJ channel 0?
        
        # Update the GUI
        self.ui.pushButton.setStyleSheet("background-color: rgb(255, 0, 255)") # button turns red
        self.ui.pushButton.setText('Valve1 On') # change on/off button text
        self.ui.sol1Button.setChecked(True) # make button look pushed
        self.ui.valve1HorizontalSlider.setValue(99) # slide the slider up to 99
        tm = strftime("%Y-%m-%d %H:%M:%S", gmtime()) # get current GMT
        self.list_entries.append(f'{tm} Solenoid 1 on') # add status to the list
        #model = QtGui.QStandardItemModel()
        #self.ui.listView.setModel(model)

        #for i in self.list_entries:
            #item = QtGui.QStandardItem(i)
            #model.appendRow(item)

        #self.gridLayout.addWidget(self.ui.listView, 1, 0, 1, 2)
        
    def sol0_off(self):
        '''
        Turns solennoid 0 off. 
        Written by A. Clarke
        Commented by M. Gentry on 09Apr20
        '''        
        self.t7.dio_write(0, 0) # deactivates LJ chennel 0?
        
        # UI alterations
        self.ui.pushButton.setStyleSheet("background-color: rgb(0, 200, 200)")
        # make the button green
        self.ui.pushButton.setText('Valve1 Off') # change text
        self.ui.sol1Button.setChecked(False) # uncheck box
        self.ui.valve1HorizontalSlider.setValue(0) #? idk which object this is in the GUI
        tm = strftime("%Y-%m-%d %H:%M:%S", gmtime())# current time GMT
        self.list_entries.append(f'{tm} Solenoid 1 off')# update the status list with time and solenoid off
        ### looks like leftovers from before the update functions
        #model = QtGui.QStandardItemModel()
        #self.ui.listView.setModel(model)
        #for i in self.list_entries:
            #item = QtGui.QStandardItem(i)
            #model.appendRow(item)
        
            
    def dataOut(self):
        '''
        Looks like this if for making fake output.
        However, it updates the GUI directly instead of going through the LJ.
        This means it is only for testing the UI, not the actual operation.
        Written by A. Clarke
        Commented by M. Gentry on 10Apr20
        '''
        v1 = random.normalvariate(20,2) # random numbers
        self.ui.label_15.setText(f'{v1:.1f}') # UI update
        v2 = random.normalvariate(-65,2)
        self.ui.label_17.setText(f'{v2:.1f}')
        v3 = random.normalvariate(705,2)
        self.ui.label_19.setText(f'{v3:.1f}')
        
        
    def appQuit(self, event):
        '''
        Quits the application after checking with the user. 
        Called when the user presses the 'Exit' button. 
        Written by A. Clarke
        Commented and edited by M. Gentry 10Apr20
        '''
        # Create a yes/cancel message box to ask if the user really wants to quit
        reply = QMessageBox.question(
        self, "Message",
        "Are you sure you want to quit?",
        QMessageBox.Yes | QMessageBox.Cancel)

        if reply == QMessageBox.Yes:
            self.close() # close is not defined here 
            # so it must be inherited from QtWidgets.QMainWindow
            sys.exit('Exit Successful') # exits python
        else:
            pass
        
    def editTable(self, event):
        '''
        Saves edits made the to sequence table to sequence.txt when the
        'save edits' button is clicked. 
        Written by A. Clarke
        Commented by M. Gentry 10 Apr20 
        '''
        reply = QMessageBox.question(
        self, "Message",
        "Are you sure you want to change edits?",
        QMessageBox.Yes | QMessageBox.Cancel)
        if reply == QMessageBox.Yes:
            
            # open sequence.txt
            with open('sequence.txt', 'w') as stream:
                writer = csv.writer(stream, lineterminator='\n')
                
                # for each row 
                for row in range(self.ui.sequenceTable.rowCount()):
                    rowdata = [] # make a list
                    # for each column
                    for column in range(self.ui.sequenceTable.columnCount()):
                        # get the corresponding entry of the UI table 'item'
                        item = self.ui.sequenceTable.item(row, column)
                        # if this is an item, 
                        if item is not None:
                            rowdata.append(item.text())
                            
                        else:
                    #stream.write(f"{rowdata[0]},{rowdata[1]},{rowdata[2]}\n")
                            rowdata.append('') # otherwise use empty string
                    writer.writerow(rowdata) # write this row to the file
                    print(rowdata)
        else: 
            pass
        
        def temperature_check(self):
            '''A mock-up function to check the trap temperature and open a 
            valve if it is not below some threshold.
            For now assume all variables are attributes of a class.
            This function would be called as a step in a loop,
            or possibly on a thread.
            For now it uses the one solenoid valve attached to the labjack, 
            in practice, it needs to access whichever valve controls the 
            supply of coolant to the trap.
            Written by M. Gentry on 15May2020'''
            
            ### Check the volaage on the channel responsible for T sensing.
            self.T_address = 0 # for now this is just the 9-volt.
            self.T_threshold = 10.0 # fill value
            ain0_data = self.t7.analog(self.T_address) 
            T = voltage_to_temp(ain0_data)
            # report this temperature to the UI
            if T > self.T_threshold:
                # open the solenoid 
                self.sol0_on()
            else:
                # close the solenoid
                self.sol0_off()
                
                
        
        @staticmethod
        def voltage_to_temp(V):
            ## do some operation, maybe all this is omega.py
            return V
            
            
            
      
    #def ain_out(self):
    
app = QtWidgets.QApplication([])
application = main()
application.show()
sys.exit(app.exec())
