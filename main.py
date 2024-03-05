from texasholdem.game.game import TexasHoldEm
from texasholdem.gui.text_gui import TextGUI
from texasholdem.agents import random_agent, call_agent
import time

game = TexasHoldEm(buyin=500, big_blind=200, small_blind=100, max_players=5)
gui = TextGUI(game = game)

num_hands = 2
for i in range(num_hands):
       game.start_hand()
       while game.is_hand_running():
              gui.display_state()
              gui.wait_until_prompted()   # 按Enter继续
              
              if game.current_player == 1:
                     game.take_action(*call_agent(game))	# player0 利用Random Agent采取行动
              else:
                     game.take_action(*random_agent(game))		# player1 利用Call Agent采取行动
              gui.display_win()
       path = game.export_history('./pgns/test'+str(i+1)+'.pgn')     # save history，它默认每一个Hand存一次历史记录

# 这个模拟器存的历史记录永远都是以庄家Button作为player 0，回放历史记录的时候也是这样的，但是开局的player id跟保存的不一样
# 有个办法就是告诉chatGPT它在将保存的pgn文件里的id，即canon_idx，然后说明0是button，1是小盲注，2是大盲注
# gui = TextGUI()
# gui.replay_history("./pgns/test(1).pgn")