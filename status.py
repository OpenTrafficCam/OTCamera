from datetime import datetime as dt
import config

shutdownactive = False
noblink = False
wifiapon = False
interval_finished = False
more_intervals = True
new_preview = True

current_interval = 0



def record_time():
    current_hour = dt.now().hour
    bytime = current_hour >= config.STARTHOUR and current_hour < config.ENDHOUR

    record = bytime
    record = record and (not shutdownactive)
    # returned true oder false
    return record



if __name__ == "__main__":
    pass

