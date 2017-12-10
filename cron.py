import select
import threading
import time
from collections import namedtuple

import channel
from constants import cronmessage_types

# time field uses the monotonic time returned by time.monotonic()
Event = namedtuple('Event', ['time', 'channel', 'message'])

class CronThread(threading.Thread):
	def __init__(self, cron_control_channel):
		self.cron_control_channel = cron_control_channel

		# Sorted array of events
		self.events = []

		threading.Thread.__init__(self)

	def get_timeout_value(self):
		if len(self.events) == 0:
			# No events, block until we get a message
			# Timeout of -1 makes poll block indefinitely
			return -1

		else:
			# First event in the array is always the earliest
			seconds_to_wait = self.events[0].time - time.monotonic()

			# time.monotonic() uses fractional second but poll uses milliseconds, convert
			ms_to_wait = int(seconds_to_wait * 1000)

			# In case we somehow took long enough that next one should be run by now, make it run now
			if ms_to_wait < 0:
				ms_to_wait = 0

			return ms_to_wait

	def run_events(self):
		assert len(self.events) > 0

		current_time = time.monotonic()

		# Look for first event that should be run after current time, and split the array there
		# index should point at the first to be after current time, or at end of array
		# Either way, we can split the array at that location, first part being what to run and second rest
		index = 0
		while index < len(self.events):
			if self.events[index].time > current_time:
				break
			index += 1

		# Split array
		to_run = self.events[:index]
		self.events = self.events[index:]

		# Run events
		for event in to_run:
			event.channel.send(event.message)

	def add_event(self, event):
		# Look for first event that should be run after event, and split the array there
		# index should point at the first to be after event, or at end of array
		# Either way, we can split the array at that location safely
		index = 0
		while index < len(self.events):
			if self.events[index].time > event.time:
				break
			index += 1

		self.events = self.events[:index] + [event] + self.events[index:]

	def delete_event(self, event):
		# Try to find the element with same channel and message
		index = 0
		while index < len(self.events):
			if self.events[index].channel == event.channel and self.events[index].message == event.message:
				break
			index += 1

		if index < len(self.events):
			# The event at index is the one we need to delete
			self.events = self.events[:index] + self.events[index + 1:]

	def reschedule_event(self, event):
		self.delete_event(event)
		self.add_event(event)

	def run(self):
		# Create poll object and register the control channel
		# The poll object is used to implement both waiting and control of the cron thread
		poll = select.poll()
		poll.register(self.cron_control_channel, select.POLLIN)

		while True:
			timeout = self.get_timeout_value()
			poll_result = poll.poll(timeout)

			if len(poll_result) == 0:
				# No fds were ready → we timed out. Time to run some events
				self.run_events()

			else:
				# New message was received, handle it
				command_type, *arguments = self.cron_control_channel.recv()

				if command_type == cronmessage_types.quit:
					break

				elif command_type == cronmessage_types.schedule:
					event, = arguments
					self.add_event(event)

				elif command_type == cronmessage_types.delete:
					event, = arguments
					self.delete_event(event)

				elif command_type == cronmessage_types.reschedule:
					event, = arguments
					self.reschedule_event(event)

				else:
					assert False #unreachable

def start():
	cron_control_channel = channel.Channel()
	CronThread(cron_control_channel).start()
	return cron_control_channel

def quit(cron_control_channel):
	"""Stop the cron instance"""
	cron_control_channel.send((cronmessage_types.quit,))

def schedule(cron_control_channel, seconds, channel, message):
	"""Schedules message to be send to channel"""
	event = Event(time.monotonic() + seconds, channel, message)
	cron_control_channel.send((cronmessage_types.schedule, event))

def delete(cron_control_channel, channel, message):
	"""Remove an event. If event is not found, this is a no-op.
	Matches events based on channel and message, and only applies to the earlier one found."""
	event = Event(None, channel, message)
	cron_control_channel.send((cronmessage_types.delete, event))

def reschedule(cron_control_channel, seconds, channel, message):
	"""Reschedules message to be send to channel. If event is not found, a new one is created.
	Matches events based on channel and message, and only applies to the earlier one found."""
	event = Event(time.monotonic() + seconds, channel, message)
	cron_control_channel.send((cronmessage_types.reschedule, event))
