from datetime import  timedelta
INTERVAL_MINUTES = 10  # Интервал записи (10 минут)

class Logger:
    def getNextLogTime(self, current_time):
        next_time = current_time.replace(second=0, microsecond=0) + \
                    timedelta(minutes=INTERVAL_MINUTES - (current_time.minute % INTERVAL_MINUTES))
        return next_time