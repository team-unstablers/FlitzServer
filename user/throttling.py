from rest_framework.throttling import UserRateThrottle


class UserEmailRateThrottle(UserRateThrottle):
    scope = 'user_email'