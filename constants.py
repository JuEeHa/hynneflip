import enum

class logmessage_types(enum.Enum):
	sent, received, internal = range(3)

class internal_submessage_types(enum.Enum):
	quit, error = range(2)

class controlmessage_types(enum.Enum):
	quit, send_line = range(2)
