from bs4 import BeautifulSoup

import mechanize
import cookielib

def check_login(data):
    cj = cookielib.CookieJar()
    br = mechanize.Browser()
    br.set_handle_robots(False)
    br.set_cookiejar(cj)
    br.open("http://www.boiteajeux.net")

    br.select_form(nr=0)
    br.form['username'] = data[0]
    br.form['password'] = data[1]
    br.submit()

    html = br.response().read()
    soup = BeautifulSoup(html, 'lxml')
    games_list = soup.find('div', id='dvEnCours')
    return True if games_list else False

def check(data):
    cj = cookielib.CookieJar()
    br = mechanize.Browser()
    br.set_handle_robots(False)
    br.set_cookiejar(cj)
    br.open("http://www.boiteajeux.net")

    br.select_form(nr=0)
    br.form['username'] = data[0]
    br.form['password'] = data[1]
    br.submit()

    html = br.response().read()
    soup = BeautifulSoup(html, 'lxml')
    games_list = soup.find('div',id='dvEnCours')
    my_turn_games = []
    for row in games_list.find_all('div',recursive=False):
        if row['class'][0].startswith('clLigne'):
            # lines with games
            span = row.find('a').find('span')
            if span:
                # span with red color = your turn
                my_turn_games.append(span.text)
    return len(my_turn_games)
