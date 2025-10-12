"""
Battle session management for MCP-controlled battles.

Each BattleSession represents an active battle with its own websocket connection
and state. The session manages the async battle loop and coordinates LLM decisions.
"""

import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Optional

from fp.battle import Battle
from fp.websocket_client import PSWebsocketClient


logger = logging.getLogger(__name__)


class BattleStatus(Enum):
    """Status of a battle session."""

    INITIALIZING = "initializing"  # Creating websocket connection
    SEARCHING = "searching"  # Searching for opponent
    FOUND = "found"  # Match found, battle starting
    ACTIVE = "active"  # Battle in progress
    WAITING_MOVE = "waiting_move"  # Waiting for LLM decision
    FINISHED = "finished"  # Battle completed
    ERROR = "error"  # Error occurred
    FORFEITED = "forfeited"  # Battle was forfeited


class BattleSession:
    """
    Manages a single battle session with LLM control.

    The session coordinates between:
    - Pokemon Showdown websocket connection
    - Battle state (Battle object)
    - LLM decision queue
    - Async battle loop
    """

    def __init__(
        self,
        battle_id: str,
        websocket_client: PSWebsocketClient,
        pokemon_format: str,
        team_dict: Optional[dict] = None,
    ):
        self.battle_id = battle_id
        self.websocket_client = websocket_client
        self.pokemon_format = pokemon_format
        self.team_dict = team_dict

        # Battle state
        self.battle: Optional[Battle] = None
        self.status = BattleStatus.INITIALIZING
        self.awaiting_decision = False
        self.last_state_update = datetime.now()

        # Decision coordination
        self.decision_queue: asyncio.Queue[str] = asyncio.Queue()
        self.decision_timeout = 150  # seconds (PS timer is typically 150s)

        # Battle results
        self.winner: Optional[str] = None
        self.turn_count = 0
        self.error_message: Optional[str] = None
        self.error_log: Optional[str] = None  # Full traceback/log for debugging

        # Battle loop task
        self.battle_loop_task: Optional[asyncio.Task] = None

    async def wait_for_decision(self, timeout: Optional[float] = None) -> str:
        """
        Wait for LLM to submit a decision via the decision queue.

        Args:
            timeout: Maximum time to wait (default: self.decision_timeout)

        Returns:
            The decision string (move name or switch command)

        Raises:
            asyncio.TimeoutError: If timeout is reached
        """
        if timeout is None:
            timeout = self.decision_timeout

        self.awaiting_decision = True
        self.status = BattleStatus.WAITING_MOVE

        try:
            decision = await asyncio.wait_for(
                self.decision_queue.get(), timeout=timeout
            )
            logger.info(f"[{self.battle_id}] Received decision: {decision}")
            # Don't set awaiting_decision = False here - let the battle loop manage it
            # after the move is sent and server responds
            return decision
        except asyncio.TimeoutError:
            logger.error(f"[{self.battle_id}] Decision timeout after {timeout}s")
            self.awaiting_decision = False
            if self.battle and self.status != BattleStatus.FINISHED:
                self.status = BattleStatus.ACTIVE
            raise

    async def submit_decision(self, action: str) -> None:
        """
        Submit a decision from the LLM.

        Args:
            action: The move to make (e.g., "thunderbolt", "switch charizard")
        """
        if not self.awaiting_decision:
            raise ValueError(
                f"Battle {self.battle_id} is not waiting for a decision"
            )

        await self.decision_queue.put(action)
        logger.info(f"[{self.battle_id}] Decision submitted: {action}")

    def update_state(self, battle: Battle):
        """Update the battle state and metadata."""
        self.battle = battle
        self.turn_count = battle.turn
        self.last_state_update = datetime.now()

        if self.status == BattleStatus.SEARCHING:
            self.status = BattleStatus.FOUND
        elif self.status != BattleStatus.WAITING_MOVE:
            self.status = BattleStatus.ACTIVE

    def mark_finished(self, winner: Optional[str] = None):
        """Mark the battle as finished."""
        self.status = BattleStatus.FINISHED
        self.winner = winner
        self.awaiting_decision = False
        logger.info(f"[{self.battle_id}] Battle finished. Winner: {winner}")

    def mark_error(self, error: str, error_log: Optional[str] = None):
        """Mark the battle as errored.

        Args:
            error: Brief error message
            error_log: Full traceback or detailed error log for debugging
        """
        self.status = BattleStatus.ERROR
        self.error_message = error if error else "Unknown error occurred"
        self.error_log = error_log
        # Keep awaiting_decision as-is so LLM can see error state
        # Don't set to False as that would hide the error from the LLM
        logger.error(f"[{self.battle_id}] Error: {self.error_message}")
        if error_log:
            logger.error(f"[{self.battle_id}] Error log:\n{error_log}")

    def forfeit(self):
        """Mark the battle as forfeited."""
        self.status = BattleStatus.FORFEITED
        self.awaiting_decision = False
        logger.info(f"[{self.battle_id}] Battle forfeited")

    def to_dict(self) -> dict:
        """
        Serialize session metadata to dict.

        Returns:
            Dict with session status and metadata
        """
        result = {
            "battle_id": self.battle_id,
            "status": self.status.value,
            "awaiting_decision": self.awaiting_decision,
            "turn": self.turn_count,
            "winner": self.winner,
            "error": self.error_message,
            "last_update": self.last_state_update.isoformat(),
            "format": self.pokemon_format,
        }
        if self.error_log:
            result["error_log"] = self.error_log
        return result

    def __repr__(self):
        return (
            f"BattleSession(id={self.battle_id}, "
            f"status={self.status.value}, "
            f"turn={self.turn_count})"
        )
