import asyncio
import websockets
import requests
import json
import time

import logging

logger = logging.getLogger(__name__)


class LoginError(Exception):
    pass


class SaveReplayError(Exception):
    pass


class PSWebsocketClient:
    websocket = None
    address = None
    login_uri = None
    username = None
    password = None
    last_message = None
    last_challenge_time = 0
    _is_connected = False
    current_rooms = set()

    @classmethod
    async def create(cls, username, password, address):
        self = PSWebsocketClient()
        self.username = username
        self.password = password
        self.address = address
        self.websocket = await websockets.connect(self.address)
        self.login_uri = "https://play.pokemonshowdown.com/api/login"
        self._is_connected = True
        self.current_rooms = set()
        return self

    def is_connected(self):
        """Check if the websocket is currently connected"""
        return self._is_connected and self.websocket and not self.websocket.closed

    async def reconnect(self):
        """Reconnect to the websocket server"""
        try:
            if self.websocket and not self.websocket.closed:
                await self.websocket.close()
        except Exception as e:
            logger.debug(f"Error closing existing websocket: {e}")
        
        logger.info("Attempting to reconnect to Pokemon Showdown...")
        self.websocket = await websockets.connect(self.address)
        self._is_connected = True
        logger.info("Successfully reconnected to websocket")

    async def get_current_rooms(self):
        """Get list of current rooms the user is in"""
        await self.send_message("", ["/cmd rooms"])
        
        # Wait for the response
        try:
            msg = await asyncio.wait_for(self.receive_message(), timeout=5.0)
            
            # Parse rooms from the response
            rooms = set()
            if "|queryresponse|rooms|" in msg:
                rooms_data = msg.split("|queryresponse|rooms|")[1].split("\n")[0]
                try:
                    rooms_json = json.loads(rooms_data)
                    if "rooms" in rooms_json:
                        for room in rooms_json["rooms"]:
                            rooms.add(room)
                except (json.JSONDecodeError, KeyError) as e:
                    logger.debug(f"Error parsing rooms data: {e}")
            
            self.current_rooms = rooms
            return rooms
            
        except asyncio.TimeoutError:
            logger.debug("Timeout waiting for rooms response")
            return set()

    async def check_for_active_battles(self):
        """Check for any active battles after reconnection"""
        rooms = await self.get_current_rooms()
        
        battle_rooms = [room for room in rooms if room.startswith("battle-")]
        
        if battle_rooms:
            logger.info(f"Found active battle rooms: {battle_rooms}")
            return battle_rooms[0]  # Return the first battle room found
        
        return None

    async def rejoin_battle_room(self, battle_tag):
        """Rejoin a specific battle room"""
        try:
            await self.send_message("", [f"/join {battle_tag}"])
            logger.info(f"Rejoined battle room: {battle_tag}")
            return True
        except Exception as e:
            logger.error(f"Failed to rejoin battle room {battle_tag}: {e}")
            return False

    async def forfeit_battle(self, battle_tag):
        """Forfeit a battle gracefully"""
        try:
            await self.send_message(battle_tag, ["/forfeit"])
            logger.info(f"Forfeited battle: {battle_tag}")
            return True
        except Exception as e:
            logger.error(f"Failed to forfeit battle {battle_tag}: {e}")
            return False

    async def join_room(self, room_name):
        message = "/join {}".format(room_name)
        await self.send_message("", [message])
        self.current_rooms.add(room_name)
        logger.debug("Joined room '{}'".format(room_name))

    async def receive_message(self):
        try:
            message = await self.websocket.recv()
            logger.debug("Received message from websocket: {}".format(message))
            
            # Track room changes
            if "|deinit|" in message:
                # Extract room from message and remove from current_rooms
                lines = message.split("\n")
                for line in lines:
                    if line.startswith(">") and "|deinit|" in line:
                        room = line.split("\n")[0].replace(">", "").strip()
                        self.current_rooms.discard(room)
                        logger.debug(f"Left room: {room}")
            
            return message
        except (websockets.exceptions.ConnectionClosed, websockets.exceptions.ConnectionClosedError) as e:
            self._is_connected = False
            logger.warning(f"Websocket connection closed: {e}")
            raise ConnectionError(f"Websocket connection lost: {e}")
        except Exception as e:
            logger.error(f"Error receiving message: {e}")
            raise

    async def send_message(self, room, message_list):
        message = room + "|" + "|".join(message_list)
        logger.debug("Sending message to websocket: {}".format(message))
        try:
            await self.websocket.send(message)
            self.last_message = message
        except (websockets.exceptions.ConnectionClosed, websockets.exceptions.ConnectionClosedError) as e:
            self._is_connected = False
            logger.warning(f"Websocket connection closed while sending: {e}")
            raise ConnectionError(f"Websocket connection lost while sending: {e}")
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            raise

    async def avatar(self, avatar):
        await self.send_message("", ["/avatar {}".format(avatar)])
        await self.send_message("", ["/cmd userdetails {}".format(self.username)])
        while True:
            # Wait for the query response and check the avatar
            # |queryresponse|QUERYTYPE|JSON
            msg = await self.receive_message()
            msg_split = msg.split("|")
            if msg_split[1] == "queryresponse":
                user_details = json.loads(msg_split[3])
                if user_details["avatar"] == avatar:
                    logger.info("Avatar set to {}".format(avatar))
                else:
                    logger.warning(
                        "Could not set avatar to {}, avatar is {}".format(
                            avatar, user_details["avatar"]
                        )
                    )
                break

    async def close(self):
        self._is_connected = False
        if self.websocket and not self.websocket.closed:
            await self.websocket.close()

    async def get_id_and_challstr(self):
        while True:
            message = await self.receive_message()
            split_message = message.split("|")
            if split_message[1] == "challstr":
                return split_message[2], split_message[3]

    async def login(self):
        logger.info("Logging in...")
        client_id, challstr = await self.get_id_and_challstr()
        response = requests.post(
            self.login_uri,
            data={
                "name": self.username,
                "pass": self.password,
                "challstr": "|".join([client_id, challstr]),
            },
        )

        if response.status_code != 200:
            logger.error("Could not log-in\nDetails:\n{}".format(response.content))
            raise LoginError("Could not log-in")

        response_json = json.loads(response.text[1:])
        if "actionsuccess" not in response_json:
            logger.error("Login Unsuccessful: {}".format(response_json))
            raise LoginError("Could not log-in: {}".format(response_json))

        assertion = response_json.get("assertion")
        message = ["/trn " + self.username + ",0," + assertion]
        logger.info("Successfully logged in")
        await self.send_message("", message)
        await asyncio.sleep(3)
        return response_json["curuser"]["userid"]

    async def update_team(self, team):
        await self.send_message("", ["/utm {}".format(team)])

    async def challenge_user(self, user_to_challenge, battle_format):
        logger.info("Challenging {}...".format(user_to_challenge))
        message = ["/challenge {},{}".format(user_to_challenge, battle_format)]
        await self.send_message("", message)
        self.last_challenge_time = time.time()

    async def accept_challenge(self, battle_format, room_name):
        if room_name is not None:
            await self.join_room(room_name)

        logger.info("Waiting for a {} challenge".format(battle_format))
        username = None
        while username is None:
            msg = await self.receive_message()
            split_msg = msg.split("|")
            if (
                len(split_msg) == 9
                and split_msg[1] == "pm"
                and split_msg[3].strip().replace("!", "").replace("‽", "")
                == self.username
                and split_msg[4].startswith("/challenge")
                and split_msg[5] == battle_format
            ):
                username = split_msg[2].strip()

        message = ["/accept " + username]
        await self.send_message("", message)

    async def search_for_match(self, battle_format):
        logger.info("Searching for ranked {} match".format(battle_format))
        message = ["/search {}".format(battle_format)]
        await self.send_message("", message)

    async def leave_battle(self, battle_tag):
        message = ["/leave {}".format(battle_tag)]
        await self.send_message("", message)
        self.current_rooms.discard(battle_tag)

        while True:
            msg = await self.receive_message()
            if battle_tag in msg and "deinit" in msg:
                return

    async def save_replay(self, battle_tag):
        message = ["/savereplay"]
        await self.send_message(battle_tag, message)