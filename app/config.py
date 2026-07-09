import os


SOURCE_REDIS_URL = os.getenv("SOURCE_REDIS_URL", "redis://10.192.202.210:6379/0")
HISTORY_REDIS_URL = os.getenv("HISTORY_REDIS_URL", "redis://10.192.202.210:6379/1")

SOURCE_VOTING_RESULT_KEY = os.getenv("SOURCE_VOTING_RESULT_KEY", "voting_result")
HISTORY_VOTE_KEY = os.getenv("HISTORY_VOTE_KEY", "vote_history")
HISTORY_ATTENDANCE_KEY = os.getenv("HISTORY_ATTENDANCE_KEY", "attendance_history")
ACTIVE_VOTE_KEY = os.getenv("ACTIVE_VOTE_KEY", "vote_history_active")
ACTIVE_ATTENDANCE_KEY = os.getenv("ACTIVE_ATTENDANCE_KEY", "attendance_history_active")
DELEGATE_DIRECTORY_KEY = os.getenv("DELEGATE_DIRECTORY_KEY", "delegate_directory")
MONITOR_CHANNEL = os.getenv("MONITOR_CHANNEL", "voting_monitor_channel_6")
