import logging
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, Job, MessageHandler, Filters, CallbackQueryHandler, JobQueue

import parser

class UserChat:
    def __init__(self, chat_id):
        self.id = chat_id
        self.state = 'init'
        self.login_data = None
        self.games_to_move = 0
        # todo change # of games to move check to last update check

class Bot:
    def __init__(self):
        self.updater = Updater(os.environ['APP_TOKEN'])
        self.dispatcher = self.updater.dispatcher

        logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                            level=logging.INFO)

        self.users = {}

        self.logger = logging.getLogger(__name__)

        self.dispatcher.add_error_handler(self.error)
        self.dispatcher.add_handler(MessageHandler(Filters.text, self.reply_to_query))
        self.dispatcher.add_handler(CallbackQueryHandler(self.buttons_callback))
        self.dispatcher.add_handler(CommandHandler('start', self.start))
        self.dispatcher.add_handler(CommandHandler('login', self.login_start))

        self.updater.start_polling()
        self.updater.idle()

    def error(self, bot, update, error):
        self.logger.warn('Update "%s" caused error "%s"' % (update, error))

    def get_login_data(self, chat_id):
        return self.users[chat_id].login_data

    def start(self, bot, update):
        if update.message.chat_id not in self.users:
            self.users[update.message.chat_id] = UserChat(update.message.chat_id)
        login_data = self.get_login_data(update.message.chat_id)
        if not login_data:
            inline_keyboard = [[
                InlineKeyboardButton(text='Set login data', callback_data='login')
            ]]

            bot.sendMessage(
                update.message.chat_id,
                'Ok, lets go!',
                reply_markup=InlineKeyboardMarkup(inline_keyboard))

        self.users[update.message.chat_id].state = 'start'

    def buttons_callback(self, bot, update):
        #self.last_message.edit_reply_markup(reply_markup=[])
        data = update.callback_query.data
        if data=='login':
            self.login_start(bot, update.callback_query.from_user.id)
        elif data=='check_login':
            self.check_login(bot, update.callback_query.from_user.id)
        elif data=='watch':
            self.check_start(bot, update.callback_query.from_user.id)

    def login_start(self, bot, chat_id):
        self.users[chat_id].login_data = []
        bot.sendMessage(chat_id, 'Print your login')
        self.users[chat_id].state = 'login'

    def reply_to_query(self, bot, update):
        if self.users[update.message.chat_id].state=='login':
            self.users[update.message.chat_id].login_data.append(update.message.text)
            update.message.reply_text('Print your password')
            self.users[update.message.chat_id].state = 'password'
        elif self.users[update.message.chat_id].state=='password':
            self.users[update.message.chat_id].login_data.append(update.message.text)
            inline_keyboard = [[
                InlineKeyboardButton(text='Check login', callback_data='check_login'),
                InlineKeyboardButton(text='Update login data', callback_data='login')
            ], [
                InlineKeyboardButton(text='Start watching', callback_data='watch')
            ]]
            update.message.reply_text('Your login data saved',
                                      reply_markup=InlineKeyboardMarkup(inline_keyboard) )
            self.users[update.message.chat_id].state = 'init'

    def check_login(self, bot, chat_id):
        if parser.check_login(self.get_login_data(chat_id)):
            bot.sendMessage(chat_id, 'It works')
        else:
            bot.sendMessage(chat_id, 'Something went wrong')

    def check_start(self, bot, chat_id):
        job_queue = JobQueue(bot)
        job_queue.start()
        job_alarm = Job(self.check, 180.0, context=chat_id)
        job_queue.put(job_alarm, next_t=0)

    def check(self, bot, job):
        my_turn_games = parser.check(self.users[job.context].login_data)
        if my_turn_games > 0:
            if self.users[job.context].games_to_move != my_turn_games:
                bot.sendMessage(chat_id=job.context, text='%d games to make move' % my_turn_games)
        self.users[job.context].games_to_move = my_turn_games

b = Bot()