from collections import namedtuple
from datetime import datetime
from ..clock import Time
from ..messages import AskForVolunteeringNotification, VolunteeringReminderNotification


NudgesParams = namedtuple('NudgesParams', 'volunteers now urls message_users_seen_no_later_than_days')


class ChoreEvent(object):
    def __init__(self, chore, ts):
        self.chore = chore
        self.ts = ts

    def get_object_key(self):
        return {
            'chore_id': self.chore.chore_id,
            'ts': self.ts.as_int_timestamp(),
        }

    def for_json(self):
        return {
            'chore': self.chore.for_json(),
            'when': {
                'timestamp': self.ts.as_int_timestamp(),
                'human_str': self.ts.human_str(),
            }
        }

    def iter_nudges(self, params):
        for reminder in self.chore.reminders:
            for nudge in reminder.iter_nudges(self, params):
                yield nudge


class BasicChore(object):
    def __init__(self, chore_id, name, description, min_required_people, first_tuesday, reminders):
        self.chore_id = chore_id
        self.name = name
        self.description = description
        self.min_required_people = min_required_people
        self.first_tuesday = Time.from_datetime(datetime.strptime(first_tuesday, '%d/%m/%Y %H:%M'))
        self.reminders = [build_reminder(self.min_required_people, **reminder) for reminder in reminders]

    # Once every other week
    def iter_events_from_to(self, ts_from, ts_to):
        ts = self.first_tuesday
        while ts <= ts_to:
            if ts >= ts_from:
                yield ChoreEvent(self, ts)
            ts = ts.add(14, 'days')

    def for_json(self):
        return {
            'chore_id': self.chore_id,
            'name': self.name,
            'description': self.description,
            'min_required_people': self.min_required_people,
        }

    def get_num_days_of_earliest_reminder(self):
        return max([0] + [reminder.when['days_before'] for reminder in self.reminders])


ALL_CHORE_TYPES = [
    BasicChore,
]


class EmailNudge(object):
    def __init__(self, event, nudge_key, destination, subject, body):
        self.event = event
        self.nudge_key = nudge_key
        self.destination = destination
        self.subject = subject
        self.body = body

    def get_string_key(self):
        event_key = self.event.get_object_key()
        return '{0}-{1}-{2}'.format(self.nudge_key, event_key['chore_id'], event_key['ts'])

    def send(self, aggregator, logger):
        aggregator.email_adapter.send_email(self.destination, self.destination, self, logger)

    # Honour the Message API (see messages.py)
    def get_subject_for_email(self):
        return self.subject

    # Honour the Message API (see messages.py)
    def get_email_text(self):
        return self.body


class VolunteerViaChatBotNudge(object):
    def __init__(self, event, nudge, params):
        self.event = event
        self.nudge = nudge
        self.message_users_seen_no_later_than_days = params.message_users_seen_no_later_than_days

    def get_string_key(self):
        event_key = self.event.get_object_key()
        return '{0}-{1}-{2}'.format(self.nudge['nudge_key'], event_key['chore_id'], event_key['ts'])

    def send(self, aggregator, logger):
        users = aggregator.get_users_seen_no_later_than_days(self.message_users_seen_no_later_than_days, logger)
        for user in users:
            aggregator.send_user_notification(user, AskForVolunteeringNotification(user, self.event), logger)


class VolunteerReminderViaChatBotNudge(object):
    def __init__(self, event, params):
        self.event = event
        self.volunteers = params.volunteers

    def get_string_key(self):
        event_key = self.event.get_object_key()
        return 'volunteer-reminder-{0}-{1}'.format(event_key['chore_id'], event_key['ts'])

    def send(self, aggregator, logger):
        for user in self.volunteers:
            aggregator.send_user_notification(user, VolunteeringReminderNotification(user, self.event), logger)


class MissingVolunteersReminder(object):
    def __init__(self, min_required_people, when, nudges):
        self.min_required_people = min_required_people
        self.when = when
        self.nudges = nudges

    def iter_nudges(self, event, params):
        reminder_time = calculate_reminder_time(event, self.when)
        if params.now > reminder_time and len(params.volunteers) < self.min_required_people:
            for nudge in self.nudges:
                if nudge['nudge_type'] == 'email':
                    yield self._buildEmailNudge(event, nudge, params)
                if nudge['nudge_type'] == 'volunteer_via_chat_bot':
                    yield VolunteerViaChatBotNudge(event, nudge, params)

    def _buildEmailNudge(self, event, nudge, params):
        template_data = {
            'event_day': event.ts.strftime('%a %d/%m/%Y %H:%M'),
            'chore_description': event.chore.description,
            'num_volunteers_needed': self.min_required_people - len(params.volunteers),
            'signup_url': params.urls.chores(),
        }
        return EmailNudge(
            event=event,
            nudge_key=nudge['nudge_key'],
            destination=nudge['destination'],
            subject=nudge['subject_template'].format(**template_data),
            body=nudge['body_template'].format(**template_data),
        )


class VolunteersReminder(object):
    def __init__(self, when):
        self.when = when

    def iter_nudges(self, event, params):
        reminder_time = calculate_reminder_time(event, self.when)
        if params.now > reminder_time:
            yield VolunteerReminderViaChatBotNudge(event, params)


class ChoresLogic(object):
    def __init__(self, chores):
        self.chores = [build_chore_instance(chore) for chore in chores]

    def get_events_from_to(self, ts_from, ts_to):
        events = []
        for chore in self.chores:
            events.extend(chore.iter_events_from_to(ts_from, ts_to))
        events.sort(key = lambda c: c.ts)
        return events

    def iter_events_with_reminders_from_to(self, ts_from, ts_to):
        num_days_of_earliest_reminder = max([0] + [chore.get_num_days_of_earliest_reminder() for chore in self.chores])
        for event in self.get_events_from_to(ts_from, ts_to.add(num_days_of_earliest_reminder + 1, 'days')):
            for reminder in event.chore.reminders:
                reminder_time = calculate_reminder_time(event, reminder.when)
                if ts_from <= reminder_time <= ts_to:
                    yield event


# -- Utility functions ----


def get_chore_type_class(chore):
    for chore_class in ALL_CHORE_TYPES:
        if chore_class.__name__ == chore.class_type:
            return chore_class
    raise Exception(f'Cannot find Python class for chore of type "{chore.class_type}"')


def build_chore_instance(chore):
    chore_class = get_chore_type_class(chore)
    return chore_class(chore.chore_id, chore.name, chore.description, **chore.configuration)


def build_reminder(min_required_people, reminder_type, when, nudges=None):
    if reminder_type == 'missing_volunteers':
        return MissingVolunteersReminder(min_required_people, when, nudges)
    if reminder_type == 'volunteers_who_signed_up':
        return VolunteersReminder(when)
    raise Exception(f'Unknown reminder type {repr(reminder_type)}')


def parse_hhmm(hhmm_str):
    hh, mm = hhmm_str.split(':')
    return int(hh), int(mm)


def calculate_reminder_time(event, when):
    hh, mm = parse_hhmm(when['time'])
    reminder_time = event.ts.add(-when['days_before'], 'days').replace(hour=hh, minute=mm)
    return reminder_time
