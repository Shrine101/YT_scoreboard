from flask import Flask
from flask import render_template, jsonify

app = Flask(__name__)



@app.route('/data_json')
def data_json():
    # The game state including player information, turns, and current throws
    game_data = {
        # Player information - names and total scores
        "players": [
            {"id": 1, "name": "Player 1", "total_score": 501},
            {"id": 2, "name": "Player 2", "total_score": 501},
            {"id": 3, "name": "Player 3", "total_score": 501},
            {"id": 4, "name": "Player 4", "total_score": 501}
        ],
        
        # Turn data - for each turn, what each player scored
        "turns": [
            {
                "turn_number": 1,
                "scores": [
                    {"player_id": 1, "points": 180},
                    {"player_id": 2, "points": 140},
                    {"player_id": 3, "points": 120},
                    {"player_id": 4, "points": 100}
                ]
            },
            {
                "turn_number": 2,
                "scores": [
                    {"player_id": 1, "points": 140},
                    {"player_id": 2, "points": 95},
                    {"player_id": 3, "points": 85},
                    {"player_id": 4, "points": 60}
                ]
            }
        ],
        
        # Current active turn information
        "current_turn": 2,
        "current_player": 1,
        
        # Current throw information for display beneath dartboard
        "current_throws": [
            {"throw_number": 1, "points": 60},
            {"throw_number": 2, "points": 60},
            {"throw_number": 3, "points": 20}
        ]
    }
    
    return jsonify(game_data)
    

@app.route('/')
def index():
    game_data = data_json()

    return render_template(
        'index.html',
        game_data = game_data.json
        
    )