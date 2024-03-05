from texasholdem.game.game import TexasHoldEm
from texasholdem.gui.text_gui import TextGUI
from texasholdem.agents import random_agent, call_agent
from LLM_agent import llm_agent
import time

num_test = 1
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