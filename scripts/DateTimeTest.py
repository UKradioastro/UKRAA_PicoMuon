from datetime import datetime, timedelta

DateText = '2024-05-18'
y = datetime.strptime(DateText, '%Y-%m-%d')
print(y)
print(type(y))

TimeText = '15:17:34.123456'
z = datetime.strptime(TimeText, '%H:%M:%S.%f')
print(z)
print(type(z))

DateTimeText = '2024-05-18 15:17:34.123456'
x = datetime.strptime(DateTimeText, '%Y-%m-%d %H:%M:%S.%f')
print(x)
print(type(x))
