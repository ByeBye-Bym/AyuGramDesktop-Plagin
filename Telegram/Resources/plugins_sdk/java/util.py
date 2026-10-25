# java.util.Calendar on top of local-time datetime.

import datetime


class Calendar:
    YEAR = 1
    MONTH = 2
    DAY_OF_MONTH = 5
    DATE = 5
    HOUR_OF_DAY = 11
    MINUTE = 12
    SECOND = 13
    MILLISECOND = 14

    _ATTRS = {
        YEAR: "year",
        DAY_OF_MONTH: "day",
        HOUR_OF_DAY: "hour",
        MINUTE: "minute",
        SECOND: "second",
    }

    def __init__(self):
        self._dt = datetime.datetime.now()

    @staticmethod
    def getInstance(*args):
        return Calendar()

    def setTimeInMillis(self, millis):
        self._dt = datetime.datetime.fromtimestamp(int(millis) / 1000)

    def getTimeInMillis(self):
        return int(self._dt.timestamp() * 1000)

    def get(self, field):
        if field == Calendar.MONTH:
            return self._dt.month - 1  # Java months are zero-based
        if field == Calendar.MILLISECOND:
            return self._dt.microsecond // 1000
        return getattr(self._dt, Calendar._ATTRS[field])

    def set(self, field, value):
        if field == Calendar.MONTH:
            self._dt = self._dt.replace(month=int(value) + 1)
        elif field == Calendar.MILLISECOND:
            self._dt = self._dt.replace(microsecond=int(value) * 1000)
        else:
            self._dt = self._dt.replace(**{Calendar._ATTRS[field]: int(value)})
