"""Short in-memory conversation history.

Key = (uid, conversation_id): a user can never read or continue another user's
conversation, even by guessing the id. Only text turns are kept (not tool results),
bounded in size and expiring.

Known MVP limitation: it lives in the process (single worker). Scaling to several
replicas would require moving it to Redis or Postgres.
"""
import threading
import time
from collections import OrderedDict

MAX_MESSAGES = 12          # 6 user/assistant turns
TTL_SECONDS = 30 * 60
MAX_CONVERSATIONS = 1000


class ConversationStore:
    def __init__(self, ttl: int = TTL_SECONDS, max_messages: int = MAX_MESSAGES,
                 max_conversations: int = MAX_CONVERSATIONS, clock=time.monotonic):
        self._data: OrderedDict[tuple[int, str], tuple[float, list[dict]]] = OrderedDict()
        self._lock = threading.Lock()
        self.ttl, self.max_messages, self.max_conversations, self._clock = ttl, max_messages, max_conversations, clock

    def get(self, uid: int, cid: str) -> list[dict]:
        with self._lock:
            item = self._data.get((uid, cid))
            if item is None or self._clock() - item[0] > self.ttl:
                self._data.pop((uid, cid), None)
                return []
            return list(item[1])

    def append(self, uid: int, cid: str, user: str, assistant: str) -> None:
        with self._lock:
            now = self._clock()
            _, msgs = self._data.pop((uid, cid), (now, []))
            msgs = (msgs + [{"role": "user", "content": user}, {"role": "assistant", "content": assistant}])
            self._data[(uid, cid)] = (now, msgs[-self.max_messages:])
            while len(self._data) > self.max_conversations:
                self._data.popitem(last=False)  # evict the oldest


store = ConversationStore()
