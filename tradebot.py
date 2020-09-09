import requests
import json
import re
import time
import asyncio
import os

base_url = "https://www.myfantasyleague.com/"

franchises_dict_g = {}
players_dict_g = {}
timestamp_g = 0
league_id_g = ""
groupme_bot_id_g = ""
year_g = "2020"
mfl_user_agent_g = ""
chat_api_list_g = []
rosters_json_g = None

def current_unix_timestamp():
    return int(time.time())

def remove_html_from_string(s):
    clean = re.compile('<.*?>')
    return re.sub(clean, '', s)

def https_request(url):
    headers = {
        'User-Agent': mfl_user_agent_g
    }

    resp = requests.get(url, headers=headers)
    return resp.text

def get_rosters():
    global rosters_json_g
    s = base_url + year_g + "/export?TYPE=rosters&L=" + league_id_g + "&JSON=1"
    print("requesting: " + s)
    rosters_json_g = json.loads(https_request(s))


def get_trades():
    s = base_url + year_g + "/export?TYPE=transactions&TRANS_TYPE=TRADE&DAYS=7&L=" + league_id_g + "&JSON=1"
    trades_json = https_request(s)
    return trades_json

def get_league():
    s = base_url + year_g + "/export?TYPE=league&L=" + league_id_g + "&JSON=1"
    league_json_string = https_request(s)
    league_json = json.loads(league_json_string)
    franchises = (league_json["league"]["franchises"]["franchise"])
    for franchise in franchises:
        franchises_dict_g[franchise["id"]] = remove_html_from_string(franchise["name"])


def get_players_from_MFL():
    s = base_url + year_g + "/export?TYPE=players&L=" + league_id_g + "&JSON=1"
    players_json_string = https_request(s)
    players_json = json.loads(players_json_string)
    players = players_json["players"]["player"]
    for player in players:
        players_dict_g[player["id"]] = player

    players_dict_g["timestamp"] = str(current_unix_timestamp())
    
    with open('players.json', 'w') as f:
        f.write(json.dumps(players_dict_g))

def get_players():
    # Attempt to load from disk before making API call
    global players_dict_g
    if not players_dict_g:
        try:
            with open('players.json', 'r') as f:
                players_dict_g = json.load(f)
                print("Loaded players file")
        except:
            print("No players file: retrieving from MFL")

    if not players_dict_g:
        get_players_from_MFL()
        return

    print("MFL Players DB last updated:")
    print(time.strftime("%d %b %Y %H:%M:%S %z", time.localtime(int(players_dict_g["timestamp"]))))
    if int(players_dict_g["timestamp"]) + 86400 < current_unix_timestamp():
        print("Players file is stale, updating from MFL")
        get_players_from_MFL()
    

def parse_future_pick(asset):
    asset_split = asset.split("_")
    s = u'\u00b7' + " " + asset_split[2] + " " + asset_split[3]
    if asset_split[3] == "1":
        s += "st"
    elif asset_split[3] == "2":
        s += "nd"
    elif asset_split[3] == "3":
        s += "rd"
    else:
        s += "th"

    s += "\n"    
    return s
    
def parse_draft_pick(asset):
    asset_split = asset.split("_")
    rd = int(asset_split[1]) + 1
    pick = int(asset_split[2]) + 1
    s = u'\u00b7' + " " + str(rd) + "." + str(pick).zfill(2) + "\n"
    return s

def round_to_dollar(amt):
    return str(int(round(float(amt), 0)))

def get_player_contract_details(player):
    franchises = rosters_json_g["rosters"]["franchise"]
    for franchise in franchises:
        for roster_player in franchise["player"]:
            if roster_player["id"] == player["id"]:
                return "($" + round_to_dollar(roster_player["salary"]) + ", " + roster_player["contractYear"] + "yr)\n"
    return "\n"


def parse_player(asset):
    player = players_dict_g[asset]
    print(player)
    s = u'\u00b7' + " " + player["name"] + " " + player["team"] + " " + player["position"] + " \n"
    # s += get_player_contract_details(player)
    return s

def trade_asset_parser(assets):
    s = ""
    for asset in assets.split(","):
        if asset == "":
            continue
        if asset[0] == "F":
            s += parse_future_pick(asset)
        elif asset[0] == "D":
            s += parse_draft_pick(asset)
        else:
            s += parse_player(asset)
    return s

def franchise_parser(franchise):
    return "**" + franchises_dict_g[franchise] + "**"

def update_timestamp(new_ts):
    global timestamp_g
    timestamp_g = new_ts
    with open("timestamp", "w") as f:
        f.write(str(timestamp_g))

def load_timestamp():
    global timestamp_g
    try:
        with open("timestamp", "r") as f:
            s = f.read()
            timestamp_g = int(s)
    except:
        print("No timestamp file...")

def trade_parser(trade):
    ts_int = int(trade["timestamp"])
    if ts_int > timestamp_g:
        update_timestamp(ts_int)
    else:
        #Trade already processed
        print("trade already processed")
        return None

    s = ""

    s += franchise_parser(trade["franchise"]) + " trades:\n"
    s += trade_asset_parser(trade["franchise1_gave_up"])

    s += franchise_parser(trade["franchise2"]) + " trades:\n"
    s += trade_asset_parser(trade["franchise2_gave_up"])
    return s

def process_trades(trades_json_string):
    transactions_json = json.loads(trades_json_string)
    transactions = transactions_json["transactions"]["transaction"]

    if isinstance(transactions, dict):
        ret = trade_parser(transactions)
        if ret:
            print("API Call(s)")
            call_APIs(ret)
    elif isinstance(transactions, list):
        transactions.reverse()
        for trade in transactions:
            ret = trade_parser(trade)
            if ret:
                print("API Call(s)")
                call_APIs(ret)

def groupme_API_post_message(message):
    url = "https://api.groupme.com/v3/bots/post"
    data = {
        "text": message,
        "bot_id": groupme_bot_id_g
    }
    
    resp = requests.post(url, data=data)
    print(resp.text)

def call_APIs(message):
    groupme_API_post_message(message)

def load_config():
    global league_id_g
    global groupme_bot_id_g
    global year_g
    global mfl_user_agent_g
    global chat_api_list_g

    config_file = "config.json"

    with open(config_file, "r") as f:
        config = json.load(f)
        league_id_g = config["league_id"]
        groupme_bot_id_g = config["groupme_bot_id"]
        year_g = config["year"]
        mfl_user_agent_g = config["mfl_user_agent"]

    # mfl_user_agent_g = os.environ["MFL_USER_ID"]
    # league_id_g = os.environ["MFL_LEAGUE_ID"]
    # groupme_bot_id_g = os.environ["GROUPME_BOT_ID"]
    
    if not league_id_g or not year_g or not mfl_user_agent_g:
        print("config.json missing mfl league information")
    
    if groupme_bot_id_g:
        chat_api_list_g.append("groupme")

    if not chat_api_list_g:
        print("No chat clients provided... exiting")
        return False
    else:
        print("Loaded " + config_file + "...")
        return True

def main():
    if load_config():
        load_timestamp()
        get_rosters()
        get_league()
        get_players()
        process_trades(get_trades())
    else:
        print("Incorrect config.json options")


if __name__ == "__main__":
    main()