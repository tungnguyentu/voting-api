import os


SOURCE_REDIS_URL = os.getenv("SOURCE_REDIS_URL", "redis://10.192.202.210:6379/0")
HISTORY_REDIS_URL = os.getenv("HISTORY_REDIS_URL", "redis://10.192.202.210:6379/1")

SOURCE_VOTING_RESULT_KEY = os.getenv("SOURCE_VOTING_RESULT_KEY", "voting_result")
HISTORY_VOTE_KEY = os.getenv("HISTORY_VOTE_KEY", "vote_history")
HISTORY_ATTENDANCE_KEY = os.getenv("HISTORY_ATTENDANCE_KEY", "attendance_history")
HISTORY_DISCUSS_KEY = os.getenv("HISTORY_DISCUSS_KEY", "discuss_history")
ACTIVE_VOTE_KEY = os.getenv("ACTIVE_VOTE_KEY", "vote_history_active")
ACTIVE_ATTENDANCE_KEY = os.getenv("ACTIVE_ATTENDANCE_KEY", "attendance_history_active")
ACTIVE_DISCUSS_KEY = os.getenv("ACTIVE_DISCUSS_KEY", "discuss_history_active")
DELEGATE_DIRECTORY_KEY = os.getenv("DELEGATE_DIRECTORY_KEY", "delegate_directory")
MONITOR_CHANNEL = os.getenv("MONITOR_CHANNEL", "voting_monitor_channel_6")

_DEFAULT_CORS_ORIGINS = (
    "https://ihdnd.hanoi.gov.vn,"
    "http://ihdnd.hanoi.gov.vn,"
    "http://10.10.98.186,"
    "https://10.10.98.186"
)
CORS_ALLOW_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOW_ORIGINS", _DEFAULT_CORS_ORIGINS).split(",")
    if origin.strip()
]
