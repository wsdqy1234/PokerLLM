from texasholdem.game.game import TexasHoldEm
from texasholdem.game.action_type import ActionType
from texasholdem.game.player_state import PlayerState
from texasholdem.game.hand_phase import HandPhase
import re
from openai import OpenAI
from http import HTTPStatus
import dashscope
import requests
import json
import time

def llm_agent(game: TexasHoldEm, model="gpt-3.5-turbo"):
    # game_history = game.hand_history.to_string()
    
    # 玩家id
    player_id = game.current_player
    num_players = len(game.players)
    
    # 庄家Button赋予id 0，小盲注Small Blind赋予id 1，大盲注Big Blind赋予id 2，这里将player的id转换成了以庄家为0
    old_ids = [
            i % num_players
            for i in range(game.hand_history.prehand.btn_loc, game.hand_history.prehand.btn_loc + num_players)
            if game.hand_history.prehand.player_chips[i % num_players] > 0
        ]
    canon_ids = dict(zip(old_ids, range(len(old_ids))))
    canon_player_id = canon_ids[player_id]
    canon_num_players = len(old_ids)
    
    # 手牌
    my_cards = game.hand_history.prehand.player_cards[player_id]
    my_cards_str = '[' + str(my_cards[0]) + ', ' + str(my_cards[1]) + ']'
    
    # 筹码
    my_chips = game.hand_history.prehand.player_chips[player_id]
    
    # 可取的Action moves
    MOVES_DICT = {
        ActionType.CALL: "Call",
        ActionType.CHECK: "Check",
        ActionType.FOLD: "Fold",
        ActionType.RAISE: "Raise",
        ActionType.ALL_IN: "Allin"
    }
    moves = game.get_available_moves()
    action_types = moves._action_types
    raise_range = moves._raise_range
    move_str = ""
    for action_type in action_types:
        if action_type == ActionType.RAISE:
            tmp = "Raise " + str(raise_range)
        else:
            tmp = MOVES_DICT[action_type]
        move_str += tmp
        move_str += "; "
    move_str += "\n"

    # 历史游戏信息
    game_history = "PREHAND\nBig Blind: "+ str(game.hand_history.prehand.big_blind) + "\nSmall Blind: " + str(game.hand_history.prehand.small_blind) + "\n"
    
    for history_item, name in [
        (game.hand_history.preflop, HandPhase.PREFLOP.name),
        (game.hand_history.flop, HandPhase.FLOP.name),
        (game.hand_history.turn, HandPhase.TURN.name),
        (game.hand_history.river, HandPhase.RIVER.name),
        (game.hand_history.settle, HandPhase.SETTLE.name),
    ]:
        if history_item is not None:
            game_history += f"{name.upper()}\n" + history_item.to_string(canon_ids)
            game_history += "\n"

    # 提示词
    background_prompt = "Suppose you are a professional No-limit Texas Hold'em player in a "+str(canon_num_players)+"-player game. Your player ID is " + str(canon_player_id) + ", where 0 is Button, 1 is Small Blind, and 2 is Big Blind. Your hand cards include " + my_cards_str + ". Please select your next action based on the Historical Game Information, where the action '(0, RAISE, 100)' means that the player 0 RAISES 100 CHIPS. YOU MUST CHOOSE FROM THE AVAILABLE ACTIONS. If you choose 'Raise', please provide a specific number in the range. For example, you can answer 'Raise 100' if the ACTION CHOICES include 'Raise range(90, 120)'\n"
    
    history_prompt = " Historical Game Information: " + game_history
    
    moves_prompt = "AVAILABLE ACTIONS: " + move_str
    
    answer_prompt = "<Output Requirement> YOU MUST OUTPUT THE NEXT ACTION WITHOUT ANY EXPLANATIONS IN THE FOLLOWING FORMAT:\n[Action]: 'your next action'"
    
    prompt = background_prompt + history_prompt + moves_prompt + answer_prompt
    
    # LLM agent输出
    if model == "gpt-3.5-turbo":
        response = GPT_35(prompt) # Example: "[Action]: 'Fold'"
    elif model == "qwen_plus":
        response = Qwen(prompt)
    elif model == "ernie-bot":
        response = Ernie_Bot(prompt)
    else:
        # CALL Agent
        player = game.players[game.current_player]
        if player.state == PlayerState.TO_CALL:
            return ActionType.CALL, None
        return ActionType.CHECK, None
    
    
    # 将输出转换为行动
    match = re.search(r"\[Action\]:\s*'(\w+)(\s+(\d+))?'", response)
    # 使用正则表达式匹配所需的部分
    # 此正则表达式解释：
    # \[Action\]: 匹配字面上的"[Action]:"文本
    # \s* 匹配任何数量的空格
    # ' 匹配一个单引号
    # (\w+) 匹配并捕获一个或多个字母数字字符（行动）
    # (\s+(\d+))? 匹配可选的空格和数字组合，数字为可选捕获组
    # ' 匹配一个单引号
    Action_DICT = {
        "Call": ActionType.CALL,
        "CALL": ActionType.CALL,
        "Check": ActionType.CHECK,
        "CHECK": ActionType.CHECK,
        "Fold": ActionType.FOLD,
        "FOLD": ActionType.FOLD,
        "Raise": ActionType.RAISE,
        "RAISE": ActionType.RAISE,
        "Allin": ActionType.ALL_IN
    }
    if match:
        action = match.group(1)  # 捕获的行动
        act = Action_DICT[action]
        number = int(match.group(3)) if match.group(3) else None  # 捕获的数字，如果存在的话
        # 如果要加注
        if act == ActionType.RAISE and number:
            min_raise = game.value_to_total(game.min_raise(), game.current_player)
            max_raise = game.player_bet_amount(game.current_player) + game.players[game.current_player].chips
            if max_raise < min_raise:
                if game.players[game.current_player].chips > game.chips_to_call(game.current_player):
                    min_raise = max_raise
                else:
                    player = game.players[game.current_player]
                    if player.state == PlayerState.TO_CALL:
                        return ActionType.CALL, None
                    return ActionType.CHECK, None
            number = min_raise if number < min_raise else number
            number = max_raise if number > max_raise else number
            return act, number
        else:
        # 如果其他操作，判断一下有没有Call这个选项，有的时候LLM会乱输出
            if act == ActionType.CALL:
                player = game.players[game.current_player]
                if player.state != PlayerState.TO_CALL:
                    return ActionType.CHECK, None
                    
            return act, None
    else:
        player = game.players[game.current_player]
        if player.state == PlayerState.TO_CALL:
            return ActionType.CALL, None
        return ActionType.CHECK, None



