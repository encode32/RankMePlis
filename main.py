from os.path import dirname, join
from flask import Flask, g, redirect, session, json, render_template, send_file, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_openid import OpenID
import urllib, urllib2
import re,time,string,random

masterkey = "" # Master Key for app API

app = Flask(__name__)
app.config.update(
    SQLALCHEMY_TRACK_MODIFICATIONS = False,
    SQLALCHEMY_DATABASE_URI = 'sqlite:///database.db',
    SECRET_KEY = '', # Steam API SECRET
    DEBUG = False
)

openid = OpenID(app, join(dirname(__file__), 'openid_store'))
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    steam_id = db.Column(db.String(40))
    nickname = db.Column(db.String(80))
    lobby_id = db.Column(db.String(40))
    avatar_url = db.Column(db.String(150))

    @staticmethod
    def get_or_create(steam_id):
        rv = User.query.filter_by(steam_id=steam_id).first()
        if rv is None:
            rv = User()
            rv.steam_id = steam_id
            db.session.add(rv)
        return rv

class Lobby(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lobby_id = db.Column(db.String(40))
    timestamp = db.Column(db.Integer)
    type = db.Column(db.String(40))
    min_rank = db.Column(db.Integer)
    prime = db.Column(db.String(5))
    external = db.Column(db.String(5))

    @staticmethod
    def createorupdate(lobby_id, type, min_rank, prime, external):
        rv = Lobby.query.filter_by(lobby_id=lobby_id).first()
        if rv is None:
            rv = Lobby()
            rv.lobby_id = lobby_id
        rv.timestamp = int(time.time())
        rv.type = type
        rv.min_rank = min_rank
        rv.prime = prime
        rv.external = external
        db.session.add(rv)

    @staticmethod
    def getLobbies(count=5):
        rv = Lobby.query.order_by(Lobby.id.desc()).paginate(1,count)
        return rv

class Api(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip = db.Column(db.String(15))
    api_key = db.Column(db.String(64))
    write = db.Column(db.String(5))

    @staticmethod
    def create(api_key,write):
        rv = Api.query.filter_by(api_key=api_key).first()
        if rv is None:
            rv = Api()
            rv.ip = "None"
            rv.api_key = api_key
            rv.write = write
            db.session.add(rv)
            db.session.commit()

    @staticmethod
    def isAcceptable(api_key,ip):
        rv = Api.query.filter_by(api_key=api_key).first()
        if rv is None:
            return False
        if rv.ip == "None":
            rv.ip = ip
            db.session.add(rv)
            db.session.commit()
            return True
        else:
            if rv.ip == ip:
                return True
        return False

    @staticmethod
    def canbeCreated(api_key):
        rv = Api.query.filter_by(api_key=api_key).first()
        if rv is None:
            return True
        return False

def isInt(s):
    try:
        int(s)
        return True
    except ValueError:
        return False

def json_response(data):
    response = app.response_class(
        response=json.dumps(data),
        status=200,
        mimetype='application/json'
    )
    return response

def api_key_generator(size=64, chars= string.ascii_lowercase + string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

def _timeFromTimestamp(timestamp):
    hours, rem = divmod(time.time() - timestamp, 3600)
    minutes, seconds = divmod(rem, 60)
    time_str = ""
    if hours > 0:
        time_str += (str(int(hours)) + (" hours " if hours > 1 else " hour "))
        return time_str
    if minutes > 0:
        time_str += (str(int(minutes)) + (" minutes " if minutes > 1 else " minute "))
        return time_str
    if seconds > 0:
        time_str += (str(int(seconds)) + (" seconds " if seconds > 1 else " second "))
        return time_str
    return time_str

def _csgoRankToImg(rank):
    if (rank > 0 and rank < 19):
        return "./img/ranks/"+str(rank)+".png"
    else:
        return ""

def _refreshLobbyid():
    steamdata = get_steam_userinfo(g.user.steam_id)
    if 'lobbysteamid' in steamdata:
        lobbysteamid = steamdata['lobbysteamid']
        g.user.lobby_id = lobbysteamid
    else:
        g.user.lobby_id = "None"
    db.session.commit()

_steam_id_re = re.compile('steamcommunity.com/openid/id/(.*?)$')

def get_steam_userinfo(steam_id):
    options = {
        'key': app.secret_key,
        'steamids': steam_id
    }
    url = 'http://api.steampowered.com/ISteamUser/' \
          'GetPlayerSummaries/v0001/?%s' % urllib.urlencode(options)
    rv = json.load(urllib2.urlopen(url))
    return rv['response']['players']['player'][0] or {}

@app.before_request
def before_request():
    g.user = None
    if 'user_id' in session:
        g.user = User.query.filter_by(id=session['user_id']).first()

@app.route("/login")
@openid.loginhandler
def login():
    if g.user is not None:
        return redirect(openid.get_next_url())
    else:
        return openid.try_login("http://steamcommunity.com/openid")

@openid.after_login
def new_user(resp):
    match = _steam_id_re.search(resp.identity_url)
    g.user = User.get_or_create(match.group(1))
    steamdata = get_steam_userinfo(g.user.steam_id)
    g.user.nickname = steamdata['personaname']
    if 'lobbysteamid' in steamdata:
        g.user.lobby_id = steamdata['lobbysteamid']
    else:
        g.user.lobby_id = "None"
    if 'avatar' in steamdata:
        g.user.avatar_url = steamdata['avatar']
    else:
        g.user.avatar_url = "None"

    db.session.commit()
    session['user_id'] = g.user.id
    return redirect(openid.get_next_url())

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(openid.get_next_url())

@app.route('/api/<api_key>/<action>/<value>')
def api(action, api_key, value):
    client_ip = request.remote_addr
    ismaster = False
    if len(api_key) != 64:
        error = {'result': 'error', 'error':'APIKEY not valid'}
        return json_response(error)
    if api_key == masterkey:
        ismaster = True
    if action == "CREATEAPIKEY":
        if ismaster:
            api_keys = []
            print(value)
            for i in range(0,int(value)):
                exit = False
                while(not exit):
                    key = api_key_generator()
                    if Api.canbeCreated(key):
                        api_keys.append(key)
                        Api.create(key,"False")
                        exit = True
            info = {'result' : 'ok', 'api_keys' : api_keys}
            return json_response(info)
        else:
            error = {'result': 'error', 'error':'MASTERKEY needed'}
            return json_response(error)
    if action == "ADDAPIKEY":
        if ismaster:
            if Api.canbeCreated(str(value)):
                Api.create(str(value),"False")
                info = {'result': 'ok', 'info' : 'APIKEY added'}
                return json_response(info)
            else:
                error = {'result': 'error', 'error': 'APIKEY already exist'}
                return json_response(error)
        else:
            error = {'result': 'error', 'error':'MASTERKEY needed'}
            return json_response(error)
    if action == 'GETLOBBIES':
        if ismaster or Api.isAcceptable(api_key, str(client_ip)):
            if isInt(value):
                lobbiescount = int(value)
                if int(value)< 1: lobbiescount = 1
                if int(value) > 50: lobbiescount = 50
                r_lobbies = []
                for lobby in Lobby.getLobbies(lobbiescount).items:
                    if lobby.external == "False":
                        r_lobbydata = {'lobby_id' : lobby.lobby_id, 'type' : lobby.type, 'min_rank' : lobby.min_rank, 'prime' : lobby.prime, 'timestamp' : lobby.timestamp, 'external' : lobby.external}
                        r_lobbies.append(r_lobbydata)
                    else:
                        r_lobbydata = {'lobby_id' : lobby.lobby_id, 'type' : lobby.type, 'timestamp' : lobby.timestamp, 'external' : lobby.external}
                        r_lobbies.append(r_lobbydata)
                info = {'result' : 'ok', 'lobbies' : r_lobbies}
                return json_response(info)
            else:
                error = {'result': 'error', 'error': 'VALUE passed is not integer'}
                return json_response(error)
        else:
            error = {'result': 'error', 'error': 'APIKEY not valid'}
            return json_response(error)
    if action == "ADDLOBBY":
        if ismaster or Api.isAcceptable(api_key,str(client_ip)):
            split_v = str(value).split(';')
            lobby_id = split_v[0]
            type = split_v[1]
            rank = 0
            if isInt(split_v[2]):
                rank = int(split_v[2])
            prime = split_v[3]
            Lobby().createorupdate(lobby_id, type, rank, prime, "False")
            db.session.commit()
            info = {'result': 'ok', 'info': 'Lobby with lobby_id ' + lobby_id + ' added'}
            return json_response(info)

        else:
            error = {'result': 'error', 'error': 'APIKEY not valid'}
            return json_response(error)
    if action == "ADDEXLOBBY":
        if ismaster or Api.isAcceptable(api_key,str(client_ip)):
            split_v = str(value).split(';')
            lobby_id = split_v[0]
            type = split_v[1]
            Lobby().createorupdate(lobby_id, type, 0, "False", "True")
            db.session.commit()
            info = {'result': 'ok', 'info': 'Lobby with lobby_id ' + lobby_id + ' added'}
            return json_response(info)

        else:
            error = {'result': 'error', 'error': 'APIKEY not valid'}
            return json_response(error)

    error = {'result': 'error', 'error':'ACTION not valid'}
    return json_response(error)

@app.route('/api/<api_key>/<action>')
def api2(action, api_key):
    client_ip = request.remote_addr
    ismaster = False
    if len(api_key) != 64:
        error = {'result': 'error', 'error':'APIKEY not valid'}
        return json_response(error)
    if api_key == masterkey:
        ismaster = True
    if action == "GETLASTTICK":
        if ismaster or Api.isAcceptable(api_key,str(client_ip)):
            lobby = Lobby.getLobbies(1).items[0]
            r_lasttick = lobby.timestamp
            info = {'result': 'ok', 'last_tick': r_lasttick}
            return json_response(info)

        else:
            error = {'result': 'error', 'error': 'APIKEY not valid'}
            return json_response(error)

    error = {'result': 'error', 'error':'ACTION not valid'}
    return json_response(error)

@app.route('/favicon.ico')
def favicon():
    return send_file('./favicon.ico', attachment_filename='favicon.ico')

@app.route('/img/steam_login.png')
def steamLoginImg():
    return send_file('./img/steam_login.png', attachment_filename='steam_login.png')

@app.route('/img/ranks/<rank>.png')
def ranks(rank):
    return send_file('./img/ranks/'+rank+".png", attachment_filename='bg.jpg')

@app.route('/img/prime.png')
def prime():
    return send_file('./img/prime.png', attachment_filename='prime.png')

@app.route('/img/steam.png')
def steam():
    return send_file('./img/steam.png', attachment_filename='steam.png')

@app.route('/img/discord.png')
def discord():
    return send_file('./img/discord.png', attachment_filename='discord.png')

@app.route('/img/bg.jpg')
def bg():
    return send_file('./img/bg.jpg', attachment_filename='bg.jpg')

@app.route('/createlobby', methods=['POST'])
def createlobby():
    type = request.form.get('type', "legit")
    rank = request.form.get('rank', "0")
    prime = request.form.get('prime', "off")
    if not g.user:
        return redirect('/')
    _refreshLobbyid()
    if g.user.lobby_id != "None":
        Lobby.createorupdate(g.user.lobby_id,"Rage" if type == "rage" else "Legit",int(rank),"True" if prime == "on" else "False", "False")
        db.session.commit()
        return redirect('/')
    else:
        return redirect('/notinlobby')

@app.route('/notinlobby')
def notinlobby():
    return render_template("notinlobby.html")

@app.route('/')
def hello():
    login = ""

    lobby_data = ""
    form = ""

    for lobby in Lobby.getLobbies().items:
        if lobby.external == "False":
            lobby_data += """
                <ul class="list-group">
                    <li class="lobylist list-group-item">
                        <div class="info text-left">
                            %s Lobby | %s
                        </div>
                        <div class="rank text-left">
                            %s
                        </div>
                        <div class="prime text-left">
                            %s
                        </div>
                        <div class="join text-right">
                            <a href="steam://joinlobby/730/%s" class="btn btn-success" role="button">JOIN</a>
                        </div>
                    </li>
                </ul>""" % (
                lobby.type, _timeFromTimestamp(lobby.timestamp)+ " ago", "<img class='ranks' src='"+_csgoRankToImg(
                    lobby.min_rank)+"'>" if lobby.min_rank != 0 else "Unranked",
                "<img class='prime_logo' src='./img/prime.png'>" if "True" in lobby.prime else "", lobby.lobby_id)
        else:
            lobby_data += """
                <ul class="list-group">
                    <li class="lobylistexternal list-group-item">
                        <div class="info text-left">
                            %s Lobby | %s
                        </div>
                        <div class="join text-right">
                            <a href="steam://joinlobby/730/%s" class="btn btn-success" role="button">JOIN</a>
                        </div>
                    </li>
                </ul>""" % (
                lobby.type, _timeFromTimestamp(lobby.timestamp) + " ago", lobby.lobby_id)
    if g.user:
        _refreshLobbyid()
        login = """
                <li class="avatar"><a href='http://steamcommunity.com/profiles/%s'><img src='%s'></a></li>
                <li class="dropdown">
                    <a class="dropdown-toggle" data-toggle="dropdown" href="#">%s
                    <span class="caret"></span></a>
                    <ul class="dropdown-menu">
                        <li><a href="/logout">Logout</a></li>
                    </ul>
                </li>""" % (
        g.user.steam_id, g.user.avatar_url, g.user.nickname)

        form = """
                <ul class="list-group">
                    <li class="formlist list-group-item">
                        <form action="createlobby" method="post">
                          <div class="form-group">
                            <select name="type" class="form-control" id="sel1">
                              <option value="legit">Legit</option>
                              <option value="rage">Rage</option>
                            </select>
                          </div>
                          <div class="form-group">
                            <select name="rank" class="form-control" id="sel1">
                              <option value="0">Unranked</option>
                              <option value="1">SI</option>
                              <option value="2">SII</option>
                              <option value="3">SIII</option>
                              <option value="4">SIV</option>
                              <option value="5">SE</option>
                              <option value="6">SEM</option>
                              <option value="7">GNI</option>
                              <option value="8">GNII</option>
                              <option value="9">GNIII</option>
                              <option value="10">GNM</option>
                              <option value="11">MGI</option>
                              <option value="12">MGII</option>
                              <option value="13">MGE</option>
                              <option value="14">DMG</option>
                              <option value="15">LE</option>
                              <option value="16">LEM</option>
                              <option value="17">SMFC</option>
                              <option value="18">GE</option>
                            </select>
                          </div>
                          <div class="checkbox">
                            <label><input name="prime" type="checkbox"> Prime</label>
                          </div>
                          <button type="submit" class="btn btn-success text-right">Submit</button>
                        </form>
                    </li>
                </ul>"""
    else:
        login = "                <a href='/login'><img id='steam_login_img' src='./img/steam_login.png'></a>"

    data = {'login' : login, 'form' : form, 'lobby_data' : lobby_data}

    return render_template('index.html', data=data)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8888)
