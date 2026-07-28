from abc import ABC, abstractmethod
from typing import List
from autonomous_media.db.models import SourceVideo

class ContentSourceProtocol(ABC):
    @abstractmethod
    def poll(self) -> List[SourceVideo]:
        pass
