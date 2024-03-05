from texasholdem.game.game import TexasHoldEm
from texasholdem.gui.text_gui import TextGUI
from texasholdem.agents import random_agent, call_agent
from texasholdem.game.action_type import ActionType


game = TexasHoldEm(buyin=500, big_blind=100, small_blind=100, max_players=2)

game.start_hand()
while game.is_hand_running():
    # print(game.hand_history.to_string())
    if game.current_player == 0:
        MOVES_DICT = {
        ActionType.CALL: "Call",
        ActionType.CHECK: "Check",
        ActionType.FOLD: "Fold",
        ActionType.RAISE: "Raise",
        ActionType.ALL_IN: "All in"
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
        print(move_str)
        # for move in moves:
        #     action, int = move
        #     if action == ActionType.CHECK:
        #         print("Check")
            # print(int)
        # a = game.hand_history.to_string()\
        game.take_action(*random_agent(game))	# player0 利用Random Agent采取行动
    else:
        game.take_action(*call_agent(game))		# player1 利用Call Agent采取行动
            
# path = game.export_history('./pgns/test.pgn')     # save history
# gui = TextGUI()
# gui.replay_history(path)