def GPT_35(prompt):
    client = OpenAI(api_key='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')
    try:
        # 使用ChatGPT模型发送prompt并获取响应，适配新的API接口
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  # 请根据需要选择合适的模型，例如"gpt-3.5-turbo"等
            messages=[
                {"role": "system", "content": "You are a professional Texas Hold'em poker player."},
                {"role": "user", "content": prompt}
            ])
        
        # # 打印响应的文本内容
        # print(response.choices[0].message.content)
    except Exception as e:
        print(f"An error occurred: {e}")
    
    return response.choices[0].message.content


def GPT_4(prompt):
    # API: sk-W9mKTeweD6i0jC0U051a69A2C80540329d487f95754149F4
    # 中转url：https://www.jcapikey.com
    return NotImplementedError



def Qwen(prompt):
    # API: sk-e6db9866c9eb4362b4453f08554a6d72
    dashscope.api_key = "sk-e6db9866c9eb4362b4453f08554a6d72"
    
    messages = [{'role': 'system', 'content': "You are a professional Texas Hold'em poker player."},
                {'role': 'user', 'content': prompt}]
    
    response = dashscope.Generation.call(
        dashscope.Generation.Models.qwen_plus,
        messages=messages,
        result_format='message'
    )
    if response.status_code == HTTPStatus.OK:
        return response["output"]["choices"][0]["message"]["content"]
    else:
        print('Request id: %s, Status code: %s, error code: %s, error message: %s' % (
            response.request_id, response.status_code,
            response.code, response.message
        ))
        return None



def Ernie_Bot(prompt):
    # Access_token: 24.c6151ba780fc4b42fae5e13a9f73eace.2592000.1711295401.282335-52968506
    API_KEY = "gSY1ShtVreKQBTVDcdvr5H9C"
    SECRET_KEY = "b1r5DeWrH2T1mjWNyaJIi9ZEr3mPZPEP"
    access_token = "24.c6151ba780fc4b42fae5e13a9f73eace.2592000.1711295401.282335-52968506"
    
    def get_access_token():
        """
        使用 AK，SK 生成鉴权签名（Access Token）
        :return: access_token，或是None(如果错误)
        """
        url = "https://aip.baidubce.com/oauth/2.0/token"
        params = {"grant_type": "client_credentials", "client_id": API_KEY, "client_secret": SECRET_KEY}
        return str(requests.post(url, params=params).json().get("access_token"))

    url = "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/eb-instant?access_token=" + get_access_token()
    
    # Prompt
    messages = [{'role': 'user', 'content': prompt}]
    system = "You are a professional Texas Hold'em poker player."
    
    payload = json.dumps({
        "messages": messages,
        "system": system
    })
    
    headers = {
        'Content-Type': 'application/json'
    }
    
    response = requests.request("POST", url, headers=headers, data=payload).json()
    return response["result"]
    
    
    

from texasholdem.game.game import TexasHoldEm
from texasholdem.gui.text_gui import TextGUI
from texasholdem.agents import random_agent, call_agent
from texasholdem.game.action_type import ActionType

if __name__ == "__main__":
    num_test = 10
    for i in range(num_test):
        game = TexasHoldEm(buyin=500, big_blind=50, small_blind=25, max_players=5)
        gui = TextGUI(game=game)
        game.start_hand()
        while game.is_hand_running():
            gui.display_state()
            # gui.wait_until_prompted()
            
            # 对player id的正则化，按照行动顺序，0-庄，1-小盲，2-大盲
            old_ids = [
                i % len(game.players)
                for i in range(game.hand_history.prehand.btn_loc, game.hand_history.prehand.btn_loc + len(game.players))
                if game.hand_history.prehand.player_chips[i % len(game.players)] > 0
            ]
            canon_ids = dict(zip(old_ids, range(len(old_ids))))
            
            if canon_ids[game.current_player] == 0:
                game.take_action(*call_agent(game))
            elif canon_ids[game.current_player] == 1:
                game.take_action(*random_agent(game))
            elif canon_ids[game.current_player] == 2:
                game.take_action(*llm_agent(game, "gpt-3.5-turbo"))
            elif canon_ids[game.current_player] == 3:
                game.take_action(*llm_agent(game, "qwen_plus"))
            elif canon_ids[game.current_player] == 4:
                game.take_action(*llm_agent(game, "ernie-bot"))
                
                
        # gui.wait_until_prompted()
        # gui.display_win()
        # path = game.export_history('./pgns/llm_'+str(i+1)+'.pgn')     # save history
        # gui.replay_history("./pgns/llm.pgn")