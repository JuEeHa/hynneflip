import enum

class logmessage_types(enum.Enum):
	sent, received, internal = range(3)

class internal_submessage_types(enum.Enum):
	quit, error = range(2)

class controlmessage_types(enum.Enum):
	quit, send_line, ping, ping_timeout = range(4)

class cronmessage_types(enum.Enum):
	quit, schedule, delete, reschedule = range(4)
