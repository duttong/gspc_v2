import time
from threading import Timer, Thread

""" Timer that repeats indefinitely. To stop call the cancel Timer methods.
    Use initial_delay to start the timer later.
"""


class RepeatTimer(Timer):
    def __init__(self, initial_delay, interval, function, *args):
        super().__init__(interval, function, *args)
        self.initial_delay = initial_delay
        print('help')
    def run(self):
        time.sleep(self.initial_delay)
        t = Thread(target=self.function, args=(*self.args,))
        t.setDaemon(True)
        t.start()
        print('here', self.finished.wait(self.interval))
        while not self.finished.wait(self.interval):
            print('going')
            t = Thread(target=self.function, args=(*self.args,))
            t.setDaemon(True)
            t.start()

if __name__ == '__main__':
    def f(x):
        print(x)
        
    timers=[] # will hold timers I assume
    
    # add a timer that turns sol0 on
    t = RepeatTimer(30, 60, f,['hello']) # class defined in repeat_timer.py
    timers.append(t) # add that timer to the list
    
    # add a timer 30 seconds out of phase that turns sol1 off
    t = RepeatTimer(0, 60, f,['goodbye'])
    timers.append(t)

    # start all the timers
    for t in timers:
        t.setDaemon(True) # make the timers stop if the main code finishes.
        t.start() # start() calls run(). Don't call run()
        # run() doesn't create a new thread
        
    time.sleep(120)
        
#    timers = []
#    initial_delay = 5.0   
#    args = ['hello']
#    t = Thread(target=f, args=(*args,))
#    timers.append(t)
#    
#    initial_delay = 0.0
#    args = ['goodbye']
#    t = Thread(target=f, args=(*args,))
#    timers.append(t)
#    
#    for t in timers:
#        t.setDaemon(True)
#        t.start()
#    
#    time.sleep(60)
    