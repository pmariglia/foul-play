from flask import Flask, render_template, request, jsonify
import threading
import asyncio
import time
import logging

# Shared state accessible by bot and web UI
class BotManager:
    def __init__(self):
        self.loop = None
        self.bot_task = None
        self.thread = None
        self.running = False
        self.connected = False
        self.username = None
        self.password = None
        self.websocket_uri = None
        self.bot_mode = None
        self.pokemon_format = None
        self.stats = {
            'battles_played': 0,
            'wins': 0,
            'losses': 0,
            'current_battle': None,
            'start_time': None,
            'last_error': None
        }
        self._lock = threading.Lock()

    def update_connection(self, connected: bool):
        with self._lock:
            self.connected = connected

    def update_stats(self, **kwargs):
        with self._lock:
            self.stats.update(kwargs)

    def get_state(self):
        with self._lock:
            uptime = 0
            if self.stats['start_time']:
                uptime = int(time.time() - self.stats['start_time'])
            data = {
                'running': self.running,
                'connected': self.connected,
                'username': self.username,
                'websocket_uri': self.websocket_uri,
                'bot_mode': self.bot_mode,
                'pokemon_format': self.pokemon_format,
                'stats': {
                    **self.stats,
                    'uptime_seconds': uptime,
                }
            }
        return data

    def start_bot(self, run_coro_factory):
        if self.running:
            return False, 'Bot already running'

        def runner():
            try:
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
                self.stats['start_time'] = time.time()
                self.running = True
                self.bot_task = self.loop.create_task(run_coro_factory(self))
                self.loop.run_until_complete(self.bot_task)
            except Exception as e:
                logging.exception('Bot crashed')
                with self._lock:
                    self.stats['last_error'] = str(e)
            finally:
                self.running = False
                try:
                    pending = asyncio.all_tasks(self.loop)
                    for t in pending:
                        t.cancel()
                except Exception:
                    pass
                try:
                    self.loop.stop()
                    self.loop.close()
                except Exception:
                    pass

        self.thread = threading.Thread(target=runner, daemon=True)
        self.thread.start()
        return True, 'Bot starting'

    def stop_bot(self):
        if not self.running:
            return False, 'Bot is not running'
        if self.loop is None:
            return False, 'No loop'
        for t in list(asyncio.all_tasks(self.loop)):
            t.cancel()
        self.running = False
        return True, 'Stop signal sent'

    def restart_bot(self, run_coro_factory):
        self.stop_bot()
        time.sleep(0.5)
        return self.start_bot(run_coro_factory)

bot_manager = BotManager()

app = Flask(__name__, template_folder='web/templates', static_folder='web/static')

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/api/state')
def api_state():
    return jsonify(bot_manager.get_state())

@app.route('/api/config', methods=['POST'])
def api_config():
    data = request.json or {}
    with bot_manager._lock:
        bot_manager.username = data.get('username')
        bot_manager.password = data.get('password')
        bot_manager.websocket_uri = data.get('websocket_uri')
        bot_manager.bot_mode = data.get('bot_mode')
        bot_manager.pokemon_format = data.get('pokemon_format')
    return jsonify({'ok': True})

@app.route('/api/control/<action>', methods=['POST'])
def api_control(action):
    from run import run_foul_play_controlled

    if action == 'start':
        ok, msg = bot_manager.start_bot(run_foul_play_controlled)
        return jsonify({'ok': ok, 'message': msg})
    if action == 'stop':
        ok, msg = bot_manager.stop_bot()
        return jsonify({'ok': ok, 'message': msg})
    if action == 'restart':
        ok, msg = bot_manager.restart_bot(run_foul_play_controlled)
        return jsonify({'ok': ok, 'message': msg})
    return jsonify({'ok': False, 'message': 'Unknown action'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
