'use strict';
/**
 * Runs Pokemon Showdown battles in-process and frames the output the way
 * server/room-battle.ts would send it to each player over the websocket.
 *
 * Usage: node fuzz/ps_driver.js <path-to-pokemon-showdown-checkout>
 *
 * PS must be built (`node build` in the checkout) so that `dist/sim` exists.
 *
 * Talks JSON lines over stdin/stdout:
 *
 *   in:  {"cmd": "start", "format": "gen9randombattle", "seed": "gen5,...",
 *         "p1": {"name": "...", "seed": "gen5,..."}, "p2": {...}, "roomid": "battle-..."}
 *        {"cmd": "choose", "side": "p1", "choice": "move 1"}
 *        {"cmd": "inputlog"}
 *
 *   out: {"type": "frame", "side": "p1", "data": ">battle-...\n|move|..."}
 *        {"type": "end", "winner": "...", "turns": 12, "inputLog": [...]}
 *        {"type": "inputlog", "inputLog": [...]}
 *        {"type": "driver_error", "message": "...", "stack": "..."}
 */

const path = require('path');
const readline = require('readline');

// stdout is reserved for the JSON protocol: anything PS itself logs goes to stderr
console.log = console.error;
console.info = console.error;

const psDir = path.resolve(process.argv[2] || '../pokemon-showdown');
const sim = require(path.join(psDir, 'dist', 'sim'));
const { extractChannelMessages } = require(path.join(psDir, 'dist', 'sim', 'battle'));

const SIDES = ['p1', 'p2'];

let battle = null;
let roomid = '';
let rqid = 0;

function emit(obj) {
	process.stdout.write(JSON.stringify(obj) + '\n');
}

function frame(side, lines) {
	if (!lines.length) return;
	emit({ type: 'frame', side, data: `>${roomid}\n${lines.join('\n')}` });
}

function send(type, data) {
	switch (type) {
	case 'update': {
		const channels = extractChannelMessages(data.join('\n'), [1, 2]);
		frame('p1', channels[1]);
		frame('p2', channels[2]);
		break;
	}
	case 'sideupdate': {
		const newline = data.indexOf('\n');
		const side = data.slice(0, newline);
		const line = data.slice(newline + 1);
		if (line.startsWith('|request|')) {
			// server/room-battle.ts adds the rqid before forwarding the request
			const request = JSON.parse(line.slice(9));
			request.rqid = ++rqid;
			frame(side, [`|request|${JSON.stringify(request)}`]);
		} else {
			frame(side, [line]);
		}
		break;
	}
	case 'end': {
		const log = JSON.parse(data);
		emit({ type: 'end', winner: log.winner, turns: log.turns, inputLog: log.inputLog });
		break;
	}
	default:
		emit({ type: 'driver_error', message: `unexpected battle output: ${type}`, stack: String(data) });
	}
}

function start(cmd) {
	roomid = cmd.roomid;
	rqid = 0;

	// the server sends these before any sim output
	const names = SIDES.map(s => cmd[s].name);
	for (const side of SIDES) {
		frame(side, ['|init|battle', `|title|${names.join(' vs. ')}`, ...names.map(n => `|j|☆${n}`)]);
	}

	battle = new sim.Battle({ formatid: cmd.format, seed: cmd.seed, send });
	for (const side of SIDES) {
		battle.setPlayer(side, { name: cmd[side].name, seed: cmd[side].seed });
		battle.sendUpdates();
	}
}

function handle(cmd) {
	switch (cmd.cmd) {
	case 'start':
		start(cmd);
		break;
	case 'choose':
		battle.choose(cmd.side, cmd.choice);
		battle.sendUpdates();
		break;
	case 'inputlog':
		emit({ type: 'inputlog', inputLog: battle ? battle.inputLog : [] });
		break;
	default:
		throw new Error(`unknown command: ${cmd.cmd}`);
	}
}

const rl = readline.createInterface({ input: process.stdin });
rl.on('line', line => {
	if (!line.trim()) return;
	try {
		handle(JSON.parse(line));
	} catch (e) {
		emit({ type: 'driver_error', message: e.message, stack: e.stack });
	}
});
rl.on('close', () => process.exit(0));
