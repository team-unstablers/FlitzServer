from django.utils import timezone
from timezonefinder import TimezoneFinder

import pytz

tf = TimezoneFinder()

def get_timezone_from_coordinates(latitude, longitude) -> pytz.timezone:
    """위도/경도로부터 시간대를 결정합니다."""
    timezone_str = tf.timezone_at(lat=latitude, lng=longitude)
    if timezone_str:
        return pytz.timezone(timezone_str)
    return pytz.UTC  # 기본값으로 UTC 반환

def get_today_start_in_timezone(tz):
    """특정 시간대의 '오늘' 시작 시간을 계산합니다."""
    now = timezone.now()
    local_time = now.astimezone(tz)
    today_start = local_time.replace(hour=0, minute=0, second=0, microsecond=0)
    return today_start

