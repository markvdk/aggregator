from collections import namedtuple

# -- BOT Commands ----

Command = namedtuple('Command', 'text description')


COMMAND_WHO = Command('who', 'Show the last checkins at the Space')
COMMAND_HELP = Command('help', 'Show the available commands')
COMMAND_OUT = Command('out', 'Check-out of the Space')
COMMAND_CHECKIN = Command('checkin', 'Check-in to the Space')

BASIC_COMMANDS = (COMMAND_WHO, COMMAND_HELP, COMMAND_OUT)

COMMAND_YES = Command('yes', 'Yes')
COMMAND_NO = Command('no', 'No')
YES_NO_COMMANDS = (COMMAND_YES, COMMAND_NO)


# -- Messages ----

CR = '\n'


class BaseBotMessage(object):
    next_commands = BASIC_COMMANDS
    message = ''

    def get_markdown(self):
        return self.get_text()

    def get_text(self):
        return self.message

    def get_email_text(self):
        return self.get_text()

    def get_subject_for_email(self):
        return f'Notification <{self.__class__.__name__}>'


class MessageNotRegistered(BaseBotMessage):
    message = (
        "Hi! I'm the MakerSpace Leiden BOT.\n"
        "In order to interact with me you must first connect your CRM account.\n"
        "You can do that from the your Your Data page, in the Notification Settings."
    )


class MessageWho(BaseBotMessage):
    def __init__(self, user, space_status):
        self.user = user
        self.space_status = space_status

    def get_text(self):
        return (
            f'''{self.user.first_name}, the space is marked as {'OPEN' if self.space_status["space_open"] or True else "closed"}.\n'''
            f"Latest checkins today:\n"
            f"{CR.join(' - {0} ({1} - {2})'.format(user_data['user']['full_name'], user_data['ts_checkin_human'], user_data['ts_checkin']) for user_data in self.space_status['users_in_space'])}"
        )


class MessageUnknown(BaseBotMessage):
    def __init__(self, user):
        self.user = user

    def get_text(self):
        return f"Sorry {self.user.first_name}, I don't understand that command. Try \"help\"."


class MessageHelp(BaseBotMessage):
    def __init__(self, user, commands):
        self.user = user
        self.commands = commands

    def get_text(self):
        commands_text = '\n'.join(f'{command.text} - {command.description}' for command in self.commands)
        return (
            f"Hello {self.user.first_name}! I'm the MakerSpace Leiden BOT.\n"
            "I try to help where I can, reminding people to turn off machines, and stuff like that.\n"
            f'These are the commands you can type:\n{commands_text}'
        )


class MessageUserNotInSpace(BaseBotMessage):
    def __init__(self, user):
        self.user = user

    def get_text(self):
        return f"{self.user.first_name}, it doesn't look like you are in the space in this moment."


class MessageConfirmCheckout(BaseBotMessage):
    next_commands = YES_NO_COMMANDS

    def __init__(self, user, ts_checkin):
        self.user = user
        self.ts_checkin = ts_checkin

    def get_text(self):
        return f"So, {self.user.first_name}, it looks like you checked into the Space at {self.ts_checkin.human_str()}.\nDo you want to check-out now?"


class MessageConfirmedCheckout(BaseBotMessage):
    def __init__(self, user):
        self.user = user

    def get_text(self):
        return f"Ok {self.user.first_name}, you are now checked out of the Space."


class MessageCancelAction(BaseBotMessage):
    message = 'Ok, never mind.'


# -- Notifications ----


class StaleCheckoutNotification(BaseBotMessage):
    def __init__(self, ts_checkin):
        self.ts_checkin = ts_checkin

    def get_text(self):
        return f'Did you forget to checkout yesterday?\nYou entered the Space at {self.ts_checkin.human_str()}'


class MachineLeftOnNotification(BaseBotMessage):
    def __init__(self, machine):
        self.machine = machine

    def get_text(self):
        return f"You forgot to press the red button on the {self.machine.name}! But don't worry: it turned off automatically. Just don't forget next time. ;-)"


class TestNotification(BaseBotMessage):
    def __init__(self, user):
        self.user = user

    def get_text(self):
        return f"Hello {self.user.first_name}! This is a test notification from your friendly MakerSpace BOT. You can safely ignore it. Cheers!"

    def get_email_text(self):
        return (
            f"Hello {self.user.first_name}!\n\n"
            "This is a test notification from your friendly MakerSpace BOT.\n"
            "You can safely ignore it.\n\n"
            "Cheers!\n"
            "The MakerSpace BOT"
        )

    def get_subject_for_email(self):
        return 'Test notification'
