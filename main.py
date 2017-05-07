import logging
import mysql.connector
import os
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, Job, MessageHandler, Filters, CallbackQueryHandler, JobQueue

import parser


class UserChat:
    def __init__(self, chat_id, bot):
        self.id = chat_id
        self.state = 'init'
        self.login_data = None
        self.games_to_move = 0
        # todo change # of games to move check to last update check
        self.bot = bot
        query = "SELECT * FROM users WHERE chat_id=%d" % chat_id
        self.bot.cursor.execute(query)
        if self.bot.cursor.rowcount==0:
            # no such user
            query = "INSERT INTO users (chat_id) VALUES (%d)" % chat_id
            self.bot.cursor.execute(query)
            self.bot.cnx.commit()
            self.watching = 0
        else:
            data = self.bot.cursor.fetchone()
            self.login_data = data[2:4]
            self.watching = data[4]

    def save_login_data(self):
        query = 'UPDATE users SET login="%s", password="%s" WHERE chat_id=%d' % tuple(self.login_data+[self.id])
        self.bot.cursor.execute(query)
        self.bot.cnx.commit()

    def set_watching(self, state):
        query = "UPDATE users SET watching=%d WHERE chat_id=%d" % (state,self.id)
        self.bot.cursor.execute(query)
        self.bot.cnx.commit()

class Bot:
    def __init__(self):
        self.updater = Updater(os.environ['APP_TOKEN'])
        self.dispatcher = self.updater.dispatcher
        self._bot = self.dispatcher.bot

        logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                            level=logging.INFO)

        self.users = {}
        db_conn_string = os.environ['JAWSDB_URL'] if 'JAWSDB_URL' in os.environ else os.environ['DATABASE_URL']
        user, password, host, port, database = re.match('mysql://(.*?):(.*?)@(.*?):(.*?)/(.*)', db_conn_string).groups()
        self.cnx = mysql.connector.connect(
            user=user, password=password,
            host=host, port=port, database=database)
        self.cursor = self.cnx.cursor(buffered=True)

        # restart users watchers
        query = "SELECT * FROM users WHERE watching=1"
        self.cursor.execute(query)
        for row in self.cursor:
            self.users[row[1]] = UserChat(row[1], self)
            self.check_start(self._bot, row[1])
            # todo distributed in time checks

        self.logger = logging.getLogger(__name__)

        self.start_inline_keyboard = [[
                InlineKeyboardButton(text='Check login', callback_data='check_login'),
                InlineKeyboardButton(text='Update login data', callback_data='login')
            ], [
                InlineKeyboardButton(text='Start watching', callback_data='watch')
            ]]


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
        self.users[update.message.chat_id] = UserChat(update.message.chat_id, self)
        login_data = self.get_login_data(update.message.chat_id)
        if not login_data[0]:
            inline_keyboard = [[
                InlineKeyboardButton(text='Set login data', callback_data='login')
            ]]
        else:
            inline_keyboard = self.start_inline_keyboard

        update.message.reply_text('Ok, lets go!',
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
            self.users[update.message.chat_id].save_login_data()
            update.message.reply_text('Your login data saved',
                                      reply_markup=InlineKeyboardMarkup(self.start_inline_keyboard) )
            self.users[update.message.chat_id].state = 'start'

    def check_login(self, bot, chat_id):
        if parser.check_login(self.get_login_data(chat_id)):
            bot.sendMessage(chat_id, 'It works')
        else:
            bot.sendMessage(chat_id, 'Something went wrong')

    def check_start(self, bot, chat_id):
        job_queue = JobQueue(bot)
        job_queue.start()
        self.users[chat_id].set_watching(True)
        job_alarm = Job(self.check, 180.0, context=chat_id)
        job_queue.put(job_alarm, next_t=0)

    def check(self, bot, job):
        my_turn_games = parser.check(self.users[job.context].login_data)
        if my_turn_games > 0:
            if self.users[job.context].games_to_move != my_turn_games:
                bot.sendMessage(chat_id=job.context, text='%d games to make move' % my_turn_games)
        self.users[job.context].games_to_move = my_turn_games

b = Bot()